---
task: 5
status: done
---

## Task 5: 전멸 안내가 실제로 쓰인 정책을 가리키게

- **에이전트**: `kit-scripts`
- **모델**: heavy
- **대상 파일**: `core/scripts/run-delegation.sh` (1개)
- **선행**: Task 1·2 (정책 탐색·시그니처가 이미 들어와 있어야 한다)
- **목표**: `MODEL_EXHAUSTED` 직후의 "사용자에게 보고할 것" 안내가 **그 실행이 실제로 쓴
  정책 파일**(`$POLICY`)을 가리킨다. 프로젝트 정책으로 돈 실행이 호스트 경로를 안내받는
  일이 없어야 하고, 호스트 정책으로 돈 실행은 기존과 같은 경로를 안내받는다.

### 왜 이 task 가 생겼나

구조 리뷰어(페이즈 말 1회 호출) 지적. 이 페이즈는 `POLICY_USED=` 로 "어느 정책이 쓰였는지"를
보이게 만들었는데, 정작 사용자가 정책 파일에 손을 대야 하는 유일한 순간(체인 전멸)의 안내는
`~/.config/opencode/model-policy.json` 을 **하드코딩**한 채 남았다. 이 페이즈가 없애려던
"실제로 쓰인 정책이 안 보인다"가 이 한 줄에서 그대로 재현된다.

### 재사용

`개선 후 재사용 core/scripts/run-delegation.sh:emit()` — 새 출력 헬퍼를 만들지 말 것.
정책 경로 변수는 이미 Task 1 이 만든 `$POLICY`(실사용 경로)·`$POLICY_SOURCE`(project|host)가
있다. **새 변수를 만들지 말고 그대로 쓴다.** `grep -n 'POLICY' core/scripts/run-delegation.sh` 로 확인할 것.

### 실패 테스트 (이미 동결됨 — 커밋 `a041e8e`, 수정 금지)

- `tests/test_run_delegation.py::ModelPolicyScopeTest::test_exhaustion_notice_names_the_project_policy_in_use`
  — 프로젝트 정책으로 돈 전멸 실행에서, 안내 **줄** 안에 프로젝트 정책 절대경로가 있고
  `.config/opencode/model-policy.json` 은 없어야 한다.
- `tests/test_run_delegation.py::ModelPolicyScopeTest::test_exhaustion_notice_keeps_host_path_when_host_policy_ran`
  — 호스트 정책으로 돈 전멸 실행에서, 안내 줄이 **전개된** 호스트 절대경로를 담아야 한다
  (현재 코드는 `~` 리터럴이라 이 단정도 RED 다). 프로젝트 경로를 무조건 찍는 구현을 거른다.

두 테스트는 안내 줄(`사용자에게 보고할 것` 을 포함한 줄)을 **정확히 1줄** 요구한다 — 안내를
두 줄로 쪼개면 실패한다.

### 필수 규칙

- `tests/` 는 **오케스트레이터 전속**이다. 테스트 파일을 열어 읽는 것은 되지만 **수정 금지**.
- 대상 파일 1개 외 수정 금지. `git commit` 금지. docker 조작 금지.
- 기존 `FAIL_RE`·정책 탐색 블록·`emit()` 을 건드리지 말 것 — 이 task 는 안내 문구 한 줄이다.
- `$POLICY` 는 정책 확정 블록에서만 설정된다. 그 앞으로 옮기거나 재할당하지 말 것.

### 완료 조건

- `python3 -m unittest tests.test_run_delegation` → `Ran 93 tests` / `OK`
  (93 이 아니면 테스트를 건드린 것이다 — 즉시 보고할 것)
- `bash -n core/scripts/run-delegation.sh` → 무출력
