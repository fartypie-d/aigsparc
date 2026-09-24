"""Pin phase-tools root resolution to its own checkout and the calling checkout.

The matrix deliberately tests both functions independently for every case:
P0 main/no env, P1 main worktree/no env, A1 sibling/no env, B1 GIT_DIR,
B2 GIT_COMMON_DIR, B3 GIT_WORK_TREE, B4 GIT_DIR plus GIT_WORK_TREE, and N1
an outside-git directory.  The fixture uses only temporary fake repositories;
the real repository is copied into the fake main checkout as the script under test.
"""

import contextlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


class PhaseToolsRootResolutionTests(unittest.TestCase):
    """Exercise the sixteen root-resolution expectations independently."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.main = self.root / "main"
        self.sibling = self.root / "sibling"
        self.outside = self.root / "outside"
        self.main.mkdir()
        self.sibling.mkdir()
        self.outside.mkdir()
        self.tmp_home = self.root / "home"
        self.tmp_home.mkdir()
        self._git_init(self.main)
        self._git_init(self.sibling)
        (self.main / "marker.txt").write_text("main\n", encoding="utf-8")
        self._git(self.main, "add", "marker.txt")
        self._git(self.main, "-c", "user.name=phase-test", "-c",
                  "user.email=phase-test@example.invalid", "commit", "-m", "initial")
        self.worktree = self.root / "main-worktree"
        self._git(self.main, "worktree", "add", str(self.worktree), "-b", "test-worktree")
        script_source = Path(__file__).resolve().parents[1] / "core" / "scripts" / "phase-tools.py"
        script_copy = self.main / "scripts" / "phase-tools.py"
        script_copy.parent.mkdir()
        shutil.copyfile(script_source, script_copy)
        self.module = self._load_module(script_copy)

    def tearDown(self):
        self.tempdir.cleanup()

    def _git_env(self):
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.tmp_home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }

    def _git_init(self, path):
        subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", str(path)],
            env=self._git_env(), check=True, capture_output=True, text=True,
        )

    def _git(self, cwd, *args):
        return subprocess.run(
            ["git", "-C", str(cwd), *args], env=self._git_env(), check=True,
            capture_output=True, text=True,
        )

    def _load_module(self, script_copy):
        name = f"phase_tools_under_test_{id(self)}"
        spec = importlib.util.spec_from_file_location(name, script_copy)
        module = importlib.util.module_from_spec(spec)
        sys.modules.pop(name, None)
        spec.loader.exec_module(module)
        sys.modules.pop(name, None)
        return module

    @contextlib.contextmanager
    def _cwd_and_git_env(self, cwd, **variables):
        previous = Path.cwd()
        with mock.patch.dict(os.environ, {}, clear=False):
            for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE"):
                os.environ.pop(name, None)
            os.environ.update({name: str(value) for name, value in variables.items()})
            try:
                os.chdir(cwd)
                yield
            finally:
                os.chdir(previous)

    def _find_root(self, cwd, **variables):
        with self._cwd_and_git_env(cwd, **variables):
            return self.module.find_root()

    def _find_docs_root(self, cwd, **variables):
        with self._cwd_and_git_env(cwd, **variables):
            return self.module.find_docs_root(self.main)

    def test_p0_main_cwd_no_env_resolves_main(self):
        self.assertEqual(self._find_root(self.main), self.main.resolve())

    def test_p0_main_cwd_no_env_find_docs_root_resolves_main(self):
        self.assertEqual(self._find_docs_root(self.main), self.main.resolve())

    def test_p1_worktree_cwd_no_env_resolves_main_for_find_root(self):
        self.assertEqual(self._find_root(self.worktree), self.main.resolve())

    def test_p1_worktree_cwd_no_env_find_docs_root_resolves_worktree(self):
        self.assertEqual(self._find_docs_root(self.worktree), self.worktree.resolve())

    def test_a1_sibling_cwd_is_rejected_by_find_root(self):
        with self.assertRaises(SystemExit):
            self._find_root(self.sibling)

    def test_a1_sibling_cwd_is_rejected_by_find_docs_root(self):
        with self.assertRaises(SystemExit):
            self._find_docs_root(self.sibling)

    def test_b1_git_dir_is_ignored_by_find_root(self):
        self.assertEqual(
            self._find_root(self.main, GIT_DIR=self.sibling / ".git"),
            self.main.resolve(),
        )

    def test_b1_git_dir_find_docs_root_stays_main(self):
        self.assertEqual(
            self._find_docs_root(self.main, GIT_DIR=self.sibling / ".git"),
            self.main.resolve(),
        )

    def test_b2_git_common_dir_is_ignored_by_find_root(self):
        self.assertEqual(
            self._find_root(self.main, GIT_COMMON_DIR=self.sibling / ".git"),
            self.main.resolve(),
        )

    def test_b2_git_common_dir_find_docs_root_stays_main(self):
        self.assertEqual(
            self._find_docs_root(self.main, GIT_COMMON_DIR=self.sibling / ".git"),
            self.main.resolve(),
        )

    def test_b3_git_work_tree_is_rejected_by_find_root_docs_axis_only(self):
        self.assertEqual(
            self._find_root(self.main, GIT_WORK_TREE=self.sibling),
            self.main.resolve(),
        )

    def test_b3_git_work_tree_is_rejected_by_find_docs_root(self):
        with self.assertRaises(SystemExit):
            self._find_docs_root(self.main, GIT_WORK_TREE=self.sibling)

    def test_b4_git_dir_and_work_tree_are_ignored_by_find_root(self):
        self.assertEqual(
            self._find_root(
                self.main,
                GIT_DIR=self.sibling / ".git",
                GIT_WORK_TREE=self.sibling,
            ),
            self.main.resolve(),
        )

    def test_b4_git_dir_and_work_tree_are_rejected_by_find_docs_root(self):
        with self.assertRaises(SystemExit):
            self._find_docs_root(
                self.main,
                GIT_DIR=self.sibling / ".git",
                GIT_WORK_TREE=self.sibling,
            )

    # C1도 C1b도 우리 코드의 방어를 재지 못한다. GIT_CONFIG_*로 넣은
    # core.worktree는 GIT_DIR을 명시해도 rev-parse --show-toplevel을 움직이지
    # 못한다. git이 무시한다(2026-09-19 실측). 아래 raw 관측 테스트가 그 사실을
    # 고정한다. 따라서 C1/C1b/raw 셋은 정보성 회귀 핀이다. 지금은 이 축이 닫혀
    # 있다는 사실을 고정할 뿐이고, 막고 있는 것은 우리 코드가 아니라 git의
    # 동작이다. 은퇴 규칙 ③의 자리이므로 git 동작이나 저장소 배치가 바뀌면
    # 이 핀이 먼저 빨개진다. 지우지 마라.
    # 위치 축에서 실제로 판별력이 있는 것은 B3/B4다(GIT_WORK_TREE는 실제로
    # 먹힌다). find_docs_root()의 미정화 --show-toplevel과 계보 단언을 실제로
    # 실증하는 것도 B3/B4다. 🟡 여전히 안 잰 것: bare 저장소 배치.
    # 재는 법: bare 저장소를 임시 fixture로 만들고, 그 배치에서 GIT_DIR과
    # GIT_WORK_TREE를 각각 설정해 find_root/find_docs_root 및 raw git 출력을
    # 관측한다. 값은 여기 박지 않는다.
    def test_c1_raw_git_config_worktree_records_observed_paths(self):
        config = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.worktree",
            "GIT_CONFIG_VALUE_0": str(self.sibling),
        }
        with self._cwd_and_git_env(self.main, **config):
            without_git_dir = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                env=os.environ.copy(), check=True, capture_output=True, text=True,
            )
            with_git_dir = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                env={**os.environ, "GIT_DIR": str(self.main / ".git")},
                check=True, capture_output=True, text=True,
            )
        self.assertEqual(without_git_dir.stdout.strip(), str(self.main.resolve()))
        self.assertEqual(with_git_dir.stdout.strip(), str(self.main.resolve()))

    def test_c1_git_config_worktree_does_not_move_find_root(self):
        self.assertEqual(
            self._find_root(
                self.main,
                GIT_CONFIG_COUNT=1,
                GIT_CONFIG_KEY_0="core.worktree",
                GIT_CONFIG_VALUE_0=self.sibling,
            ),
            self.main.resolve(),
        )

    def test_c1_git_config_worktree_does_not_move_find_docs_root(self):
        self.assertEqual(
            self._find_docs_root(
                self.main,
                GIT_CONFIG_COUNT=1,
                GIT_CONFIG_KEY_0="core.worktree",
                GIT_CONFIG_VALUE_0=self.sibling,
            ),
            self.main.resolve(),
        )

    def test_c1b_git_config_worktree_with_git_dir_find_root_stays_main(self):
        self.assertEqual(
            self._find_root(
                self.main,
                GIT_DIR=self.sibling / ".git",
                GIT_CONFIG_COUNT=1,
                GIT_CONFIG_KEY_0="core.worktree",
                GIT_CONFIG_VALUE_0=self.sibling,
            ),
            self.main.resolve(),
        )

    def test_c1b_git_config_worktree_with_git_dir_does_not_move_docs_root(self):
        self.assertEqual(
            self._find_docs_root(
                self.main,
                GIT_DIR=self.sibling / ".git",
                GIT_CONFIG_COUNT=1,
                GIT_CONFIG_KEY_0="core.worktree",
                GIT_CONFIG_VALUE_0=self.sibling,
            ),
            self.main.resolve(),
        )

    def test_n1_outside_git_raises_system_exit_from_find_root(self):
        with self.assertRaises(SystemExit):
            self._find_root(self.outside)

    def test_n1_outside_git_raises_system_exit_from_find_docs_root(self):
        with self.assertRaises(SystemExit):
            self._find_docs_root(self.outside)


if __name__ == "__main__":
    unittest.main()
