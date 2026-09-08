---
phase: 16
date: 2026-09-02
kind: task
domain: scripts, tests, docs
status: done
commits: 16825fa..b5f98ba (+ 마감 커밋)
cost: $15.31 (파트 세션 4파일 실측 — 16-1 54679ff8 $8.42 + 16-2 22a81052 $3.20 + 1회차 프로브 2건 $3.68; 홈 감독 세션은 메인 슬러그 누적 $62.48 에 섞여 분리 불가. 리뷰어 서브에이전트 별도)
compactions: 0
interventions: 0
summary: 감독 체계 선행 — phase-tools tasks 워크트리 해석(KF-13)·session-cost --project/--session(KF-11) + 파트 세션 프로토콜·허용 도구 템플릿 + 병합 주체 정책 문구
---

# 작업 지시서 — 감독(supervisor) 체계 선행 작업 (2026-09-02)

근거: 설계 `~/docs/2026-09-02-phase-supervisor-design.md`(사용자 승인 2026-09-02) §9, 플랜
`~/docs/2026-09-02-phase-supervisor-plan.md`. 하류 피드백 `tobuilder-bot/docs/phases/REVIEW_kit-feedback-20260901.md` KF-11·KF-13.
이 페이즈는 **홈 감독 세션이 지시서를 쓰고, 파트 세션(헤드리스, 이 워크트리 cwd)이 위임·검수·커밋을 수행**하는
첫 실전이다. 파트 세션 규칙은 `.claude/part-protocol.md`.

## 인터뷰 결과 (홈 감독 세션에서 사용자 결정 완료 — 설계 §3 D-1~D-7)
- 스코프: ① `core/scripts/phase-tools.py` `tasks`가 워크트리 cwd의 페이즈 문서를 우선 해석
  ② `core/scripts/session-cost.py`에 `--project`·`--session`·`--json` + 워크트리에서 메인 슬러그 해석
  ③ 파트 세션 프로토콜·허용 도구 파일을 claude 어댑터 템플릿에 추가 ④ 어댑터 CLAUDE.md·SKILL.md의 푸시/병합 문구를
  "감독 자동 병합" 규칙으로 갱신. **범위 밖**: run-delegation.sh, 드라이버 스크립트, bot 저장소 적용.
- 우선순위: Task 1 → 2 → 3 → 4(마감). 1·2는 독립(병렬 위임 가능하되 같은 프로젝트라 락 직렬).
- 제약: `scripts/*`는 심링크 — **`core/scripts/*` 원본만 수정**. RED 테스트는 오케스트레이터(파트 세션)가 직접
  작성·동결하고 위임 프롬프트에 `tests/` 수정 금지 명시(PITFALLS 14). 위임 산출물과 tests/ 수정을 한 커밋에 묶지 않는다(27).
  워크트리 위임 프롬프트는 상대 경로만(16). 변이 검증은 `.orchestrate/mutation/`에 저장소 전체 복사(15).
  push·PR·병합은 **홈 감독이** 한다 — 파트 세션은 로컬 커밋까지.
- 크기 등급: **large** (스크립트 2 + 테스트 2 + 템플릿·문서 4, 에이전트 2종) → task-orchestrator 경유, kit-scripts task는 heavy.

## 전제 실측 (2026-09-02, 홈 감독)

| 전제 | 근거 | 판정 |
|---|---|---|
| `find_root()`가 `--git-common-dir` 부모 = 메인 루트를 돌려준다 | core/scripts/phase-tools.py:54-60 | 유지 |
| `cmd_tasks`가 `find_root()` 결과로만 `find_tasks_dir`를 호출한다 | phase-tools.py:511-520 | 유지 — 원인 |
| `sh()`가 `check` 인자를 받고 CompletedProcess를 돌려준다 | phase-tools.py:44 | 유지 |
| `tests/test_phase_tools.py`의 `Base`가 docs_dir `DOCs`·기본 브랜치 `develop`로 격리 저장소를 만든다 | tests/test_phase_tools.py:24-63 | 유지 — 새 테스트는 이 Base를 상속 |
| `session-cost.py`가 cwd 슬러그로 세션 디렉터리를 잡고 `sys.argv[1]`만 받는다 | core/scripts/session-cost.py:25-27, 66-70 | 유지 — 원인 |
| 프로젝트 `.claude/` 템플릿 원본은 `adapters/claude/project/.claude/`이고 stamp가 없는 파일만 복사한다 | lib/stamp.sh:29-32, 40-52 | 유지 |
| 어댑터 SKILL.md 푸시 문구 3곳 | adapters/claude/global/skills/orchestrate/SKILL.md:36, 552, 556 | 유지 |
| 헤드리스 세션은 allow 밖 도구를 거부한다 | 홈 프로브 세션 43e955ea | 유지 — `.claude/part-allowed-tools.txt` |

