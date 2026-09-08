"""hook-selfcheck.sh 의 진입점별 프로젝트 루트 해석 테스트.

Phase 12 (오케스트레이터 작성·동결 — 위임의 tests/ 수정 금지).

`scripts/` 는 `core/scripts/` 의 파일 심링크 모음이다. 루트를 `$0` 기준
'한 단계 위'로 계산하면 심링크 진입점에서만 맞고 실경로에서는 `core/` 를
루트로 착각한다. 두 진입점 모두 같은 프로젝트 루트를 봐야 한다.
"""
import subprocess
import unittest

from _install_helpers import KIT, RUN_TIMEOUT


def run_selfcheck(relative_path):
    """저장소 루트를 cwd 로 두고 주어진 진입점으로 자가진단을 실행한다."""
    return subprocess.run(
        ["bash", relative_path],
        capture_output=True, text=True, cwd=str(KIT), timeout=RUN_TIMEOUT,
    )


class HookSelfcheckEntrypointTest(unittest.TestCase):
    def test_symlink_entrypoint_passes(self):
        """문서·CLAUDE.md 가 안내하는 `bash scripts/hook-selfcheck.sh` (회귀 가드)."""
        result = run_selfcheck("scripts/hook-selfcheck.sh")

        self.assertIn(
            "HOOK_SELFCHECK_PASS", result.stdout,
            "심링크 진입점 자가진단이 통과하지 않았다:\n"
            f"{result.stdout}{result.stderr}",
        )

    def test_real_path_entrypoint_passes(self):
        """실경로 `bash core/scripts/hook-selfcheck.sh` 도 통과해야 한다.

        현재는 `core/` 를 프로젝트 루트로 착각해 `.claude/hooks/*` 를 찾지 못하고
        모든 검사가 exit 127 로 떨어진다 (`HOOK_SELFCHECK_FAIL`).
        """
        result = run_selfcheck("core/scripts/hook-selfcheck.sh")

        self.assertIn(
            "HOOK_SELFCHECK_PASS", result.stdout,
            "실경로 진입점 자가진단이 통과하지 않았다:\n"
            f"{result.stdout}{result.stderr}",
        )




class HookSelfcheckFailureContractTest(unittest.TestCase):
    """Phase 12 라운드 2 RED (오케스트레이터 작성·동결 — 위임 수정 금지).

    루트 판정 실패도 `HOOK_SELFCHECK_FAIL` 계약을 따라야 한다.
    문서 여러 곳과 SessionStart 훅이 이 키워드의 **부재**로 통과를 판정하므로,
    사유만 출력하고 키워드를 빠뜨리면 "조용히 실패"와 구분되지 않는다.
    """

    def test_resolution_failure_emits_selfcheck_fail_keyword(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bogus = f"{tmp}/no-such-dir/entry.sh"
            result = subprocess.run(
                ["bash", "-c", "source core/scripts/hook-selfcheck.sh", bogus],
                capture_output=True, text=True, cwd=str(KIT), timeout=RUN_TIMEOUT,
            )

            combined = result.stdout + result.stderr
            self.assertIn(
                "HOOK_SELFCHECK_FAIL", combined,
                "루트 판정 실패가 HOOK_SELFCHECK_FAIL 계약을 따르지 않는다:\n"
                f"{combined}",
            )


if __name__ == "__main__":
    unittest.main()
