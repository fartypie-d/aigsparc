---
phase: 15
date: 2026-09-01
kind: task
domain: scripts, tests, docs
status: done
commits: 7398461..0bc05dd
cost: $39.11 (세션 2개 실측 — 6fd086d0 $27.31 + d4ba6231 $11.80, 리뷰어 서브에이전트 별도)
compactions: 0
interventions: 1
summary: 위임 모델 정책의 프로젝트 스코프화(.claude/model-policy.json) + 크레딧·한도 실패 시그니처를 좁은 앵커로 확장 — 초안 REJECT 2건 해소
---

# 작업 지시서 — 모델 정책 프로젝트 스코프 + 한도 시그니처 (2026-09-01)

> 입력 문서: [PLAN_model-policy-scope.md](PLAN_model-policy-scope.md) (초안 `04429d6` REJECT 근거).
> 초안을 그대로 채택하지 않는다 — 아래 인터뷰 결정이 우선한다.

## 인터뷰 결과

- **스코프**: PLAN 6항목 전부. 단 항목 2는 "정책 위치를 `.orchestrate/` 밖으로" 분기로 충족되므로
  `phase-tools.py` 재니터는 **건드리지 않는다**. 항목 3은 좁은 앵커만 — 초안의
  `grep -aE 'ERROR|Error:'` 라인 필터 확대는 **불채택**.
- **정책 위치**: `<프로젝트>/.claude/model-policy.json` (git 추적 경로). 재니터 무관·저장소와 함께 이동.
- **우선순위**: Task 1(경로) → Task 2(시그니처) → Task 3(문서). 1·2는 같은 파일이라 순차.
- **제약**: `phase-tools.py` 수정 금지 / `tests/` 는 오케스트레이터 전속(함정 14) /
  호스트 전역 정책 폴백 동작은 하위 호환 유지 / main 직접 push 금지.
- **크기 등급**: **standard** (3 task, 4파일, 사용자 표면 계약 변경 1건, `kit-scripts` = ⚠️ 도메인 → heavy tier).

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| POLICY 가 호스트 전역 하드코딩 | `core/scripts/run-delegation.sh:68` | 유지 |
| `model_error_in_log()` 가 rc 무관 최종 판정에 쓰임 | `run-delegation.sh:249, 417` | 유지 |
| 인터림 감시와 최종 판정이 main 에선 같은 기준 | `:346, :402` vs `:249` 모두 `grep -a 'ERROR'` | **뒤집힘** — 비대칭은 초안이 만든 것 |
| 재니터가 `.orchestrate/` 하위를 7일 뒤 이동 | `phase-tools.py:424` (제외는 `archive`·`events.jsonl` 뿐) | 유지 (위치 변경으로 무력화) |
| `.claude/` 는 git 추적 대상 | `.gitignore` — `settings.local.json`·`worktrees` 만 제외 | 유지 |
| PLAN 의 "문서 3파일 6곳" | `grep -rn model-policy README.md docs/WORKFLOW*.md` = **9곳** | **뒤집힘** — Task 3 은 9곳 검토 |
| 그 3파일이 문서 표면의 전부 | 저장소 전역 재실측: `README.ko.md`·배포용 SKILL 사본·프로젝트 템플릿 로스터가 더 있음 | **뒤집힘 (사후)** — 파일 목록 자체가 과소 측정이었다. Task 4 로 정정 |
| 실제 402 로그 샘플을 아카이브에서 확보 가능 | `.orchestrate/**` 의 `402` 는 전부 `timestamp=...402Z`·messageID (정상 INFO) | **뒤집힘** — 양성 픽스처는 합성, **음성 픽스처는 실제 로그 라인** |
| 위임 로그에 `Error:` 오탐 재료가 실재 | `grep -ah 'Error:' .orchestrate/**/*.log \| grep -v level=ERROR` = **61건** | 유지 — 라인 필터 확대 불채택 근거 |

## task 목록

