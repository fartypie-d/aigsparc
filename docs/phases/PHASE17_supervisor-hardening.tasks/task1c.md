---
task: 1c
status: done
---

## Task 1c: task 1b 잔여 🔴 2건 마무리 (감독 신설 — 에스컬레이션 처리)
- **에이전트**: 1c-A 는 kit-scripts(heavy) 3차 위임 **1회 승인** / 1c-RED 는 오케스트레이터 직접
- **선행**: 1b (`11493ea` 까지 반영됨)
- **배경**: 파트 17-1 이 재위임 2회·반려 2회 한도를 소진해 `ESCALATION.md`(kind: blocked)로 넘긴 건.
  감독 결정 2026-09-02: **3차 위임 1회 승인**. 두 건 다 `11493ea` 가 새로 만든 비대칭이라
  다음 페이즈로 넘기면 원인 맥락이 흩어진다는 파트 판단을 수용한다.

### A. `core/scripts/kit-doctor.sh:597` — actions 임시 파일 봉쇄 사전 검사 누락
- **감독 지정 수정 방향**: 리뷰어가 제시한 두 안(ⓐ 검사 한 줄 추가 / ⓑ `/dev/null` 소스로 되돌려 `mktemp` 제거)
  중 **ⓑ 를 택한다.** actions 파일은 내용 치환이 필요 없으므로(빈 파일) 임시 파일 자체가 불필요하다.
  가드를 하나 더 얹는 것보다 **봉쇄 밖에 임시 파일이 생길 수 있는 경로를 없애는 쪽**이 결함 종류를 지운다.
  state 블록(`:577`)은 치환이 필요하므로 현행 `mktemp` + 사전 검사를 그대로 둔다.
- **RED**: 만들지 않는다. ⓑ 는 코드 경로를 제거하는 수정이라 고정할 동작이 남지 않는다
  (심링크 픽스처 비용 대비 실익 없음 — 감독 판단). 대신 기존 `DoctorPathContainmentTest` 가
  회귀 없이 GREEN 인지 확인한다.

### B. `lib/stamp.sh:231-232` — state 생성 실패가 actions 성공에 가려진다
- **RED 선행 (오케스트레이터 직접, `tests/`)**: state 쓰기를 실패시켰을 때
  `stamp_supervisor` 가 **non-zero 를 돌려주고** `adopt-project.sh` 의 `⚠️ 감독 자산은 만들지 못했다` 경고가
  실제로 출력되는지 단정하는 테스트 1건. 쓰기 실패 주입은 상태 디렉터리를 읽기 전용으로 만들거나
  경로를 파일로 선점하는 식으로 만든다(격리 HOME/XDG 안에서).
- **수정**: 리뷰어 제시안 그대로 — `_state_ok`·`_actions_ok` 로 각각 받고 둘 다 1일 때만 성공.

- **필수 규칙**: `core/scripts/*`·`lib/*` 원본만 수정. 위임 프롬프트에 `tests/` 수정 금지 명시.
  RED 커밋과 구현 커밋을 분리(PITFALLS 27). 3차 위임은 **1회뿐** — 또 반려가 나오면 재위임하지 말고
  ESCALATION 에 남기고 파트를 계속 진행한다(2a 로 넘어간다).
- **완료 조건**: B RED GREEN 전환 · 동결 8건 GREEN 유지 · 회귀 0(선재 10건) ·
  `bash -n` exit 0 · hook-selfcheck PASS.

### 위임 로그 요약 (파트 17-2, 2026-09-02)

| 항목 | 결과 |
|---|---|
| RED 커밋 | `cda574f` — `tests/test_stamp_supervisor_status.py` 신설. 끊어진 심링크로 state 만 실패시켜 `stamp_supervisor` 가 `rc=0` 을 돌려주는 것을 확인(RED 1건) + 정상 경로 대칭 단정 1건(당시 GREEN) |
| 위임 | `kit-scripts` / heavy 1회 (`MODEL_USED=openai/gpt-5.6-terra`). 반려 없음 — 3차 위임 승인분을 1회로 소진 |
| 구현 커밋 | `7d79ae9` — A: `add_missing_file /dev/null` 복귀로 `mktemp` 제거 / B: `_state_ok`·`_actions_ok` 분리 |

검증(오케스트레이터 직접 실행, `7d79ae9` 기준):
- `python3 -m unittest discover -s tests` → `Ran 432 tests` / `FAILED (failures=10)` = **선재 10건뿐, 회귀 0**
  (430 → 432 는 이 task 가 추가한 2건)
- `python3 -m unittest discover -s tests -p 'test_stamp_supervisor_status.py' -v` → `Ran 2 tests` / `OK` (RED→GREEN)
- `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh core/scripts/kit-doctor.sh` → exit 0
- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`
- 변이 검증: 미실행 — A 는 코드 경로 제거라 고정할 동작이 없고(감독 지정), B 는 동결 테스트의
  대칭 단정(정상 경로 rc=0)이 "항상 실패" 변이를 잡는다.

리뷰(3인 병렬, `7d79ae9` 대상): `bash-reviewer` · `security-reviewer` · `silent-failure-hunter`
→ **셋 다 🔴 없음**. 잔여 지적은 아래 2건뿐이며 둘 다 이번 커밋 밖이다.
- 🟡 (silent-failure-hunter, **이번 커밋 아님 — `11493ea` 도입, 페이즈 마감 입력**):
  `core/scripts/kit-doctor.sh` 의 `add_missing_file` 심링크 감지 3곳(`:268`·`:292`·`:296`)이
  `report_warn` 만 부르고 `report_fail` 을 부르지 않아, 목적지가 심링크라 자산을 못 만들어도
  doctor 종료코드가 0 일 수 있다.
- 🟢 (bash-reviewer): `stamp_supervisor` 만 "두 사유를 모두 시도 후 합산" 스타일이라 왜 즉시
  `return 1` 하지 않는지 주석 한 줄이 있으면 좋겠다. 블로킹 아님.
