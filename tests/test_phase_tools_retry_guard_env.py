"""RED pins for retry-guard's git-environment and call-site invariants.

Current measured 2026-09-19: A no-env=root main, GIT_WORK_TREE=root sibling,
GIT_DIR=root main, GIT_COMMON_DIR=RuntimeError, sibling cwd=root sibling,
worktree=root main-worktree; B positive=3, GIT_WORK_TREE=0, GIT_DIR=0,
GIT_COMMON_DIR=1.
"""

import ast
import contextlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


EXEMPT_UNSANITIZED = {
    ("sh", "subprocess.run"): "정화 단일 통로 그 자체; env가 파라미터다",
    ("find_docs_root", "git rev-parse --show-toplevel"):
        "의도적으로 미정화해 오염을 불일치로 드러내는 프로브",
    ("cmd_retry_guard", "supervisor-state.sh"):
        "git이 아니며 XDG_STATE_HOME을 넣은 env를 의도적으로 만든다",
}
DEFERRED_UNSANITIZED = {
    ("stale_prs", "gh"): "Phase 34 범위 밖; 후속 id 후보",
}


def is_clean_git_env(node):
    """Return whether an env expression is rooted in _clean_git_env()."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
            node.func.id == "_clean_git_env"):
        return True
    return (isinstance(node, ast.Dict) and any(
        key is None and is_clean_git_env(value)
        for key, value in zip(node.keys, node.values)))


def resolved_root_from_calls(calls):
    """Resolve the status command's root from cwd= or its -C argument."""
    status = [item for item in calls if all(
        option in item[0] for option in ("status", "-z", "-uall"))]
    if len(status) != 1:
        raise AssertionError(calls)
    argv, cwd_arg = status[0]
    if cwd_arg is not None:
        return Path(cwd_arg).resolve()
    argv = list(argv)
    if "-C" not in argv:
        raise AssertionError(calls)
    return Path(argv[argv.index("-C") + 1]).resolve()


