# Task 3: install.sh --doctor 위임 dispatch

- **에이전트**: `kit-scripts`
- **모델**: heavy (⚠️ 도메인 — 설치 진입점)
- **대상 파일**: `install.sh` (단일)
- **선행**: Task 2
- **목표**: `./install.sh --doctor` 가 진단만 수행하고(설치 부작용 0) `core/scripts/kit-doctor.sh`
  의 종료 코드를 그대로 물려준다. 하네스 CLI 가 하나도 없는 깨진 호스트에서도 동작한다.
- **재사용**: 개선 후 재사용 `install.sh:72-102` 인자 파싱 블록 + `INSTALL_PARSE_ONLY` 출력부
  (호출부 1곳). 새 파싱 루프를 만들지 말 것.
- **실패 테스트**: `tests/test_install_args.py::test_doctor_flag_is_parsed`,
  `tests/test_kit_doctor.py::test_install_doctor_dispatches_to_kit_doctor`,
  `tests/test_kit_doctor.py::test_doctor_runs_without_detected_harness`
  → **먼저 실행해 실패를 확인한 뒤** 구현할 것.
- **필독 스킬**: `karpathy-guidelines`
- **필수 규칙**
  - **dispatch 위치가 이 task 의 핵심이다**: `--doctor` 는 하네스 자동감지(`install.sh:91-93`,
    실패 시 `exit 64`) **앞에서** 처리해야 한다. 그러지 않으면 하네스가 없는 호스트에서 doctor 가
    exit 64 로 죽어 진단 자체가 불가능하다 (실측 근거: `install.sh:92`).
  - 동시에 `INSTALL_PARSE_ONLY=1` 일 때는 dispatch 하지 말고 파싱 결과만 출력해야 한다
    (파서 테스트가 실제 실행으로 번지면 안 된다). `INSTALL_PARSE_ONLY` 출력 블록에
    `echo "DOCTOR=$DOCTOR"` 를 추가한다.
  - 선택된 하네스가 있으면 `--claude`/`--codex` 를 kit-doctor 에 그대로 넘긴다. 없으면 넘기지 않고
    kit-doctor 의 자체 감지에 맡긴다.
  - `exec` 또는 `bash ... ; exit $?` 중 어느 쪽이든 **kit-doctor 의 종료 코드를 보존**해야 한다.
  - `install.sh` 증가분은 **20줄 이내** — 진단 로직을 install.sh 에 넣지 말 것 (이미 1768줄).
  - 헤더 주석(`install.sh:4-5`)의 사용법에 `[--doctor]` 를 추가한다.
  - 기존 플래그·마법사·메뉴 동작을 바꾸지 말 것. `tests/` 수정 금지.
  - 대상 파일 외 수정 금지, `git commit` 금지.
- **완료 조건**
  1. `python3 -m unittest discover -s tests -v` — 전부 통과 (기존 install 계열 테스트 회귀 0건).
  2. `bash -n install.sh` 통과.
  3. `INSTALL_DRY_RUN=1` 계열 기존 테스트가 그대로 통과함을 보고에 포함.
