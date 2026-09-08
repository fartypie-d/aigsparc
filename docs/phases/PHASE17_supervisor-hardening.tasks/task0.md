---
task: 0
status: done
---

## Task 0: 큐 초안 → `docs/phases/QUEUE.md` 이관
- **에이전트**: 오케스트레이터 직접 (위임 금지 — 감독 산출물 이관)
- **대상 파일**: `docs/phases/QUEUE.md` (신규)
- **선행**: 없음
- **목표**: 감독이 홈 상태 디렉터리에 들고 있던 큐 초안이 저장소의 정본이 된다. 다음 감독 세션이
  `~/.local/state/orchestrate/supervisor/queue-drafts/aigsprac.md` 가 아니라 이 파일을 읽는다.
- **원본**: `~/.local/state/orchestrate/supervisor/queue-drafts/aigsprac.md` (홈 경로 — 파트 세션은 읽을 수 없다.
  **감독이 이 task 를 직접 수행하고 커밋한다**. 파트 세션은 이 task 가 이미 커밋돼 있음을 확인만 한다).
- **이관 규칙**: frontmatter 의 `draft: true` 제거, K-SH1 행의 상태를 `in-progress (Phase 17)` 로,
  선행 열의 "Phase 16 done — 충족" 을 유지. "K-SH1 스코프 메모" 절은 **지시서로 옮겼으므로 제외**하고
  `근거 문서` 열에서 `docs/phases/PHASE17_supervisor-hardening.md` 를 가리킨다.
- **실패 테스트**: 불가 사유 — 문서. 대체 검증: `test -f docs/phases/QUEUE.md` ·
  `grep -c 'K-SH1\|K-SH2\|K-SH3' docs/phases/QUEUE.md` → 3 이상 · `grep -c 'draft: true' docs/phases/QUEUE.md` → 0.
- **완료 조건**: 위 3개 기대값 + 커밋 1개(`docs(phase17): 큐 정본 QUEUE.md 신설`).

- **완료 (2026-09-02, 감독 직접)**: 커밋 `4af2824`. 검증 3개 전부 기대값.