## Task 목록

| # | 제목 | 에이전트 | 모델 | 선행 | 상태 |
|---|---|---|---|---|---|
| 1a | RED: tasks 워크트리 해석 동결 테스트 5건 | 오케스트레이터 직접 (tests/) | — | 없음 | **done** (a4bd61f) |
| 1b | phase-tools `find_docs_root` + cmd_tasks 문서 루트 분리 | kit-scripts | heavy | 1a | **done** (7ad7c77 → 반려 → c247f8e·b63dc1c·773899c) |
| 2a | RED: session-cost 옵션·워크트리 슬러그 테스트 3건 | 오케스트레이터 직접 (tests/) | — | 없음 | **done** (f11e996) |
| 2b | session-cost `--project/--session/--json` + `main_checkout()` | kit-scripts | heavy | 2a | **done** (f396a54 → 반려 → c9bd716·b630cf5) |
| 3 | 파트 프로토콜·허용 도구 템플릿 + 병합 주체 문구 (어댑터 4파일) | kit-docs | default (`openai/gpt-5.6-luna`) | 없음 | **done** (ca55d39, 리뷰 1라운드 SIGN OFF) |
| 4 | 마감: docs-index·structure-reviewer·frontmatter | 오케스트레이터 직접 | — | 1b·2b·3 | **done** (마감 커밋) |

상세: `PHASE16_supervisor-bootstrap.tasks/task<N>.md`. 상태 전이는 `python3 scripts/phase-tools.py tasks 16 --set <N>=<status>`
(1b 완료 전까지 워크트리에서 실패하면 task 파일 frontmatter를 직접 편집 — 이 페이즈가 고치는 바로 그 결함이다).

## 파트 16-1 (세션 1): Task 1a → 1b → 2a → 2b
## 파트 16-2 (세션 2): Task 3 → 4

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 |
|---|---|---|
| `find_docs_root` 폴백 | git 밖·해석 실패를 메인 루트로 **조용히** 폴백 (silent fallback) | test_phase_tools.py::WorktreeTasksTest::test_tasks_from_main_cwd_without_docs_is_explicit_error (1a) |
| 병합 후 메인에서 조회 | 워크트리 우선 도입으로 메인 체크아웃 조회가 깨짐 | WorktreeTasksTest::test_tasks_from_worktree_falls_back_to_main_when_absent + 기존 TasksTest 6건 (1a) |
| session-cost 미존재 세션 | 파일 없음을 빈 합계 `$0.00`으로 보고 | test_session_cost.py::SessionCost::test_missing_session_is_explicit_error (2a) |

## 검증 총괄 (마감 실측, 2026-09-02 파트 16-2)

