---
task: 2b
status: done
---

## Task 2b: `core/scripts/supervisor-state.sh` 신설 (A1 + A3)
- **에이전트**: kit-scripts / **모델**: heavy / **선행**: 2a
- **목표**: 감독 상태 파일을 손으로 통째 다시 쓰던 것을 **원자·충돌 감지 쓰기**로 바꾸고,
  owner 잠금을 mtime 30분 휴리스틱에서 **PID + start_id 리스**로 승격한다.
- **대상 파일**: `core/scripts/supervisor-state.sh` (신규) · `core/install-manifest.tsv`(필요 시 설치 행)
- **인터페이스**:
  - `get <project>` → 상태 JSON 을 stdout 으로. 없으면 stderr + exit 2 (**빈 값 폴백 금지**).
  - `set <project> <json-file|->` → baseline 비교 후 tmp+`mv`. baseline 은 `--baseline <sha256>` 으로 받거나
    `get` 이 함께 출력한 해시를 쓴다. 불일치면 exit 3 + 현재 파일 해시 보고.
  - `patch <project> <key=value ...>` (또는 `--json` 병합) → 내부적으로 get→병합→set.
  - `owner-check <project>` → `alive` / `reclaimable <이유>` 를 stdout 으로, 종료코드로도 구분.
  - `owner-take <project> --pid <PID> --start-id <ID>` → 리스 획득(회수 가능할 때만).
- **구현 근거 (2026-09-02 홈 실측)**: 감독 프로세스 PID 는 Bash 도구의 `$PPID`(=24980, cmdline `claude --remote-control …`).
  start_id 는 두 경로에서 **같은 값**(`677122373`)이 나온다:
  ⓐ `awk '{print $22}' /proc/<pid>/stat` ⓑ **하네스가 직접 쓰는 `~/.claude/sessions/<pid>.json` 의 `procStart` 필드**.
  → **ⓑ 를 1차 소스로 쓴다.** 같은 파일에 `sessionId`·`cwd`·`kind`·`status`·`updatedAt` 이 함께 있어
  owner 스키마(`session_id`·`host`·`pid`·`start_id`)를 채우고 생존 판정까지 한 파일로 끝난다.
  ⓐ 는 `sessions/<pid>.json` 이 없을 때의 폴백(Linux 한정)이고, 둘 다 없으면 mtime 폴백임을
  **명시적으로 출력**한다(조용한 폴백 금지). 파일은 실행 중인 프로세스가 갱신하므로 **읽기 전용으로만 쓴다** —
  감독 상태 파일이 아니다. 절대 쓰지 말 것.
- **필수 규칙**: `core/scripts/*` 원본만 수정, `tests/` 수정 금지, `git commit` 금지, bash 3.2 호환,
  JSON 조작은 저장소에 이미 쓰는 방식(python3 인라인)을 따르고 새 의존성(jq 등) 추가 금지.
- **완료 조건**: 2a RED 6건 GREEN · 전체 회귀 0 · `bash -n` exit 0 · hook-selfcheck PASS · 변이 검증 1건.

### 위임 로그 요약 (파트 17-2, 2026-09-02)

| 항목 | 결과 |
|---|---|
| 위임 | `kit-scripts` / heavy **2회** (`MODEL_USED=openai/gpt-5.6-terra`). **반려 1회**(1라운드 🔴 2건) |
| 1차 구현 커밋 | `6ba0f67` — `core/scripts/supervisor-state.sh` 신설(319줄) + `core/install-manifest.tsv` 한 줄 |
| 리뷰 반영 RED | `313d917` — `SupervisorStateReviewTest` 3건 동결(오케스트레이터, 위임과 분리) |
| 재위임 커밋 | `508c6d0` — 🔴 2건 · 🟡 4건 반영 |

검증(오케스트레이터 직접 실행, `6ba0f67` 기준):
- `python3 -m unittest discover -s tests -p 'test_supervisor_state.py' -v` → `Ran 7 tests` / `OK` (2a RED 7건 전부 GREEN)
- `python3 -m unittest discover -s tests` → `Ran 439 tests` / `FAILED (failures=10)` = **선재 10건뿐, 회귀 0**
  (432 → 439 는 이 task 가 GREEN 으로 바꾼 2a 테스트 7건)
