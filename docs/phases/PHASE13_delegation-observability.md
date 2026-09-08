---
phase: 13
date: 2026-08-19
kind: task
domain: scripts, docs
status: done
commits: 05d4ccf..74c3717 (21개 — feat 3 · fix 4 · test 4 · docs 10)
cost: $42.00 (scripts/session-cost.py 실측, 세션 2개 합산 — 지시서 작성 세션 + 재개 세션)
compactions: 0
interventions: 1 (세션 중단 후 사용자 재개 지시)
summary: 위임 계측(.wrapper 로그·reject_cause)·총 벽시계 캡·구조 리뷰어 신설
---

# 작업 지시서 — 위임 관측성·안정성 + 구조 리뷰어 (2026-08-19)

## 인터뷰 결과

- **스코프**: ① 래퍼 stdout을 `.wrapper` 로그로 영속화 ② 총 벽시계 캡 ③ `events.jsonl`
  `reject_cause` 필드 ④ 구조 리뷰어 신설. **락 입도(`--show-toplevel`)와 모델 tier 정책 개편은 제외.**
- **우선순위**: 계측(②의 계측기) → 안정성 → 문서·리뷰어
- **제약**:
  - `run-delegation.sh`를 고치는 페이즈다 → **PITFALLS 13**: 이 페이즈의 위임은 반드시
    **동결 사본**으로 실행한다 (아래 "페이즈 고유 제약").
  - 구조 리뷰어는 오케스트레이터 직접 작성 → **위임 산출물과 커밋 분리** (PITFALLS 27).
  - 회귀 테스트는 오케스트레이터가 작성·동결하고 위임의 `tests/` 수정을 금지 (PITFALLS 14).
- **크기 등급**: `standard` (5파일 / events 계약 확장 / kit-scripts ⚠️ 도메인 → 최소 standard)

### 착수 배경 (실측 근거)

| 관측 | 값 | 출처 |
|---|---|---|
| 위임 벽시계 최대 | **611분** (Phase 4 task 8a) — p90은 19.7분 | `.orchestrate/events.jsonl` n=55 |
| 폴백 발생 증거 | `.failed-*` 8건 — 로그엔 `MODEL_FALLBACK` 없음 (stdout 유실) | `find .orchestrate -name '*.failed-*'` |
| 리뷰 반려율 | terra 51%(20/39) vs luna 0%(0/8), Fisher p=0.014 — 원인 미기록 | `events.jsonl` review_verdict n=56 |
| 구조 지적 건수 | 리뷰 56회 중 **0건** (담당 리뷰어 없음) | 로스터 리뷰어 매핑 |

## 전제 실측 (2026-08-19)

| 전제 | 근거 | 판정 |
|---|---|---|
| exit 8이 비어 있다 | `run-delegation.sh` 사용 코드 = 0,2,3,4,5,6,7,64,66 | **유지** |
| `run-delegation-v3.sh` 이름이 PREFLIGHT의 관리 근거로 인정된다 | `core/scripts/run-delegation.sh:165` `/^run-delegation(-v[0-9]+)?[.]sh$/` | **유지** — 동결 사본 이름으로 사용 |
| `tests/test_run_delegation.py`에 stdout 정확일치 단정이 없다 | `assertEqual` 70건 전부 returncode·권한 대상, 신호는 `assertIn` 41건 | **유지** — PITFALLS 29 위험 낮음 |
| 로그 권한 600 단정 선례가 있다 | `tests/test_run_delegation.py:443` `st_mode & 0o777 == 0o600` | **유지** — `.wrapper`도 동일 단정 |
| 설치본 스킬 == 저장소 소스 | `diff ~/.claude/skills/orchestrate/SKILL.md adapters/claude/global/skills/orchestrate/SKILL.md` → 동일 | **유지** — 소스 수정 후 설치 재실행이 있어야 실제 반영 |
| 로스터에 `adapters/**/skills/**/*.md` 담당이 있다 | kit-docs 범위 = README·docs/·project-template·containers README | **뒤집힘** — 담당 없음. Task 4에서 로스터 확장 후 Task 5 위임 |
| ECC에 읽기전용 구조 **리뷰어**가 있다 | `architect`·`code-architect`는 읽기전용이나 **설계 생성용**, `code-simplifier`·`refactor-cleaner`는 Write/Edit 보유(PITFALLS 26 위험) | **뒤집힘** — 신설 근거 성립 |

