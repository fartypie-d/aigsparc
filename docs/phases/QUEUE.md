---
kind: queue
updated: 2026-09-02
---

# 페이즈 큐 — aigsprac

> 감독 세션(`/supervise-aigsprac`)이 idle 일 때 이 표에서 `approved && 선행 done && 🔴 아님` 인 항목을
> 골라 착수한다. 큐에 없는 페이즈 신설·`approved` 전환은 **사용자 확인 사항**이다(설계 D-4).
> 2026-09-02 이전에는 `~/.local/state/orchestrate/supervisor/queue-drafts/aigsprac.md` 초안이 정본이었다 —
> 이 파일이 그 초안을 대체한다.

| id | slug | 근거 문서 | 선행 | 위험 | approved | 상태 |
|---|---|---|---|---|---|---|
| K-SH1 | supervisor-hardening | [PHASE17_supervisor-hardening.md](PHASE17_supervisor-hardening.md) (원 근거: `~/docs/2026-09-02-prime-agent-review.md` §2 상 A1~A4 + 감독 시작 계층 키트 이관) | Phase 16 supervisor-bootstrap — **done** (PR #14) | 보통 — 스크립트·프로토콜·설치 매니페스트, 감독 상태 파일 스키마 변경(`owner`) 포함 | **true** (사용자 승인 2026-09-02 "좋아, 추가해보자") | **done** (Phase 17 — 파트 17-1~17-4, 마감 커밋까지. 병합·`phase-close` 는 감독) |
| K-RD1 | run-delegation-reconcile | 동료 세션 인계 2026-09-02 + 감독 실측: 킷 정본 `f3cad341` 을 쓰는 프로젝트가 **0** 인 4판 드리프트(`340a88c1` console·bot / `7a0cb7c7` polybuilder / `e7f479e1` s-orch·dashboard·k-stock·cloak) | K-SH1 | **높음** — 전 프로젝트 위임 경로. tobuilder-console 의 미커밋 로컬 수정(프로젝트 로컬 model-policy 폴백·한도 시그니처 확장) 흡수 선행, 단순 덮어쓰기 금지 | **true** (사용자 승인 2026-09-02) | pending |
| K-OC2 | serve-freshness-check | 동료 세션 인계 2026-09-02 + 감독 실측: 킷 `core/scripts/opencode-serve-ctl.sh`(281줄)에 신선도 개념 없음, `~/.local/bin/model-doctor-cron.sh`·`opencode-autoupdate.sh` 는 매니페스트에 없는 호스트 전용 자산 | K-RD1 | 보통 — 크론·serve 수명주기. `/proc` 의존이라 macOS 대응 필요(현행 판의 **조용한 skip** 을 그대로 옮기지 말 것) | **true** (사용자 승인 2026-09-02) | pending |
| K-SH2 | supervisor-hardening-2 | `~/docs/2026-09-02-prime-agent-review.md` §2 중 B1~B7 + PITFALLS 39(접미사 task 조회 누락) + Phase 17 잔여(지시서 "후속 제안"·"구조 리뷰") | K-SH1 — **done** | 보통 | false — **K-SH1 실측 완료, `approved` 판단 대상**(사용자 확인 필요) | pending |
| K-SH3 | escalation-resume-injection | 같은 보고서 §2 B8 — `claude -p --resume` 이 `--allowedTools`·`--append-system-prompt-file` 을 유지하는지 드라이 런 선행 | K-SH1 — **done** · 드라이 런 결과 | ⚠️ "파트=프로세스" 원칙의 예외 — 드라이 런 결과에 따라 방향 결정 필요 | false | blocked (드라이 런 미실시) |

## K-RD1 방향 (사용자 결정 2026-09-02)

**「소비자 판을 키트로 승격」** — 킷 정본 강제가 아니다. 실사용 검증을 거친 3판의 차이를 대조해 통합본을
만들고 그것을 킷 정본으로 올린다. 각 프로젝트로 되돌리는 전파는 **별도 작업**(프로젝트별 감독 세션 소관)이고
이 페이즈는 킷 정본 확정까지다.

## K-OC2 배경 (실측)

`opencode-autoupdate.sh` 의 serve 재활용이 `UPGRADED=1` 안에만 있어 **설정 변경은 영원히 serve 에 반영되지 않았다**.
serve 가 08-13 기동분으로 19일간 `/proc/<pid>/exe` = `(deleted)`, 09-01 설정 변경도 미반영이었다.
호스트에는 이미 검사가 들어갔다(양방향 검증 완료 — 스큐 시 STALE, 재활용 후 신선). 이 페이즈는 그 검사를
킷 자산으로 추출하는 것이며, 크론 래퍼를 편입할지 `serve-ctl` 서브커맨드로 넣을지는 착수 시 결정한다.

## 상태 값

`pending`(착수 전) · `in-progress`(페이즈 진행 중) · `done`(병합·`phase-close` 완료) ·
`blocked`(선행 미해소 또는 방향 결정 대기).