| 명령 | 결과 |
|---|---|
| `python3 -m unittest discover -s tests` | `Ran 422 tests` / `FAILED (failures=10)` — 실패 10건은 **전부 선재**(서브모듈 미초기화: `InstallDashboardContainerTest` 9 + `test_actual_container_up_failure_marks_manual_step`, PITFALLS 24). **회귀 0** |
| `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` | exit 0 |
| `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |
| `git stash list` | 비어 있음 (PITFALLS 26 잔재 없음) |
| 변이 검증 | 1b·2b 2건 모두 RED 복귀 확인 (파트 16-1 기록) |

"전체 초록"은 미달성 — 워크트리에서 서브모듈을 init 하면 `phase-close` 가 크래시하므로(함정 7·24)
초기화하지 않았다. 실패 목록이 파트 16-1과 동일함을 대조 확인했다.

## 구조 리뷰 (structure-reviewer, 마감 1회 — 게이트 아님)

🔴 급 없음. **부채 5건 / 분할 후보 4건** — 전문은 `.tasks/task4.md` "구조 리뷰 상세".
핵심: `find_root()`↔`main_checkout()` 중복(견고성이 갈림), `session-cost.py:main()` 65줄(1.3×),
`cmd_tasks` 84줄(1.68×), `part-protocol.md` 이중 사본 드리프트 위험.

## 후속 제안 (다음 페이즈 입력)

1. **`core/scripts/_gitroot.py` 공통화** — `find_root()`/`main_checkout()` 을 견고한 쪽 구현으로 통합.
   호출부 2곳, 난이도 낮음. 미루면 세 번째 스크립트가 또 복제한다.
2. **`session-cost.py:project_dir()` 슬러그에 `.` → `-` 치환** (PITFALLS 38 근본 수정) —
   현재 파트 세션은 **자기 비용을 기본 명령으로 못 잰다**.
3. **`phase-tools.py` 접미사 task 지원** — `TASK_FILE_RE`·`--set` 파싱·정렬 키 (PITFALLS 39).
   지금은 `tasks` JSON 이 1a~2b 를 누락하고 `complete` 가 거짓 완료를 낼 수 있다.
4. `part-protocol.md` 단일 소스화 — 내용이 아직 동일한 지금이 충돌 없는 시점.
5. 이월된 🟡 5건: `task1b.md`·`task2b.md` 의 "리뷰 2라운드" 절 참조.

## 전파 제약 누적
- (1b 완료) `tasks` JSON에 `docs_root` 추가, `path`는 그 기준 상대경로. 폴백 시 **stderr 통지 1줄**,
  `--set` stdout은 `task {n} → {status}: {절대경로}`. `--next` 는 여전히 숫자 한 줄(기계 판독 계약).
  미발견 오류 메시지에 **정확일치 단정 금지**(PITFALLS 29 계열). `find_docs_root()` 는 git 밖에서
  `SystemExit`(exit 1) — `tasks` 호출은 체크아웃 안에서. 상세는 `task1b.md`.
- (2b 완료) `session-cost.py` 구 위치 인자 유지 + `--project/--session/--json`.
  **`--project` 미지정 기준은 cwd가 아니라 메인 체크아웃**(`--git-common-dir` 의 부모, `resolve()`) —
  이후 문서는 "cwd 슬러그"가 아니라 "메인 체크아웃 슬러그"로 표기할 것.
  JSON: `{files, project_dir, usd, usd_complete, unknown_models, by_model}`. 표 출력은 동결,
  집계 디렉터리는 **stderr**. 세션 ID의 `/`·`..` 는 명시 오류(CWE-22). 상세는 `task2b.md`.
- (문서, **파트 16-2에서 반영 완료**) CLAUDE.md·PITFALLS 38의 "session-cost는 워크트리에서 실행하면 세션을 못 찾는다"
  문장을 갱신했다. 정확히는 **절반만 해소**다 — 메인 체크아웃 세션은 워크트리 cwd 에서도 집계되지만,
  **세션 자체가 워크트리에서 시작한 경우**(파트 세션이 그렇다)는 슬러그의 `.`→`-` 미치환 때문에 여전히 못 찾는다.
  우회: `--project /<repo>/-claude/worktrees/<디렉터리>` 유사 경로(2026-09-02 실측).
- (3 완료) 어댑터 템플릿에 `part-protocol.md`·`part-allowed-tools.txt` 추가 — stamp 가 새 프로젝트로 복사한다.
  허용 도구 템플릿의 `Bash(tee -a __EVENTS_JSONL__)` 는 **stamp 가 치환하지 않는** 플레이스홀더이므로
  프로젝트가 자기 `.orchestrate/events.jsonl` 절대경로로 채워야 한다(안 채우면 이벤트 로그만 누락되고 파트 진행은 계속된다).
  SKILL.md 의 "푸시는 절대 금지" 문구는 사라졌다 — 이후 문서는 "프로젝트 세션의 푸시는 금지, 병합은 감독 규칙"으로 표기할 것.

## 자동 결정 로그
- [2026-09-02 홈] push·PR·병합은 파트 세션이 아니라 홈 감독이 수행 (설계 D-5, 프로토콜 §금지).
- [2026-09-02 15:27 감독] task 3 허용 도구 템플릿: 제외 항목에 `Bash(rsync:*)` 추가, 저장소 절대경로
  `tee -a` 항목은 `Bash(tee -a __EVENTS_JSONL__)` 플레이스홀더로 대체(stamp는 `__PROJECT__`만 치환).
  대상 파일 1·2의 소스는 **파트 16-2 시작 시점의 워크트리 현재 내용**.
