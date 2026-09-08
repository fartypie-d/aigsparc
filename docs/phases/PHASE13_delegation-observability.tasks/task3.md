---
task: 3
status: done
---

## Task 3: 총 벽시계 캡 + exit 8

- **에이전트**: `kit-scripts`
- **모델**: `heavy` (⚠️ 도메인)
- **대상 파일**: `core/scripts/run-delegation.sh` (1개)
- **선행**: Task 1, Task 2 (`emit()`을 사용한다)
- **목표**: 위임 하나의 **총 벽시계**에 상한을 둔다. 기존 워치독은 *무진행*만 감지하므로,
  진행하면서 영원히 도는 루프를 잡지 못한다.

### 배경 (왜 필요한가)

실측: 위임 벽시계 중앙값 4.4분 / p90 19.7분 / **최대 611분(10.2시간, Phase 4 task 8a)**.
611분짜리 실행이 아무 신호 없이 완주했다. 이는 무진행이 아니라 진행하는 폭주였다.

- **재사용**: `그대로 재사용 core/scripts/run-delegation.sh:abort_server_session()` — attach 모드의
  API abort 경로. `그대로 재사용 :kill_client()` — standalone 경로.
  **새 종료 함수를 만들지 말 것.** `timeout` 명령은 절대 쓰지 말 것 (SIGTERM이 opencode 세션
  DB를 오염시켜 다음 실행까지 막는다 — 이 스크립트가 존재하는 이유다).

### 계약

- 환경변수 **`ORCHESTRATE_DELEGATION_MAX_SEC`** (기본 `3600`). 0 또는 빈 값이면 캡 비활성.
- 시작 시각을 잡고 기존 워치독 루프(10초 폴링) 안에서 초과를 판정한다 — 새 루프를 만들지 말 것.
- 초과 시:
  1. `emit "WALLCLOCK_CAP=<경과초>/<상한초> — 총 벽시계 상한 초과로 중단"`
  2. `kill_client "$OC_PID"` (init 스톨 경로와 동일)
  3. attach 모드 → `abort_server_session()`. **실패하면 기존 `abort_or_exit()` 계약을 그대로
     따른다 — `ORPHAN_SESSION`/`ORPHAN_SESSIONS` 신호 + `exit 6`.**
     고아 세션은 다음 위임을 막으므로 캡보다 우선하는 안전 속성이다 (침묵 금지).
  4. abort 성공 또는 standalone 모드 → **`exit 8`. 다음 모델로 폴백하지 않는다.**
     한도·프로바이더 장애가 아니므로 체인을 도는 것은 상한을 N배로 늘릴 뿐이다.

| 상황 | exit |
|---|---|
| 캡 초과 + abort 성공 (attach) | `8` |
| 캡 초과 + standalone | `8` |
| 캡 초과 + abort 실패 (attach) | `6` (기존 고아 계약 우선) |
- 스크립트 상단 주석의 exit 코드 목록에 `8 총 벽시계 상한 초과`를 추가한다.

### 완료 조건

1. `python3 -m unittest discover -s tests -k test_run_delegation` → Task 1이 동결한
   `test_wallclock_cap_does_not_fall_back`·`test_wallclock_cap_reports_orphan_on_abort_failure`
   **GREEN**. `Ran N tests`의 N을 보고에 포함.
2. `bash -n core/scripts/run-delegation.sh`
3. **변이 검증**: `.orchestrate/mut13-3/`에 저장소 전체를 복사하고(`/tmp` 금지), 사본에서
   ① `exit 8`을 `continue`(폴백)로 바꾸면 `test_wallclock_cap_does_not_fall_back`이 FAIL
   ② abort 실패 시 신호 출력 줄을 삭제하면 `test_..._reports_orphan_on_abort_failure`가 FAIL
   — 두 출력 모두 보고에 첨부한다.

### 금지

- 대상 파일 외 수정, **`tests/` 수정 금지**
- `timeout`·`kill -9`를 서버 세션에 직접 사용 (abort API가 우선)
- 기존 무진행 워치독(90초 재시도 루프 스톨, init 스톨)의 동작·신호 변경 —
  이 task는 **추가**이지 대체가 아니다
- `git commit`·`git push`·docker 조작

## 라운드 1 반려 (2026-08-19) — 계약 보강

리뷰어 3종(`bash-reviewer`·`security-reviewer`·`silent-failure-hunter`) 전원 반려. 커밋 `9c1d540`.

| # | 심각도 | 지적 |
|---|---|---|
| 1 | 🔴 (3인 합의) | `DELEGATION_START` 가 `for MODEL in "${CHAIN[@]}"` 루프 **안**에 있어 캡이 모델 시도마다 리셋된다. 캡이 아닌 사유(429·모델 오류·90초 스톨)로 폴백하면 다음 모델이 상한을 통째로 새로 받는다 → 실효 상한이 `체인 길이 × 3600초` (default 5모델 = 5시간, heavy 3모델 = 3시간). 지시서 목표 "위임 하나의 **총** 벽시계"와 정면 배치이며, 이 task 가 막으려던 611분 완주와 같은 클래스가 배수만 줄어든 채 남는다. |
| 2 | 🟠/🟡 (2인) | `ORCHESTRATE_DELEGATION_MAX_SEC` 가 비수치·음수·거대값이면 `[ "$X" -gt 0 ]` 가 `set -e` 부재로 실패를 삼켜 **캡이 무음 비활성화**(fail-open)되고, 10초 폴링마다 `integer expression expected` 가 stderr 를 채운다. 안전장치가 오타 하나로 조용히 사라진다. |

### 보강된 계약 (동결 테스트로 고정)

- **캡의 기준 시각은 체인 진입 전 1회** 설정한다. 모델 시도마다 리셋하지 않는다.
  `WALLCLOCK_CAP=<경과>/<상한>` 의 경과는 **체인 전체 누적 경과**여야 한다.
  → `test_wallclock_cap_is_cumulative_across_chain`
- **손상된 캡 값은 착수 전에 거부**한다: 비수치·음수 → `WALLCLOCK_CAP_INVALID` 신호 +
  **`exit 64`** (기존 사용법·정책 오류 관례). 위임을 띄운 뒤 거부하면 세션·토큰이 낭비된다.
  → `test_invalid_wallclock_cap_is_rejected_before_launch`, `test_negative_wallclock_cap_is_rejected`
- **계약상 비활성 형태(빈 값·`0`)는 거부가 아니라 그대로 비활성**이다 (회귀 가드).
  → `test_documented_disable_forms_still_work`

> 결정: 손상값을 "경고 후 비활성"이 아니라 **exit 64 거부**로 정한 이유 — 이 기능은 폭주를 막는
> 안전장치다. fail-open 은 안전장치의 존재 이유와 배치되고, 검증은 착수 전 1회라 비용이 없다.
> 스크립트에는 이미 "알 수 없는 tier → exit 64" 선례가 있다 (같은 설정 오류 계열).
