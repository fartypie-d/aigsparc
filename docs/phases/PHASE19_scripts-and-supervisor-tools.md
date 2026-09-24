---
phase: 19
date: 2026-09-23
kind: task
domain: scripts, supervisor, install, tests, docs
status: done
commits: 387f7fa..eece5df (+ 마감 커밋)
cost: 미측정 — 홈 세션이 Claude 서브에이전트로 수행(구현 ≈270K·후속 ≈60K·리뷰 ≈145K 토큰, session-cost.py 경로 밖)
compactions: 0 (서브에이전트 보고 기준)
interventions: 1 (리뷰 SIGN OFF + MEDIUM 2건 후속 커밋 → 재검수)
summary: phase-tools 루트 해석 앵커·git 위치 env 정화 + docs-index 전순서 정렬 이식(묶음 1) · 감독 도구 instruction-check·scaffold-drift 를 키트 자산으로(묶음 2)
---

# Phase 19 — 스크립트 수선 이식 + 감독 도구 키트화 (2026-09-23)

## 근거

- **phase-tools 루트 앵커 결함**: 키트 `core/scripts/phase-tools.py`(Phase 17 판, 952줄)는 `find_root()` 가 cwd 만
  보고 루트를 정한다. cwd 가 형제 저장소로 표류하면 `close` 의 `worktree remove`·`branch -d` 와 `tasks --set` 이
  형제를 고친다. 프로젝트 저장소들이 2026-09-19 에 각자 수선했고(「루트 해석을 스크립트 위치로 앵커 + git 위치
  env 정화」, 이어서 「retry_guard_snapshot env 정화 + 앵커 계보 대조」), 09-20 에 마지막 저장소로 그대로
  이식돼 수선 판 둘이 바이트 동일(1050줄)이었다. 키트 원본은 그 사이 결함 판 그대로였다.
- **docs-index 정렬 비결정성**: (phase, date) 동률 행이 `rglob` 의 파일시스템 순서를 타 호스트와 CI 러너의
  INDEX.md 가 달라진다(프로젝트 저장소 2026-09-04 실측 · `sort_rows` 로 수선).
- **감독 도구 둘이 호스트 손 설치본**: `~/.claude/supervisor/tools/{instruction-check,scaffold-drift}.py`
  (2026-09-19~20)는 키트에 원본이 없다. `scaffold-drift.py` 는 호스트 저장소 이름 넷을 상수로 박고 있었다.

## 범위

### 묶음 1 — phase-tools 앵커·env 정화 + docs-index sort_rows

| 항목 | 출처 | 키트 반영 |
|---|---|---|
| `sh(..., env=None)` 파라미터 | 프로젝트 저장소 2026-09-19 앵커 커밋 | `core/scripts/phase-tools.py` |
| `_clean_git_env()` — `GIT_DIR`·`GIT_COMMON_DIR`·`GIT_WORK_TREE` 만 제거, `GIT_CONFIG_*` 보존 | 같은 커밋 | 동일 (주석의 저장소 전용 테스트 파일명은 일반 서술로) |
| `git()` 래퍼가 정화 env 로 실행 | 같은 커밋 | 동일 |
| `find_root()` — `Path(__file__).resolve()` 앵커 + 「cwd 저장소 == 스크립트 저장소」 단언, 불일치·git 밖은 `SystemExit` | 같은 커밋 | 동일 |
| `find_docs_root()` — `--show-toplevel` 은 미정화로(오염이 불일치로 드러나게) + 공통 디렉터리 계보 단언 | 같은 커밋 | 동일 |
| `retry_guard_snapshot(anchor_root=None)` — 위치 env 3종 있으면 명시 거부 · 계보 대조 · git 호출 4곳 `env=_clean_git_env()` (래퍼로 안 바꿈: 바이트 해시 정의 보존) | 프로젝트 저장소 2026-09-19 retry-guard 커밋 | 동일 |
| `cmd_retry_guard` 진입 시 위치 env 3종 pop + `retry_guard_snapshot(root)` | 같은 커밋 | 동일 |
| `docs-index.py sort_rows()` — phase·date 내림차순, 동률은 doc 오름차순(안정 정렬 2단) | 프로젝트 저장소 2026-09-04 「docs-index 정렬을 전순서로」 | `core/scripts/docs-index.py` |

