---
task: 4
status: done
---

## Task 4: A4 교훈 초안 규격 + 절차·설계 문서 갱신
- **에이전트**: kit-docs / **모델**: default / **선행**: 1b·2b·3b
- **문제**: 함정이 3회 재발견됐고 키트 반영 판정이 수작업이라 근거가 유실된다
  (근거: prime-agent 분석 A4 — 제안까지만 자동, **적용은 감독/사람**. D-4 유지).
- **대상 파일**:
  1. `adapters/claude/project/.claude/part-protocol.md` — "파트 종료 절차" 에 `LESSONS.json` 절 추가.
     규격: `{summary, rationale, edits:[{action, kind: "pitfall"|"decision"|"skill", title, content, reason, evidence}]}`.
     **없을 게 없으면 빈 배열** 을 쓴다(파일 자체를 생략하지 않는다). 적용은 하지 않는다 — 초안만 남긴다.
  2. `core/project-template/docs/phases/PITFALLS.md`(또는 해당 템플릿 위치) — 항목 규격을
     `trigger / changes / evidence / outcome` 4필드 + `scope: local|kit` 로 명문화.
  3. `core/supervisor/PROCEDURE.md` — §7 상태 갱신 규칙을 `supervisor-state.sh` 호출로,
     §2 owner 잠금을 PID+start_id 리스로, §5 파트 실패 처리에 `retry-guard` 를 넣는다(task 1b·2b·3b 실산출물 기준).
  4. `docs/phases/PITFALLS.md` — 이 페이즈에서 실측된 함정 신규 항목(있으면).
  5. 설계 문서 §4.1 D-8 문구를 "키트 설치 기준" 으로 갱신 — **설계 문서는 홈(`~/docs/`)에 있어
     파트 세션이 쓸 수 없다.** 파트는 `docs/phases/PHASE17_supervisor-hardening.tasks/task4-design-delta.md` 에
     **갱신 문구 초안만** 남기고, 실제 반영은 감독이 한다.
- **실패 테스트**: 불가 사유 — 문서. 대체 검증: `grep -c 'LESSONS.json' adapters/claude/project/.claude/part-protocol.md` → 1 이상 ·
  `grep -c 'scope: local|kit\|scope: local' <PITFALLS 템플릿>` → 1 이상 ·
  `grep -c 'supervisor-state.sh' core/supervisor/PROCEDURE.md` → 1 이상 ·
  `grep -c 'start_id' core/supervisor/PROCEDURE.md` → 1 이상 · `test -f ...task4-design-delta.md`.
- **필수 규칙**: 홈 경로(`~/docs`, `~/.claude`) 수정 금지. 스크립트 파일 수정 금지(문서 전용 task).
- **완료 조건**: 위 대체 검증 전부 기대값 + hook-selfcheck PASS.

## 위임 로그 요약 (파트 17-4)

- 위임 1회: `kit-docs` / tier `default` / `MODEL_USED=openai/gpt-5.6-luna` / `DONE`.
  락 대기·모델 폴백 없음. 로그 `.orchestrate/task4.log`.
- 산출 커밋 `b856117` — 6파일 (+215/−36).

### 오케스트레이터 사전 실측 (문서에 적을 명령을 **심링크 진입점으로 실제 실행**했다 — PITFALLS 40 대응)

격리 상태 파일 `.orchestrate/probe4/orchestrate/supervisor/probe.json` 으로
`python3 scripts/phase-tools.py retry-guard …` 를 직접 돌린 결과:

| 명령 | 실측 종료코드 | stdout |
|---|---|---|
| `retry-guard 17 4 --check` (기록 없음) | 0 | (없음) |
| `retry-guard 17 4 --record` | 0 | (없음) — `last_failure.worktree_hash` 기록됨 |
| `retry-guard 17 4 --check` (무변경) | **3** | `retry_exhausted: phase=17 part=4 워크트리 변경 없음` |
| `retry-guard 17 5 --check` (스코프 불일치) | 0 | `스코프 불일치로 통과` |
| `retry-guard 17 4 --check --state <없는 파일>` | 2 | (stderr) `상태 파일이 없다` |
| `retry-guard 17 04 --check` (**zero-padding**) | **0** | `스코프 불일치로 통과` ← fail-open, PITFALLS 43 근거 |

