---
task: 5
status: done
---

## Task 5: 마감
- **에이전트**: 오케스트레이터 직접 / **선행**: 0~4
- **할 일**:
  1. `python3 scripts/docs-index.py` 재생성 (INDEX.md 10KB 상한 주의 — Phase 16 은 381B 초과했다).
  2. 지시서 frontmatter: `status: done`, `commits`, **정량 3필드**(`cost`·`compactions`·`interventions`) 기입.
     비용은 `python3 scripts/session-cost.py --project <메인경로> --session <id> --json` 실측
     (워크트리 세션은 슬러그 `.`→`-` 미치환 때문에 유사 경로 우회 필요 — PITFALLS 38).
  3. `structure-reviewer` 1회(게이트 아님) — 부채·분할 후보를 지시서 "구조 리뷰" 절에 요약.
  4. 검증 총괄 표 기입 (unittest·`bash -n`·hook-selfcheck·`git stash list`·변이 검증).
  5. `docs/phases/QUEUE.md` 의 K-SH1 행 상태를 `done` 으로, K-SH2 를 `approved` 판단 대상으로 남긴다.
  6. `HANDOFF.md` 는 **삭제하지 않는다** — 감독이 병합 시 지운다(Phase 16 관례 확정).
- **완료 조건**: 마감 커밋 1개 + `PART_DONE 17-<k> next=none`.

## 수행 기록 (파트 17-4)

| 항목 | 결과 |
|---|---|
| `python3 scripts/docs-index.py` | 재생성. `INDEX.md` 크기는 아래 참조 — 10KB 상한 여유 |
| 지시서 frontmatter | `status: done` · `commits` · `cost`/`compactions`/`interventions` 기입 |
| `structure-reviewer` 1회 | 부채 8건 / 분할 후보 5건. 지시서 "구조 리뷰" 절에 요약, "후속 제안" 에 우선순위 5건 |
| 검증 총괄 표 | 지시서 "검증 총괄" 절에 기입 (전부 실제 실행) |
| `docs/phases/QUEUE.md` | K-SH1 → **done**. K-SH2 는 선행 `done` 표기 + `approved` 판단 대상 명시. K-SH3 는 드라이 런 미실시로 `blocked` 유지 |
| `HANDOFF.md` | **삭제하지 않음** (감독이 병합 시 처리) |
| `ESCALATION.md` | **삭제하지 않음** — frontmatter 에 `resolved: 2026-09-02` 와 처리 결과(3차 위임 승인 → task 1c done) 한 절 추가 |

### 정량 3필드 산출 근거

- **cost**: `python3 scripts/session-cost.py --project /home/jh/aigsprac/-claude/worktrees/phase17-supervisor-hardening --json`
  → `{"files": 5, "usd": 43.58, "usd_complete": true}`. PITFALLS 38 의 **점 자리에 `-` 를 넣은 유사 경로**
  우회가 필요했다(워크트리 세션 슬러그 미치환). 이 값은 **파트 세션 4개(17-1~17-4)의 합**이며,
  마감 커밋 이후 이 세션 잔여분만큼 소폭 더 늘어난다.
  **홈 감독 세션·opencode 위임(7회)·리뷰어 서브에이전트 비용은 포함되지 않는다** — 감독 세션은
  메인 슬러그 누적에 섞여 분리 불가(Phase 16 과 같은 한계).
- **compactions**: 파트 17-4 는 **0**. 17-1~17-3 은 각 파트 보고에 기록이 없어 **미상**.
- **interventions**: 감독/사용자 개입 **4회** — ① 파트 17-1 `blocked` 에스컬레이션 → 3차 위임 승인
  ② task 1c 신설 결정 ③ 큐에 K-RD1·K-OC2 추가(사용자 승인) ④ 파트 17-4 프롬프트의 `결정:` 5건
  (범위·홈 경로 금지·HANDOFF/ESCALATION 보존·구조 부채 이월·스크래치 보존).
