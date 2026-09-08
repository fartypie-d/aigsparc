---
task: 3b
status: done
---

## Task 3b: standalone 폴백 비밀번호 가드 완결 + 캡 기준 시각을 락 획득 뒤로

- **에이전트**: `kit-scripts`
- **모델**: `heavy` (⚠️ 도메인 — 로스터 규정)
- **대상 파일**: `core/scripts/run-delegation.sh` (1개)
- **선행**: Task 3
- **목표**: Task 3 수정 위임이 계약 밖으로 끼워 넣은 비밀번호 가드가 **절반만 작동**한다.
  시도 단위 폴백 경로를 막고, 함께 지적된 캡 기준 시각 문제를 고친다.

### 배경 (왜 필요한가 — 리뷰 라운드 2 실측)

Task 3 수정 위임(`3cf16ff`)에 지시서에 없던 한 줄이 들어왔다:

```
[ "$MODE" = "attach" ] || unset OPENCODE_SERVER_PASSWORD
```

리뷰어 3인이 각각 확인한 결과 **동기는 정당했다** — `secrets.env` 를 `set -a` 로 소싱하므로
standalone 자식이 서버 비밀번호를 상속하는 실제 유출 경로가 있었고, 그것이 앞서 관측된
`test_password_is_absent_in_standalone_mode` 간헐 실패의 정체였다.

그러나 **구현이 절반이다.** 가드는 전역 `$MODE` 만 본다. `serve ensure` 는 성공해
`MODE=attach` 인데 **그 모델 시도의 세션 생성 API 가 실패**하면
(`core/scripts/run-delegation.sh:302-306`) `ATTEMPT_MODE=standalone` 으로 떨어지고,
그 경로의 `nohup`(무프리픽스, :316)은 비밀번호를 그대로 물려받는다.
silent-failure-hunter 가 `CURL_CREATE_HTTP_CODE=500` 으로 재현했고, 오케스트레이터가
동결 테스트로 고정했다 (아래 실패 테스트 — 현재 RED).

절반만 작동하는 유출 방지 코드는 없느니만 못하다. "standalone 자식은 인증정보를 받지
않는다"는 문장을 코드가 실제로 지키게 만든다.

- **재사용**: `그대로 재사용 core/scripts/run-delegation.sh:302-306 ATTEMPT_MODE` — 시도 단위
  모드 판정은 이미 이 변수가 갖고 있다. **새 모드 변수·새 가드 함수를 만들지 말 것.**
  `:314` 의 attach 자식이 `OPENCODE_SERVER_PASSWORD="$SERVE_PASSWORD"` 접두로 값을 명시 주입하는
  기존 구조도 그대로 둔다 (그 경로는 값이 필요하다).

### 실패 테스트 (오케스트레이터가 이미 동결 — 위임은 `tests/` 수정 금지)

- `tests/test_run_delegation.py::test_password_is_absent_when_attempt_falls_back_to_standalone`
  — 전역 attach + 시도 단위 standalone 폴백에서 자식 환경에 비밀번호가 없어야 한다. **현재 RED.**
- 회귀 가드 (계속 GREEN 이어야 함):
  `test_password_is_absent_in_standalone_mode` · `test_attach_passes_password_to_child`(있으면) ·
  `test_wallclock_cap_does_not_fall_back` · `test_wallclock_cap_is_cumulative_across_chain` ·
  `test_documented_disable_forms_still_work` · `test_leading_zero_cap_is_normalized_not_disabled`

### 함께 고칠 것 — 캡 기준 시각을 락 획득 뒤로

`DELEGATION_START` 가 **flock 락 획득보다 먼저** 잡혀 있다. 같은 프로젝트의 다른 위임이
실행 중이면 최대 30분(`LOCK_WAIT_MAX=1800`)을 대기하는데, 그 대기 시간이 캡 예산을 깎는다.
상한 3600초짜리 위임이 30분 대기 후 30분만 일하고 잘릴 수 있다.

