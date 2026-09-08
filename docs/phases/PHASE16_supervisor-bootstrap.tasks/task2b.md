---
task: 2b
status: done
---

## Task 2b: `session-cost.py` — `--project`·`--session`·`--json` + 워크트리에서 메인 슬러그
- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/session-cost.py`
- **선행**: 2a
- **목표**: `python3 scripts/session-cost.py [--project <메인 체크아웃>] [--session <id> ...] [--json] [구 위치 인자 세션id]`.
  `--project` 미지정 시 `git rev-parse --git-common-dir`의 부모(메인 체크아웃)로 슬러그를 만들어 워크트리 cwd에서도 동작한다(KF-11).
  git 밖이면 cwd. 인자 없음이면 기존대로 오늘 파일. 세션 파일 없음은 명시 오류(exit≠0, stderr `세션 파일 없음: …`, stdout 비움).
  `--json` 출력: `{"files": n, "usd": <float>, "unknown_models": [...], "by_model": {model: usd}}` 한 줄.
- **재사용**: 그대로 재사용 `core/scripts/session-cost.py:collect`·`PRICES` (수정 금지). `argparse` 도입.
- **실패 테스트**: `tests/test_session_cost.py::SessionCost` 3건 (2a에서 동결 — **tests/ 수정 금지**)
- **필독 스킬**: `coding-discipline`
- **필수 규칙**: 구 호출 `python3 scripts/session-cost.py <session-id>` 하위 호환 유지(홈 세션·기존 지시서가 쓴다). 단가 미등록 모델은 여전히 `?`(추정 금지).
  표 출력 형식(비-JSON) 변경 금지 — 기존 페이즈 문서가 그 형식을 인용한다. `tests/`·`docs/` 수정 금지, `git commit` 금지.
- **완료 조건**:
  1. `python3 -m unittest tests.test_session_cost -v; echo "exit=$?"` → 3건 OK, exit=0.
  2. `python3 -m unittest discover -s tests -v` 전체 초록.
  3. 실환경 스모크(오케스트레이터): `python3 scripts/session-cost.py --json; echo "exit=$?"` → 워크트리 cwd에서 `세션 디렉터리 없음: …worktrees…` **미발생**, JSON 한 줄, exit=0.
  4. 변이 검증(오케스트레이터): `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut2b/` 사본에서(함정 34 — `cp` 금지) `main_checkout()`이 `start`를 그대로 돌려주도록 변이 → `test_worktree_cwd_resolves_main_checkout_slug` FAIL 확인.

참고 구현 (플랜 Task 2 Step 3 — 프롬프트에 인라인): `main_checkout(start: Path) -> Path`, `project_dir(project: Path | None) -> Path`,
`main()`은 argparse(`--project` type=Path, `--session` action=append, `--json` store_true, `legacy_session` nargs="?")로 파일 목록을 정한 뒤
기존 집계 루프를 돌리고, `--json`이면 dict를 `json.dumps(ensure_ascii=False)`로 한 줄 출력하고 return.

## 위임 로그 요약 · 반려 이력

### 1회차 위임 (kit-scripts / `openai/gpt-5.6-terra`, exit 0) — 승인
- 로그: `.orchestrate/task2b.log` (wrapper: `DONE`, `MODEL_USED=openai/gpt-5.6-terra`)
- 변경 파일: `core/scripts/session-cost.py` 단 1개 (+59/-14). `tests/`·심링크 `scripts/session-cost.py` 무수정.
- 위임 보고의 "전체 회귀 11건 실패" 주장은 재검증에서 재현되지 않음 —
  `test_serve_ctl.ServeCtlTest.test_start_fails_without_password` 는 오케스트레이터 재실행 시 통과(간헐).

### 검수(오케스트레이터) 실행 기록
| 항목 | 명령 | 결과 |
|---|---|---|
| 조건 1 | `python3 -m unittest tests.test_session_cost -v` | `Ran 3 tests` / **OK** (exit=0) |
| 조건 2 | `python3 -m unittest discover -s tests` | `Ran 416 tests` / `FAILED (failures=10)` — **선재 실패만** (`InstallDashboardContainerTest` 9건 + `test_actual_container_up_failure_marks_manual_step`, 서브모듈 미초기화 원인). 회귀 0 |
| 조건 3 스모크 | `python3 scripts/session-cost.py --json` (워크트리 cwd) | exit=0, 한 줄 JSON `{"files": 3, "usd": 62.476472, "unknown_models": [], "by_model": {"claude-opus-5": 62.476472}}` — `…worktrees…` 경로 오류 **미발생**(메인 체크아웃 슬러그로 해석됨) |
| 조건 4 변이 | `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut2b/` 후 `main_checkout` 본문을 `return start` 로 치환 → `python3 -m unittest discover -s .orchestrate/mut2b/tests -p test_session_cost.py -v` | `FAILED (failures=1)` — `test_worktree_cwd_resolves_main_checkout_slug` 만 FAIL (`세션 디렉터리 없음: …-proj-.claude-worktrees-phase9-x`). 나머지 2건 통과 → 테스트가 실제로 해당 동작을 잡는다 |

### 계약 준수 확인
- `PRICES`·`collect()` diff 상 무변경(재사용 필드 준수).
- 표 출력(비-JSON) 문자열 3개(`헤더 f-string`, 행 f-string, `합계: ${grand:.2f}` + `(파일 N개)`)가 HEAD 버전과 **문자 단위 동일** — `if not args.json:` 블록으로 감싸기만 함. 실측 출력 `합계: $62.48  (파일 3개)`.
- 단가 미등록 모델의 `"       ?"`(공백 7 + `?`) 유지.
- 오류 경로는 `sys.exit(메시지)`(stderr) 이며 `--json` 시 헤더도 찍지 않으므로 stdout 비움.
- 모듈 최상위 git 실행 없음 — `main_checkout()` 안에서만 `subprocess.run`.
- 구 위치 인자와 `--session` 동시 지정 시 두 세션을 합산(위치 인자를 목록에 append) — 합리적.

### 잔여 관찰 (비차단)
- `main_checkout()` 은 `git` 실행 파일이 아예 없으면 `FileNotFoundError` 로 죽는다(현 저장소 전제상 미발생).
- `main_checkout`/`project_dir` 이 경로를 `resolve()` 하므로 심링크 경유 cwd 의 슬러그가 구 버전과 달라질 수 있다(메인 체크아웃 `/home/jh/aigsprac` 는 실경로라 영향 없음).
- 스크래치 `.orchestrate/mut2b/`, `.orchestrate/cmp_table.py` 는 gitignore 대상이라 커밋에 영향 없음 — 삭제는 메인이 처리(권한 가드로 `rm` 미시도).

### 리뷰 1라운드 (2026-09-02) — **반려**
- `python-reviewer` **SIGN OFF** (🟡 7건: `args.sessions` 제자리 변경, 위치인자+`--session` 합산 미문서화,
  `unknown` dead store, JSON 부동소수점 미반올림, `subprocess` timeout 부재, git 바이너리 부재 시 크래시,
  `find_root()` 와의 로직 중복).
- `silent-failure-hunter` **BLOCK**: 🔴 출력 어디에도 **어느 디렉터리를 집계했는지 없음**(provenance 부재 —
  틀린 숫자가 페이즈 보고서에 조용히 박제된다) · 🟠 파일은 있으나 usage 레코드 0건이면 `$0.00` 을 exit 0 으로 보고 ·
  🟠 `--json` 의 `usd` 가 단가 미등록 모델을 조용히 제외(완전성 신호 없음) · 🟠 git 실패 흡수/부재 크래시 비대칭.
- `security-reviewer` **BLOCK**: 🟠 **CWE-22** — `pdir / f"{session}.jsonl"` 은 `session` 이 절대경로면 `pdir` 를
  통째로 버린다(pathlib 동작). `..` 상대 탈출도 성립. 🟠 `find_root()` 중복(기술부채).

**판정**: 🔴 1건 + 보안 🟠 → 반려.

### 반려 수정 (1회차)
1. 오케스트레이터가 동결 RED 6건 추가 — 커밋 `c9bd716`, 수정 전 `Ran 9 tests / FAILED (failures=4, errors=2)` 실측.
   경로 탈출은 **실증**됐다: `--session <저장소 밖 절대경로>` → `합계: $45.00  (파일 1개)` 로 밖의 파일이 집계됨.
2. 재위임 `kit-scripts` / **heavy** (`MODEL_USED=openai/gpt-5.6-terra`, exit 0) → 커밋 `b630cf5`:
   JSON 에 `project_dir`·`usd_complete` 추가 · 표 모드는 **stderr** 로 집계 대상 통지(stdout 형식 불변) ·
   `collect()` 결과가 비면 출력 전에 명시 오류 · `--session` 의 `/`·`..` 거부(조용한 basename 깎기 아님) ·
   `FileNotFoundError` 를 cwd 폴백으로 흡수 + `timeout=60`.
3. 검증(오케스트레이터 직접 실행): `python3 -m unittest tests.test_session_cost` → `Ran 9 tests` / **OK**.
   `discover -s tests` → `Ran 422 tests` / `FAILED (failures=10)` — 선재 실패 10건뿐(회귀 0).
   실환경 스모크: `python3 scripts/session-cost.py --json` (워크트리 cwd) → exit 0,
   `{"files": 3, "project_dir": "/home/jh/.claude/projects/-home-jh-aigsprac", "usd": 62.476472, "usd_complete": true, …}`
   — **워크트리에서 메인 체크아웃 슬러그가 해석됨(KF-11 실증)**.

### 리뷰 2라운드 (재검수) — **통과**
- `silent-failure-hunter` **SIGN OFF** · `security-reviewer` **SIGN OFF**
  (우회 벡터 백슬래시·NUL·개행·`.`·빈 문자열·`~`·`--project` `..`/심링크 전수 검토 후 탈출 없음 확인).
- **다음 페이즈로 이월** (🟡, 두 리뷰어 모두 비차단 판정):
  (a) usage 레코드가 전부 0-토큰이면 여전히 `합계: $0.00` exit 0 (잔여 침묵 경로),
  (b) `subprocess.TimeoutExpired` 미포착 — `timeout=60` 도입으로 새로 활성화된 예외,
  (c) `git` `returncode != 0` 시 `result.stderr` 무시(정상적 "git 밖"과 권한·손상 오류를 구분 못 함),
  (d) 토큰 0인 미등록 모델이 `unknown_models` 에서 빠짐(감사 가시성),
  (e) `main_checkout()` 과 `phase-tools.py:find_root()` 의 로직 중복 — 세 번째 소비자가 생기면 공용 헬퍼로 추출,
  (f) `args.sessions` 제자리 변경 · 위치 인자와 `--session` 동시 지정 시 합산이 미문서화.