- `bash -n core/scripts/supervisor-state.sh install.sh new-project.sh adopt-project.sh lib/stamp.sh` → exit 0
- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`
- **변이 검증 1건 (오케스트레이터 직접)**: `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut2b-orch/`
  사본에서 start_id 비교(`if [ "$_current_start" = "$_owner_start" ]`)를 `if true` 로 무력화
  → `test_stale_owner_with_reused_pid_is_reclaimed` 가 `AssertionError: 'alive' != 'reclaimable'` 로 **RED 복귀**.
  나머지 6건은 GREEN 유지 = 변이가 정확히 그 단정에만 잡힌다.

### 리뷰 1라운드 (`6ba0f67` 대상, 3인 병렬) — **반려**

- `security-reviewer`: 🔴 없음 / 🟡 3건 — 봉쇄 검사 부재(상위 디렉터리 심링크 추종) ·
  `owner-take` 리스 회수 TOCTOU · `kill -0` 에 검증 안 된 `owner.pid`.
- `bash-reviewer`: PASS(🔴 없음) / 🟡 1건 — `_take_check=$?` 죽은 코드.
- `silent-failure-hunter`: **🔴 2건** →
  ① mtime 폴백 `alive`(exit 0)가 검증된 `alive` 와 종료코드로 구분되지 않아, 종료코드만 보는
  `command_owner_take` 가 **추측을 검증인 양** 근거 삼는다(이 페이즈가 없애려던 휴리스틱의 재도입).
  ② `make_temp` 실패가 3개 호출부에서 맥락 없이 `return 1` — 같은 파일 안에서 1곳만 메시지를 남기는 비대칭.

처리: 🔴 2건 + 🟡 4건을 **한 번의 재위임에 묶었고**, 그 전에 테스트로 고정할 수 있는 3건을
오케스트레이터가 먼저 RED 로 동결했다(`313d917`, 위임과 커밋 분리 — PITFALLS 27).

### 재위임 검증 (`508c6d0` 기준)
- `python3 -m unittest discover -s tests -p 'test_supervisor_state.py' -v` → `Ran 10 tests` / `OK`
- `python3 -m unittest discover -s tests` → `Ran 442 tests` / `FAILED (failures=10)` = **회귀 0**
- `bash -n core/scripts/supervisor-state.sh …` → exit 0 · `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`
- **변이 검증 2건째**: 사본에서 `state_directory_is_contained` 호출을 무력화
  → `test_refuses_when_state_directory_escapes_containment` 만 RED 복귀(나머지 9건 GREEN).

### 리뷰 2라운드 (`508c6d0` 대상, 3인 병렬) — **통과**

셋 다 **🔴 없음**. 1라운드 🔴 2건 · 🟡 4건 전부 **해소 확인**(테스트·코드·bash 실측 3방향).
`bash-reviewer` VERDICT: PASS.

잔여 🟡 (**블로킹 아님 — task 4 문서화 · 다음 페이즈 입력**):
1. **종료코드 1 이 "봉쇄/심링크 위반"과 "정상 reclaimable"을 뭉친다** (bash·silent 공통 지적).
   실제 우회는 없다 — `command_owner_take` 는 `require_state` 를 3중으로 돌므로 쓰기까지 못 간다.
   다만 종료코드로만 분기하는 새 호출자가 생기면 오판 여지. 권고: 봉쇄 위반 전용 코드(예: 5) 분리.
2. `command_owner_take` 의 `case` 에 `*)` 기본 분기가 없다 — 지금은 `owner_check` 반환 도메인이
   `{0,1,2,4}` 로 닫혀 있어 의도된 폴스루지만, 새 종료코드가 추가되면 조용히 "회수 진행"이 된다.
3. `set_state` 는 `mv` 직전에 **leaf 심링크만** 재검사하고 디렉터리 봉쇄는 재검사하지 않는다
   (검사-쓰기 사이 잔존 TOCTOU). 순수 셸의 구조적 한계 — `flock` 없이는 닫을 수 없다.
4. **`unverified`(4) 는 회수를 영구 거부한다** — 자동 복구가 없다. fail-secure 방향의 의도된
   트레이드오프지만 **운영자 수동 해제 절차를 문서화해야 한다**(`set`/`patch` 는 `owner_check` 를
   거치지 않으므로 baseline 만으로 owner 를 비울 수 있다).
5. `[ "$_owner_pid" -eq 0 ]` 는 `008` 같은 0-패딩 값에서 8진수 오인 stderr 노이즈를 낸다
   (안전하게 `kill -0` 경로로 흘러가므로 결과는 옳다).
6. `patch` 는 값을 **항상 문자열**로 저장한다 — `phases_since_review` 같은 숫자 필드를 patch 하면
   타입이 문자열로 바뀐다. 동결 테스트는 문자열 필드만 다루므로 계약 위반은 아니다.

### 구현 실측 (다음 파트·task 4 문서화 입력)

- **start_id 소스 3단**: ⓐ `session_start_id()` = `$HOME/.claude/sessions/<pid>.json` 의 `procStart`
  → ⓑ `proc_start_id()` = `/proc/<pid>/stat` 를 **마지막 `)` 뒤부터** 잘라 22번째 필드
  → ⓒ 둘 다 실패하면 **추정 불가**로 본다.
- **`owner-check` 판정 규약 (task 4 문서화 필수 — PROCEDURE.md 가 이 종료코드로 분기해야 한다)**:

  | 판정 | stdout 첫 낱말 | 종료코드 |
  |---|---|---|
  | start_id 일치 | `alive` | 0 |
  | start_id 불일치 · PID 없음 · owner 없음 · pid 가 유효하지 않음 · 봉쇄 위반 | `reclaimable` | 1 |
  | 상태 파일 없음 | — | 2 |
  | start_id 를 어디서도 못 얻음 (문구에 `mtime` 포함) | `unverified` | **4** |

  **mtime 나이로 alive 를 판정하지 않는다** — 30분 임계값은 제거됐다. `owner-take` 는 `0`·`4` 모두
  회수를 거부하되 `4` 는 "검증 불가(mtime 추정)" 임을 stderr 에 밝힌다.
- **`set` 은 `--baseline` 필수** — 우회 플래그 없음. baseline 재확인을 `mv` 직전에 한 번 더 한다.
- **`owner-take` 는 baseline 을 `owner-check` 앞에서 뜬다** — 검사와 쓰기 사이에 진짜 owner 가
  리스를 갱신하면 baseline 불일치(exit 3)로 걸린다.
- **봉쇄 검사는 자체 구현**이다(`state_directory_is_contained`). 매니페스트가 이 스크립트를
  `~/.local/bin/supervisor-state.sh` 로 **단독 설치**하므로 런타임에 `lib/stamp.sh` 가 없다 — 주석에 명시.
- 하네스 세션 파일은 **읽기만** 한다 — 쓰기·삭제 코드 없음.
