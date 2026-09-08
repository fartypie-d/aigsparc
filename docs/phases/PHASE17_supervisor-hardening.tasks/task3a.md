---
task: 3a
status: done
---

## Task 3a: RED — `retry-guard` 동결 테스트 (A2)
- **에이전트**: 오케스트레이터 직접 (`tests/`)
- **대상 파일**: `tests/test_phase_tools.py` 에 `RetryGuardTest` 추가 (기존 `Base` 격리 저장소 상속)
- **동결할 RED (4건)**:
  1. 워크트리 스냅샷 해시가 **직전 실패 시점과 같으면** `retry-guard` 가 non-zero (재spawn 금지 신호).
  2. 추적 파일이 바뀌었으면 통과(exit 0).
  3. **untracked 파일만** 바뀌어도 통과 — 스냅샷은 `git status -z -uall` + `git diff --binary HEAD` +
     untracked 내용 sha256 을 모두 포함해야 한다.
  4. 직전 실패 기록이 없으면(첫 시도) 통과.
- **완료 조건**: 4건 RED 확인 출력 + 테스트만 커밋.

## 위임 로그 요약 (오케스트레이터 직접 수행)
- 커밋: `ef702b7` (테스트만, 위임 산출물 없음 — PITFALLS 27)
- RED 확인: `python3 -m unittest tests.test_phase_tools.RetryGuardTest -v` → `Ran 4 tests` / `FAILED (failures=4)`
  (전부 `invalid choice: 'retry-guard'`), 모듈 전체 `Ran 46 tests` / `FAILED (failures=4)`
- 동결한 계약 (task 3b 가 만족해야 하는 것):
  1. 무변경 재시도 → exit **3** + stdout 에 `retry_exhausted`
  2. `--record` 는 기존 상태 키(`status`·`owner`)를 보존하고 `last_failure.worktree_hash` 에
     64자 소문자 16진 sha256 을 넣는다 (상태 파일을 통째로 갈아엎지 않는다 = `supervisor-state.sh` 경유)
  3. untracked 파일의 **내용만** 바뀐 경우도 "변경 있음" — `git status -z -uall` 목록만으로는 못 잡는다
  4. `last_failure` 기록이 없으면 통과, 플래그 생략 시 기본은 `--check`
- 상태 파일 경로 계약: 테스트는 `--state <XDG_STATE_HOME>/orchestrate/supervisor/<project>.json`
  (격리 HOME·XDG 주입) 로 호출한다 — 홈은 읽지도 쓰지도 않는다.