## 페이즈 고유 제약 — 동결 사본 위임 (PITFALLS 13)

이 페이즈는 `core/scripts/run-delegation.sh`를 수정한다. 수정 중인 스크립트로 위임하면
자기 자신을 실행하다 깨진다. **첫 위임 전에 한 번** 안정본을 얼린다:

```bash
cp /home/jh/aigsprac/core/scripts/run-delegation.sh .orchestrate/run-delegation-v3.sh
```

이후 이 페이즈의 **모든 위임**은 `bash .orchestrate/run-delegation-v3.sh ...`로 실행한다
(정본 `scripts/run-delegation.sh` 호출 금지). 사본 이름은 PREFLIGHT의 관리 근거 패턴에
맞으므로 exit 3으로 차단되지 않는다(전제 실측 참조).

## Task 목록

| # | 제목 | 주체 | 모델 | 선행 | 상태 | 커밋 |
|---|---|---|---|---|---|---|
| 1 | 회귀 테스트 동결 (RED) | 오케스트레이터 | — | — | **done** | b17617a |
| 2 | 래퍼 stdout → `.wrapper` 로그 | kit-scripts | heavy | 1 | **done** | e109e13, 1daa493, da907a8 |
| 3 | 총 벽시계 캡 + exit 8 | kit-scripts | heavy | 1, 2 | **done** | 9c1d540, 3cf16ff |
| 3b | standalone 폴백 비밀번호 가드 완결 + 캡 기준 시각 | kit-scripts | heavy | 3 | **done** | a9ab42c |
| 4 | structure-reviewer 신설 + 로스터 | 오케스트레이터 | — | — | **done** | d9ef8c1 |
| 5 | events 계약 `reject_cause` + exit 8 문서화 | kit-docs | default | 4 | **done** | 2808b53 |

**상태 전이는 이번 페이즈에 한해 위 표와 task 파일 frontmatter를 직접 고쳐 갱신한다.**
`phase-tools.py tasks 13 --set`은 이 페이즈에서 쓸 수 없다 — `find_root()`가
`--git-common-dir`로 **메인 체크아웃**을 가리키므로(`core/scripts/phase-tools.py:54`),
지시서가 아직 피처 브랜치에만 있는 진행 중 페이즈는 조회되지 않는다
(실측 2026-08-19: 워크트리에서 `tasks 13` → `PHASE13_*.tasks 디렉터리 없음`, `tasks 10`은 정상).

### 파트 그룹핑

- **파트 13-1 (세션 1)**: Task 1~3 — 계측·캡 (위임 2건)
- **파트 13-2 (세션 2)**: Task 4~5 — 구조 리뷰어·문서 (위임 1건)

파트 경계 = 세션 경계 = HANDOFF 시점.

## 리뷰 예상 지점 (RED 사전 고정)

| 지점 | 예상 지적 | 고정 RED 테스트 (담당) |
|---|---|---|
| `.wrapper` 로그 권한 | 644로 생성 → `SESSION_ID`·서버 정보 유출 (🔴 security) | `test_wrapper_log_is_600` (Task 1) |
| tee 도입이 flock fd 9·`nohup` 자식·`wait`를 흔듦 | 위임이 조용히 안 돌거나 exit 코드 유실 (🔴) | `test_existing_signals_and_exit_unchanged` (Task 1) |
| 캡 도달 시 abort 실패를 삼킴 | 고아 세션 침묵 (🔴 silent failure) | `test_wallclock_cap_reports_orphan_on_abort_failure` (Task 1) |
| 캡이 모델 폴백 체인으로 오인됨 | 한도 문제가 아닌데 다음 모델로 재시도 → 캡이 N배로 늘어남 (🔴) | `test_wallclock_cap_does_not_fall_back` (Task 1) |

7단계 리뷰어 호출 시 이 표를 전달물에 포함한다.

