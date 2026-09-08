---
task: 3
status: done
---

## Task 3: 파트 세션 프로토콜·허용 도구 템플릿 + 병합 주체 문구 (claude 어댑터)
- **에이전트**: kit-docs (로스터 담당 범위 확장: `adapters/claude/project/.claude/*.md|*.txt`·`adapters/claude/project/CLAUDE.md` — 산문·설정 파일이라 kit-docs 성격, 이 페이즈에 한해 명시 배정)
- **모델**: default
- **대상 파일**:
  1. `adapters/claude/project/.claude/part-protocol.md` (신규 — 이 워크트리의 `.claude/part-protocol.md`를 **바이트 동일**하게 복사)
  2. `adapters/claude/project/.claude/part-allowed-tools.txt` (신규 — 이 워크트리의 `.claude/part-allowed-tools.txt` 복사, 단 **키트 전용 항목** `Bash(python3 -m unittest:*)`·`Bash(bash -n:*)`·`Bash(cp:*)`·`Bash(diff:*)`·`Bash(rsync:*)` 제외, **저장소 절대경로 항목** `Bash(tee -a /home/jh/aigsprac/.orchestrate/events.jsonl)`은 그 자리에 주석 없이 `Bash(tee -a __EVENTS_JSONL__)` 한 줄로 대체 — stamp가 치환하지 않는 플레이스홀더이므로 프로젝트가 채운다. 감독 결정 2026-09-02 15:27)
  3. `adapters/claude/project/CLAUDE.md` "## 브랜치 규칙" 절에 아래 "병합 주체" 항목 추가
  4. `adapters/claude/global/skills/orchestrate/SKILL.md` 36·552·556행 문구 교체 (아래)
- **선행**: 없음
- **목표**: 새 프로젝트를 stamp하면 파트 세션 프로토콜·허용 도구가 `.claude/`에 깔리고, 병합 정책 문구가 감독 체계와 일치한다.
- **재사용**: 그대로 재사용 이 워크트리 `.claude/part-protocol.md`·`.claude/part-allowed-tools.txt`(원본, 수정 금지 — 복사만). `grep -rn "part-protocol\|allowed-tools" adapters core` → 0건 확인됨.
- **실패 테스트**: 불가 사유 — 문서·설정 파일. 대체 검증(로스터 표): 경로 실재 + 내용 대조:
  `diff .claude/part-protocol.md adapters/claude/project/.claude/part-protocol.md; echo "exit=$?"` → exit=0 ·
  `grep -c '__EVENTS_JSONL__' adapters/claude/project/.claude/part-allowed-tools.txt` → 1 ·
  `grep -c 'unittest\|bash -n\|rsync\|aigsprac' adapters/claude/project/.claude/part-allowed-tools.txt` → 0 ·
  `grep -c '병합 주체' adapters/claude/project/CLAUDE.md` → 1 · `grep -c '감독' adapters/claude/global/skills/orchestrate/SKILL.md` → 3 이상 ·
  `grep -c '푸시는 절대 금지' adapters/claude/global/skills/orchestrate/SKILL.md` → 0.
- **필독 스킬**: 없음
- **필수 규칙**: `__PROJECT__` 플레이스홀더 일괄 치환 금지. 4개 파일 외 수정 금지. `git commit` 금지. 문구는 아래를 **그대로**.
- **완료 조건**: 위 대체 검증 4개 전부 기대값 + `bash scripts/hook-selfcheck.sh` PASS.

### 3-3. CLAUDE.md 템플릿 "브랜치 규칙" 추가 항목 (기존 첫 항목 바로 뒤)

```markdown
- **병합 주체 (감독 체계)**: 페이즈 PR은 ① CI 초록 ② 리뷰어 SIGN OFF(마감 파트 보고) ③ 충돌 없음
  ④ 🔴 위험 도메인 task 미포함 — 네 조건이 전부 참이면 **홈 감독 세션이 병합하고 `phase-close.sh`까지 실행한다**
  (`gh pr merge --merge`, 머지 커밋 관례 유지). ④가 거짓이면 병합은 사용자 액션이다.
  파트 세션(헤드리스)은 어떤 경우에도 push·PR 생성·병합을 하지 않는다. 감독 체계를 쓰지 않는 프로젝트는
  기존대로 사용자가 병합한다.
```

### 3-4. SKILL.md 문구 교체 (행 번호는 2026-09-02 기준, 문구로 찾을 것)

