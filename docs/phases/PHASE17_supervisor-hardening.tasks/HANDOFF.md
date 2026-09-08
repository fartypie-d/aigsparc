# HANDOFF — PHASE 17 supervisor-hardening

> **페이즈 완료.** 파트 17-4(마지막 파트)가 task 4·5 를 끝내고 마감 커밋까지 했다.
> 남은 것은 **감독 소관**: push · PR · CI · 병합 · `phase-close`. 이 파일은 감독이 병합 시 지운다.

## 완료 상태 (2026-09-02, 파트 17-4 종료 = 페이즈 종료)

| task | 상태 | 커밋 |
|---|---|---|
| 0 | **done** (감독 직접) | `4af2824` |
| 1a | **done** — RED 8건 동결 | `abefb62` · `44cebde` |
| 1b | **done** (잔여 2건은 1c 에서 마무리) | `74597da` → `7d7c723` → `11493ea` |
| 1c | **done** — 리뷰 3인 🔴 없음 | `cda574f`(RED) → `7d79ae9` |
| 2a | **done** — RED 7건 동결, 당시 7건 전부 실패 확인 | `898bc98` |
| 2b | **done** — 반려 1회 후 재위임 통과, 리뷰 2라운드 🔴 없음 | `6ba0f67` → `313d917`(RED) → `508c6d0` |
| 3a | **done** — RED 4건 동결 | `ef702b7` |
| 3b | **done** — 반려 2회(한도 소진) 후 3라운드 🔴 없음 | `ed53ea9` → `12da8a1`(RED) → `d15a8ed` → `bc7b086`(RED) → `5f3951a` |
| 4 | **done** — 반려 1회 후 2라운드 🔴 0건, 리뷰어 2인 SIGN OFF | `b856117` → `2ec0dfc` |
| 5 | **done** — 마감 | 마감 커밋 |

## 다음 task
**없음.** 페이즈의 모든 task 가 `done` 이다.

## 검증 상태 (마감 커밋 직전, `2ec0dfc` 기준 — 오케스트레이터가 직접 실행)

- `python3 -m unittest discover -s tests` → `Ran 454 tests` / `FAILED (failures=10)` = **회귀 0**
- 선재 실패 10건: `test_install_dashboard_container` **9건** + `test_install_container_step` **1건**.
  전부 서브모듈 미초기화(PITFALLS 24) 탓이다. 다른 모듈은 없다. 워크트리에서 서브모듈 init 은 금지(PITFALLS 7).