## 검증 명령 (전 task 공통)

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh
bash -n core/scripts/run-delegation.sh
bash scripts/hook-selfcheck.sh          # HOOK_SELFCHECK_PASS 기대
```

> 이 워크트리는 서브모듈 미초기화라 컨테이너·대시보드 테스트 10건이 실패한다
> (**PITFALLS 24** — 회귀가 아님). 워크트리 안에서 `submodule update --init` 하지 말 것
> (PITFALLS 7: phase-close 크래시). 판정은 실패 목록이 `test_install_container_step` ·
> `test_install_dashboard_container` **그 10건과 정확히 일치**하는지로 한다.

## 결정 로그

| 시각 | 결정 | 사유 |
|---|---|---|
| 2026-08-19 | 스코프에서 락 입도 제외 | 회귀 테스트 동결 선행 + PITFALLS 9 재발 위험 → 별도 페이즈 |
| 2026-08-19 | 모델 tier 정책 개편 제외 | 정책 변경 근거(`reject_cause`)가 이 페이즈 산출물 — 데이터 수집이 선행 |
| 2026-08-19 | `--base main`으로 claim | 훅이 main 직접 push를 차단 → origin/main이 32커밋 낡음 (PITFALLS 25 회피) |
| 2026-08-19 | 캡 기본값 3600초 | 실측 p90 19.7분의 3배. `ORCHESTRATE_DELEGATION_MAX_SEC`로 조정 가능 |

## 미해결 / 후속

### 이 페이즈에서 처리 완료

- 신규 함정 3건을 `PITFALLS.md` 에 등재하고 CLAUDE.md 에 한 줄 인덱스를 달았다 —
  31(에이전트 레지스트리 스냅샷) · 32(동결 사본의 serve attach 상실) · 33(`phase-tools tasks` 워크트리).
- 리뷰가 만든 신설 task 3b(비밀번호 가드 완결 + 캡 시계를 락 획득 뒤로) 완료.
- Task 5 리뷰가 지적한 문서 공백(`WALLCLOCK_CAP_INVALID`/exit 64 미문서화)을 Task 5b 로 보완.

### 남은 것 — 사용자 조치 필요

- **로컬 main 미푸시** — 훅이 main 직접 push 를 차단하므로 사용자가 직접 실행해야 한다.
- **설치본 반영** — 이 페이즈가 고친 `adapters/claude/global/skills/orchestrate/SKILL.md` 는
  저장소 소스다. 실제 절차가 바뀌려면 `~/.claude/skills/orchestrate/SKILL.md` 에 재설치해야 한다.
  홈 디렉터리를 건드리므로 GATE 2 에서 별도 확인 대상.
- **Phase 12 마감 미완** — RED 커밋 `052e899` + 미커밋 구현, GREEN 확인됨. 리뷰·커밋·close 만 남았다.
- **Phase 10 워크트리 잔존** — 병합 후에도 남아 있어 phase-close 재실행 대상.

### 다음 페이즈 후보 (구조 리뷰어 우선순위 반영)

1. **`tests/test_run_delegation.py` 분할** (1,295줄 = max 의 1.62×). 배치 축이 "리뷰 라운드"로
   무너졌고 `tests/_install_helpers.py` 공유 선례가 있다. 행동 변경 0의 독립 페이즈로.
2. **`for MODEL` 본문 워치독 함수 추출** (131줄 = 함수 max 의 2.62×). 이 안에 캡 7줄을 넣는 데
   반려 3라운드가 들었다.
3. **프롤로그 초기화 순서 계약 문서화** + `LOCK_WAIT_MAX`(1800) 와 `DELEGATION_MAX_SEC`(3600) 이
   직렬 합산 최대 90분이라는 사실 명시.
4. `run-delegation.sh` 의 남은 🟠 — 다중 에피소드 기록 실패 시 `WRAPPER_LOG_WRITE_FAILURE_REPORTED`
   가 리셋되지 않아 두 번째 실패 에피소드가 무신호·무마커 (Task 2 리뷰 잔여, 새 동결 테스트 필요).
5. `test_serve_ctl.test_start_fails_without_password` — 단독 16/16 통과, 전체 스위트에서만 실패.
   테스트 간 상태 오염 의심 (Task 5 리뷰 관찰).
6. 락 입도(`--show-toplevel`), 모델 tier 정책 개편(`reject_cause` 표본 축적 후), `install.sh` 분할(1,810줄).
