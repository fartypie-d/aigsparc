---
phase: 14
date: 2026-09-01
kind: task
domain: scripts, docs
status: done
commits: 587c46f..66abab4 (7개 — feat 1 · fix 1 · test 2 · docs 3)
cost: $13.71
compactions: 0
interventions: 0
summary: tobuilder-bot 실적용 피드백(KF-1·KF-2) 반영 — docs-index가 DESIGN_·PLAN_ 문서를 인덱싱·kind 추론하고 규약 주석을 실태에 맞춘다
---

# 작업 지시서 — 키트 피드백 KF-1·KF-2 반영 (2026-09-01)

> 출처: tobuilder-bot `docs/phases/REVIEW_kit-feedback-20260901.md` (하류 실적용 피드백).
> 워크트리: `.claude/worktrees/phase14-kf-docs-index` / 브랜치 `feature/phase14-kf-docs-index`

## 인터뷰 결과

- 스코프: KF-1(INCLUDE_PATTERNS에 `DESIGN_*`·`PLAN_*` 추가) + KF-2(규약 주석 갱신) +
  kind 파일명 추론(DESIGN→design, PLAN→plan) + 킷 자신의 `PLAN_docs-lowercase-migration.md`
  frontmatter 정비·INDEX 재생성 + 반영 후 하류 리뷰 문서에 "상류 반영됨" 추기
- 우선순위: Task 1(소스, 위임) → Task 2(문서, 오케스트레이터 직접)
- 제약: 셀프체크는 kit-doctor가 아니라 **동결 회귀 테스트**로 (kit-doctor는 설치 상태 검사기 —
  저장소 내부 불변식과 도메인이 다름). 파서 동작 계약(best-effort frontmatter)은 불변.
- 크기 등급: **small** (소스 1파일, 계약 변경 없음)

## 전제 실측

| 전제 | 근거 | 판정 |
|---|---|---|
| INCLUDE_PATTERNS에 DESIGN·PLAN 없음 | core/scripts/docs-index.py:46-53 | 유지 |
| 규약 주석 kind 3종·status 3종만 | core/scripts/docs-index.py:15,17 (규약 언급처 유일) | 유지 |
| 킷 자신도 재현 | PLAN_docs-lowercase-migration.md가 INDEX.md에 없음 (grep rc=1) | 유지 |
| DESIGN_ 명명이 킷 규약 | 스킬·템플릿 grep 결과 없음 — 부트스트랩 세션의 자연 명명 | 뒤집힘 (수용은 타당 — 자연 명명은 재발) |
| kit-doctor에 셀프체크 | kit-doctor.sh = 홈 설치본 vs 킷 원본 검사기 | 뒤집힘 → 동결 테스트로 대체 |

## Task 1: docs-index.py — DESIGN·PLAN 패턴 + kind 추론 + 규약 주석

- **에이전트**: `kit-scripts`
- **모델**: (생략 = default)
- **대상 파일**: `core/scripts/docs-index.py` (이 1개만)
- **선행**: 없음 (동결 테스트는 오케스트레이터가 선커밋)
- **목표**: `DESIGN*.md`·`PLAN*.md`(대소문자 무관 아님 — 대문자 접두사)가 인덱스 스캔에 포함되고,
  frontmatter 없는 경우 파일명에서 kind가 `design`/`plan`으로 추론된다. 규약 주석이 실태와 일치한다.
- **재사용**: 개선 후 재사용 `core/scripts/docs-index.py:INCLUDE_PATTERNS`(참조 1곳
  `is_included_document`)·`extract()` kind 추론 블록(113-122행). 새 함수·새 파일 금지.
- **실패 테스트** (오케스트레이터 작성·동결 — `tests/test_docs_index.py` **수정 금지**):
  - `test_design_doc_indexed_with_inferred_kind` — frontmatter 없는 `DESIGN_repo-bootstrap-20260901.md`
    단독으로 docs/phases가 선택되고 INDEX에 1행, kind=design (KF-1 실측 시나리오 그대로)
  - `test_plan_doc_indexed_with_inferred_kind` — `PLAN_roadmap.md` → 인덱싱, kind=plan
  - `test_frontmatter_kind_overrides_filename_inference` — DESIGN_ 파일에 `kind: plan`이면 frontmatter 우선
  - `test_convention_docstring_matches_indexer` — 소스 규약 주석에 design·plan·decided·draft 존재
    (부트스트랩 산출물 접두사 ↔ INCLUDE_PATTERNS 정합 셀프체크의 동결 형태)
