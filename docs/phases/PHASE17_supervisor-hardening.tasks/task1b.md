---
task: 1b
status: blocked
---

## Task 1b: 감독 시작 계층 키트 이관 구현
- **에이전트**: kit-scripts
- **모델**: heavy
- **선행**: 1a (RED 동결 완료)
- **목표**: 손 설치본이 아니라 **키트 원본 + 설치 스크립트**가 감독 시작 계층을 깐다. task 1a 의 RED 6건이 GREEN 이 된다.
- **대상 파일**:
  1. `core/supervisor/PROCEDURE.md` (신규 — 원본은 `~/.claude/supervisor/PROCEDURE.md`.
     **감독이 이 task 착수 전에 워크트리로 복사해 둔다** — 파트 세션은 홈을 읽을 수 없다.
     복사본에서 아래 2건을 고친다: ⓐ §0 의 **프로젝트 6개 하드코딩 허용 목록 제거** → "레지스트리
     `~/.local/state/orchestrate/registry/<project>.json` 이 존재하는 프로젝트" 로 판정 ⓑ §7 "통째로 다시 쓴다" →
     `supervisor-state.sh` 호출로 교체(스크립트는 task 2b 산출물 — 문구만 먼저 반영하고 task 2b 완료 후 경로 확정))
  2. `core/install-manifest.tsv` — 2행 추가:
     `claude	file	core/supervisor/PROCEDURE.md	.claude/supervisor/PROCEDURE.md` ·
     `claude	tree	adapters/claude/global/commands	.claude/commands`
     (열 구분자는 **탭**. 기존 `claude tree ... skills` 행 근처에 둔다)
  3. `adapters/claude/global/commands/supervise.md` (신규 — 범용 `$1` 판)
     · `adapters/claude/global/commands/supervise-PROJECT.md.tpl` (신규 — 프로젝트별 템플릿,
     플레이스홀더는 `__PROJECT__`. `stamp_placeholders` 가 `.stamp-copied` 목록만 치환하므로
     이 `.tpl` 은 **adopt/new 스크립트가 직접 치환**해 `$HOME/.claude/commands/supervise-<name>.md` 로 쓴다)
     원본 내용은 감독이 워크트리에 복사해 둔 `.orchestrate/supervise-src/` 를 쓴다.
     범용판의 `argument-hint` 에서 프로젝트 6개 하드코딩을 지우고 `<project>` 로 일반화한다.
  4. `adopt-project.sh` · `new-project.sh` — `stamp_finalize` 뒤에 supervise 생성 단계 추가:
     `$HOME/.claude/commands/supervise-<name>.md`(없을 때만) ·
     `$STATE/supervisor/<name>.json`(**없을 때만** idle 스키마) · `$STATE/supervisor/actions-<name>.md`(없을 때만).
     `STATE` 는 `${XDG_STATE_HOME:-$HOME/.local/state}/orchestrate` 로 해석한다(테스트 격리 가능해야 함).
     공통 로직은 `lib/stamp.sh` 에 `stamp_supervisor <TARGET> <NAME>` 로 넣고 두 스크립트가 호출한다.
  5. `core/scripts/kit-doctor.sh` — 드리프트 검사 1건 추가: 레지스트리에 있는 프로젝트인데
     supervise 커맨드 또는 상태 파일이 없으면 `report_drift`, `--add-missing` 이면 생성.
- **재사용**: `lib/stamp.sh` 의 "기존 파일 절대 안 덮음" 규약(`_stamp_copy_tree`)과 `kit-doctor.sh` 의
  `report_drift`·`add_missing_file` 을 **그대로 쓴다**. 새 헬퍼를 만들지 말 것.
- **필수 규칙**: `scripts/*` 는 심링크 — `core/scripts/*` 원본만 수정. `tests/` 수정 금지(1a 가 동결).
  실제 `~/.claude`·`~/.local/state` 를 **수정하는 코드를 테스트에서 실행하지 말 것**(격리 HOME).
  `git commit` 은 오케스트레이터가 한다. macOS bash 3.2 호환(연관배열·mapfile 금지 — `lib/stamp.sh` 규약).
