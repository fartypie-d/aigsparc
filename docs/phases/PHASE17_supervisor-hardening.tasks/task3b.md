---
task: 3b
status: done
---

## Task 3b: `phase-tools.py retry-guard <N> <k>` (A2 무변경 재시도 차단)
- **에이전트**: kit-scripts / **모델**: heavy / **선행**: 3a
- **문제**: "같은 파트 재시도 1회" 한도가 **아무것도 바뀌지 않은 재시도**를 걸러내지 못한다
  (근거: `~/docs/2026-09-02-prime-agent-review.md` A2, prime-agent `captureGitWorktreeSnapshot`).
- **인터페이스**: `python3 scripts/phase-tools.py retry-guard <phase> <part> [--record|--check] [--state <path>]`
  - `--record`: 현재 워크트리 스냅샷 해시를 감독 상태 JSON 의 `last_failure.worktree_hash` 에 기록.
  - `--check`(기본): 기록된 해시와 현재 해시가 같으면 exit 3 + `retry_exhausted` 사유 출력, 다르면 exit 0.
- **스냅샷 규격**: `git status -z -uall` 출력 + `git diff --binary HEAD` + untracked 파일 내용의 sha256 을
  이어 붙여 단일 sha256. 바이너리·개행 차이에 안정적이어야 한다.
- **필수 규칙**: 기존 서브커맨드 파서 관례(`sub.add_parser`)를 따르고 `cmd_retry_guard` 로 분리.
  `core/scripts/phase-tools.py` 원본만 수정. `tests/` 수정 금지. 상태 파일 쓰기는 task 2b 의
  `supervisor-state.sh` 를 **경유**한다(직접 덮어쓰기 금지 — A3 와 충돌).
- **완료 조건**: 3a RED 4건 GREEN · 회귀 0 · hook-selfcheck PASS · 변이 검증 1건.

## 위임 로그 요약

에이전트 `kit-scripts` / tier `heavy` / `MODEL_USED=openai/gpt-5.6-terra` (3회 모두 동일).
**반려 2회 → 재위임 2회(한도 소진) → 3라운드에서 🔴 없음.**

| 라운드 | 커밋 | 결과 |
|---|---|---|
| 1차 위임 | `ed53ea9` | 리뷰 1라운드 🔴 3건 → **반려** |
| RED 동결 | `12da8a1` | 리뷰 반영 RED 5건 (오케스트레이터) |
| 재위임 1회차 | `d15a8ed` | 리뷰 2라운드 🔴 1건 → **반려** |
| RED 동결 | `bc7b086` | 리뷰 반영 RED 3건 (오케스트레이터) |
| 재위임 2회차 | `5f3951a` | 리뷰 3라운드 **🔴 없음 — 통과** |

### 검증 (오케스트레이터가 위임 종료 후 직접 실행)
- `python3 -m unittest tests.test_phase_tools.RetryGuardTest tests.test_phase_tools.RetryGuardHardeningTest`
  → `Ran 12 tests` / `OK` (동결 4 + 8건)
- `python3 -m unittest discover -s tests` → `Ran 454 tests` / `FAILED (failures=10)` = **회귀 0**.
  실패 10건은 선재분 그대로(`test_install_dashboard_container` 9 + `test_install_container_step` 1).
- `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS` / `git stash list` 비어 있음
- 변이 검증: 라운드마다 1건씩 3건(`mut3b`·`mut3b-r2`·`mut3b-r3`) — 각각 untracked 내용 해시 제거·
  toplevel 고정 되돌리기·스코프 하위호환 되돌리기 변이로 해당 테스트가 실패함을 확인.

### 반려 사유가 된 🔴 (재발 방지용 기록)
1. **심링크 진입점에서 `--record` 가 매번 크래시** — `Path(__file__).with_name("supervisor-state.sh")` 가
   `scripts/supervisor-state.sh`(존재하지 않음)를 가리켰다. 오케스트레이터가 실측 재현
   (`FileNotFoundError`). 기록이 안 되니 `--check` 는 늘 exit 0 = **가드 전체 fail-open**.
   테스트가 `core/scripts/` 를 직접 실행해 안 걸렸다. → `.resolve()`.
2. **스냅샷이 호출 cwd 에 의존** — `git status -z` 는 `-z` 가 porcelain v1 을 함의해 루트 기준이라
   안전하지만 `git ls-files --others` 는 cwd 하위만 cwd 상대로 나열한다.
   → `git rev-parse --show-toplevel` 기준 고정 + `--full-name`.
   (`find_root()` 는 메인 체크아웃을 돌려주므로 스냅샷 기준으로 쓰면 안 된다.)
3. **`--record` 가 `supervisor-state.sh` 의 exit 3(CAS 충돌)을 그대로 반환** — `--check` 의
   `retry_exhausted`(3)와 뭉쳤다. → `3→4`, `2→2`, 나머지→1 재매핑.
4. **스코프 필드 없는 `last_failure` 를 침묵 통과** — `phase`·`part` 는 이번에 처음 기록하는
   필드라 구기록은 항상 불일치 → 무변경 재시도가 흔적 없이 통과. → 키가 없으면 통지 후
   하위호환 해시 비교, 있는데 불일치면 통지 후 통과, 비교는 `str()` 정규화.

### 확정된 종료코드 (task 4 문서화 대상)

| 상황 | 코드 |
|---|---|
| `--check` 통과(변경 있음·기록 없음·스코프 불일치) | 0 |
| `--check` 무변경 재시도 | 3 (stdout `retry_exhausted`) |
| 상태 파일 없음 | 2 |
| `--record` baseline 충돌 | 4 |
| 그 밖의 오류(JSON 손상·git 실패·`phase` 비정수 등) | 1 |
