---
task: 2
status: done
---

## Task 2: 크레딧·한도 시그니처 좁은 앵커 + 판정 기준 단일화

- **에이전트**: `kit-scripts`
- **모델**: heavy (⚠️ 도메인 — 오탐 1건이 성공한 위임을 폐기시킨다)
- **대상 파일**: `core/scripts/run-delegation.sh` (이 파일 **하나만**)
- **선행**: Task 1
- **목표**: 크레딧 소진·한도 실패가 `FAIL_RE` 에 잡혀 모델 폴백이 걸리게 한다. 단
  **정상 로그를 매칭하면 안 된다** — `model_error_in_log()` 는 `OC_RC` 와 무관하게 417행 최종
  판정에 쓰이므로, 오탐 1건이 rc=0 으로 정상 완료한 위임을 `.failed-<모델>` 로 폐기시킨다.
  함께, 인터림 감시(346·402행)와 최종 판정(249행)이 **같은 매처**를 쓰도록 단일화한다.

### 왜 좁아야 하는가 (실측 근거 — 이 저장소의 실제 로그)

- `.orchestrate/**/*.log` 의 `402` 는 **전부 정상 INFO 라인**이다:
  `timestamp=2026-08-08T07:47:11.402Z level=INFO ...`, `messageID=msg_fe070402e001...`.
  → 맨 `402` 앵커는 그 자체로 오탐원이다. **반드시 `status.?402` 처럼 앵커링**할 것
  (기존 `status.?429` 와 같은 형태).
- `Error:`(level=ERROR 아님) 라인은 실제 로그에 **61건** 있다 (전부 위임 테스트 출력의
  `AssertionError:` 류). → 라인 필터 `grep -a 'ERROR'` 를 **확대하지 말 것**.
  초안의 `grep -aE 'ERROR|Error:'` 는 **불채택**이다.
- `.*` 탐욕 매칭 금지 — 범위를 `.{0,N}` 으로 제한한다.

### 계약 (동결 테스트가 검증하는 것)

1. `FAIL_RE` 에 크레딧·한도 앵커를 추가한다 (좁게, 예: `status.?402`,
   `insufficient.{0,10}(credit|fund)`, `out of credit`, `credit balance.{0,20}too low`,
   `(usage|spending).?limit.{0,20}(reached|exceeded)`). 정확한 목록은 재량이나
   **동결 테스트의 양성·음성 케이스를 모두 만족**해야 한다.
2. 라인 필터는 `grep -a 'ERROR'` 를 **유지**한다.
3. 매처(라인 필터 + `FAIL_RE`)를 **단일 헬퍼**로 추출하고 249·346·402행이 모두 그것을 호출한다.
   윈도(`tail -n 50` / `tail -n 3`)와 402행의 추가 조건(`ERROR` ≥3)은 호출부에 남긴다 —
   동작을 바꾸는 것이 아니라 **발산을 구조적으로 막는 것**이 목적이다.
4. 246~249행 주석을 실태에 맞게 갱신한다 ("에이전트 산출물의 우연한 매치를 막는다"는 설계
   의도가 왜 라인 필터 유지로 지켜지는지 + 새 앵커가 왜 좁은지를 한두 줄로).

- **실패 테스트**: `tests/test_run_delegation.py::SignatureAnchorTest` — 오케스트레이터가 이미
  작성·커밋해 두었다(RED 확인 완료). **이 파일을 수정하지 말 것** (함정 14).
  **양성 4건이 실패하고 음성 3건은 이미 통과한다 — 음성은 끝까지 통과를 유지해야 한다.**

  | 케이스 | 성격 |
  |---|---|
  | `test_credit_exhaustion_error_triggers_fallback` | 양성(합성) — `status 402` + `Insufficient credits` |
  | `test_low_credit_balance_error_triggers_fallback` | 양성(합성) — `credit balance is too low` |
  | `test_usage_limit_reached_triggers_fallback` | 양성(합성) — `usage limit reached` |
  | `test_interim_watcher_also_detects_credit_signature` | 양성 — 인터림 감시 경로 (리뷰 예상 지점) |
  | `test_normal_info_line_with_402_is_not_a_limit_error` | 음성 — **실제 아카이브 INFO 라인** |
  | `test_error_line_with_402_timestamp_is_not_a_limit_error` | 음성 — 타임스탬프 `.402Z` 가 든 ERROR 라인 (리뷰 예상 지점) |
  | `test_agent_output_error_lines_are_not_limit_errors` | 음성 — **실제 아카이브 산출물 라인**('한도' + `ERROR`) |

  양성 픽스처는 기존 `FAIL_RE` 에 걸리지 않는 형태로 골랐다 — `AI_APICallError` 처럼 이미
  잡히는 문구를 쓰면 새 앵커 없이도 통과하는 약한 계약이 되기 때문이다.
- **필수 규칙**:
  - `core/scripts/run-delegation.sh` 를 고친다 (`scripts/` 는 심링크).
  - 기존 `FAIL_RE` 항목을 **삭제·약화하지 말 것** — 추가만 한다.
  - `tests/` 수정 금지. 대상 파일 외 수정 금지. `git commit`·docker 조작 금지.
- **완료 조건**:
  - `bash -n core/scripts/run-delegation.sh` (무출력)
  - `python3 -m unittest tests.test_run_delegation -v` — 전부 통과, `Ran N tests` 의 N 명시
  - 보고에 추가한 앵커 목록과 **각 앵커가 왜 정상 로그를 매칭하지 않는지** 한 줄씩 근거 첨부
