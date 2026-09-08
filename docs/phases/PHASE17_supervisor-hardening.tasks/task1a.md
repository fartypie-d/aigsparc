---
task: 1a
status: done
---

## Task 1a: RED — 감독 시작 계층 이관 동결 테스트
- **에이전트**: 오케스트레이터 직접 (`tests/` 는 위임 금지 — PITFALLS 14)
- **모델**: —
- **대상 파일**: `tests/test_adopt_supervise.sh` (신규) · `tests/test_kit_doctor*.py` 또는 해당 위치에 드리프트 케이스 1건 추가
- **선행**: 없음
- **목표**: task 1b 착수 전에 "무엇이 맞는가" 를 **실행 가능한 형태로 동결**한다. 이 시점에 전부 RED 여야 한다.
- **동결할 RED (6건)**:
  1. `adopt-project.sh <tmp프로젝트>` 실행 후 `~/.claude/commands/supervise-<name>.md` 에 해당하는
     **생성 산출물이 존재**한다 (테스트는 `HOME` 을 tmp 로 격리 — 실제 홈을 건드리면 실패로 간주).
  2. 같은 실행 후 `<STATE>/supervisor/<name>.json` 이 idle 스키마로 생성되고
     `<STATE>/supervisor/actions-<name>.md` 가 존재한다 (`STATE` = `~/.local/state/orchestrate`, 격리된 HOME 기준).
  3. **멱등성**: 손으로 만든 `supervise-<name>.md`(내용 `SENTINEL`)가 이미 있으면 adopt 재실행이
     그 파일을 **덮지 않는다** (`grep -q SENTINEL` 통과).
  4. **상태 보존**: `<name>.json` 이 `"status":"running"` 인 상태에서 adopt 재실행이 idle 로 리셋하지 않는다.
  5. 매니페스트 설치 경로로 `core/supervisor/PROCEDURE.md` → `~/.claude/supervisor/PROCEDURE.md` 가 깔린다
     (`kit-doctor.sh` 의 매니페스트 순회가 이 행을 인식하고, `--add-missing` 이 채운다).
  6. `kit-doctor.sh` 드리프트: 레지스트리 `<STATE>/registry/<p>.json` 이 있는데 supervise 커맨드 또는
     상태 파일이 없으면 **drift 를 보고한다**(exit/출력으로 판별 — 침묵 금지).
- **필수 규칙**: 테스트는 반드시 격리 `HOME`/`XDG` 를 쓴다 — 실제 `~/.claude`·`~/.local/state` 를 절대 수정하지 않는다.
  기존 테스트 파일의 격리 패턴(`tests/test_phase_tools.py` 의 `Base`, 기존 셸 테스트의 tmpdir 관례)을 그대로 따른다.
- **완료 조건**: 6건 전부 **RED 확인 출력**을 파트 보고에 첨부 + 커밋 1개(테스트만, 구현과 분리 — PITFALLS 27).

## 실행 결과 (오케스트레이터 직접, 2026-09-02)

커밋 `abefb62` (테스트만).

**파일 위치 판단**: 지시서는 `tests/test_adopt_supervise.sh` 를 지목했으나, 이 저장소의 러너는
`python3 -m unittest discover -s tests` 이고 discover 는 `test*.py` 만 수집한다 — `.sh` 로 쓰면
회귀 기준에서 통째로 빠진다. 따라서 `tests/test_adopt_supervise.py`(adopt 계층 4건) +
`tests/test_kit_doctor.py` 말미(doctor 계층 4건, `unittest.main()` 가드 앞 — PITFALLS 35)로 나눠 썼다.

| RED # | 테스트 | 위치 |
|---|---|---|
| 1 커맨드 생성 | `AdoptSupervisorTest::test_adopt_creates_supervise_command_in_isolated_home` | test_adopt_supervise.py |
| 2 상태·actions 생성 | `AdoptSupervisorTest::test_adopt_creates_idle_state_and_actions_file` | test_adopt_supervise.py |
| 3 멱등성 | `AdoptSupervisorTest::test_rerun_preserves_hand_written_command_file` | test_adopt_supervise.py |
| 4 running 보존 | `AdoptSupervisorTest::test_rerun_preserves_running_state_file` | test_adopt_supervise.py |
| 5 매니페스트 설치 | `SupervisorManifestTest::test_manifest_installs_supervisor_procedure_and_commands` | test_kit_doctor.py |
| 6 doctor 드리프트 | `SupervisorDriftTest::test_registry_without_supervisor_assets_reports_drift` (+ 반대 방향 `..._reports_no_drift`, `..._add_missing_creates_...`) | test_kit_doctor.py |

3·4 는 "기존 파일 보존"만 단정하면 아무것도 만들지 않는 현행 코드에서 **항상 참**이 되므로,
같은 실행에서 *없던* 산출물이 채워지는지도 함께 단정해 RED 를 확보했다.
6 의 반대 방향 테스트도 "침묵으로 통과"를 막기 위해 해당 프로젝트 이름이 들어간 `OK` 보고를 요구한다.

**RED 확인 출력** (`python3 -m unittest discover -s tests`, 430 tests, 118.9s):
`FAILED (failures=18)` = 선재 실패 10건(서브모듈 미초기화 — `test_install_container_step` 1 +
`test_install_dashboard_container` 9, PITFALLS 24) + **신규 RED 8건 전부 실패**.