- **완료 조건**: task 1a RED 6건 GREEN · `python3 -m unittest discover -s tests` 회귀 0(선재 실패 10건은
  Phase 16 과 동일 목록) · `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh core/scripts/kit-doctor.sh` exit 0 ·
  `bash scripts/hook-selfcheck.sh` PASS · 변이 검증 1건(핵심 분기 뒤집었을 때 RED 복귀).

## 위임 로그 요약 (2026-09-02)

에이전트 `kit-scripts`, 3회 실행 모두 `MODEL_USED=openai/gpt-5.6-terra` (heavy).

| 회차 | 로그 | 커밋 | 결과 |
|---|---|---|---|
| 1 | `.orchestrate/task1b.log` | `74597da` | 리뷰 3인 중 2인 🔴 반려 |
| 2 (재위임 1) | `.orchestrate/task1b-retry1.log` | `11493ea` 에 포함 | 🔴 2건 해소, 새 🟠 1건(아래) |
| 3 (재위임 2) | `.orchestrate/task1b-retry2.log` | `11493ea` 에 포함 | 🟠 해소 + 중복 제거 |

### 오케스트레이터가 실제로 실행한 검증 (마지막 상태 `11493ea`)

- `python3 -m unittest discover -s tests` → **exit 1, `Ran 430 tests` / `FAILED (failures=10)`**.
  실패 10건은 전부 선재(`test_install_container_step` 1 + `test_install_dashboard_container` 9,
  서브모듈 미초기화 PITFALLS 24). **회귀 0**, task 1a 동결 8건 전부 GREEN.
- `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh core/scripts/kit-doctor.sh` → **exit 0**
- `bash scripts/hook-selfcheck.sh` → **`HOOK_SELFCHECK_PASS`**
- `test_serve_ctl.test_start_fails_without_password` 는 위임 세션이 켜 둔 opencode serve 의
  환경 상속 때문에 위임 쪽 전체 실행에서만 실패했다. 오케스트레이터가 단독·전체로 두 번 재실행해
  **통과** 확인(회귀 아님).
- 변이 검증(위임 수행, `.orchestrate/mut1b2/`): dangling-symlink 가드를 약화하자
  `test_kit_doctor.DoctorPathContainmentTest.test_add_missing_does_not_write_through_dangling_symlink`
  RED 복귀.

### 리뷰 이력

1차(`74597da`): `bash-reviewer` REJECT(🟠2·🟡4) · `security-reviewer` REJECT(🔴1) ·
`silent-failure-hunter` REJECT(🔴2). 핵심 지적 — ⓐ `stamp_supervisor` 에 경로 봉쇄·심링크·원자성
보호가 전무 ⓑ doctor 백필이 상태 파일 `root` 에 `$HOME_DIR` 을 박아 넣음(조용한 오답)
ⓒ 인라인 스테이징이 `add_missing_file` 의 보호를 재현하지 못함.

2차 확인 리뷰(`11493ea`): 두 리뷰어 모두 **1차 🔴 전부 해소 확인**. 각자 새 🔴 1건씩 제기 →
`ESCALATION.md` 참조(반려 2회 · 재위임 한도 2회 소진).

### 오케스트레이터가 추가로 잡은 사항

- 재위임 1 결과물은 프로젝트명이 `[A-Za-z0-9._-]` 밖이면 **온보딩 전체를 `exit 1`** 시켰다.
  한글 디렉터리명 프로젝트를 adopt 할 수 없게 되는 회귀 — 재위임 2 에서 "감독 자산만 건너뛰고
  나머지 설치는 계속" 으로 교정했다.
- task 1b 로 adopt 가 `$HOME` 에 쓰게 되면서 `tests/test_adopt.py`(HOME 미주입)가 **실제 홈을
  오염**시켰다(실측: 이 세션 스킬 목록에 `supervise-existing`·`supervise-plain` 등장).
  격리 HOME/XDG 주입으로 고쳤다(커밋 `7d7c723`, 위임 산출물과 분리 — PITFALLS 27).
  **이미 생긴 실제 홈의 잔재 제거는 감독 몫이다** — HANDOFF "감독이 할 일" 참조.
