---
task: 1
status: done
---

## Task 1: 정책 경로 프로젝트 스코프화 + 출처 가시화

- **에이전트**: `kit-scripts`
- **모델**: heavy (⚠️ 도메인 — 사용자 홈·위임 전체에 영향)
- **대상 파일**: `core/scripts/run-delegation.sh` (이 파일 **하나만**)
- **선행**: 없음
- **목표**: 위임 모델 정책을 프로젝트별로 재정의할 수 있게 한다. `<저장소 루트>/.claude/model-policy.json`
  이 있으면 그것을, 없으면 기존 호스트 전역 `~/.config/opencode/model-policy.json` 을 쓴다.
  어느 정책이 실제로 쓰였는지가 로그에 남아야 하고, 둘 다 없을 때는 **두 후보 경로가 모두** 보여야 한다.
- **재사용**: 개선 후 재사용 `core/scripts/run-delegation.sh:66-84` (`RUN_DIR`·`POLICY`·`CHAIN` 결정부,
  호출부 1곳). `RUN_DIR` 은 66행에 이미 있다 — **`$PWD` 나 새 경로 변수를 만들지 말 것**.
  로그 출력은 `emit()`(38행)을 그대로 쓴다 — stdout + `.wrapper` 양쪽에 남는 기존 헬퍼다.

### 계약 (동결 테스트가 검증하는 것)

1. `$RUN_DIR/.claude/model-policy.json` 이 존재하면 그 파일의 tier 체인이 쓰인다.
2. 없으면 `$HOME/.config/opencode/model-policy.json` 으로 폴백한다 (**기존 동작 하위 호환**).
3. 둘 다 없으면 exit **64**, 오류 메시지에 **두 경로가 모두** 포함된다.
4. 정책 확정 직후 `emit "POLICY_USED=<경로> (project|host)"` 를 한 줄 남긴다
   (`MODEL_USED=` 와 같은 관례 — stdout 과 `.wrapper` 양쪽).
5. 기존 검사 **순서를 바꾸지 말 것** — `PROMPT_FILE` → 정책 → `OPENCODE_BIN` 순서와
   `.wrapper` 설치 시점에 의존하는 기존 테스트가 있다 (`tests/test_run_delegation.py:1221` 부근).
6. (리뷰 반려 보강) 저장소 **하위 디렉터리**에서 호출해도 프로젝트 정책을 찾아야 한다.
   탐색 상한은 **git 최상위**(`git -C "$RUN_DIR" rev-parse --show-toplevel`)로 묶는다 —
   상한 없이 위로 올라가면 `$HOME/.claude/model-policy.json` 같은 무관한 조상을 집는다.
   git 저장소가 아니면 기존대로 `RUN_DIR` 기준으로 되돌아간다.
7. (리뷰 반려 보강) `HOME` 미설정은 **원인을 지목하며 즉시 실패**해야 한다.
   `${HOME:-}` 로 빈 문자열을 허용하지 말 것 — 경로가 조용히 `/` 기준으로 어긋나
   원인과 무관한 "opencode 없음 — install.sh 실행 필요" 로 끝난다.

- **실패 테스트**: `tests/test_run_delegation.py::ModelPolicyScopeTest` — 오케스트레이터가 이미
  작성·커밋해 두었다(RED 확인 완료). **이 파일을 수정하지 말 것** (함정 14).
  포함 케이스: `test_project_policy_overrides_host`,
  `test_falls_back_to_host_policy_when_project_absent`,
  `test_missing_policy_reports_both_candidate_paths`(리뷰 예상 지점),
  `test_policy_used_line_names_the_source`,
  `test_project_policy_is_found_from_a_subdirectory`(리뷰 반려 🔴),
  `test_non_git_directory_still_uses_its_own_project_policy`(하위 호환 가드),
  `test_unset_home_fails_with_a_named_cause`(리뷰 반려 🔴).
- **필독 스킬**: `bash-scripting` 계열이 없으면 생략 가능 — 대신 대상 파일 상단 주석 규약을 먼저 읽을 것.
- **필수 규칙**:
  - `scripts/` 는 `core/scripts/` 로의 심링크다 — **반드시 `core/scripts/run-delegation.sh` 를 고친다**.
  - `set -u` 하에서 안전해야 한다. HOME 을 제거하고 호출하는 동결 테스트가 있다
    (`test_unset_home_fails_with_a_named_cause`).
  - `phase-tools.py`·`.gitignore`·`tests/` 수정 금지. 대상 파일 외 수정 금지.
  - `git commit`·`git push`·docker 조작 금지.
- **완료 조건**:
  - `bash -n core/scripts/run-delegation.sh` (무출력)
  - `python3 -m unittest tests.test_run_delegation -v` — **전부 통과**, `Ran N tests` 의 N 을 보고에 명시
  - 보고에 수정한 파일 목록 + 위 두 명령의 실제 출력 첨부