- **필수 규칙**:
  - INCLUDE_PATTERNS에 `^DESIGN.*\.md$`·`^PLAN.*\.md$` 추가 (기존 튜플 스타일 유지)
  - kind 추론: `name.startswith("DESIGN")` → `design`, `name.startswith("PLAN")` → `plan`
    (기존 CURRENT_TASK/AGENT_PROMPTS startswith 분기와 같은 사다리에, frontmatter 우선 유지)
  - 규약 주석(모듈 docstring): `kind: task | review | investigation | design | plan`,
    `status: done | in-progress | superseded | decided | draft`
  - 그 외 동작(정렬·표 포맷·reviews 특례·fallback) 변경 금지
- **완료 조건**: `python3 -m unittest tests.test_docs_index -v` 전건 통과 (`Ran 12 tests` 확인) +
  구현 후 오케스트레이터 변이 검증(패턴 2개 제거 사본에서 신규 테스트 FAIL — PITFALLS 15·34 절차)

## Task 1b: 접두사 충돌 보강 (리뷰 🟠 대응 — silent-failure-hunter 재현 지적)

- **에이전트**: `kit-scripts` / **모델**: default / **대상 파일**: `core/scripts/docs-index.py`
- **배경**: `^DESIGN.*\.md$`·`^PLAN.*\.md$`가 구분자 없이 접두만 검사해 `PLANK_*.md`·
  `DESIGNATED_*.md`가 각각 plan/design으로 조용히 오분류됨 (리뷰에서 재현).
- **실패 테스트** (오케스트레이터 작성·동결): `test_prefix_collision_not_indexed`(RED),
  `test_bare_and_delimited_design_plan_still_indexed`(핀 고정 — 과긴축 방지)
- **필수 규칙**: 패턴을 `^DESIGN([_.-].*)?\.md$`·`^PLAN([_.-].*)?\.md$`로 교체,
  kind 추론도 대칭으로 `startswith(("DESIGN_", "DESIGN.", "DESIGN-"))`·PLAN 동형으로 강화.
  그 외 변경 금지.
- **완료 조건**: `python3 -m unittest tests.test_docs_index -v` 14건 전부 통과

## Task 2: 킷 자체 정비 + 하류 추기 (오케스트레이터 직접 — docs 경로)

- **대상**: `docs/phases/PLAN_docs-lowercase-migration.md`(frontmatter 추가 + 낡은 각주 수정),
  `docs/phases/INDEX.md` 재생성, (병합 후) tobuilder-bot `REVIEW_kit-feedback-20260901.md`에
  반영 상태 + 커밋 해시 추기
- **완료 조건**: INDEX.md에 PLAN 문서 행 존재 (kind=plan), `python3 scripts/docs-index.py` 출력
  문서 수 증가 확인

## 리뷰 예상 지점

| 지점 | 예상 지적 | 고정 RED |
|---|---|---|
| 패턴이 `.tasks/` 하위·TEMPLATES 문서까지 잡는가 | 과포함 | 기존 test_scaffolding_only… 회귀로 커버 |
| frontmatter 우선순위 파괴 | kind 추론이 frontmatter를 덮음 | test_frontmatter_kind_overrides_filename_inference |

## 리뷰 총괄

- Task 1 (93866a0): python·security·silent-failure 3종 PASS — 🟠 1건(접두사 충돌 오분류, 재현됨) → Task 1b로 해소
- Task 1b (b2beef9): 3종 PASS, 🔴·🟠 0건. ReDoS 선형 실측, 변이 검증 3회 유효
- structure-reviewer (마감 1회): 부채 3건·후속 3건 — ① phase-tools.py 문서 디렉터리 판정이
  docs-index와 발산(KF-1 시나리오에서 서로 다른 답 가능, 테스트 부재) ② INCLUDE_PATTERNS↔kind
  추론 이중 표현의 단일 테이블 병합 ③ test_docs_index.py 경로/kind 스위트 분리(133→222줄)
- 전체 스위트 374건 중 컨테이너 10건 실패 = 워크트리 서브모듈 미초기화 환경 실패(PITFALLS 24),
  메인 체크아웃에서 동일 파일 29건 OK — 이번 diff와 무관 확인

## 자동 결정 로그

(없음 — 일반 모드)
