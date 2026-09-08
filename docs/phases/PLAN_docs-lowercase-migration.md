---
date: 2026-08-15
kind: plan
domain: docs, scripts
status: draft
summary: DOCs/ → 소문자 docs/ 통일 실행 계획 — 미착수, 페이즈 착수 시 근거 문서
---

# 실행 계획 — `DOCs/` → 소문자 `docs/` 통일

> 상태: **미착수 (계획 문서 전용)**. 작성 2026-08-15, Phase 7 마감 직후.
> 사용자 지시로 **실행하지 않고 문서만** 남긴다 — 나중에 저장소 루트에서 직접 수행하기 위한 것.
> 페이즈로 진행하려면 `bash scripts/phase-claim.sh docs-lowercase` 로 번호를 발급받고
> 이 문서를 그 지시서의 근거로 삼는다. (Phase 14부터 `PLAN*.md` 도 `docs-index.py` 가
> 인덱싱한다 — `INDEX.md` 에 kind=plan 행으로 나온다.)

## 왜 하는가 — 취향이 아니라 이식성 결함

- dev-orchestrate-kit·insane-cloak 은 한 저장소 안에 `DOCs/` 와 `docs/` 가 **동시에** 있다.
- macOS 기본 파일시스템(APFS/HFS+)은 대소문자를 구분하지 않는다 → 그 머신에서 클론하면
  두 디렉터리가 하나로 뭉개진다. "어떤 머신에든 재현"이 목표인 킷에서는 결함이다.
- 부수 효과: usage-dashboard 레지스트리의 `docs_dir` 가 프로젝트마다 `DOCs`/`docs` 로 갈려 있어
  Phase 7 에서 확인한 기본값 비대칭(생성기는 필드 필수, 대시보드는 누락 시 `docs`)의 온상이다.

## 현황 실측 (2026-08-15)

| 저장소 | `DOCs/` 항목 | `docs/` | `DOCs` 참조 파일(문서 자신 제외) |
|---|---|---|---|
| dev-orchestrate-kit | 15 | 있음 (PORTING·WORKFLOW·plans·specs·assets·superpowers) | 25 |
| insane-cloak | 10 | 있음 | 4 |
| k-stock | 23 | 없음 | 10 |
| s-orchestrator | 87 | 없음 | 10 |

레지스트리 `docs_dir`: kit·insane-cloak·k-stock·s-orchestrator = `DOCs`, usage-dashboard = `docs`.

## 전제 실측 (근거 파일:라인)

| 전제 | 근거 | 판정 |
|---|---|---|
| phase-tools 는 문서 경로를 레지스트리 `docs_dir` 로 받는다 | `core/scripts/phase-tools.py:78,95,191,266,422` | 유지 — 레지스트리 값만 바꾸면 따라온다 |
| 단, `init` 기본값만 하드코딩 | 같은 파일 `:9`, `:457` (`--docs-dir` default `"DOCs"`) | **바꿔야 함** |
| docs-index 는 경로를 하드코딩한다 | `core/scripts/docs-index.py:32` (`parent.parent / "DOCs"`), `:158` 제목 문구 | **바꿔야 함 — 설정 불가** |
| 훅이 `*/DOCs/*` 를 검사 제외한다 | `.claude/hooks/post-edit-check.sh:7` | **주의** — 단순히 `*/docs/*` 로 바꾸면 제품 문서까지 검사에서 빠진다 |
| 대시보드는 레지스트리 값을 그대로 연다 | `components/usage-dashboard/app/main.py:425` | 유지 — 대소문자 강제 없음 |

## 권장 결정 (미확정 — 착수 시 GATE 1 에서 확정)

1. **범위**: 킷만 먼저 → 도그푸딩으로 절차 검증 → 나머지 3개를 저장소당 1페이즈로 순차.
   s-orchestrator 87개 문서를 미검증 절차로 건드리지 않는다.
2. **구조**: `docs/phases/` 하위로 통째 이동 (지시서·INDEX·reviews·archive·PITFALLS).
   제품 문서(`docs/*.md`)와 오케스트레이션 상태 문서가 섞이지 않고, 레지스트리
   `docs_dir` 를 `docs/phases` 로 지정하면 대시보드 스캔 범위가 지금과 정확히 같다.
3. **선행**: Phase 7 마감 완료(2026-08-15, merge `53df907`) — 두 변경을 섞지 않는다.

## task 초안 (킷 범위)

| # | 제목 | 에이전트 | 모델 | 비고 |
|---|---|---|---|---|
| 1 | `git mv DOCs docs/phases` + 레지스트리 `docs_dir` 전환 | kit-scripts | heavy | rename 이력 보존 확인, 워크트리 열려 있으면 충돌 주의 |
| 2 | `docs-index.py` 경로 하드코딩 제거(레지스트리 `docs_dir` 참조) + `phase-tools.py init` 기본값 | kit-scripts | heavy | RED 선고정: 경로가 바뀌어도 INDEX 가 생성되는지 |
| 3 | 훅·어댑터·템플릿·CLAUDE.md·AGENTS.md 문구 일괄 갱신 | kit-scripts | heavy | 훅 제외 패턴은 `*/docs/phases/*` 로 좁혀 제품 문서 검사 유지 |
| 4 | README·WORKFLOW·PORTING 문서 갱신 | kit-docs | default | 영문/국문 대응 |

## 착수 전 확인할 것

- **모든 워크트리를 닫은 상태에서 실행**할 것. 열린 워크트리 안의 `DOCs/` 는 이동에 따라오지
  않고 따로 남는다.
- `~/.claude/skills/orchestrate/SKILL.md` 등 **전역 설치본**은 킷에서 재설치해야 반영된다
  (`adapters/claude/global/…` 수정 후 `./install.sh` 재실행).
- 타 프로젝트 3개는 각 저장소의 CLAUDE.md·훅·스크립트도 함께 고쳐야 하므로 저장소당 1페이즈.
  다른 프로젝트를 건드리기 전에 프로젝트 확인 가드(CLAUDE.md "세션 운영")에 따라 승인부터 받는다.
