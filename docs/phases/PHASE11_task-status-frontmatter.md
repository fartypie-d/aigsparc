---
phase: 11
date: 2026-08-17
kind: task
domain: scripts, skill
status: done
commits: fbece86..547c91d (지시서·구현 TDD 6건·스킬 규칙)
summary: task 상태 기계판독화 — task 파일 frontmatter(status) + phase-tools tasks 서브커맨드 (Ralph 패턴 검토 채택 ②)
---

# 작업 지시서 — task 상태 기계판독화 (2026-08-17)

> 배경: snarktank/ralph 패턴 검토(2026-08-17)에서 채택한 권고 ②.
> task 진행 상태가 지시서 markdown 산문(상태표)에만 있어 LLM 없이는 다음 task를
> 고를 수 없고, 대시보드 표 파싱은 헤딩 누락 시 조용히 0건이 되는 취약성이 실측돼 있다
> (usage-dashboard Phase 14·18). 상태를 frontmatter로 구조화해 무인 드라이버(후속 ①③)와
> 대시보드의 공통 기반을 만든다.

## 인터뷰 결과

- 사용자 승인 범위: 권고 ② 단독 선행 도입 ("도입해보고", 2026-08-17). ①③(드라이버)은 후속.
- 스코프: task 상세 파일(`.tasks/task<N>.md`) frontmatter 규격 + `phase-tools.py tasks`
  서브커맨드(조회 JSON / `--set` / `--next`) + 오케스트레이트 스킬 지시서 규칙 1줄.
- 제외: 대시보드(usage-dashboard) 파서 전환 — 별도 저장소, 후속 페이즈. 무인 루프 드라이버(①③).
- 크기 등급: small (파일 3개, 계약 신설이지만 기존 흐름 비파괴 — frontmatter 없는 기존
  task 파일은 `status: unknown`으로 노출될 뿐 어떤 기존 명령도 깨지지 않는다).

## 전제 실측

| 전제 | 근거 | 유지/뒤집힘 |
|---|---|---|
| task 파일에 frontmatter 규격이 없다 | PHASE9.tasks/task1.md 실측 — `# Task 1:` 헤딩으로 시작 | 유지 |
| phase-tools에 task 단위 명령이 없다 | `--help` 실측: init/claim/close/janitor/dashboard-mounts | 유지 |
| docs-index.py의 parse_frontmatter 재사용 가능 | 파일명 하이픈(`docs-index.py`)이라 import 불가 — 최소 사본 필요 | **뒤집힘** (사본 사유 명시) |

## Task 1: phase-tools `tasks` 서브커맨드 (TDD)

- **대상 파일**: `core/scripts/phase-tools.py`, `tests/test_phase_tools.py` (이 외 수정 금지)
- **재사용**: `Registry`/`find_root` 기존 헬퍼 사용. frontmatter 파서는 docs-index.py의
  `parse_frontmatter`와 동일 로직 최소 사본 — 하이픈 파일명으로 import 불가(전제 실측).
- **실패 테스트**: `tests/test_phase_tools.py::TasksTest` — 조회 JSON 형태, `--set` 갱신,
  frontmatter 신규 삽입, `--next` 선택 순서, 전량 done 시 exit 1, unknown 비실행 취급.
- **규격**:
  - task 파일 frontmatter: `task: <번호>`, `status: pending|in-progress|done|blocked|superseded`.
  - `tasks <phase>` → stdout JSON `{phase, tasks: [{task, status, title, path}], complete}`.
    frontmatter 없는 파일은 `status: "unknown"` (무경고 디폴트 대입 금지 — 값 그대로 노출).
  - `tasks <phase> --set <task>=<status>` → frontmatter 갱신(없으면 삽입). 허용 외 status는 에러.
  - `tasks <phase> --next` → 실행 가능 task(in-progress 우선, 다음 pending 최소 번호) 번호만
    stdout 출력. 없으면 출력 없이 exit 1 (드라이버 루프 종료 조건).

## Task 2: 스킬·템플릿 규칙 반영

- **대상 파일**: `adapters/claude/skills/orchestrate/SKILL.md`(분할 지시서 절),
  `core/project-template/.claude/task-templates/_reuse-rules.md` 인접이 아닌 스킬 본문만.
- **내용**: 분할 지시서 규칙에 "task 파일은 `task`·`status` frontmatter로 시작하고,
  상태 전이는 `phase-tools.py tasks <N> --set` 명령으로 갱신한다" 1개 항목 추가.

## 검증

- `python3 -m unittest discover -s tests -v` 전체 green (베이스라인 대비 신규 실패 0)
- `bash -n` 해당 없음 (python만)

## 자동 결정 로그

- [2026-08-17] status 어휘 → 기존 INDEX frontmatter 관례(done·in-progress·planned)와 겹치되
  task 수준에선 pending을 시작값으로 채택 (planned는 phase 수준 어휘로 남김).
- [2026-08-17] `--next`의 all-done 신호 → 별도 센티널 문자열 대신 exit code 1
  (bash 드라이버 `while` 조건과 자연 결합, 출력 파싱 불필요).
