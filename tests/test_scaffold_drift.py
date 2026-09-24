"""core/supervisor/tools/scaffold-drift.py 테스트 — 함수 단위 드리프트 표 + 레지스트리 기본 대상.

출처: 호스트 ~/.claude/supervisor/tools/test_scaffold_drift.py (2026-09-20) 를 Phase 19 에서
키트 tests/ 로 옮겼다 (모듈 경로만 조정 · 케이스 4건은 그대로). 레지스트리 스캔 케이스는 Phase 19 신설.
실제 홈·상태 디렉터리는 건드리지 않는다 — 서브프로세스 env 에 임시 HOME 을 주입하고
ORCH_STATE_DIR·XDG_STATE_HOME 은 지운다.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOL = Path(__file__).resolve().parents[1] / "core" / "supervisor" / "tools" / "scaffold-drift.py"
PHASE_TOOLS = Path(__file__).resolve().parents[1] / "core" / "scripts" / "phase-tools.py"



def load_tool(path=TOOL, name="sd"):
    """도구를 모듈로 적재한다. core/supervisor/tools/ 에 __pycache__ 를 남기지 않는다 —
    매니페스트 트리 행이 그 디렉터리를 통째로 홈에 깐다."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


sd = load_tool()

SAME = "def shared():\n    return 1\n"
GUARDED = "def find_root():\n    anchor = __file__\n    return anchor\n"
PLAIN = "def find_root():\n    return '.'\n"


def make_repo(root, body):
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "tool.py").write_text(SAME + body)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)


class DriftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        for repo, body in (("a", GUARDED), ("b", GUARDED), ("c", GUARDED + "def only_c():\n    pass\n"), ("d", PLAIN)):
            make_repo(self.home / repo, body)

    def tearDown(self):
        self.tmp.cleanup()

    def test_flags_the_repo_whose_function_alone_differs(self):
        shared = sd.file_table(self.home, ["a", "b", "c", "d"])
        lines = "\n".join(sd.report_functions(self.home, "tool.py", shared["tool.py"]))
        self.assertIn("find_root", lines)
        self.assertIn("d 만 다르다", lines)

    def test_flags_functions_missing_from_some_repos(self):
        shared = sd.file_table(self.home, ["a", "b", "c", "d"])
        lines = "\n".join(sd.report_functions(self.home, "tool.py", shared["tool.py"]))
        self.assertIn("only_c", lines)
        self.assertIn("일부에만 있음: c", lines)

    def test_identical_function_is_not_a_suspect(self):
        shared = sd.file_table(self.home, ["a", "b", "c", "d"])
        lines = sd.report_functions(self.home, "tool.py", shared["tool.py"])
        self.assertFalse(any(line.strip().startswith("shared") for line in lines))

    def test_unreadable_repo_exits_two(self):
        done = subprocess.run([sys.executable, str(TOOL), "--home", str(self.home), "--repos", "a", "nope"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)

    def test_two_repos_lower_the_shared_threshold_to_two(self):
        # Phase 19: 호스트 판은 「세 저장소 이상」 고정이라 --repos 둘로는 표가 비었다.
        shared = sd.file_table(self.home, ["a", "d"])
        self.assertIn("tool.py", shared)
        self.assertEqual(set(shared["tool.py"]), {"a", "d"})


class RegistryDefaultTest(unittest.TestCase):
    """--repos 를 생략하면 오케스트레이션 레지스트리의 root 들을 비교한다 (Phase 19).

    레지스트리 위치는 phase-tools 의 state_dir() 과 같다: ORCH_STATE_DIR, 없으면 ~/.local/state/orchestrate.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.registry = self.home / ".local" / "state" / "orchestrate" / "registry"
        self.registry.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def register(self, name, root):
        (self.registry / f"{name}.json").write_text(json.dumps({"project": name, "root": root}), encoding="utf-8")

    def run_tool(self, *args, home=None):
        env = {key: value for key, value in os.environ.items() if key not in ("ORCH_STATE_DIR", "XDG_STATE_HOME")}
        env["HOME"] = str(home or self.home)
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, env=env)

    def test_registry_dir_agrees_with_phase_tools_state_dir(self):
        # PR #21 리뷰 MEDIUM: 두 도구가 다른 레지스트리를 읽으면 안 된다. env 조합 둘로 잰다.
        phase_tools = load_tool(PHASE_TOOLS, "phase_tools_for_registry")
        with mock.patch.dict(os.environ, {"HOME": str(self.home), "ORCH_STATE_DIR": str(self.root / "orch")}):
            self.assertEqual(sd.registry_dir(), phase_tools.state_dir())
        with mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_STATE_HOME": str(self.root / "fake-xdg")}, clear=False):
            os.environ.pop("ORCH_STATE_DIR", None)
            self.assertEqual(sd.registry_dir(), phase_tools.state_dir())
            self.assertEqual(sd.registry_dir(), self.registry)

    def test_registry_roots_are_the_default_targets(self):
        for repo, body in (("a", GUARDED), ("b", GUARDED), ("c", GUARDED), ("d", PLAIN)):
            make_repo(self.home / "src" / repo, body)
            self.register(repo, str(self.home / "src" / repo))
        self.register("no-root", None)                           # root 없는 항목(예: 교차 검토 세션)
        self.register("gone", str(self.home / "src" / "gone"))   # 디스크에 없는 root
        (self.registry / "a.json.bak-1").write_text("{}", encoding="utf-8")  # 백업 파일은 *.json 이 아니다

        done = self.run_tool()

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("저장소 4: a, b, c, d", done.stdout)
        self.assertIn("d 만 다르다", done.stdout)
        self.assertNotIn("gone", done.stdout)

    def test_registry_honours_orch_state_dir_first(self):
        other = self.root / "orch-state"
        (other / "registry").mkdir(parents=True)
        for repo in ("a", "b"):
            make_repo(self.home / repo, GUARDED)
            (other / "registry" / f"{repo}.json").write_text(json.dumps({"root": str(self.home / repo)}), encoding="utf-8")
        env = {**os.environ, "HOME": str(self.home), "ORCH_STATE_DIR": str(other)}
        done = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("저장소 2: a, b", done.stdout)

    def test_xdg_state_home_alone_does_not_move_the_registry(self):
        # phase-tools 가 XDG_STATE_HOME 을 안 보므로 여기서도 안 본다 — 홈 기본 경로의 레지스트리를 읽는다.
        for repo in ("a", "b"):
            make_repo(self.home / repo, GUARDED)
            self.register(repo, str(self.home / repo))
        env = {**os.environ, "HOME": str(self.home), "XDG_STATE_HOME": str(self.root / "fake-xdg")}
        env.pop("ORCH_STATE_DIR", None)
        done = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("저장소 2: a, b", done.stdout)

    def test_missing_registry_dir_exits_two_with_a_clear_message(self):
        done = self.run_tool(home=self.root / "nowhere")
        self.assertEqual(done.returncode, 2)
        self.assertIn("레지스트리가 없다", done.stderr)
        self.assertIn("--repos", done.stderr)

    def test_fewer_than_two_registered_repos_exits_two(self):
        make_repo(self.home / "solo", GUARDED)
        self.register("solo", str(self.home / "solo"))
        done = self.run_tool()
        self.assertEqual(done.returncode, 2)
        self.assertIn("2개 미만", done.stderr)

    def test_explicit_repos_bypass_the_registry(self):
        make_repo(self.home / "x", GUARDED)
        make_repo(self.home / "y", PLAIN)
        done = self.run_tool("--home", str(self.home), "--repos", "x", "y", home=self.root / "nowhere")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("저장소 2: x, y", done.stdout)
        self.assertIn("갈라짐 1", done.stdout)  # 둘뿐이면 「혼자만 다름」 후보는 못 고른다 — 갈라짐 계수로 본다


if __name__ == "__main__":
    unittest.main()