**수정**: `DELEGATION_START` 설정을 **락 획득 직후**(모델 체인 진입 전)로 옮긴다.
캡 값 검증(`WALLCLOCK_CAP_INVALID`/`exit 64`)은 지금 위치(락 획득 전, 착수 전 거부)에 그대로 둔다 —
설정 오류는 락을 기다린 뒤가 아니라 즉시 알려야 한다.

> **대체 검증 사유**: 이 이동은 행위 테스트로 고정할 수 없다. 스텁 `date` 는 호출될 때만
> 진행하는데 `flock -w` 대기는 블로킹 syscall 이라 대기 중 `date` 호출이 없다 — 두 구현이
> 스텁 상에서 구분되지 않는다. 따라서 **구조 검증**으로 대신한다 (완료 조건 4).

### 완료 조건

1. `python3 -m unittest discover -s tests -k test_password_is_absent_when_attempt_falls_back_to_standalone`
   → **GREEN**. (`-k` 에 불리언 식 금지 — 0건 매칭은 거짓 그린이다. `Ran 1 test` 확인.)
2. `python3 -m unittest discover -s tests -k test_run_delegation` → `Ran N tests` 의 N 과 결과를 보고에 포함.
3. `bash -n core/scripts/run-delegation.sh`
4. **구조 검증**: 아래 두 명령의 줄 번호를 보고에 첨부하고, `DELEGATION_START` 가 flock 획득
   **뒤**임을 보일 것.
   `grep -n 'DELEGATION_START=' core/scripts/run-delegation.sh`
   `grep -n 'flock -n 9\|exec 9>' core/scripts/run-delegation.sh`
5. **변이 검증**: `.orchestrate/mut13-3b/` 에 저장소 전체를 복사하고(`/tmp` 금지),
   사본에서 가드를 다시 `[ "$MODE" = "attach" ]` 로 되돌리면
   `test_password_is_absent_when_attempt_falls_back_to_standalone` 이 **FAIL** 함을 보이고
   출력을 첨부한다.

### 금지

- 대상 파일 외 수정. **`tests/` 수정 금지** (오케스트레이터 동결분, PITFALLS 14).
- `scripts/run-delegation.sh`(심링크) 수정.
- attach 자식(`:314`)의 비밀번호 주입 제거 — 그 경로는 값이 필요하다.
- 캡 값 검증(`WALLCLOCK_CAP_INVALID`·`exit 64`)의 위치·문구·exit 코드 변경.
- 기존 stdout 신호의 문구·순서·스트림·exit 코드 변경, 무진행 워치독 동작 변경.
- bash 4 전용 문법(`mapfile`·연관배열·`${var^^}`·`[[ =~ ]]`) — bash 3.2 호환 유지.
- `git commit`·`git push`·docker 조작.

### 보고

수정 파일 목록 + RED 출력 + GREEN 출력(`Ran N`) + `bash -n` + 구조 검증 줄 번호 + 변이 검증 출력.

## 리뷰 결과 (2026-08-19)

| 리뷰어 | 판정 | 🔴 | 🟠 | 🟡 |
|---|---|---|---|---|
| bash-reviewer | PASS | 0 | 0 | 0 |
| security-reviewer | SIGN OFF | 0 | 0 | 0 |
| silent-failure-hunter | SIGN OFF | 0 | 0 | 0 |

세 리뷰어 모두 유출 차단과 attach 정당 주입 유지를 **독립 하네스로 재현**했다:
1차 시도 standalone 폴백 → 자식 환경 `OPENCODE_SERVER_PASSWORD=<unset>`,
2차 시도 attach 복귀 → 비밀번호 정상 도달. `SERVE_PASSWORD` 는 가드가 건드리지 않으므로
체인 후속 시도의 인증이 살아 있다 (침묵실패 리뷰어가 자기 가설을 재현으로 반증).
`DELEGATION_START` 는 flock 분기와 디렉터리 락 분기가 합류한 뒤 한 곳에만 있어 양쪽 모두 커버된다.
