"""adopt-project.sh 테스트 — 기존 프로젝트 비파괴 stamp 검증.

격리 규약: adopt 는 Phase 17 부터 `$HOME/.claude/commands/` 와
`${XDG_STATE_HOME:-$HOME/.local/state}/orchestrate/` 에도 쓴다(`stamp_supervisor`).
따라서 모든 실행에 임시 HOME·XDG_STATE_HOME 을 주입한다 — 실제 홈을 오염시키면 안 된다.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]


def adopt(target, *args, home=None):
    env = os.environ.copy()
    if home is not None:
        env["HOME"] = str(home)
        env["XDG_STATE_HOME"] = str(Path(home) / ".local" / "state")
    return subprocess.run(
        [str(KIT / "adopt-project.sh"), str(target), *args],
        capture_output=True, text=True, env=env,
    )


class AdoptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.proj = Path(self.tmp.name) / "existing"
        self.proj.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(self.proj)],
                       check=True, capture_output=True)
        (self.proj / "README.md").write_text("기존 프로젝트\n")

    def test_stamps_without_touching_existing_files(self):
        r = adopt(self.proj, "--claude", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.proj / "README.md").read_text(), "기존 프로젝트\n")
        self.assertTrue((self.proj / ".claude/orchestrate.md").exists())
        self.assertTrue((self.proj / "scripts/run-delegation.sh").exists())

    def test_existing_settings_json_is_preserved_and_suggested(self):
        (self.proj / ".claude").mkdir()
        (self.proj / ".claude/settings.json").write_text('{"mine": true}\n')
        r = adopt(self.proj, "--claude", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.proj / ".claude/settings.json").read_text(), '{"mine": true}\n')
        self.assertTrue((self.proj / ".claude/settings.json.kit-suggested").exists())
        self.assertIn("병합", r.stdout)

    def test_no_suggested_file_when_none_existed(self):
        adopt(self.proj, "--claude", home=self.home)
        self.assertTrue((self.proj / ".claude/settings.json").exists())
        self.assertFalse((self.proj / ".claude/settings.json.kit-suggested").exists())

    def test_warns_on_dirty_worktree_but_succeeds(self):
        (self.proj / "dirty.txt").write_text("uncommitted\n")
        r = adopt(self.proj, "--claude", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("커밋되지 않은 변경", r.stdout)

    def test_non_git_directory_is_reported(self):
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        r = adopt(plain, "--claude", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("git 저장소가 아니다", r.stdout)

    def test_rerun_is_idempotent(self):
        adopt(self.proj, "--claude", home=self.home)
        first = (self.proj / ".claude/orchestrate.md").read_text()
        r = adopt(self.proj, "--claude", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.proj / ".claude/orchestrate.md").read_text(), first)


if __name__ == "__main__":
    unittest.main()