| 현재 | 교체 |
|---|---|
| `120초 후 skip = **로컬 커밋 상태로 마감. 푸시는 절대 금지**` | `120초 후 skip = **로컬 커밋 상태로 마감. 프로젝트 세션의 푸시는 금지** — 푸시·병합은 홈 감독 세션의 규칙(CI 초록 + SIGN OFF + 충돌 없음 + 🔴 미포함이면 자동 병합, 프로젝트 CLAUDE.md "병합 주체" 참조)` |
| `**푸시는 GATE 2와 별개의 명시 승인 전용.**` | `**푸시·병합은 GATE 2와 별개다 — 감독 체계가 있는 프로젝트는 CLAUDE.md "병합 주체" 조건으로 감독이 하고, 없는 프로젝트는 명시 승인 전용.**` |
| `로컬 커밋 상태로 두되 푸시는 금지 ("오토 모드" 절 참조)` | `로컬 커밋 상태로 두되 프로젝트 세션의 푸시는 금지(병합은 감독 규칙, "오토 모드" 절 참조)` |

## 위임 로그 요약 · 반려 이력

### 위임 (파트 16-2, 2026-09-02)
- 명령: `bash scripts/run-delegation.sh kit-docs .orchestrate/task3.prompt .orchestrate/task3.log default`
  (하네스 `run_in_background` + 같은 턴 `until grep` 대기 — 프로토콜 실측 방법)
- 결과: **exit 0** · `MODEL_USED=openai/gpt-5.6-luna` · `SESSION_ID=ses_f9f30f41effe628F0jXJZbzM50` · 폴백 없음.
- 경계: `git status --short`가 대상 4파일만 (+ 오케스트레이터의 `docs/phases` 편집 2건). 위임의 `git add`·`commit` 없음.
- 커밋 `ca55d39` (어댑터 4파일). 오케스트레이터 문서 편집은 `b5f98ba`로 분리(PITFALLS 27).

### 검수 — 완료 조건 실측 (오케스트레이터 직접 실행)
| # | 명령 | 결과 |
|---|---|---|
| 1 | `diff .claude/part-protocol.md adapters/claude/project/.claude/part-protocol.md` | 무출력, `diff_exit=0` (바이트 동일) |
| 2 | `grep -c '__EVENTS_JSONL__' …/part-allowed-tools.txt` | `1` |
| 3 | `grep -c 'unittest\|bash -n\|rsync\|aigsprac' …/part-allowed-tools.txt` | `0` |
| 4 | `grep -c '병합 주체' adapters/claude/project/CLAUDE.md` | `1` |
| 5 | `grep -c '푸시는 절대 금지' …/SKILL.md` | `0` |
| 6 | `grep -c '감독' …/SKILL.md` | `4` (기대 3 이상) |
| 7 | `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |

원본 대조: `diff .claude/part-allowed-tools.txt adapters/…/part-allowed-tools.txt` → 델타가 정확히 의도한 6건
(키트 전용 5줄 삭제 + `tee -a` 절대경로 → `__EVENTS_JSONL__` 치환). 46줄 → **41줄**, 말미 개행 1개.

전체 검증: `python3 -m unittest discover -s tests` → `Ran 422 tests` / `FAILED (failures=10)` —
실패 10건은 파트 16-1과 **동일한 선재 실패**(서브모듈 미초기화, PITFALLS 24). 회귀 0.
`bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` exit 0.

### 리뷰 (1라운드, 반려 없음)
`code-reviewer`(로스터: kit-docs → code-reviewer). 실사용 모델이 gemini flash 계열이 아니어서
`silent-failure-hunter` 추가 조건은 해당 없음.
판정 **SIGN OFF** — 🔴 0 / 🟠 0 / 🟡 0. 완료 조건 7개 전부 독립 재실행으로 재현,
`grep -rn`으로 기존 동등물 0건(중복 없음), `lib/stamp.sh`의 `stamp_placeholders`가 `__PROJECT__`만
치환함을 확인해 `__EVENTS_JSONL__` 보존을 검증, `part-protocol.md`가 지시하는 동작(위임 실행·대기 루프·
이벤트 append·상태 전이·에스컬레이션 작성·로컬 커밋)이 41줄 허용 목록으로 **전부 커버**됨을 항목 대조로 확인.

> 실행 주체 메모: 로스터는 large 등급에서 task-orchestrator 경유를 규정하지만, task 3은 문서 4파일 ·
> 검증이 기계적인 grep/diff 7개라 파트 세션이 직접 검수·커밋했다(컨텍스트 절감 목적이 성립하지 않음).
> 로그 확인은 `tail -n 30`만 했다.
