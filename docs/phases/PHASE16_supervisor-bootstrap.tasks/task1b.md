---
task: 1b
status: done
---

## Task 1b: `find_docs_root` 신설 + `cmd_tasks`의 레지스트리 루트/문서 루트 분리
- **에이전트**: kit-scripts
- **모델**: heavy
- **대상 파일**: `core/scripts/phase-tools.py` (심링크 `scripts/phase-tools.py`를 고치지 말 것)
- **선행**: 1a (동결 테스트 커밋됨)
- **목표**: `tasks` 서브커맨드가 호출 cwd가 속한 체크아웃(워크트리)의 `docs_dir`에서 `PHASE<N>_*.tasks`를 먼저 찾고,
  없으면 메인 루트로 폴백한다. 레지스트리 접근은 그대로 `find_root()`(메인). JSON에 `docs_root` 필드 추가, `path`는 docs_root 기준.
  git 밖·해석 실패는 조용한 폴백 없이 명시 오류(exit≠0, stderr 메시지).
- **재사용**: 개선 후 재사용 `core/scripts/phase-tools.py:find_tasks_dir` (호출부 1곳 `cmd_tasks`) · 그대로 재사용 `sh()`(`check=False` 지원) · `find_root()`는 수정 금지(claim/close/janitor가 의존).
- **실패 테스트**: `tests/test_phase_tools.py::WorktreeTasksTest` 5건 (1a에서 동결 — **tests/ 수정 금지**)
- **필독 스킬**: `coding-discipline`
- **필수 규칙**: `find_root()` 시그니처·의미 불변. `cmd_tasks` 외 서브커맨드 동작 불변. 새 헬퍼는 `find_docs_root(main_root: Path) -> Path` 하나만.
  한글 docstring에 "레지스트리는 메인, 문서는 cwd 체크아웃 우선(KF-13)" 근거를 적는다. `tests/`·`docs/` 수정 금지, `git commit` 금지.
- **완료 조건**:
  1. `python3 -m unittest tests.test_phase_tools -v; echo "exit=$?"` → 기존 전부 + `WorktreeTasksTest` 5건 OK, exit=0.
  2. `python3 -m unittest discover -s tests -v` 전체 초록 (다른 테스트 파일 회귀 없음).
  3. **변이 검증(오케스트레이터가 수행)**: `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut1b/` 로 사본을 뜬 뒤(함정 34 — `cp` 금지, `.orchestrate` 제외 필수) `find_docs_root`가 항상 `main_root`를 돌려주도록 변이 →
     `WorktreeTasksTest` 1·2·3번이 FAIL(RED 복귀)해야 한다. 결과를 이 파일 아래 "위임 로그 요약"에 기록.

참고 구현 (플랜 `~/docs/2026-09-02-phase-supervisor-plan.md` Task 1 Step 3 — 프롬프트에 인라인):

```python
def find_docs_root(main_root: Path) -> Path:
    """호출 cwd가 속한 체크아웃(워크트리면 그 워크트리)의 루트.

    레지스트리는 항상 메인 루트(find_root)를 쓰지만, 페이즈 문서는 병합 전까지
    워크트리 브랜치에만 있으므로 문서 접근은 cwd 쪽 루트를 우선한다 (KF-13).
    git 밖이면 메인 루트로 폴백하지 않고 명시 오류를 낸다.
    """
    r = sh(["git", "rev-parse", "--show-toplevel"], check=False)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(f"git 최상위를 해석할 수 없다 (cwd={Path.cwd()}): {r.stderr.strip()}")
    top = Path(r.stdout.strip()).resolve()
    if not (top / ".git").exists():
        raise SystemExit(f"해석된 최상위에 .git 이 없다: {top}")
    return top
```

`cmd_tasks` 앞부분:

```python
    root = find_root()
    with Registry(root) as reg:
        if reg.data is None:
            print("레지스트리 없음 — 먼저 init", file=sys.stderr)
            return 2
        docs_dir = reg.data["docs_dir"]
    docs_root = find_docs_root(root)
    tasks_dir = find_tasks_dir(docs_root, docs_dir, args.phase)
    if tasks_dir is None and docs_root != root:
        tasks_dir = find_tasks_dir(root, docs_dir, args.phase)  # 병합 후 메인에서만 존재하는 경우
        docs_root = root
    if tasks_dir is None:
        print(f"PHASE{args.phase}_*.tasks 디렉터리 없음 ({docs_dir}; 탐색: {find_docs_root(root)}, {root})",
              file=sys.stderr)
        return 2
```

이후 `"path": str(f.relative_to(root))` → `relative_to(docs_root)`, 출력 dict에 `"docs_root": str(docs_root)` 추가.

## 위임 로그 요약 · 반려 이력

### 1회차 (kit-scripts/heavy) — 산출물 채택, 보고 없음
위임 프로세스가 완료 보고 전에 죽어 `.orchestrate/task1b.log` 에 구현자 주장이 없다.
`core/scripts/phase-tools.py` 수정만 워킹트리에 미커밋 상태로 남아 있었고, 검수는 전부
코드 대조 + 테스트 실행으로 수행했다 (구현자 주장 무근거 채택 없음).

### 검수 (파트 세션, 2026-09-02)
- 범위: `git status --short` → `M core/scripts/phase-tools.py` 단 1건.
  `tests/`·`scripts/phase-tools.py`(심링크)·`find_root()` 모두 무수정 확인.
- 완료 조건 1: `python3 -m unittest tests.test_phase_tools` → `Ran 38 tests` / `OK` / exit=0.
  `WorktreeTasksTest` 5건 전부 ok (`-v` 출력에서 개별 확인).
