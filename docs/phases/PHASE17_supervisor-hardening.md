---
phase: 17
date: 2026-09-02
kind: task
domain: scripts, install, tests, docs
status: done
commits: 4af2824..2ec0dfc (+ 마감 커밋, 로컬 32개)
cost: $43.58 (파트 세션 4개 합계 — session-cost.py --project 유사 경로 우회 실측, PITFALLS 38. 홈 감독 세션·opencode 위임 7회·리뷰어 서브에이전트는 미포함)
compactions: 0 (파트 17-4 기준. 17-1~17-3 은 파트 보고에 기록 없어 미상)
interventions: 4 (17-1 blocked 에스컬레이션 → 3차 위임 승인 · task 1c 신설 · 큐에 K-RD1·K-OC2 추가 · 17-4 프롬프트 `결정:` 5건)
summary: 감독 계층 하드닝 — 감독 시작 계층(PROCEDURE·supervise 커맨드)을 키트로 이관 + owner PID 리스(A1)·원자 쓰기(A3)·무변경 재시도 차단(A2)·교훈 초안 규격(A4)
---

# 작업 지시서 — 감독(supervisor) 하드닝 K-SH1 (2026-09-02)

근거: `~/docs/2026-09-02-prime-agent-review.md` §2 "상" A1~A4 + §4 실행 제안, 큐 초안
`~/.local/state/orchestrate/supervisor/queue-drafts/aigsprac.md` (K-SH1, **사용자 승인 2026-09-02**).
설계 `~/docs/2026-09-02-phase-supervisor-design.md` §4.1 · §10. 선행 Phase 16 supervisor-bootstrap **done**(PR #14 병합).

**이 페이즈의 목적**: aigsprac 은 "개선 중인 스캐폴드를 어떤 프로젝트에든 빠르게 적용"하는 키트다.
2026-09-02 홈 세션이 **손으로** 만든 감독 시작 계층(`~/.claude/supervisor/PROCEDURE.md`,
`~/.claude/commands/supervise*.md`)은 키트에 원본이 없다 — 손 설치본을 키트 원본 + 설치 스크립트로 대체한다.
동시에 prime-agent 분석에서 "상" 판정된 잠금·재시도·상태 저장·교훈 채집 **규격 4건**을 넣는다.

> **호스트 → 키트 추출 순서 주의**: 이 호스트의 프로젝트들은 키트로 시작한 게 아니라 키트보다 먼저
> 손으로 만든 스캐폴드다. 따라서 전파는 "새 adopt" 가 아니라 이미 스캐폴드된 프로젝트에
> `adopt-project.sh` 재실행 + `kit-doctor.sh` 드리프트 동기화이며, 손 원본과 키트 템플릿이 다를 수 있다.

## 인터뷰 결과 (사용자 결정 완료)

- 스코프: ① 감독 시작 계층 키트 이관 ② A1 owner PID 리스 ③ A3 상태 파일 원자 쓰기 ④ A2 무변경 재시도 차단
  ⑤ A4 교훈 초안 JSON 규격(제안까지만, 적용은 감독/사람) ⑥ 큐 초안 → `docs/phases/QUEUE.md` 이관.
- **범위 밖**: codex 어댑터 동등물(후속 표기만), B1~B7(K-SH2), B8 `--resume` 주입(K-SH3, 드라이 런 선행),
  다른 프로젝트 저장소 적용(감독이 별도 페이즈로).
- 제약: `scripts/*` 는 심링크 — **`core/scripts/*` 원본만 수정**(PITFALLS). RED 테스트는 오케스트레이터가
  직접 작성·동결하고 위임 프롬프트에 `tests/` 수정 금지 명시(14). 위임 산출물과 `tests/` 수정을 한 커밋에
  묶지 않는다(27). 워크트리 위임 프롬프트는 상대 경로만(16). 변이 검증은 `.orchestrate/mutation/` 에
  저장소 전체 복사(15). push·PR·병합은 **홈 감독**이 한다 — 파트 세션은 로컬 커밋까지.
- 크기 등급: **large** (스크립트 2 신설/확장 + 테스트 3 + 설치 경로 4 + 문서 4) → 파트 3개 예정.

## 전제 실측 (2026-09-02, 홈 감독)

| 전제 | 근거 | 판정 |
|---|---|---|
| Bash 도구의 `$PPID` 가 대화형 감독 프로세스다 | 홈 감독 프로브: `PPID=24980`, cmdline `claude --remote-control --name supervise-aigsparc` | **A1 구현 가능** |
| `/proc/<pid>/stat` 22필드로 start_id 를 얻는다 | 같은 프로브: `677122373` | 유지 |
| **하네스가 이미 pid+procStart 리스를 파일로 들고 있다** | `~/.claude/sessions/<pid>.json` = `{"pid":24980,"sessionId":…,"procStart":"677122373","cwd":"/home/jh","kind":"interactive","name":…,"status":"busy","updatedAt":…}` — `procStart` 값이 위 `/proc` 실측과 **일치** | **A1 구현 방식 변경 근거** — `/proc` 직접 파싱 대신 이 파일을 1차 소스로 쓰면 macOS 에서도 동작하고 `status`·`updatedAt` 까지 공짜로 얻는다 |
| 매니페스트에 claude 전역 자산 행이 `skills` 트리 하나뿐이다 | core/install-manifest.tsv:9 `claude tree adapters/claude/global/skills .claude/skills` | 유지 — `commands` 트리 행 신설 필요 |
| 매니페스트 열 규격은 `harness / mode(file·seed·tree) / src(KIT_DIR 상대) / dst($HOME 상대)` | core/install-manifest.tsv:1 헤더 | 유지 |
| `kit-doctor.sh` 는 매니페스트를 순회해 `check_file`·`check_seed`·`check_tree` 로 검사한다 | core/scripts/kit-doctor.sh:416·442·465 | 유지 — 행 추가만으로 doctor 커버리지 확보 |
| `stamp_copy` 는 **기존 파일을 절대 덮지 않고**, 이번에 새로 복사한 파일만 `.orchestrate/.stamp-copied` 에 기록한다 | lib/stamp.sh:29-52 | 유지 — pre-kit 프로젝트에 멱등 |
| `stamp_placeholders` 는 `.stamp-copied` 목록 안에서 `__PROJECT__` 만 치환한다 | lib/stamp.sh:59-73 | 유지 — 다른 플레이스홀더는 보존됨 |
| `adopt-project.sh` 는 `stamp_copy → stamp_placeholders → stamp_finalize` 3단이다 | adopt-project.sh:56-58 | 유지 — supervise 생성은 이 뒤에 붙인다 |
| 파트 세션 프로토콜·허용 도구 템플릿 원본은 `adapters/claude/project/.claude/` 다 | Phase 16 task 3 (`ca55d39`) | 유지 |
| `phase-tools.py` 서브커맨드는 `init·claim·close·janitor·dashboard-mounts·tasks` | core/scripts/phase-tools.py:709-737 | 유지 — `retry-guard` 신설 |
| PROCEDURE.md 가 프로젝트 6개를 하드코딩한다 | ~/.claude/supervisor/PROCEDURE.md §0 | **제거 대상** — 레지스트리 존재 여부로 판정 |
| 감독 상태 파일은 손으로 통째 다시 쓰고 있다(원자성·baseline 없음) | PROCEDURE.md §7 | **A3 대상** |

## Task 목록

| # | 제목 | 에이전트 | 모델 | 선행 | 상태 |
|---|---|---|---|---|---|
| 0 | 큐 초안 → `docs/phases/QUEUE.md` 이관 | 오케스트레이터 직접 | — | 없음 | **done** `4af2824` |
| 1a | RED: 이관 동결 테스트 (adopt 후 커맨드·상태 파일 생성 / 매니페스트 설치 후 PROCEDURE.md / doctor 드리프트) | 오케스트레이터 직접 (tests/) | — | 없음 | **done** `abefb62`·`44cebde` |
| 1b | 감독 시작 계층 키트 이관 구현 | kit-scripts | heavy | 1a | **done** `74597da`→`7d7c723`→`11493ea` (잔여 2건은 1c) |
| 1c | task 1b 잔여 🔴 2건 마무리 (감독 신설 — 3차 위임 1회 승인) | kit-scripts + 직접 | heavy | 1b | **done** `cda574f`→`7d79ae9` |
| 2a | RED: `supervisor-state.sh` 테스트 (baseline 불일치 거부 / start_id 불일치 회수 / 원자 쓰기) | 오케스트레이터 직접 (tests/) | — | 없음 | **done** `898bc98` |
| 2b | `core/scripts/supervisor-state.sh` 신설 (A1 owner 리스 + A3 원자 쓰기) | kit-scripts | heavy | 2a | **done** `6ba0f67`→`313d917`→`508c6d0` (반려 1회) |
| 3a | RED: `retry-guard` 테스트 (동일 해시 재시도 거부 / 변경 있으면 통과) | 오케스트레이터 직접 (tests/) | — | 없음 | **done** `ef702b7` |
| 3b | `phase-tools.py retry-guard <N> <k>` (A2 무변경 재시도 차단) | kit-scripts | heavy | 3a | **done** `ed53ea9`→…→`5f3951a` (반려 2회, 한도 소진) |
| 4 | A4 교훈 초안 규격 — `part-protocol.md` LESSONS 절 + PITFALLS 4필드·scope 규격 + PROCEDURE/설계 문서 갱신 | kit-docs | default | 1b·2b·3b | **done** `b856117` |
| 5 | 마감: docs-index·structure-reviewer·frontmatter 정량 3필드 | 오케스트레이터 직접 | — | 0~4 | **done** (마감 커밋) |

상세: `PHASE17_supervisor-hardening.tasks/task<N>.md`.
상태 전이는 `python3 scripts/phase-tools.py tasks 17 --set <N>=<status>` —
**접미사 task(`1a`)는 아직 조회·`--set` 에서 누락된다(PITFALLS 39, K-SH2 대상)** → 접미사 task 는
task 파일 frontmatter 를 직접 편집하고 그 사실을 파트 보고에 남긴다.

## 파트 분할 (예정 — 감독이 실측으로 조정)

- **파트 17-1**: task 0 → 1a → 1b (이관. 설치 경로 변경이라 가장 위험 — 단독 파트) — **완료, `blocked` 에스컬레이션으로 종료**
- **파트 17-2**: task 1c → 2a → 2b (1c 는 17-1 에스컬레이션 처리. 감독 결정 2026-09-02) — **완료**
- **파트 17-3**: task 3a → 3b (retry-guard) — **완료** (반려 2회로 재위임 한도 소진)
- **파트 17-4**: task 4 → 5 (문서·마감) — **완료**

> 파트 17-1 실측: task 1a·1b 2개에 $17.55 / 104턴 / 위임 3회(반려 2회). 파트당 $40 한도 대비
> task 3개짜리 파트는 위험하므로 17-2 이후를 잘게 나눴다.
>
> **4파트 실측 총평**: 파트를 잘게 나눈 판단은 맞았다. 17-1(task 3개)만 에스컬레이션으로 끊겼고
> 17-2~17-4(task 2개)는 전부 파트 안에서 종료했다. 다만 **재위임 한도(2회)를 다 쓰고도 🟠 구조 부채가
> 남는** 패턴이 17-3 에서 나왔다 — 리뷰 반영을 반복할 task 는 처음부터 헬퍼 분리를 위임 프롬프트에
> 요구하는 게 낫다. 위임 총 7회, 사용 모델은 `openai/gpt-5.6-terra`(heavy) 와 `openai/gpt-5.6-luna`(default).

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| adopt 재실행 멱등성 | pre-kit 프로젝트의 손 `supervise-<p>.md`·상태 JSON 을 **덮어써 사용자 편집 유실** | `test_adopt_supervise.sh::기존 파일 보존` (1a) |
| 상태 파일 초기화 | 이미 `running` 인 상태 파일을 adopt 가 idle 로 리셋 | `test_adopt_supervise.sh::running 상태 보존` (1a) |
| owner 리스 | PID 재사용(같은 PID·다른 start_id)을 살아 있다고 오판 | `test_supervisor_state.py::test_stale_owner_with_reused_pid_is_reclaimed` (2a) |
| 원자 쓰기 | baseline 불일치를 **조용히 덮어씀** (silent overwrite) | `test_supervisor_state.py::test_set_rejects_when_baseline_changed` (2a) |
| retry-guard | 변경이 없는데 통과시킴 / 변경이 있는데 막음 (양방향) | `test_phase_tools.py::RetryGuardTest` 2건 (3a) |
| doctor 드리프트 | 레지스트리에 있는데 supervise 커맨드·상태 파일이 없어도 침묵 | `test_kit_doctor` 드리프트 1건 (1a) |
| LESSONS.json | 스키마 위반을 무시 / 없을 때 에러 (규격은 "없으면 빈 배열") | task 4 문서 규격 + 검증 스크립트 (4) |

### 실제 리뷰 결과 (파트별)

| task | 리뷰어 | 결과 |
|---|---|---|
| 1b | bash-reviewer · security-reviewer · silent-failure-hunter | 🔴 4건 → 2건 반영(`11493ea`), 잔여 2건은 task 1c 로 에스컬레이션 |
| 1c | bash-reviewer · security-reviewer · silent-failure-hunter | 🔴 0건 |
| 2b | bash-reviewer · security-reviewer · silent-failure-hunter | 1라운드 🔴 2건 → RED 동결(`313d917`) 후 재위임, 2라운드 🔴 0건 |
| 3b | python-reviewer · security-reviewer · silent-failure-hunter | 1라운드 🔴 3건 · 2라운드 🔴 1건 → 각각 RED 동결 후 재위임, 3라운드 🔴 0건. **재위임 한도 2회 소진** |
| 4 | code-reviewer · bash-reviewer | 1라운드 🔴 1건 · 🟠 1건 · 🟡 1건 — **두 리뷰어가 같은 🔴 을 독립적으로 지목**(문서의 CAS 절차가 편집 **후** 해시를 baseline 으로 넘겨 `set` 이 항상 exit 3). 재위임(`2ec0dfc`) 후 2라운드 🔴 0건, 양쪽 SIGN OFF |

> **리뷰 예상 지점표의 적중률**: 7개 중 5개가 실제로 지적됐다(owner 리스 PID 재사용 · baseline 조용한
> 덮어씀 · retry-guard 양방향 · adopt 멱등성 · doctor 드리프트). **예상 못 한 🔴 2계열**:
> ① 심링크 진입점과 테스트 실행 경로 불일치(PITFALLS 40) ② 문서에 적은 CAS 절차의 명령 **순서**가
> 스크립트 계약과 어긋나 항상 실패(task 4). 둘 다 "코드는 맞는데 **경로·순서**가 틀린" 계열이다 —
> 다음 페이즈의 리뷰 예상 지점에 이 계열을 넣을 것.

## 검증 총괄 (2026-09-02, 마감 커밋 직전 실측)

| 검증 | 명령 | 결과 |
|---|---|---|
| 전체 테스트 | `python3 -m unittest discover -s tests` | `Ran 454 tests` / `FAILED (failures=10)` — **회귀 0** |
| 선재 실패 10건의 정체 | — | `test_install_dashboard_container` 9건 + `test_install_container_step` 1건. 전부 서브모듈 미초기화(PITFALLS 24) 탓이며 이 페이즈와 무관하다. 워크트리에서 서브모듈 init 은 금지(PITFALLS 7) |
| 페이즈가 더한 테스트 | — | 442 → 454 (+12). `RetryGuardTest` 4 + `RetryGuardHardeningTest` 8. 그 이전 파트분까지 합하면 `test_supervisor_state.py` 10 · `test_stamp_supervisor_status.py` 2 · `test_adopt_supervise.py` 포함 |
| bash 문법 | `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` | 통과 (exit 0, 출력 없음) |
| 훅 자가진단 | `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |
| 워크트리 잔재 | `git stash list` | 비어 있음 (PITFALLS 26 확인) |
| 변이 검증 | `.orchestrate/mut2b/` · `mut3b/` · `mut3b-r2/` · `mut3b-r3/` (저장소 전체 복사, `.orchestrate` 제외 — PITFALLS 34) | task 2b·3b 에서 수행. task 4 는 **문서 전용이라 변이 검증 불가**(PITFALLS 21 계열) — 대체 검증은 `grep` 기대값 + 리뷰어 2인 |
| 문서화된 진입점 실측 | `python3 scripts/phase-tools.py retry-guard …` (심링크 경로) | 종료코드 0/3/2/0 실측. 상세는 `task4.md` "오케스트레이터 사전 실측" (PITFALLS 40 대응) |

## 구조 리뷰 (2026-09-02, `structure-reviewer` 1회 — 게이트 아님)

대상: 페이즈 누적 diff `git diff main...HEAD` (31 커밋). **부채 8건 / 분할 후보 5건.**
🔴 로 마감을 막지 않으며 산출물은 다음 페이즈(K-SH2) 입력이다.

### 기지 부채 5건 — 리뷰어가 등급을 확인하고 우선순위를 재정렬했다

| # | 등급 | 내용 | 우선순위 |
|---|---|---|---|
| 1 | 🟠 확정 | `phase-tools.py:614-696` `retry_guard_snapshot` **85줄**(1.7×50), `:718-800` `cmd_retry_guard` **83줄**. 중첩 `for → try/else → if S_ISLNK → try/except → try/except → if not S_ISREG → while True → if not chunk` = **7단계**(1.75×4). 둘 다 이번 페이즈 신설 — 리뷰 라운드마다 if/else 를 끼워 넣은 결과 | 1 |
| 2 | 🟡 확정 | `supervisor-state.sh:160-194` `patch` 가 값을 항상 문자열 저장. `PROCEDURE.md` 가 "숫자·null 엔 `get`+`set`" 을 명문화해 실사용 위험은 낮춤 | 2 |
| 3 | 🟡 확정 | `cmd_retry_guard:734` `state_path.read_bytes()` 만 check-then-open. 미추적 파일 경로(`:661` `O_NOFOLLOW\|O_NONBLOCK`)와 방어 수준이 비대칭 | 3 |
| 4 | 🟡 확정 | `supervisor-state.sh:307-317` `case` 에 `*)` 없음. 현 반환값 집합(0/1/2/4)에선 안전하나 새 코드 추가 시 조용히 reclaim 진행 | 4 |
| 5 | 🟡 확정 | `--check`(`phase-tools.py:939-943` mutex, `:744` `if args.check or not args.record`)는 죽은 조건. 수정 비용 ≈ 0 | 5 |

### 리뷰어가 새로 찾은 것 3건

- **🟠 idle 상태 JSON 스키마가 6곳에 중복.** `lib/stamp.sh:230`(`stamp_supervisor`)과 `kit-doctor.sh`
  레지스트리 순회 블록이 **동일 리터럴을 각자 손으로 조립**한다. 같은 스키마가 `PROCEDURE.md:19-22`
  (예시)와 테스트 3파일(`test_kit_doctor.py`·`test_supervisor_state.py`·`test_adopt_supervise.py`)에도
  하드코딩돼 있다. 필드 하나 추가 시 6곳을 맞춰야 하고 놓치면 **조용한 스키마 드리프트**
  (adopt 시점 상태 ≠ doctor 복구 시점 상태). "계약이 문서·코드·테스트 세 곳에 흩어진" 패턴의 실례다.
- **🟡 `add_missing_file`(`kit-doctor.sh:257`) 책임 확장.** 이번에 5·6번째 옵션 인자와
  `perl -pi -e 's/__PROJECT__/…/g'` 치환(`:314`)이 들어갔는데, **동일한 perl 한 줄**이
  `lib/stamp.sh:219` 에도 있다 — `kit-doctor.sh` 가 `lib/stamp.sh` 를 이미 source(`:154-158`)하는데도
  재사용하지 않고 재구현했다. 6개 호출부 중 치환을 쓰는 곳은 1곳뿐이다.
- **🟡 `kit-doctor.sh:527~608`(약 80줄) 미명명 최상위 블록.** 레지스트리 순회가 함수화되지 않은 채
  본문에 인라인이고, 나머지(제네릭 매니페스트 진단)와 관심사가 다르다.

### 분할 후보

| 대상 | 제안 경계 | 호출부 | 난이도 |
|---|---|---|---|
| `retry_guard_snapshot` | `_hash_regular_file(fd, relative_path, path_stat)` · `_hash_unreadable(...)` · `_hash_symlink(...)` | 1 | 중 |
| `cmd_retry_guard` | `_load_retry_state(state_path) -> dict` (심링크/존재/정규파일/JSON) · `_scope_check(failure, args, snapshot) -> int` | 1 | 중 |
| idle 스키마 중복 | `lib/stamp.sh` 에 `stamp_supervisor_idle_state_json <name> <root>` 신설 → `stamp_supervisor`·`kit-doctor.sh` 가 호출 | 2 (+테스트 3) | 중 |
| `kit-doctor.sh` 레지스트리 블록 | `ensure_supervisor_assets()` 함수 또는 `core/scripts/kit-doctor-supervisor.sh` 로 추출 | 1 | 하 |
| `add_missing_file` 치환 | `stamp_placeholders` 재사용 또는 `add_missing_file_with_substitution` 분리 | 6 (실사용 1) | 하 |



## 후속 제안 (다음 페이즈 입력)

- K-SH2 (B1~B7): 한도 4종 자동 검사 · `PART_FAIL <reason>` 종료 계약 · `parts[]` 레지스트리+PID 저널 ·
  깊이 1 규칙 · HANDOFF 절 확장 · PITFALLS 요약 주입 규격 · local/kit 승격 규칙.
  **PITFALLS 39(접미사 task 조회 누락)** 도 여기에 묶는다.

### 구조 리뷰가 권고한 순서 (K-SH2 후보, 우선순위 순)

1. **idle 상태 JSON 스키마를 `lib/stamp.sh` 단일 헬퍼로 통합** — 이미 프로덕션 파일 2개가 갈라졌고
   다음 필드 추가에서 드리프트가 실측될 것이 확실하다. 리뷰어가 1순위로 올렸다.
2. **`retry_guard_snapshot`·`cmd_retry_guard` 분해** — 1.7배 길이·7단계 중첩은 다음 리뷰 라운드가
   또 if/else 를 끼워 넣을 자리를 만든다.
3. **`kit-doctor.sh` 레지스트리 순회 블록 추출** — 제네릭 매니페스트 진단과 프로젝트별 감독 자산
   진단이 한 파일에서 계속 자란다.
4. **`add_missing_file` 의 `__PROJECT__` 치환을 `stamp_placeholders` 계열로 재사용** — 같은 perl
   한 줄이 두 파일에 있다는 것 자체가 한쪽만 고쳐질 위험의 증거다.
5. **`patch` 의 문자열 전용 저장 + `--check` 죽은 조건 정리** (둘 다 저비용). `PROCEDURE.md` 가 이미
   우회 절차를 문서화해 사용자 규율로 상환 중이지만, 죽은 옵션은 다음 위임을 오해시킨다.

### 이번 페이즈에서 의도적으로 **하지 않은 것** (감독 결정 2026-09-02)

- 파트 17-3 이 남긴 🟠 구조 부채(위 1·2번)와 🟡 TOCTOU 는 **이번 페이즈에서 리팩터하지 않았다.**
  재위임 한도(2회)를 이미 소진했고 🔴 이 아니었다. 범위 확장은 반려 사유였다.
- `retry-guard` 의 `phase`·`part` **정규화**(PITFALLS 43)는 넣지 않았다 — 지금은 호출 규약
  (zero-padding 금지)으로만 막혀 있다. 스크립트 쪽 정규화가 K-SH2 후보다.
- 종료코드 `1` 이 "정상 reclaimable" 과 "봉쇄/심링크 위반" 을 뭉치는 문제 — 전용 코드(예: 5) 분리.
- `command_owner_take` 의 `case` 방어적 `*)` 분기.
- `core/scripts/kit-doctor.sh` 의 `add_missing_file` 심링크 감지 3곳(`:268`·`:292`·`:296`)이
  `report_warn` 만 부르고 `report_fail` 을 안 불러, 자산을 못 만들어도 doctor 종료코드가 0 일 수 있다
  (`11493ea` 도입, 파트 17-1 silent-failure-hunter 1라운드 지적 — **이번 페이즈 밖 잔재**).
- **`docs/phases/PITFALLS.md` 1~39번의 4필드 일괄 변환.** 이번 페이즈는 신설 규격을 40~43 에만
  적용했다. 39건 변환은 별도 문서 task 로 잡을 것.
- codex 어댑터의 supervise 커맨드 동등물(`adapters/codex/global/prompts`).

### 그 밖의 후속

- K-SH3 (B8): `claude -p --resume` 이 `--allowedTools`·`--append-system-prompt-file` 을 유지하는지
  드라이 런 후 방향 결정. **드라이 런은 이 페이즈에서 실시하지 않았다** — 큐에서 여전히 `blocked`.