키트 판(952줄)과 수선 판(1050줄)의 diff 는 **위 항목이 전부**다 — 그 밖의 일반 차이는 없다(diff 전수 확인).

**넣지 않은 것**: backend 전용(`check_ci_green`·`resolve_git_path`·claim 시 `npm ci`) · console 전용(모바일 감사·
events 판독·`orphan_registry_locks` 등 14함수) — 수선 판(infra=bot)에 애초에 들어 있지 않아 이식 대상 diff 에
등장하지 않았다.

**기존 테스트 하네스 조정**: `tests/test_phase_tools.py` 는 킷 원본을 임시 저장소 cwd 로 직접 불렀다. 앵커가
들어가면 그 호출은 정의상 거부된다(스크립트 저장소=키트, cwd 저장소=임시). 픽스처 저장소마다 `scripts/` 에
`phase-tools.py`·`supervisor-state.sh` 를 찍고(`stamp_tools`) 그 사본을 부르게 바꿨다 — 프로젝트에 찍히는 실제
배치와 같다. 심링크 진입점 테스트는 그 사본으로 링크한다(`__file__` 해석이 링크를 따라 동반 스크립트를 찾는
계약은 그대로 잰다).

### 묶음 2 — 감독 도구 둘을 키트 자산으로

- `core/supervisor/tools/instruction-check.py` — 원본 그대로(docstring 의 프로젝트 사건 표기만 일반화). `COMMAND_HEADS`·
  `ALLOW_FILE`(`.claude/part-allowed-tools.txt`) 은 일반 값.
