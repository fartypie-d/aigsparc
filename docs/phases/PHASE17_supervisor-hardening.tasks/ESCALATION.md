---
part: 17-1
task: 1b
kind: blocked
resolved: 2026-09-02
---

> **처리 결과 (감독 결정 2026-09-02)**: 선택지 1 채택 — **3차 위임 1회 승인**. 잔여 🔴 2건(A·B)을
> `task1c` 로 신설(`49b2bd3`)하고, RED 를 먼저 동결(`cda574f`)한 뒤 `kit-scripts`/heavy 로 재위임해
> `7d79ae9` 로 해소했다. 리뷰 3인 재검수에서 🔴 0건. **task 1c = done.**
> 이 파일은 지우지 않는다 — 페이즈 마감 시 처리 이력으로 남긴다(감독이 병합 때 처리).

## 질문
task 1b 는 동결 8건 GREEN·회귀 0 으로 구현이 끝났고 1차 리뷰의 🔴 3건도 모두 해소됐으나,
2차 확인 리뷰에서 리뷰어 2인이 **각각 새 🔴 1건**(둘 다 좁고 한 곳 수정)을 냈다 —
재위임 한도(2회)와 반려 한도(2회)를 모두 소진했으니 3차 위임을 승인할지, 지금 상태로 받고
잔여 2건을 후속 task 로 넘길지 결정해 달라.

## 선택지
1. **3차 위임 1회 승인** (권장) — 남은 2건은 각각 한 블록짜리 수정이고 위치·수정안이 이미 확정돼 있다.
   같은 `kit-scripts`/heavy 로 15분 내 끝난다. 근거: 두 건 모두 "이번 커밋이 새로 만든" 비대칭이라
   다음 페이즈로 넘기면 원인 맥락이 흩어진다.
2. **지금 상태로 수용하고 잔여 2건을 task 5(마감) 또는 다음 페이즈 task 로 등록** — 두 건 다 실피해가
   작다(아래 참조). 파트 17-2 를 바로 시작할 수 있다.
3. 파트 17-1 을 여기서 끊고 잔여 2건을 파트 17-2 앞에 붙인다 — 2번과 실질 같으나 순서만 고정.

## 남은 🔴 2건 (둘 다 `11493ea` 가 새로 만든 비대칭)

**A. `core/scripts/kit-doctor.sh:597` — actions 임시 파일에 봉쇄 사전 검사가 없다** (security-reviewer)
state 블록(`:577`)은 `mktemp` 전에 `write_parent_is_within_root "$STATE_HOME_DIR" ...` 를 하는데
actions 블록은 그 줄이 빠졌다. `$STATE_ROOT` 자체가 봉쇄 밖을 가리키는 심링크면 **빈 임시 파일이
봉쇄 밖에 잠깐 생겼다 지워진다**(최종 자산은 `add_missing_file` 이 여전히 막는다).
전제가 이미 `$STATE_ROOT` 쓰기 권한을 가진 공격자라 실피해는 작다. 수정: state 블록과 같은 검사 한 줄
추가, 또는 수정 전처럼 `/dev/null` 을 소스로 되돌려 `mktemp` 자체를 없앤다(치환이 필요 없는 경우다).

**B. `lib/stamp.sh:231-232` — state 생성 실패가 actions 성공에 가려진다** (silent-failure-hunter)
`stamp_supervisor` 의 반환값은 마지막 명령(actions 쓰기)의 것이다. state 쓰기가 실패해도
(stderr 로는 사유가 찍히지만) 함수는 0 을 돌려주므로 `adopt-project.sh:61`·`new-project.sh:37` 의
`|| echo "⚠️ 감독 자산은 만들지 못했다 …"` 경고가 **뜨지 않는다**. 수정안(리뷰어 제시):

    _state_ok=1
    stamp_supervisor_add_content "$_state" "$_state_root" "state" "$_state_content" || _state_ok=0
    _actions_ok=1
    stamp_supervisor_add_content "$_actions" "$_state_root" "actions" "" || _actions_ok=0
    [ "$_state_ok" -eq 1 ] && [ "$_actions_ok" -eq 1 ]

두 건 모두 **동결 테스트가 잡지 못한다** — 3차 위임을 승인한다면 RED 를 먼저 동결할지
(오케스트레이터 직접, tests/) 함께 지시해 달라. B 는 테스트로 고정하기 쉽고(쓰기 실패 주입),
A 는 심링크 픽스처가 필요하다.

## 지금까지 한 것

| 커밋 | 내용 |
|---|---|
| `abefb62` | task 1a — RED 8건 동결(테스트만). 당시 8건 전부 실패 확인 |
| `44cebde` | task 1a done 기록 |
| `74597da` | task 1b 1차 구현(위임 kit-scripts/heavy) |
| `7d7c723` | `tests/test_adopt.py` 격리 HOME 주입 — 실제 홈 오염 차단(오케스트레이터, 위임과 분리) |
| `11493ea` | 리뷰 반영 수정(재위임 2회분) |

검증(오케스트레이터 직접 실행, `11493ea` 기준):
- `python3 -m unittest discover -s tests` → `Ran 430 tests` / `FAILED (failures=10)` = **선재 10건뿐, 회귀 0**
- task 1a 동결 8건 전부 GREEN
- `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh core/scripts/kit-doctor.sh` → exit 0
- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`
- 변이 검증: dangling-symlink 가드 약화 시 `DoctorPathContainmentTest` RED 복귀
