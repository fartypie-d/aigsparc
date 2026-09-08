"""`stamp_supervisor` 의 실패 보고 계약 — Phase 17 task 1c RED 동결.

동결 규약 (PITFALLS 14): 이 파일은 오케스트레이터가 작성·동결했다. 위임 구현자는 수정하지 않는다.

격리 규약: 모든 실행에 `HOME` 과 `XDG_STATE_HOME` 을 임시 디렉터리로 주입한다.
실제 `~/.claude` · `~/.local/state` 는 읽지도 쓰지도 않는다.

동결하는 계약 (task 1c-B 가 만족시켜야 할 것):
`stamp_supervisor` 는 state 자산과 actions 자산 **둘 다** 만들어졌을 때만 0 을 돌려준다.
state 생성이 실패했는데 뒤이은 actions 생성이 성공하면, 함수의 반환값이 마지막 명령(actions)의
것이 되어 실패가 가려진다 — 그러면 `adopt-project.sh` · `new-project.sh` 의
`⚠️ 감독 자산은 만들지 못했다` 경고가 뜨지 않는다.

실패 주입 방식: state 목적지를 **끊어진 심링크**로 선점한다.
`stamp_supervisor_prepare` 가 "목적지가 심링크다" 로 거부하므로 state 만 실패하고,
같은 디렉터리의 actions 는 정상 생성된다 — 정확히 위 비대칭을 만든다.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT = 120

WARNING_MARKER = "감독 자산은 만들지 못했다"


class StampSupervisorStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.name = "demoproj"
        self.proj = self.root / self.name
        self.proj.mkdir()

    # --- 헬퍼 -----------------------------------------------------------
    @property
    def supervisor_dir(self):
        return self.home / ".local" / "state" / "orchestrate" / "supervisor"

    @property
    def state_path(self):
        return self.supervisor_dir / f"{self.name}.json"

    @property
    def actions_path(self):
        return self.supervisor_dir / f"actions-{self.name}.md"

    def isolated_env(self):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["XDG_STATE_HOME"] = str(self.home / ".local" / "state")
        return env

    def break_state_destination(self):
        """state 목적지만 실패시킨다 — 끊어진 심링크로 선점."""
        self.supervisor_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.symlink_to(self.root / "nonexistent-target")
        self.assertTrue(self.state_path.is_symlink())
        self.assertFalse(self.state_path.exists(), "주입한 심링크가 끊어져 있어야 한다")

    def call_stamp_supervisor(self):
        """격리 HOME/XDG 로 stamp_supervisor 를 직접 호출하고 종료코드를 얻는다."""
        script = (
            "set -u\n"
            f'. "{KIT}/lib/stamp.sh"\n'
            f'if stamp_supervisor "{KIT}" "{self.proj}" "{self.name}"; then rc=0; else rc=$?; fi\n'
            'printf "STAMP_SUPERVISOR_RC=%s\\n" "$rc"\n'
        )
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True,
            env=self.isolated_env(), timeout=RUN_TIMEOUT,
        )
        marker = "STAMP_SUPERVISOR_RC="
        self.assertIn(marker, result.stdout,
                      f"프로브가 종료코드를 보고하지 않았다:\n{result.stdout}{result.stderr}")
        rc = int(result.stdout.rsplit(marker, 1)[1].splitlines()[0])
        return rc, result

    def run_adopt(self):
        result = subprocess.run(
            [str(KIT / "adopt-project.sh"), str(self.proj), "--claude"],
            capture_output=True, text=True, env=self.isolated_env(), timeout=RUN_TIMEOUT,
        )
        return result

    # --- 계약 -----------------------------------------------------------
    def test_state_failure_is_reported_even_when_actions_succeeds(self):
        """state 실패 + actions 성공 → 함수는 non-zero, 경고는 실제로 출력된다."""
        self.break_state_destination()

        rc, probe = self.call_stamp_supervisor()

        # 비대칭이 실제로 만들어졌는지 먼저 확인한다 — 이게 없으면 이 테스트는 가짜다.
        self.assertTrue(
            self.actions_path.exists(),
            "실패 주입이 actions 생성까지 막았다 — state 만 실패하는 비대칭이 아니다:\n"
            f"{probe.stdout}{probe.stderr}",
        )
        self.assertTrue(self.state_path.is_symlink(),
                        "주입한 심링크가 사라졌다 — 주입이 유효하지 않다")
        self.assertFalse(self.state_path.exists(),
                         "state 자산이 만들어졌다 — 실패 주입이 걸리지 않았다")

        self.assertNotEqual(
            rc, 0,
            "state 생성이 실패했는데 stamp_supervisor 가 0 을 돌려줬다 "
            "(마지막 명령인 actions 의 성공이 실패를 가렸다):\n"
            f"{probe.stdout}{probe.stderr}",
        )

        adopt = self.run_adopt()
        self.assertIn(
            WARNING_MARKER, adopt.stderr,
            "state 생성이 실패했는데 adopt-project.sh 가 감독 자산 경고를 내지 않았다:\n"
            f"{adopt.stdout}{adopt.stderr}",
        )

    def test_success_path_still_returns_zero(self):
        """주입이 없으면 0 · 두 자산 모두 생성 — '항상 실패' 수정을 막는 대칭 단정."""
        rc, probe = self.call_stamp_supervisor()
        self.assertEqual(rc, 0, f"정상 경로에서 실패했다:\n{probe.stdout}{probe.stderr}")
        self.assertTrue(self.state_path.is_file(), "state 자산이 만들어지지 않았다")
        self.assertTrue(self.actions_path.is_file(), "actions 자산이 만들어지지 않았다")

        adopt = self.run_adopt()
        self.assertEqual(adopt.returncode, 0, f"{adopt.stdout}{adopt.stderr}")
        self.assertNotIn(
            WARNING_MARKER, adopt.stderr,
            f"정상 경로인데 감독 자산 경고가 떴다:\n{adopt.stdout}{adopt.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
