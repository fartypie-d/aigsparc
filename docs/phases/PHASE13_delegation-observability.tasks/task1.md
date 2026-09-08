---
task: 1
status: done
---

## Task 1: 회귀 테스트 동결 (RED)

- **주체**: **오케스트레이터 직접 작성** (위임 금지 — PITFALLS 14)
- **모델**: —
- **대상 파일**: `tests/test_run_delegation.py`
- **선행**: 없음
- **목표**: Task 2·3이 만족해야 할 계약을 착수 전에 테스트로 고정한다. 이 시점에는 전부 RED다.
- **재사용**: `개선 후 재사용 tests/test_run_delegation.py:RunDelegationTest` — 기존 스텁 하네스
  (`self.scripts`·`self.home`·`self.log`, `os.chmod(...)` 픽스처)를 그대로 쓴다.
  새 테스트 파일·새 픽스처 헬퍼를 만들지 말 것 (호출부 확인: 기존 41개 `assertIn` 신호 단정).

### 동결할 테스트 4종

| 테스트명 | 검증 내용 |
|---|---|
| `test_wrapper_log_is_600` | `<로그>.wrapper`가 생성되고 권한이 `0o600`이다. 단정은 기존 `:443` 패턴(`st_mode & 0o777`)을 따른다 |
| `test_wrapper_log_captures_signals` | `.wrapper`에 `MODEL_USED=`·`DONE`이 들어 있다. 정확일치 금지 — `assertIn`으로만 |
| `test_existing_signals_and_exit_unchanged` | 정상 완료 시 **stdout 신호와 exit 0이 종전과 동일**하다 (tee 도입이 호출자 계약을 깨지 않음) |
| `test_wallclock_cap_does_not_fall_back` | 캡 도달 시 `WALLCLOCK_CAP=` 신호 + **exit 8**, 그리고 **다음 모델로 폴백하지 않는다** (체인 2번째 모델이 실행되지 않았음을 스텁 호출 기록으로 확인) |
| `test_wallclock_cap_reports_orphan_on_abort_failure` | attach 모드에서 캡 도달 후 abort가 실패하면 `ORPHAN_SESSION` 계열 신호를 남긴다 (침묵 금지) |

### 완료 조건

1. `python3 -m unittest discover -s tests -k test_run_delegation` 실행 → **새 테스트 5건이 FAIL**
   (RED). `Ran N tests`의 N을 보고에 기록한다 (PITFALLS 28 — `-k`에 불리언 식 금지).
2. 기존 테스트는 전부 그대로 통과.
3. 커밋 메시지 `test(delegation): 래퍼 로그·벽시계 캡 계약 동결 (오케스트레이터)`
   — heredoc·명령치환 금지 (PITFALLS 2), 단순 `-m` 여러 개.

### 금지

- **변이 검증을 요구하지 말 것** — 변이시킬 구현이 아직 없어 항상 참인 검증이 된다
  (PITFALLS 18). 변이 검증은 Task 2·3의 완료 조건이다.
- 캡 테스트는 실제로 60분을 기다리면 안 된다 — `ORCHESTRATE_DELEGATION_MAX_SEC`를 작은 값
  (예: 2)으로 주입해 검증한다. 이 환경변수 이름이 Task 3의 계약이 된다.
