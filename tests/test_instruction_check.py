"""core/supervisor/tools/instruction-check.py 테스트 — 명령↔허용목록·경로·`파일:줄` 대조.

출처: 호스트 ~/.claude/supervisor/tools/test_instruction_check.py (2026-09-19) 를 Phase 19 에서
키트 tests/ 로 옮겼다 (모듈 경로만 조정 · 케이스 8건은 그대로).
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "core" / "supervisor" / "tools" / "instruction-check.py"



def load_tool():
    """도구를 모듈로 적재한다. core/supervisor/tools/ 에 __pycache__ 를 남기지 않는다 —
    매니페스트 트리 행이 그 디렉터리를 통째로 홈에 깐다."""
    spec = importlib.util.spec_from_file_location("ic", TOOL)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


ic = load_tool()


class CommandTest(unittest.TestCase):
    PATTERNS = ["git status:*", "npm run typecheck", "bash .claude/run-integration-tests.sh"]

    def test_prefix_pattern_needs_a_token_boundary(self):
        self.assertTrue(ic.is_allowed("git status --short", self.PATTERNS))
        self.assertFalse(ic.is_allowed("git statusx", self.PATTERNS))

    def test_prohibited_command_in_prose_is_not_an_instruction(self):
        self.assertEqual(ic.extract_commands("리뷰어에게 `git stash -u` 금지"), [])

    def test_env_prefix_is_reported_as_the_reason(self):
        found = ic.check_commands("검증: `DATABASE_SSL=disable npm run typecheck`", self.PATTERNS + [])
        self.assertEqual(len(found), 1)
        self.assertIn("환경변수 접두", found[0])

    def test_unlisted_script_is_flagged(self):
        found = ic.check_commands("```bash\nbash .orchestrate/run-integration-gw.sh\n```", self.PATTERNS)
        self.assertIn("허용 목록에 없다", found[0])


class PathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "apps/gw/src/admin").mkdir(parents=True)
        (self.repo / "apps/gw/src/admin/startup.ts").write_text("a\nb\nc\n")
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        self.tracked = {"apps/gw/src/admin/startup.ts"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_abbreviated_path_resolves_by_suffix(self):
        findings, existing = ic.check_paths("`admin/startup.ts:2` 를 읽어라", self.repo, self.tracked)
        self.assertEqual((findings, existing), ([], ["apps/gw/src/admin/startup.ts"]))

    def test_line_reference_beyond_file_length_is_stale(self):
        findings, _ = ic.check_paths("`admin/startup.ts:160-300`", self.repo, self.tracked)
        self.assertIn("낡은 줄 참조", findings[0])

    def test_url_path_without_extension_is_ignored(self):
        self.assertEqual(ic.check_paths("`/v1/webhooks/endpoints`", self.repo, self.tracked)[0], [])

    def test_missing_file_is_reported(self):
        self.assertIn("저장소에 없다", ic.check_paths("`admin/nope.ts`", self.repo, self.tracked)[0][0])


if __name__ == "__main__":
    unittest.main()
