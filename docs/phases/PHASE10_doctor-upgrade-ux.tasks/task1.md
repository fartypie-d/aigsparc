# Task 1: 회귀 테스트 동결 (오케스트레이터 직접 작성 — 위임 아님)

- **담당**: 오케스트레이터 (PITFALLS 14 — 위임에 테스트를 맡기면 단정이 약화된다, 같은 계열 7회 실측)
- **대상 파일**: `tests/test_kit_doctor.py` (신규), `tests/test_install_args.py` (`--doctor` 파싱 케이스 추가)
- **선행**: 없음
- **목표**: Task 2~4의 완료 판정을 결정하는 단정을 **구현 전에** 동결한다. 이 시점에 전부 RED여야 한다.
- **재사용**: 그대로 재사용 `tests/_install_helpers.py:KIT`·`parse_only` (기존 헬퍼 — 새 헬퍼 만들지 않음)
- **필수 규칙**
  - 테스트는 `HOME` 을 `tempfile.TemporaryDirectory()` 로 주입한다. 실제 `~/.claude`·`~/.config` 금지.
  - `INSTALL_PARSE_ONLY` 로 **동작**을 검증하지 않는다 (PITFALLS 1 — 항상 참 테스트가 된다).
    파싱 단정만 PARSE_ONLY로, dispatch·리포트·복사는 **실제 실행**으로 검증한다.
  - drift 단정은 "설치본을 변조한 뒤 DRIFT가 보고되는가"로 쓴다 — 존재 여부만 보는 단정 금지.

## 동결할 테스트 (이름 고정 — 리뷰 예상 지점 표와 일치)

| 테스트 | 검증 내용 | 판정 대상 task |
|---|---|---|
| `test_manifest_exists_with_required_columns` | 매니페스트가 4열 TSV이고 규격 열 값(`any/claude/codex`, `file/seed/tree`)만 쓴다 | 2 |
| `test_manifest_covers_install_copy_targets` | `install.sh` 의 `backup_and_copy "$KIT_DIR/..."` dst 전부가 매니페스트에 있다 | 2 |
| `test_manifest_src_paths_exist_in_kit` | 매니페스트의 모든 src 가 저장소에 실재한다 | 2 |
| `test_clean_home_reports_missing_as_fail` | 빈 HOME → `any` 항목이 `FAIL`, 요약 `fail=` 이 0보다 크고 exit 1 | 2 |
| `test_complete_home_reports_ok_and_exit_zero` | 매니페스트대로 채운 HOME → `FAIL` 없음, exit 0 | 2 |
| `test_modified_asset_reports_drift` | 설치본 1개를 변조 → `DRIFT` 보고, exit 0 (drift는 실패가 아니다) | 2 |
| `test_seed_entry_never_reports_drift` | `secrets.env` 를 원본과 다르게 채워도 DRIFT/FAIL 없음 | 2 |
| `test_missing_required_tool_reports_fail` | `PATH` 를 비운 환경 → 필수 도구 `FAIL` | 2 |
| `test_doctor_flag_is_parsed` | `INSTALL_PARSE_ONLY=1 ./install.sh --doctor` → `DOCTOR=1` 출력 (test_install_args.py) | 3 |
| `test_install_doctor_dispatches_to_kit_doctor` | 실제 `./install.sh --doctor` 실행 → kit-doctor 리포트 요약 줄(`KIT_DOCTOR:`)이 나온다 | 3 |
| `test_doctor_runs_without_detected_harness` | 하네스 CLI 없는 PATH·빈 HOME → exit 64 아님, 리포트 출력됨 | 3 |
| `test_add_missing_creates_absent_assets` | 빈 HOME + `--add-missing` → `any` file 항목이 생성됨, 재실행 시 FAIL 0 | 4 |
| `test_add_missing_never_overwrites_existing` | 기존 파일에 표지 문자열 넣고 `--add-missing` → 표지 문자열이 **그대로 남는다** | 4 |
| `test_add_missing_does_not_touch_drifted_files` | 변조된 파일은 `--add-missing` 후에도 변조 상태 유지 + DRIFT 보고 유지 | 4 |
| `test_kit_doctor_symlink_points_to_core` | `scripts/kit-doctor.sh` 가 `../core/scripts/kit-doctor.sh` 심링크다 | 2 |

## 완료 조건

- `python3 -m unittest discover -s tests -v` 실행 시 **위 신규 테스트가 전부 실패**하고
  (`kit-doctor.sh`·매니페스트 부재), **기존 테스트는 전부 통과**한다 (순수 회귀 0건).
- 실패 출력을 이 파일 하단에 요약해 남긴다.

## RED 확인 결과 (2026-08-17, 완료)

`python3 -m unittest discover -s tests` → `Ran 325 tests / FAILED (failures=26)`

- **신규 동결 테스트 16건 전부 RED** (의도) — `test_kit_doctor.py` 14건 + `test_install_args.py` 2건.
  대표 실패 사유: `AssertionError: 매니페스트가 없다: core/install-manifest.tsv`.
- **환경성 baseline 10건** — `test_install_dashboard_container` 9건 + `test_install_container_step` 1건.
  **워크트리에 서브모듈이 초기화돼 있지 않아** 실패한다 (PITFALLS 24). 메인 체크아웃에서
  같은 모듈을 돌리면 `Ran 16 tests OK` / `Ran 13 tests OK` 로 전부 통과 — 즉 **회귀가 아니다**.
  워크트리 안에서 `submodule update --init` 을 하면 phase-close 가 크래시하므로(PITFALLS 7)
  **초기화하지 않고 baseline 으로 취급**한다.

### 이 페이즈의 회귀 판정 기준 (task 2~5 공통)

전체 스위트 실패 개수가 **위 baseline 10건 + 미구현 신규 테스트 수** 를 넘으면 회귀다.
task 완료 시점의 기대값: **실패 = 10건(환경성)만**.