- `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` → exit 0
- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`
- `git stash list` 비어 있음 (PITFALLS 26 확인)
- 페이즈가 더한 테스트 누계: 430 → 454 (+24)

## 감독이 할 일 (인계)

1. `git push -u origin feature/phase17-supervisor-hardening` → PR 생성.
2. 자동 병합 조건 확인: CI 초록 · 리뷰 SIGN OFF · 충돌 없음 · **🔴 위험 도메인 task 미포함**.
   → 이 페이즈에 🔴 위험 도메인 task 는 **없다**(⚠️ `kit-scripts` 는 있으나 🔴 아님). 감독 병합 가능.
3. 병합 후 `phase-close`. **서브모듈은 이 워크트리에서 init 하지 않았으므로** worktree remove 는
   정상 동작할 것이다(PITFALLS 7 회피 확인).
4. **설계 문서 반영** — `docs/phases/PHASE17_supervisor-hardening.tasks/task4-design-delta.md` 의
   §4.1 D-8 갱신 초안을 원문(`~/docs/2026-09-02-phase-supervisor-design.md`)과 대조해 접합한다.
   파트 세션은 홈을 읽을 수 없어 **원문을 못 본 채 초안만** 썼다 — 대조는 필수다.
5. `HANDOFF.md` 삭제 · `ESCALATION.md` 는 처리 이력이므로 감독 판단(지금은 `resolved` 표기만 되어 있다).
6. `.orchestrate/` 스크래치 정리 (아래).

## 파트 17-4 가 남긴 스크래치 (감독이 마감 때 정리)

`.orchestrate/` 아래 gitignored: `probe4/`(격리 상태 파일) · `probe4.sh` ·
`task4.prompt` · `task4-r2.prompt` · `task4.log*` · `task4-r2.log*`.
이전 파트분(`probe1c*` · `mut2b*` · `probe3b/` · `mut3b*` · `task3b*`)도 그대로 남아 있다 —
`mut2b`·`mut2b-orch` 는 각 66M 다. 하네스가 `rm` 을 막아 파트 세션은 지우지 못했다.

## 이 페이즈가 남긴 계약 (다음 페이즈가 지켜야 할 것)

`core/supervisor/PROCEDURE.md` §2·§5·§7 이 **정본**이다. 요약:

1. **`owner-check` 종료코드**: `alive`=0 / `reclaimable`=1 / 상태 파일 없음=2 / baseline 불일치(`set`)=3 /
   `unverified`=4. **`unverified`(4) 는 자동 복구가 없다** — `owner-take` 가 4 를 거부하며,
   운영자 수동 해제 절차가 PROCEDURE §2 에 문서화돼 있다(사용자 확인 사항).
2. **`set` 은 `--baseline <sha256>` 필수**, 우회 플래그 없음. 해시는 **편집 전 원본 바이트**의
   sha256 16진 소문자(python3 `hashlib`). **mtime 30분 휴리스틱은 제거됐다 — 되살리지 말 것.**
3. **`patch` 는 값을 항상 문자열로 저장한다** — 숫자·`null`·객체 필드에는 `get`+`set` 을 쓴다.
4. `~/.claude/sessions/<pid>.json` 은 **읽기 전용**이다.
5. `core/scripts/supervisor-state.sh` 는 `~/.local/bin/` 에 **단독 설치**된다 — `lib/` 를 source 할 수 없다.
6. **`retry-guard` 종료코드**: `--check` 통과=0 / 무변경 재시도=**3**(`retry_exhausted`) /
   상태 파일 없음=2 / `--record` CAS 충돌=4 / 그 밖=1.
7. **`retry-guard` 스코프가 두 종류**다 — 스냅샷은 호출된 워크트리, 상태 파일은 메인 체크아웃 이름.
8. **`--record` 실패를 무시하면 가드가 통째로 무력화된다** — 실패 시 파트 실패 처리 자체를 중단한다.
9. **`phase`·`part` 표기 zero-padding 금지** — 문자열 비교라 `4`≠`04` 로 fail-open (PITFALLS 43 실측).
10. 동결 테스트: `tests/test_supervisor_state.py`(10) · `tests/test_stamp_supervisor_status.py`(2) ·
    `tests/test_phase_tools.py` 의 `RetryGuardTest`(4)·`RetryGuardHardeningTest`(8).

## 남은 부채 (다음 페이즈 입력 — 지시서 "구조 리뷰"·"후속 제안" 에 상세)

- 🟠 idle 상태 JSON 스키마가 **6곳에 중복** (프로덕션 2 + 문서 1 + 테스트 3). 리뷰어 1순위 권고.
- 🟠 `retry_guard_snapshot`(85줄)·`cmd_retry_guard`(83줄), 중첩 7단계.
- 🟡 `kit-doctor.sh` 레지스트리 순회 블록(~80줄) 미함수화 · `add_missing_file` 의 perl 치환이
  `lib/stamp.sh:219` 와 중복 · `patch` 문자열 전용 · `--check` 죽은 조건 · `case` 의 `*)` 누락 ·
  `cmd_retry_guard` 상태 파일 읽기 TOCTOU.
- 🟡 **페이즈 밖 잔재**: `core/scripts/kit-doctor.sh` 의 심링크 감지 3곳(`:268`·`:292`·`:296`)이
  `report_warn` 만 부르고 `report_fail` 을 안 부른다.
- 🟡 `docs/phases/PITFALLS.md` 1~39번은 아직 산문 형식이다(40~43 만 신설 4필드 규격 적용).

## 이 페이즈에서 실측된 것 (PITFALLS 40~43 으로 승격 완료)

40. 동결 테스트가 **문서화된 심링크 진입점**으로 돌지 않으면 fail-open 을 통째로 놓친다.
41. 위임이 도는 중에 전체 스위트를 돌리면 없는 실패가 보인다 — **회귀 판정은 위임 종료 후 오케스트레이터가**.
42. RED 를 쓰고 나면 "지금 통과하는지" 를 반드시 확인한다.
43. `retry-guard` 의 `phase`·`part` 는 문자열 그대로 비교된다 — zero-padding 이 가드를 뚫는다.

**PITFALLS 승격 후보(미등재)**: "문서에 적은 절차의 **명령 순서**가 스크립트 계약과 어긋나 항상 실패한다"
— task 4 에서 리뷰어 2인이 독립적으로 잡은 🔴 이다. 코드가 아니라 **문서**의 결함이고, 40 과 같은
"코드는 맞는데 경로·순서가 틀린" 계열이다. 다음 페이즈에서 등재 여부를 판단할 것.

## 재개 지시
**없음 — 페이즈 종료.** 감독은 위 "감독이 할 일" 6단계를 수행한다.
`python3 scripts/phase-tools.py tasks 17 --next` 는 접미사 task 를 못 읽으므로(PITFALLS 39)
상태 판정은 이 표를 기준으로 한다.