def unsanitized_git_calls(source):
    """Return (function, command) for every unapproved git subprocess site."""
    tree = ast.parse(source)
    violations = []

    def literal_argv(node):
        if not isinstance(node, (ast.List, ast.Tuple)):
            return None
        values = []
        for item in node.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None
            values.append(item.value)
        return values

    def assigned_value(function_node, name):
        """Return ``name``'s assignment value from this function body, if any."""
        for candidate in ast.walk(function_node):
            if isinstance(candidate, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == name
                       for target in candidate.targets):
                    return candidate.value
            elif (isinstance(candidate, ast.AnnAssign) and
                  isinstance(candidate.target, ast.Name) and candidate.target.id == name):
                return candidate.value
        return None

    def argv_command_identifier(argv_node, function_node):
        """Resolve a named argv to its first assigned string, or fail closed."""
        if not isinstance(argv_node, ast.Name):
            return None
        value = assigned_value(function_node, argv_node.id)
        if value is None:
            return None

        def first_string(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            for child in ast.iter_child_nodes(node):
                found = first_string(child)
                if found is not None:
                    return found
            return None

        string = first_string(value)
        if string is not None:
            return Path(string).name
        return None

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.functions = []

        def visit_FunctionDef(self, node):
            self.functions.append(node)
            self.generic_visit(node)
            self.functions.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            function_node = self.functions[-1] if self.functions else None
            function = function_node.name if function_node else "<module>"
            command = None
            direct = False
            if (isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in {"run", "Popen", "call", "check_call",
                                           "check_output"}):
                direct = True
                command = "subprocess." + node.func.attr
                identifier = (argv_command_identifier(node.args[0], function_node)
                              if node.args and function_node else None)
                if identifier is not None:
                    command = identifier
                elif "supervisor-state.sh" in ast.unparse(node):
                    command = "supervisor-state.sh"
            elif (isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == "os"
                  and (node.func.attr == "system" or node.func.attr.startswith("exec"))):
                direct = True
                command = "os." + node.func.attr
            elif isinstance(node.func, ast.Name) and node.func.id == "sh" and node.args:
                argv = literal_argv(node.args[0])
                if argv is None or not argv:
                    direct = True
                    command = (argv_command_identifier(node.args[0], function_node)
                               if function_node else None) or "sh(<non-literal>)"
                elif argv[0] == "git":
                    direct = True
                    command = " ".join(argv[:4])
                elif argv[0] == "gh":
                    direct = True
                    command = "gh"
            if direct:
                clean = any(keyword.arg == "env" and is_clean_git_env(keyword.value)
                            for keyword in node.keywords)
                approved = ((function, command) in EXEMPT_UNSANITIZED or
                            (function, command) in DEFERRED_UNSANITIZED)
                if not clean and not approved:
                    violations.append((function, command))
            self.generic_visit(node)

    Visitor().visit(tree)
    return violations


class RetryGuardEnvTests(unittest.TestCase):
    """Use only two temporary fake repositories, never the host checkout."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.main = self.root / "main"
        self.sibling = self.root / "sibling"
        self.main.mkdir()
        self.sibling.mkdir()
        self.tmp_home = self.root / "home"
        self.tmp_home.mkdir()
        self._git_init(self.main)
        self._git_init(self.sibling)
        (self.main / "marker.txt").write_text("main\n", encoding="utf-8")
        self._git(self.main, "add", "marker.txt")
        self._git(self.main, "-c", "user.name=phase-test", "-c",
                  "user.email=phase-test@example.invalid", "commit", "-m", "initial")
        (self.sibling / "marker.txt").write_text("sibling\n", encoding="utf-8")
        self._git(self.sibling, "add", "marker.txt")
        self._git(self.sibling, "-c", "user.name=phase-test", "-c",
                  "user.email=phase-test@example.invalid", "commit", "-m", "initial")
        self.worktree = self.root / "main-worktree"
        self._git(self.main, "worktree", "add", str(self.worktree), "-b", "test-worktree")
        source = Path(__file__).resolve().parents[1] / "core" / "scripts" / "phase-tools.py"
        copy = self.main / "scripts" / "phase-tools.py"
        copy.parent.mkdir()
        shutil.copyfile(source, copy)
        self.module = self._load_module(copy)

    def tearDown(self):
        self.tempdir.cleanup()

    def _git_env(self):
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.tmp_home),
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}

    def _git_init(self, path):
        subprocess.run(["git", "-c", "init.defaultBranch=main", "init", str(path)],
                       env=self._git_env(), check=True, capture_output=True, text=True)

    def _git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], env=self._git_env(),
                              check=True, capture_output=True, text=True)

    def _load_module(self, script_copy):
        name = f"phase_tools_under_test_{id(self)}"
        spec = importlib.util.spec_from_file_location(name, script_copy)
        module = importlib.util.module_from_spec(spec)
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            sys.modules.pop(name, None)
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = old
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

    def _snapshot(self, cwd, **variables):
        calls = []
        original = self.module.subprocess.run

        def recording_run(*args, **kwargs):
            calls.append((args[0], kwargs.get("cwd")))
            return original(*args, **kwargs)

        with self._cwd_and_git_env(cwd, **variables), \
                mock.patch.object(self.module.subprocess, "run", side_effect=recording_run):
            parameters = inspect.signature(self.module.retry_guard_snapshot).parameters.values()
            count = sum(parameter.kind in (parameter.POSITIONAL_ONLY,
                                           parameter.POSITIONAL_OR_KEYWORD)
                        for parameter in parameters)
            result = (self.module.retry_guard_snapshot(self.main) if count else
                      self.module.retry_guard_snapshot())
        return result, resolved_root_from_calls(calls)

    def test_a1_main_without_env_is_positive_control(self):
        _, resolved = self._snapshot(self.main)
        self.assertEqual(resolved, self.main.resolve())

    def test_a2_git_work_tree_is_rejected(self):
        with self.assertRaises(SystemExit):
            self._snapshot(self.main, GIT_WORK_TREE=self.sibling)

    def test_a3_git_dir_is_rejected(self):
        with self.assertRaises(SystemExit):
            self._snapshot(self.main, GIT_DIR=self.sibling / ".git")

    def test_a4_git_common_dir_is_rejected(self):
        with self.assertRaises(SystemExit):
            self._snapshot(self.main, GIT_COMMON_DIR=self.sibling / ".git")

    def test_a5_sibling_cwd_is_rejected(self):
        with self.assertRaises(SystemExit):
            self._snapshot(self.sibling)

    def test_a6_main_worktree_is_positive_control_and_not_forced_to_main(self):
        """The worker's worktree is the retry target; lineage must not force main."""
        _, resolved = self._snapshot(self.worktree)
        self.assertEqual(resolved, self.worktree.resolve())

    def _run_cli(self, cwd=None, **variables):
        state = self.root / "state" / "orchestrate" / "supervisor" / "phase34-test.json"
        state.parent.mkdir(parents=True)
        with self._cwd_and_git_env(self.main):
            clean_hash = self.module.retry_guard_snapshot()
        state.write_text(json.dumps({"last_failure": {"worktree_hash": clean_hash,
                         "phase": "34", "part": "1"}}), encoding="utf-8")
        env = {**self._git_env(), "PYTHONDONTWRITEBYTECODE": "1", **
               {name: str(value) for name, value in variables.items()}}
        return subprocess.run([sys.executable, str(self.main / "scripts" / "phase-tools.py"),
                               "retry-guard", "34", "1", "--check", "--state", str(state)],
                              cwd=cwd or self.main, env=env, capture_output=True, text=True)

    def test_b1_cli_positive_control_returns_three(self):
        self.assertEqual(self._run_cli().returncode, 3)

    def test_b2_cli_git_work_tree_cannot_change_verdict(self):
        self.assertEqual(self._run_cli(GIT_WORK_TREE=self.sibling).returncode, 3)

    def test_b3_cli_git_dir_observed_value_cannot_change_verdict(self):
        self.assertEqual(self._run_cli(GIT_DIR=self.sibling / ".git").returncode, 3)

    def test_b4_cli_git_common_dir_observed_value_cannot_change_verdict(self):
        self.assertEqual(self._run_cli(GIT_COMMON_DIR=self.sibling / ".git").returncode, 3)

    def test_b5_cli_sibling_cwd_is_an_error_and_not_a_pass(self):
        """rc=1 은 통과가 아니다 (Phase 19 추가).

        앵커 전 판은 형제 저장소 cwd 에서 형제를 해시해 「변경 있음」 rc=0 으로 통과시켰다
        (fail-open). 판정을 내릴 수 없는 실행은 0(통과)도 3(차단)도 아닌 1 로 끝나야 하고
        stderr 에 이유가 있어야 한다 — 호출부가 「3이 아니면 통과」로 읽으면 안 되는 이유다.
        """
        done = self._run_cli(cwd=self.sibling)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertNotIn(done.returncode, (0, 3))
        self.assertEqual(done.stdout, "")
        self.assertIn("다르다", done.stderr)

    def test_c1_actual_phase_tools_has_no_unapproved_git_call(self):
        source = (Path(__file__).resolve().parents[1] / "core" / "scripts" / "phase-tools.py").read_text()
        self.assertEqual(unsanitized_git_calls(source), [])

    def test_c2_git_wrapper_is_the_clean_env_prerequisite(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "core" / "scripts" / "phase-tools.py").read_text())
        git_def = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "git")
        calls = [node for node in ast.walk(git_def) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "sh"]
        self.assertEqual(len(calls), 1)
        self.assertTrue(any(keyword.arg == "env" and is_clean_git_env(keyword.value)
                            for keyword in calls[0].keywords))

    def test_c3_synthetic_raw_subprocess_is_a_violation(self):
        self.assertEqual(unsanitized_git_calls('def new():\n subprocess.run(("git", "status"), cwd=root)\n'),
                         [("new", "subprocess.run")])

    def test_c4_synthetic_clean_subprocess_is_not_a_violation(self):
        self.assertEqual(unsanitized_git_calls('def new():\n subprocess.run(("git", "status"), cwd=root, env=_clean_git_env())\n'), [])

    def test_c5_synthetic_raw_sh_git_is_a_violation(self):
        self.assertEqual(unsanitized_git_calls('def new():\n sh(["git", "rev-parse", "--show-toplevel"])\n'),
                         [("new", "git rev-parse --show-toplevel")])

    def test_c6_exemption_is_command_specific(self):
        source = ('def find_docs_root():\n'
                  ' sh(["git", "rev-parse", "--show-toplevel"])\n'
                  ' sh(["git", "status"])\n')
        self.assertEqual(unsanitized_git_calls(source), [("find_docs_root", "git status")])

    def test_c7_cmd_retry_guard_exemption_is_command_specific(self):
        source = ('def cmd_retry_guard():\n'
                  ' subprocess.run(("scripts/supervisor-state.sh", "status"))\n'
                  ' subprocess.run(("git", "status"))\n')
        self.assertEqual(unsanitized_git_calls(source),
                         [("cmd_retry_guard", "subprocess.run")])

    def test_c8_unapproved_gh_call_is_a_violation(self):
        self.assertEqual(unsanitized_git_calls('def new():\n sh(["gh", "pr", "list"])\n'),
                         [("new", "gh")])

    def test_c9_non_literal_sh_argv_is_a_violation(self):
        self.assertEqual(unsanitized_git_calls('def new():\n sh(command_from_variable)\n'),
                         [("new", "sh(<non-literal>)")])

    def test_c10_named_supervisor_state_argv_is_exempt(self):
        source = ('def cmd_retry_guard():\n'
                  ' command = [str(Path(__file__).resolve().with_name("supervisor-state.sh")),\n'
                  '            "set", project]\n'
                  ' subprocess.run(command)\n')
        self.assertEqual(unsanitized_git_calls(source), [])

    def test_c11_named_argv_exemption_remains_command_specific(self):
        source = ('def cmd_retry_guard():\n'
                  ' command = [str(Path(__file__).resolve().with_name("supervisor-state.sh")),\n'
                  '            "set", project]\n'
                  ' subprocess.run(command)\n'
                  ' other = ["git", "status"]\n'
                  ' subprocess.run(other)\n')
        self.assertEqual(unsanitized_git_calls(source), [("cmd_retry_guard", "git")])

    def test_c12_similarly_named_clean_env_call_is_a_violation(self):
        source = 'def new():\n subprocess.run(("git", "status"), env=_clean_git_env_typo())\n'
        self.assertEqual(unsanitized_git_calls(source), [("new", "subprocess.run")])

    def test_c13_wrapper_with_clean_env_in_its_name_is_a_violation(self):
        source = 'def new():\n subprocess.run(("git", "status"), env=not_clean_git_env_wrapper())\n'
        self.assertEqual(unsanitized_git_calls(source), [("new", "subprocess.run")])

    def test_c14_clean_env_function_object_is_a_violation(self):
        source = 'def new():\n subprocess.run(("git", "status"), env=_clean_git_env)\n'
        self.assertEqual(unsanitized_git_calls(source), [("new", "subprocess.run")])

    def test_c15_clean_env_dict_unpack_is_not_a_violation(self):
        source = ('def new():\n'
                  ' subprocess.run(("git", "status"), '
                  'env={**_clean_git_env(), "XDG_STATE_HOME": x})\n')
        self.assertEqual(unsanitized_git_calls(source), [])

    def test_c16_snapshot_root_uses_cwd_argument(self):
        self.assertEqual(resolved_root_from_calls(
            [(["git", "status", "-z", "-uall"], "/x/y")]),
            Path("/x/y").resolve())

    def test_c17_snapshot_root_uses_git_c_argument(self):
        self.assertEqual(resolved_root_from_calls(
            [(["git", "-C", "/x/y", "status", "-z", "-uall"], None)]),
            Path("/x/y").resolve())


if __name__ == "__main__":
    unittest.main()