`supervisor-state.sh` 는 파트 세션 허용 도구에 `bash core/scripts/supervisor-state.sh` 가 없어
**직접 실행하지 못했다**. 다만 `retry-guard --record` 가 내부적으로 `supervisor-state.sh set … --baseline`
을 호출해 exit 0 으로 상태를 갱신한 것을 확인했으므로 `set` 경로는 간접 실측됐다. 나머지 종료코드는
소스(`core/scripts/supervisor-state.sh:38-123, 243-340`)와 동결 테스트 `tests/test_supervisor_state.py`(10건 GREEN) 근거다.

### 검증 (실제 실행)

| 명령 | 결과 |
|---|---|
| `python3 -m unittest discover -s tests` | `Ran 454 tests` / `FAILED (failures=10)` — 선재 실패 10건 그대로, **회귀 0** |
| `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |
| `grep -c 'LESSONS.json' adapters/claude/project/.claude/part-protocol.md` | 2 (기대 ≥1) |
| `grep -c 'scope' core/project-template/docs/phases/PITFALLS.md` | 3 (기대 ≥1) |
| `grep -c 'supervisor-state.sh' core/supervisor/PROCEDURE.md` | 5 (기대 ≥1) |
| `grep -c 'start_id' core/supervisor/PROCEDURE.md` | 5 (기대 ≥1) |
| `grep -c 'retry-guard' core/supervisor/PROCEDURE.md` | 3 |
| `ls docs/phases/…/task4-design-delta.md` | 존재 |

### 리뷰 (code-reviewer · bash-reviewer 병렬 2인)

**1라운드** (`b856117` 대상) — 🔴 1건 · 🟠 1건 · 🟡 1건. 두 리뷰어가 **같은 🔴 을 독립적으로** 지목했다:
- 🔴 §2 `unverified(4)` 수동 해제 절차가 **편집 후** 바이트의 해시를 `--baseline` 으로 넘겨
  `set_state()`(`core/scripts/supervisor-state.sh:88-123`)의 CAS 비교 대상(**편집 전 디스크 원본**)과
  어긋난다 → 그대로 따라 하면 **매번 exit 3**. `unverified` 의 유일한 탈출구가 항상 실패하는 결함이다.
- 🟠 `sha256sum` 은 GNU 전용 — 이 키트가 명시한 macOS 기본 환경(bash 3.2·BSD 유틸)에 없다.
  저장소의 해시 계산은 전부 python3 `hashlib` 로 통일돼 있다(`supervisor-state.sh:52-54`).
- 🟡 임시 파일이 감독 cwd(`/home/jh`)에 프로젝트 구분 없이 남고 정리 명령이 없다.
- 🟡 (code-reviewer) 같은 커밋이 신설한 4필드 규격을 그 커밋이 쓴 40~43 항목이 안 따른다.

**재위임 1회차** — `kit-docs` / tier `heavy` / `MODEL_USED=openai/gpt-5.6-terra` / `DONE`.
산출 커밋 `2ec0dfc`. 오케스트레이터가 항목 40 의 수정 커밋을 `5f3951a`→**`d15a8ed`** 로 정정했다
(위임 프롬프트에 넣은 SHA 가 틀렸다 — `git show --stat d15a8ed` 로 `__file__` 정규화가 그 커밋임을 확인).

**2라운드** (`2ec0dfc` 대상) — **🔴 0건 · 🟠 0건 · 🟡 0건, 양쪽 SIGN OFF.**
1~39번 기존 항목 무손상(diff 가 605줄 이후에서만 시작)도 확인됐다.

### 범위 판단 한 건

저장소 루트 `CLAUDE.md` 의 함정 한 줄 인덱스 4줄 추가를 위임 범위에 포함했다. task4 의 "대상 파일"
목록에는 없지만, 이 저장소의 명시 규약이 **"CLAUDE.md 한 줄 인덱스 + PITFALLS.md 상세"** 쌍이므로
`docs/phases/PITFALLS.md` 신규 항목만 쓰면 규약이 절반만 지켜진다. 새 task 신설이나 범위 확장이 아니라
지정된 산출물의 완결로 판단했다.
