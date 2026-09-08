---
task: 2a
status: done
---

## Task 2a: RED — `supervisor-state.sh` 동결 테스트 (A1 owner 리스 + A3 원자 쓰기)
- **에이전트**: 오케스트레이터 직접 (`tests/`)
- **대상 파일**: `tests/test_supervisor_state.py` (신규)
- **선행**: 없음
- **동결할 RED (6건)**:
  1. `get <project>` 가 상태 JSON 을 그대로 내보내고, 없으면 **명시적 오류**(빈 JSON·`$0` 폴백 금지).
  2. `set` 이 baseline(읽을 때의 해시)과 현재 파일 해시가 다르면 **거부**하고 non-zero 로 끝난다 (조용한 덮어쓰기 금지).
  3. `set` 이 성공하면 tmp+`mv` 로 원자 교체되고, 중간 상태(부분 기록 파일)가 남지 않는다.
  4. `patch` 가 지정 키만 바꾸고 나머지 필드를 보존한다.
  5. owner 리스: `owner.pid` 가 살아 있고 `owner.start_id` 가 `/proc/<pid>/stat` 22필드와 **일치**하면 "살아 있음" 판정.
  6. owner 리스 회수: 같은 PID 라도 `start_id` 가 다르면(=PID 재사용) **즉시 회수 가능** 판정.
     PID 부재도 회수 가능. mtime 은 보조 지표로만 쓴다.
- **필수 규칙**: 테스트는 격리 tmpdir 상태 디렉터리를 쓴다. 실제 `~/.local/state/orchestrate` 금지.
  `/proc` 의존 케이스는 현재 프로세스 자신의 pid/start_id 로 "살아 있음" 을, 가짜 start_id 로 "회수" 를 만든다
  (Linux 전용 분기는 `sys.platform` 로 skip 처리 — macOS 에서 실패하지 않게).
- **완료 조건**: 6건 RED 확인 출력 첨부 + 테스트만 커밋.

### 위임 로그 요약 (파트 17-2, 2026-09-02) — 위임 없음(오케스트레이터 직접)

커밋 `898bc98` — `tests/test_supervisor_state.py` 신설. **테스트 메서드 7개**(지시서 6건 +
`/proc` 폴백 경로 1건). `python3 -m unittest discover -s tests -p 'test_supervisor_state.py' -v`
→ `Ran 7 tests` / `FAILED (failures=9)` — **7개 메서드 전부 FAIL**(subTest 3건이 별도 계수돼 9).

| 메서드 | 동결한 계약 |
|---|---|
| `test_get_outputs_state_verbatim_and_errors_when_missing` | `get` 바이트 그대로 · 부재 시 stdout 무출력 + exit 2 |
| `test_set_rejects_when_baseline_changed` | baseline 불일치 exit 3 · 파일 불변 · 현재 해시 보고 · `--baseline` 없는 `set` 도 거부 |
| `test_set_replaces_atomically_without_leftovers` | tmp+`mv` 교체 · 상태 디렉터리에 잔재 0 |
| `test_patch_changes_only_given_keys` | 지정 키만 변경 · 나머지 값·타입 보존(`cost` 중첩 포함) |
| `test_live_owner_with_matching_start_id_is_alive` | `alive`+exit 0 · **mtime 1970 이어도 alive**(보조 지표) · 살아 있는 리스는 `owner-take` 불가 |
| `test_live_owner_falls_back_to_proc_stat` | sessions 파일 없을 때 `/proc` 22필드 폴백 (Linux 한정, `skipUnless`) |
| `test_stale_owner_with_reused_pid_is_reclaimed` | PID 재사용 → `reclaimable`+non-zero · PID 부재 → `reclaimable` · `start_id` 부재 → 출력에 `mtime` 명시 · 회수 가능할 때 `owner-take` 성공·기록 |

동결 시 확정한 인터페이스 세부(지시서가 열어 둔 것 — 2b 위임 프롬프트에 그대로 전달):
- `get` 은 **JSON 만** 낸다. baseline 해시는 `get` 출력에 섞지 않고 `set --baseline <sha256>` 으로 받는다.
- 해시는 **원본 바이트의 sha256 16진 소문자**(python3 `hashlib` 기준 — `sha256sum`/`shasum` 이식성 회피).
- `owner-check` 판정어는 stdout **첫 낱말** `alive`/`reclaimable`, 종료코드는 0 / non-zero.
- mtime 폴백은 출력에 문자열 `mtime` 을 포함해 명시한다(조용한 폴백 금지).
- start_id 1차 소스 `$HOME/.claude/sessions/<pid>.json` 은 테스트에서 **격리 HOME 안 픽스처**로만 만든다.
  실제 홈의 그 파일은 읽지도 않는다.
