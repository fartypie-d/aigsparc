# Task 2: 매니페스트 + kit-doctor.sh 진단 본체

- **에이전트**: `kit-scripts`
- **모델**: heavy (⚠️ 도메인 — 사용자 홈을 읽는 스크립트)
- **대상 파일**: `core/install-manifest.tsv` (신규), `core/scripts/kit-doctor.sh` (신규),
  `scripts/kit-doctor.sh` (신규 심링크 → `../core/scripts/kit-doctor.sh`)
- **선행**: Task 1 (테스트 동결)
- **목표**: 인자 없이 실행하면 필수 도구·CLI 유무와 매니페스트 기반 전역 자산 존재·drift 를
  점검해 규격 리포트를 출력하고, `fail>0` 일 때만 exit 1 로 끝난다.
- **재사용**
  - 그대로 재사용 `core/opencode/model-doctor.sh` 의 **리포트·인자 주입 스타일**(`--policy` 등
    경로 주입 플래그) — 진단 로직은 재구현하지 말고 이 스크립트를 참고만 한다. 모델·인증 점검은
    이번 범위 밖이므로 **호출하지 않는다**.
  - 그대로 재사용 `lib/stamp.sh:stamp_detect_harness` (하네스 감지) — 새 감지 함수 금지.
    단 실패해도 죽지 말고 빈 값으로 진행할 것 (`|| true`).
  - 필수 도구 목록은 `install.sh:781` 의 `git curl python3 jq` 와 **동일하게** 유지 (임의 추가 금지,
    `docker` 만 선택 도구로 WARN 처리).
  - 없음 — `grep -rn "install-manifest\|kit-doctor" .` 로 조사한 결과 매니페스트·통합 진단은 부재.
- **실패 테스트**: `tests/test_kit_doctor.py::test_clean_home_reports_missing_as_fail`,
  `::test_complete_home_reports_ok_and_exit_zero`, `::test_modified_asset_reports_drift`,
  `::test_seed_entry_never_reports_drift`, `::test_missing_required_tool_reports_fail`,
  `::test_manifest_exists_with_required_columns`, `::test_manifest_covers_install_copy_targets`,
  `::test_manifest_src_paths_exist_in_kit`, `::test_kit_doctor_symlink_points_to_core`
  → **먼저 실행해 실패를 확인한 뒤** 구현할 것.
- **필독 스킬**: `karpathy-guidelines`
- **필수 규칙**
  - 매니페스트 규격·리포트 규격은 지시서 인덱스의 "매니페스트 규격"·"리포트 규격" 절을 **그대로**
    따른다. 열·모드·접두사·요약 줄 형식을 바꾸지 말 것 (테스트가 문자열을 단정한다).
  - **읽기 전용**이다 — 이 task 에서는 어떤 파일도 생성·수정·삭제하지 않는다 (복사는 Task 4).
  - 주입 플래그 필수: `--home <경로>`(기본 `$HOME`), `--kit <경로>`(기본 스크립트 상위),
    `--manifest <경로>`, `--claude`/`--codex`(하네스 명시). 테스트가 이 플래그로 격리한다.
  - `set -uo pipefail` 을 쓰고 `set -e` 는 쓰지 않는다 — 점검은 실패해도 끝까지 돌아야 한다
    (조기 종료하면 리포트가 잘린다).
  - **조용한 성공 금지**: `cmp`·`diff` 의 종료 코드를 반드시 분기한다. 파일을 읽을 수 없는 경우
    (권한 등)는 OK 가 아니라 `WARN` 으로 보고한다.
  - bash 3.2 호환 (연관배열·`mapfile` 금지 — `lib/stamp.sh` 헤더 주석 참조).
  - `tests/` 수정 금지. 지시서에 없는 새 파일 생성 금지.
  - 대상 파일 외 수정 금지, `git commit` 금지, docker 조작 금지.
- **완료 조건**
  1. `python3 -m unittest discover -s tests -v` — Task 2 담당 테스트 전부 통과, 기존 테스트 회귀 0건.
  2. `bash -n core/scripts/kit-doctor.sh` 통과.
  3. 위임 보고에 **RED 확인 출력(구현 전 실패)** 과 최종 통과 출력을 함께 첨부.