| # | 제목 | 에이전트 | 모델 | 상태 | 커밋 |
|---|---|---|---|---|---|
| 1 | 정책 경로 프로젝트 스코프화 + 출처 가시화 | `kit-scripts` | heavy | done | 94707e6, 7cc536e |
| 2 | 크레딧·한도 시그니처 좁은 앵커 + 판정 기준 단일화 | `kit-scripts` | heavy | done | b75ba10, 32a1022 |
| 3 | 문서 9곳 — 정책 원본 서술 갱신 | `kit-docs` | default | done | 5361302 |
| 4 | 남은 문서 표면 3개 동기화 (스코프 정정) | `kit-docs` | default | done | c182b9f, 8cc33cd |
| 5 | 전멸 안내가 실사용 정책을 가리키게 (구조 리뷰 지적) | `kit-scripts` | heavy | done | a041e8e, 0bc05dd |

상세: `PHASE15_model-policy-scope.tasks/task<N>.md`

## 리뷰 예상 지점 — RED 사전 고정

| 지점 | 예상 지적 | 고정 RED (담당) |
|---|---|---|
| `run-delegation.sh:248` FAIL_RE 앵커 | `402` 앵커가 `timestamp=...402Z` 를 매칭해 rc=0 성공 위임이 폐기됨 | `SignatureAnchorTest::test_error_line_with_402_timestamp_is_not_a_limit_error` (task 2) |
| `run-delegation.sh:75` 정책 부재 오류 | 로컬 오버라이드를 시도했다는 사실이 사용자에게 안 보임 | `::ModelPolicyScopeTest::test_missing_policy_reports_both_candidate_paths` (task 1) |
| `:249` vs `:346`·`:402` | 한쪽만 고쳐 인터림·최종 판정 기준이 발산 | `::SignatureAnchorTest::test_interim_watcher_also_detects_credit_signature` (task 2) |
| `run-delegation.sh:447` 전멸 안내 | 프로젝트 경로를 무조건 찍어 host 실행에도 남의 경로를 안내 | `::ModelPolicyScopeTest::test_exhaustion_notice_keeps_host_path_when_host_policy_ran` (task 5) |

## 전파 제약 누적

- **Task 1 →** 정책 경로는 `git rev-parse --show-toplevel` 기준이다. 하위 디렉터리 호출도
  프로젝트 정책을 찾지만, **서브모듈·중첩 저장소 안에서 호출하면 그 중첩 루트에 묶인다**.
  `HOME` 은 68행 `${HOME:?...}` 가드가 보장하므로 이후 코드에서 `${HOME:-}` 를 쓰지 말 것.
- **Task 2 →** `FAIL_RE` 는 **좁게** 유지한다. 라인 필터 `grep -a 'ERROR'` 는 리터럴 매칭이라
  오탐의 최후 방어선이 아니다 — 방어선은 `FAIL_RE` 자신의 좁음이다. 매처는
  `error_signature_in_lines` 하나뿐이니 새 매칭을 인라인으로 만들지 말 것.
- **Task 2 →** 동결 테스트의 픽스처는 '진짜 한도 에러처럼 보이는' 문자열이다. 이 클래스에
  단정을 추가할 때 `result.stdout` 을 실패 메시지에 그대로 싣지 말 것 (`_redacted` 사용,
  `longMessage = False` 유지) — 위임 자신의 로그가 오염된다.

## 이 페이즈에 적용되는 함정

- **함정 13·32** — 이 페이즈가 `run-delegation.sh` 자신을 고친다. 착수 전
  `.orchestrate/frozen/` 에 `run-delegation.sh` + `opencode-serve-ctl.sh` 를 **함께** 얼려
  그 사본으로 위임한다 (serve attach 유실 방지).
- **함정 14** — `tests/*.py` 는 오케스트레이터가 작성·동결한다. 위임 프롬프트에 수정 금지를 명시.
- **함정 16** — 워크트리 위임 프롬프트에는 상대 경로만. 검수는 `git status` 부터.
- **함정 27** — 동결 테스트 커밋과 위임 산출물 커밋을 분리한다.
- **함정 34** — 변이 검증 사본은 `rsync -a --exclude .orchestrate --exclude .git`.
- **함정 35** — 테스트 append 후 `unittest.main()` 가드를 파일 끝으로 옮기고 건수 확인.
- **함정 36** — 시그니처 픽스처는 **양성·음성 양쪽** 필수. 음성은 실제 아카이브 로그 라인 사용.

## 자동 결정 로그

- (오토 모드 아님 — 해당 없음)
