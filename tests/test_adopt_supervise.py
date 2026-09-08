"""adopt-project.sh 의 감독(supervisor) 시작 계층 생성 — Phase 17 task 1a RED 동결.

동결 규약 (PITFALLS 14): 이 파일은 오케스트레이터가 작성·동결했다. 위임 구현자는 수정하지 않는다.

격리 규약: 모든 실행에 `HOME` 과 `XDG_STATE_HOME` 을 임시 디렉터리로 주입한다.
실제 `~/.claude` · `~/.local/state` 는 절대 읽지도 쓰지도 않는다 — 이 파일 어디에도
`Path.home()` 이나 `os.environ["HOME"]` 원본을 참조하는 코드가 없어야 한다.

동결하는 계약 (task 1b 가 만족시켜야 할 것):
- adopt 는 `$HOME/.claude/commands/supervise-<name>.md` 를 만든다 (`__PROJECT__` 치환 완료).
- adopt 는 `$STATE/supervisor/<name>.json` 을 idle 스키마로, `$STATE/supervisor/actions-<name>.md`
  를 만든다. `STATE` = `${XDG_STATE_HOME:-$HOME/.local/state}/orchestrate`.
- 세 산출물 모두 **없을 때만** 만든다 — 기존 사용자 편집·진행 중 상태를 덮지 않는다
  (`lib/stamp.sh` 의 "기존 파일 절대 안 덮음" 규약과 같은 정책).
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT = 120

# PROCEDURE.md §1 의 idle 스키마 키 — 감독 세션이 읽는 계약이다.
REQUIRED_STATE_KEYS = {
    "project", "root", "phase", "slug", "worktree", "branch", "part",
    "status", "child", "cost", "phases_since_review", "last_review", "owner",
}


def state_root(home):
    """테스트가 주입한 XDG_STATE_HOME 기준의 감독 상태 디렉터리."""
    return Path(home) / ".local" / "state" / "orchestrate" / "supervisor"


def command_path(home, name):
    return Path(home) / ".claude" / "commands" / f"supervise-{name}.md"


class AdoptSupervisorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir()
        self.name = "demoproj"
        self.proj = root / self.name
        self.proj.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(self.proj)],
                       check=True, capture_output=True)
        (self.proj / "README.md").write_text("기존 프로젝트\n")

    def adopt(self):
        """격리 HOME/XDG 로 adopt-project.sh 를 실행한다."""
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["XDG_STATE_HOME"] = str(self.home / ".local" / "state")
        result = subprocess.run(
            [str(KIT / "adopt-project.sh"), str(self.proj), "--claude"],
            capture_output=True, text=True, env=env, timeout=RUN_TIMEOUT,
        )
        self.assertEqual(result.returncode, 0,
                         f"adopt 실패:\n{result.stdout}{result.stderr}")
        return result

    def read_state(self):
        path = state_root(self.home) / f"{self.name}.json"
        self.assertTrue(path.exists(), f"감독 상태 파일이 없다: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise AssertionError(f"감독 상태 파일이 JSON 이 아니다: {error}") from error

    def assert_real_home_untouched(self):
        """격리가 실제로 걸렸는지 — 산출물이 임시 HOME 안에 있어야 한다."""
        created = command_path(self.home, self.name)
        self.assertTrue(str(created).startswith(str(self.home)),
                        "산출물 경로가 격리 HOME 밖이다")

    # 1. 커맨드 파일 생성
    def test_adopt_creates_supervise_command_in_isolated_home(self):
        self.adopt()
        created = command_path(self.home, self.name)
        self.assertTrue(created.exists(),
                        f"adopt 가 supervise 커맨드를 만들지 않았다: {created}")
        body = created.read_text(encoding="utf-8")
        self.assertIn(self.name, body,
                      "커맨드 본문에 프로젝트명이 없다 (플레이스홀더 치환 누락)")
        self.assertNotIn("__PROJECT__", body,
                         "커맨드 본문에 __PROJECT__ 플레이스홀더가 남아 있다")
        self.assert_real_home_untouched()

    # 2. 상태 파일 · actions 파일 생성
    def test_adopt_creates_idle_state_and_actions_file(self):
        self.adopt()
        data = self.read_state()
        self.assertIsInstance(data, dict, "감독 상태 파일은 JSON 객체여야 한다")
        missing = REQUIRED_STATE_KEYS - set(data)
        self.assertEqual(missing, set(), f"idle 스키마에 빠진 키: {sorted(missing)}")
        self.assertEqual(data["project"], self.name)
        self.assertEqual(data["status"], "idle")
        self.assertIsNone(data["owner"], "새로 만든 상태 파일의 owner 는 null 이어야 한다")
        self.assertIsNone(data["phase"], "새로 만든 상태 파일의 phase 는 null 이어야 한다")
        self.assertIsNone(data["child"], "새로 만든 상태 파일의 child 는 null 이어야 한다")
        self.assertEqual(os.path.realpath(data["root"]), os.path.realpath(self.proj),
                         "상태 파일의 root 가 대상 프로젝트 경로가 아니다")
        self.assertIsInstance(data["cost"], dict, "cost 는 객체여야 한다")
        self.assertIn("phase_usd", data["cost"])
        self.assertIn("parts", data["cost"])

        actions = state_root(self.home) / f"actions-{self.name}.md"
        self.assertTrue(actions.exists(), f"actions 파일이 없다: {actions}")

    # 3. 멱등성 — 손으로 만든 커맨드 파일을 덮지 않는다
    def test_rerun_preserves_hand_written_command_file(self):
        target = command_path(self.home, self.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SENTINEL — 사용자가 손으로 고친 커맨드\n", encoding="utf-8")

        self.adopt()
        self.adopt()

        self.assertIn("SENTINEL", target.read_text(encoding="utf-8"),
                      "adopt 재실행이 기존 supervise 커맨드를 덮었다 (사용자 편집 유실)")
        # 없던 산출물은 그래도 채워져야 한다 — "기존 파일이 있으면 통째로 건너뛴다" 를 막는다.
        self.assertTrue((state_root(self.home) / f"{self.name}.json").exists(),
                        "커맨드 파일이 이미 있다는 이유로 상태 파일 생성을 건너뛰었다")
        self.assertTrue((state_root(self.home) / f"actions-{self.name}.md").exists(),
                        "커맨드 파일이 이미 있다는 이유로 actions 파일 생성을 건너뛰었다")

    # 4. 상태 보존 — running 인 상태 파일을 idle 로 리셋하지 않는다
    def test_rerun_preserves_running_state_file(self):
        state_path = state_root(self.home) / f"{self.name}.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        running = {
            "project": self.name, "root": str(self.proj), "phase": 17,
            "slug": "supervisor-hardening", "worktree": ".claude/worktrees/phase17",
            "branch": "feature/phase17-supervisor-hardening", "part": "17-1",
            "status": "running", "child": {"part": "17-1"},
            "cost": {"phase_usd": 1.25, "parts": {"17-1": 1.25}},
            "phases_since_review": 2, "last_review": "2026-09-02",
            "owner": {"session_id": "SENTINEL-SESSION"},
        }
        state_path.write_text(json.dumps(running, ensure_ascii=False), encoding="utf-8")

        self.adopt()

        data = self.read_state()
        self.assertEqual(data["status"], "running",
                         "adopt 가 진행 중(running) 상태를 idle 로 리셋했다")
        self.assertEqual(data["phase"], 17, "adopt 가 진행 중 phase 를 지웠다")
        self.assertEqual(data["owner"], {"session_id": "SENTINEL-SESSION"},
                         "adopt 가 살아 있는 owner 잠금을 지웠다")
        # 상태 파일이 이미 있어도 없는 커맨드 파일은 만들어야 한다.
        self.assertTrue(command_path(self.home, self.name).exists(),
                        "상태 파일이 이미 있다는 이유로 커맨드 생성을 건너뛰었다")


if __name__ == "__main__":
    unittest.main()