- `core/supervisor/tools/scaffold-drift.py` — `DEFAULT_REPOS` 상수 제거. 기본 대상 = 레지스트리 스캔
  (phase-tools `state_dir()` 과 같은 규칙 — `ORCH_STATE_DIR`, 없으면 `~/.local/state/orchestrate` — 아래 `registry/*.json` 의 `root`, git 저장소인 것만 · PR #21 리뷰 반영).
  레지스트리 없음·2개 미만은 명확한 메시지로 exit 2. `--repos` 는 그대로(이름은 `--home` 아래, 절대 경로도 됨).
  표시 이름은 `Path(root).name`(호스트 접두 제거 코드 제거). 공유 파일 임계는 `min(3, 저장소 수)` — 둘만 주면 표가 비던
  호스트 판의 사각을 없앴다.
- 설치 배선: `core/install-manifest.tsv` 에 `claude tree core/supervisor/tools .claude/supervisor/tools` 행. 매니페스트는
  `kit-doctor.sh`(`install.sh --doctor --add-missing`)가 소비한다 — `install.sh` 본문은 손대지 않았다(PROCEDURE.md 행과 같은 경로).
- `core/supervisor/PROCEDURE.md` §5 앞머리에 「spawn 전 — 지시서를 저장소 실물과 대조한다」 6줄(조언용 · 발견 없음≠옳음 · exit 규약).

## 비범위

- 백엔드·콘솔 전용 함수(위 「넣지 않은 것」) · `stale_prs` 의 `gh` 호출 정화(원 저장소도 후속으로 미뤘다 — `DEFERRED_UNSANITIZED`).
- `docs/phases/INDEX.md`·`QUEUE.md` 갱신(지시). INDEX 는 이미 기준선에서 재생성본과 다르다 — 다음 마감 때 `docs-index` 로.
- 호스트 `~/.claude/supervisor/tools` 손 설치본 교체·키트 `install.sh` 재실행(호스트 반영은 별도 결정).

## DoD

- [x] 회귀 테스트 2파일(48건)을 키트 판에서 먼저 돌려 RED 확인(16 FAIL + 2 ERROR = 18) → 이식 뒤 48/48 GREEN.
- [x] 「rc=1 은 통과가 아니다」 축 케이스 신설(`test_b5_cli_sibling_cwd_is_an_error_and_not_a_pass`) — 옛 판에서 rc=0(fail-open) RED, 새 판 rc=1 GREEN.
- [x] `sort_rows` 케이스 4건(동률 doc 오름차순 · 입력 역순 불변 · 비정수 phase 후순 · 입력 불변 · 생성 INDEX 순서).
- [x] 감독 도구 원본 테스트 12건 그대로 통과 + 레지스트리 스캔 케이스 6건.
- [x] 매니페스트 행 + `kit-doctor --add-missing` 설치 단언(바이트 동일 · 재점검 시 DRIFT/FAIL 없음).
- [x] 변경 파일 전용 값 grep(호스트 프로젝트 이름 · 호스트 홈 절대 경로) 0줄 — 이 문서 자신도 포함.

## 검증 (워크트리 루트, 2026-09-23)

| 검증 | 명령 | 결과 |
|---|---|---|
| 기준선 | `python3 -m unittest discover -s tests` (착수 전) | `Ran 468` / `FAILED (failures=10)` — 선재 실패 10건 = `test_install_dashboard_container` 9 + `test_install_container_step` 1(서브모듈 미초기화, PITFALLS 24 · Phase 17 과 동일) |
| RED | `python3 -m unittest discover -s tests -p 'test_phase_tools_r*.py'` (이식 전) | `Ran 48` / `FAILED (failures=16, errors=2)` |
| GREEN | 같은 명령 (이식 후) | `Ran 48` / `OK`; 새 케이스 포함 `Ran 49` |
| 전체 | `python3 -m unittest discover -s tests` | `Ran 540 tests` / `FAILED (failures=10)` — 468 → 540 (+72), 실패 10건은 기준선과 **같은 집합**(선재) ⇒ 회귀 0 |
| 전체 (PR #21 리뷰 반영 후) | 같은 명령 | `Ran 543 tests` / `OK` — 리뷰어의 서브모듈 초기화로 선재 실패 10건이 0 이 됐고, 리뷰 MEDIUM 2건 케이스 +3 |
| bash 문법 | `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` | exit 0 |
| 훅 자가진단 | `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |
| scaffold-drift 실행 | `python3 core/supervisor/tools/scaffold-drift.py --repos <저장소 둘>` · 인자 없이(레지스트리 9곳) | exit 0 · 표 출력 |
| instruction-check 실행 | `python3 core/supervisor/tools/instruction-check.py docs/phases/PHASE17_supervisor-hardening.tasks/task2b.md --repo .` | exit 0 · 명령 5 · 경로 3 · 발견 없음 |
| 전용 값 | 변경 파일 14개에 호스트 프로젝트 이름·홈 절대 경로 grep | 0줄 |

## 변경 목록

- `core/scripts/phase-tools.py` — 앵커·env 정화(위 표 7항목).
- `core/scripts/docs-index.py` — `sort_rows`.
- `core/supervisor/tools/instruction-check.py`, `core/supervisor/tools/scaffold-drift.py` — 신설.
- `core/install-manifest.tsv` — 트리 행 1.
- `core/supervisor/PROCEDURE.md` — §5 앞머리 6줄.
- `tests/test_phase_tools_root_resolution.py`(21) · `tests/test_phase_tools_retry_guard_env.py`(27+1) — 이식.
- `tests/test_phase_tools.py` — 픽스처에 스크립트 사본 찍기(`stamp_tools`·`tool_for`).
- `tests/test_docs_index.py`(+4) · `tests/test_instruction_check.py`(8) · `tests/test_scaffold_drift.py`(4+6) · `tests/test_kit_doctor.py`(+1).
- `docs/phases/PHASE19_scripts-and-supervisor-tools.md` — 이 문서.