- 완료 조건 2: `python3 -m unittest discover -s tests` → `Ran 412 tests` / `FAILED (failures=12)` / exit=1.
  12건은 **전부 이 task 와 무관한 선재 실패**로 확인:
  - 10건 (`InstallDashboardContainerTest` 9 + `test_actual_container_up_failure_marks_manual_step`)
    — 서브모듈 미초기화(`git submodule status` 가 `components/usage-dashboard`,
    `containers/browser` 모두 `-`)로 compose 파일 부재. PITFALLS 24 의 알려진 환경 조건.
    **베이스라인 대조**: 사본 `.orchestrate/base1b` 에서 `cmd_tasks` 변경분만 HEAD 동작으로 되돌려
    실행 → `InstallDashboardContainer` 16건 중 동일하게 9건 FAIL, 컨테이너 스텝 1건도 FAIL.
    즉 이 커밋이 유발한 회귀가 아니다.
  - 2건 (`test_session_cost.SessionCost` 의 `test_session_option_sums_only_that_file`,
    `test_worktree_cwd_resolves_main_checkout_slug`) — task 2a 의 동결 RED (커밋 f11e996), 의도된 적색.
- 완료 조건 3 변이 검증: `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut1b/`
  (함정 34 준수) 후 사본의 `find_docs_root` 본문을 `return main_root` 로 치환 →
  `python3 -m unittest tests.test_phase_tools` → `Ran 38 tests` / `FAILED (failures=3)`,
  실패 3건이 지정된 그것과 정확히 일치:
  `test_tasks_next_from_worktree_cwd_finds_worktree_tasks`,
  `test_tasks_json_from_worktree_reports_docs_root_and_relative_path`,
  `test_tasks_set_from_worktree_writes_worktree_file` (모두 exit 2 = 문서 미발견). RED 복귀 확인.
- 부가 검증: `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` → exit=0,
  `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`.
- 잔재: `.orchestrate/mut1b`, `.orchestrate/base1b` 사본이 세션 권한 가드(rm 차단)로 삭제되지
  않았다. gitignore 대상이라 트리는 깨끗하지만 **메인이 수동 삭제**해야 한다.

### 리뷰 1라운드 (2026-09-02) — **반려**
- `python-reviewer` **BLOCK**: 🟠 폴백 후 `docs_root = root` 재대입으로 오류 메시지가 `탐색: X, X` 가 되어
  실제로 뒤진 워크트리 루트를 잃음 · 🟠 `find_docs_root` 의 `SystemExit`(exit 1)이 파일 관습 `return 2` 와 불일치 +
  신규 SystemExit 분기 2곳 미검증 · 🟡 `main_root` 인자 미사용 · 🟡 `find_root()`/`find_docs_root()` `.resolve()` 비대칭.
- `security-reviewer` **SIGN OFF**: 쓰기 위치 이탈·명령 주입·비밀 없음. 🟡 1건(심링크 tasks 디렉터리, 이 diff 이전부터 존재).
- `silent-failure-hunter` **BLOCK**: 🔴 `--next` 폴백이 무신호(무인 드라이버가 워크트리 문서로 오인) ·
  🔴 `--set` 이 폴백 시 경고 없이 메인 체크아웃 파일을 수정하고 성공 메시지에 경로 없음 ·
  🟠 "silent fallback 금지" 원칙이 JSON 조회 경로에만 적용됨.

**판정**: 🔴 2건 → 반려. 단, 🔴 는 구현이 지시서를 어긴 것이 아니라 **지시서가 폴백 신호를 규정하지 않은** 데서 왔다
(폴백 자체는 `test_tasks_from_worktree_falls_back_to_main_when_absent` 로 정상 동작으로 동결돼 있다).
따라서 폴백을 없애지 않고 **신호를 추가**하는 방향으로 수정했다.

### 반려 수정 (1회차)
1. 오케스트레이터가 동결 RED 3건 추가 — 커밋 `c247f8e`, 수정 전 `Ran 41 tests / FAILED (failures=3)` 실측:
   `test_fallback_to_main_is_announced_on_stderr` · `test_set_reports_written_file_path` ·
   `test_missing_tasks_message_names_the_worktree_root_it_searched`.
2. 재위임 `kit-scripts` / **heavy** (`MODEL_USED=openai/gpt-5.6-terra`, exit 0) → 커밋 `b63dc1c`:
   `searched_docs_root` 로 탐색 루트 보존 · 폴백 시 stderr 통지 1줄(stdout 기계 판독 계약 불변) ·
   `--set` stdout 에 실제 쓴 파일 절대경로.
3. 검증: `python3 -m unittest tests.test_phase_tools` → `Ran 41 tests` / **OK**.
   `discover -s tests` → `Ran 415 tests` / `FAILED (failures=12)` — 실패 건수가 1라운드와 **동일(12)**,
   phase_tools 관련 실패 0건. 회귀 없음.

### 리뷰 2라운드 (재검수) — **통과**
- `python-reviewer` **SIGN OFF** · `silent-failure-hunter` **SIGN OFF**.
- 남은 지적: 🟡 폴백+`--set` 조합 전용 테스트 부재 → 오케스트레이터가 `test_set_on_fallback_announces_and_reports_main_path`
  를 추가해 해소 (`Ran 42 tests / OK`).
- **다음 페이즈로 이월** (두 리뷰어가 이월 타당 판정): 🟠 `find_docs_root` 의 `SystemExit` → `return 2` 관습 통일 +
  git 밖 cwd 케이스 테스트 · 🟡 `main_root` 미사용 인자 · 🟡 `GIT_DIR` 오염 시 오귀속 · 🟡 깨진 심링크가
  "문서 없음"으로 뭉개짐 · 🟡 심링크 tasks 디렉터리 경유 쓰기. 앞의 셋은 지시서가 시그니처·오류 방식을
  고정했기 때문에 이번 범위 밖이다.
