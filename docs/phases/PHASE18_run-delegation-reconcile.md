---
phase: 18
date: 2026-09-23
kind: task
domain: scripts, tests, docs
status: done
commits: a91f229..d51c4b6 (+ 마감 커밋)
cost: 미측정 — 홈 세션이 Claude 서브에이전트로 수행(구현 ≈380K·리뷰 ≈175K 토큰, session-cost.py 경로 밖)
compactions: 0 (서브에이전트 보고 기준)
interventions: 1 (리뷰 조건부 SIGN OFF → 반려 3건 반영 후 재검수 SIGN OFF)
summary: run-delegation 4판 드리프트 통합(K-RD1) — 하류 정본(tobuilder-backend)의 한도·인증 문구와 공백 앵커, console 의 SIGPIPE 수정을 키트 core/scripts/run-delegation.sh 로 승격 · console 401 축은 오탐으로 제외
---

# 작업 지시서 — run-delegation 4판 통합 K-RD1 (2026-09-23)

근거: 큐 `docs/phases/QUEUE.md` `K-RD1 run-delegation-reconcile`(사용자 승인 2026-09-02, 방향 「소비자 판을
키트로 승격」) + 홈 세션 조사(2026-09-23). 선행 K-SH1(Phase 17) **done**.

## 배경 — 4판 드리프트 (2026-09-23 실측 `diff`)

키트 `core/scripts/run-delegation.sh`(455줄, `scripts/run-delegation.sh` 는 심링크)가 tobuilder 저장소들에
복제된 뒤 각자 수선됐다. 키트 판 대비:

| 판 | 줄 | 마지막 수선 | 키트 대비 차이 | 판정 |
|---|---|---|---|---|
| **tobuilder-backend** (정본) | 467 | `0952b63` 2026-09-09 | `FAIL_RE` 한도 5문구 + 좁힌 인증 축 · `ERROR_LINE_RE` 에 공백 앵커 · 주석 | **이식** — `scripts/run-delegation.selftest.sh` RED 케이스가 근거 |
| tobuilder-bot | 466 | `eeb3c2f` 2026-09-03 | 옛 키트(무앵커 `Error:`) + 「로컬 오버레이」 블록(`spending/usage limit` · `token (is\|has) expired`) | 문구는 backend 에 이미 포함 · **`(is\|has)` 교대만 일반화로 채택** · 무앵커 줄 선택은 제외 |
| tobuilder-console | 464 | `4113de1` 2026-09-18 | `FAIL_RE`/`AUTH_RE` 분리 · `ERROR_ANCHOR` 단일 정의 · **`status.?401\|unauthorized\|forbidden`** · `-q` SIGPIPE 수정(C-48) · `LOCK_FALLBACK` emit · 프로젝트 정책 폴백 **없음**(키트가 앞섬) | **SIGPIPE 수정만 이식** · 401 축 제외(아래) · 구조 분리·LOCK_FALLBACK 제외 |
| tobuilder-infra | 455 | `044f704` 2026-09-10 | 없음 (`diff` exit 0) | — |

## 범위

1. `core/scripts/run-delegation.sh` 탐지기(`FAIL_RE` · `ERROR_LINE_RE` · `error_signature_in_lines`)에
   **일반 규율만** 이식하고 변경마다 출처(저장소·커밋·날짜) 주석을 단다.
2. backend selftest 의 RED 케이스를 `tests/test_run_delegation.py` 로 옮긴다(먼저 RED 확인 → 이식 → GREEN).
   console 401 축이 **오탐으로 남는지**(401 문자열만으로 실패 판정하지 않음) 단언하는 케이스를 넣는다.
3. 이 문서.

## 비범위

- **console 의 `status.?401|unauthorized|forbidden` 축** — backend 가 실측 2건으로 반려했다(`0952b63`):
  401/403 의미론을 다루는 저장소에서는 `ERROR  test failed: expected 403 forbidden but received 200` 같은
  평범한 테스트 실패 줄이 `ERROR` 갈래(앵커 없음)로 들어와 발화하고, 성공한 위임이 버려진다. 저장소마다
  산출물 어휘가 다르므로 키트는 좁힌 인증 문구(`no api key` · `api key missing|not provided|invalid` ·
  `authentication expired|failed|required` · `token (is|has) expired`)만 갖는다.
  `DetectorParityTest.test_status_401_banner_alone_is_quiet` · `SignatureAnchorTest.test_status_401_alone_is_not_a_limit_error`
  가 이 경계를 고정한다 — 깨지면 누군가 그 축을 들여온 것이다.
- **console 의 `FAIL_RE`/`AUTH_RE` 분리 · `ERROR_ANCHOR`/`LINE_RE`/`error_lines`/`fail_signature_in_tail` 구조** —
  심볼 개명은 backend selftest(`require_single '^FAIL_RE=' …` 네 심볼을 소스에서 추출·eval)의 계약을
  깬다. 키트는 backend 와 같은 네 심볼을 유지해 하류 selftest 를 그대로 겨눌 수 있게 한다.
- **bot 의 무앵커 `grep -aE 'ERROR|Error:'` 줄 선택** — 키트 `38030b2` 가 앵커를 넣은 이유(산출물 `Error:` 오탐)와
  충돌. bot 판이 옛 키트 기반이라 앵커가 없을 뿐이다.
- **console 의 `LOCK_FALLBACK` emit**(`4113de1`, 락 키 정규화 실패를 말하게) — 판정 규율이 아닌 관측성.
  일반적이긴 하나 이 페이즈(탐지기 통합)와 무관해 후속 후보로 남긴다.
- 각 프로젝트로 되돌리는 전파 — 프로젝트별 감독 세션 소관(큐 방향 그대로).
- 큐 `QUEUE.md` · `INDEX.md` 갱신 — 홈 세션이 마감 때.

## 변경 목록

| # | 파일 | 변경 | 출처 |
|---|---|---|---|
| 1 | `core/scripts/run-delegation.sh` `FAIL_RE` | `spending.?limit` · `usage.?limit` · `out of credits` · `insufficient.?credit` · `(^\|[^[:alnum:]_])(usage\|spending\|rate\|quota\|token\|credit\|monthly\|daily\|weekly\|billing\|plan\|account).{0,40}limit.{0,40}(reached\|exceeded)`(backend 의 `limit.*(reached\|exceeded)` 를 리뷰 뒤 주어 한정) 추가 | backend `3622784` 2026-09-09 · bot `9b6698f` 2026-09-02 (KF-16 실측 2종) · 주어 한정은 PR #19 리뷰 |
| 2 | 〃 | `token[[:space:]_-]+((is\|has)[[:space:]_-]+)?expired` — openai OAuth 만료 배너 | bot `eeb3c2f` 2026-09-03(파트 7-1 3회 실측 · 두 tier 모두 exit 0·DONE·산출물 0) · backend `bc1ab67` 2026-09-09. `(is\|has)` 교대는 bot 판의 일반화(backend 판은 `has` 형을 놓친다) |
| 3 | 〃 | `no api.?key` · `api.?key.*(missing\|not provided\|invalid)` · `authentication[[:space:]_-]+(has[[:space:]_-]+)?(expired\|failed)`(backend 의 `.*(expired\|failed\|required)` 를 리뷰 뒤 인접 형태로, `required` 제외) | backend `0952b63` 2026-09-09 (console 축을 **좁혀서** 채택) · 인접 형태는 PR #19 리뷰 |
| 4 | 〃 `ERROR_LINE_RE` | `^([[:space:]]\|ESC[..m)*Error:` — 앵커에 공백 허용 | backend `3622784` 2026-09-09: 실측 배너 바이트 `\033[2m  \033[1mError:` 를 공백 없는 앵커가 놓쳤다 |
| 5 | 〃 `error_signature_in_lines` | `grep -qiE` → `grep -iE … >/dev/null` | console `e73422e` 2026-09-11 C-48: `-q` 가 첫 매치에서 입력을 닫아 앞 단 grep 이 SIGPIPE(141), `pipefail` 이 그것을 결과로 올려 매치가 있어도 거짓. 키트 판 재현 **0/50 → 수정 후 50/50**(50줄×4KB) |
| 6 | `tests/test_run_delegation.py` | `DetectorParityTest` 신설(32건 — 소스에서 네 정의를 추출해 실행, backend selftest 픽스처 이식 + `token has expired` + 401 단독 음성 + 리뷰 반례 4 음성 + `authentication has expired` 양성) · `SignatureAnchorTest` e2e +8(공백+ANSI 배너 · 토큰 만료 · 401 단독 음성 · 49×4KB 긴 줄 · 리뷰 반례 4 음성) · 기존 `test_indented_prose_error_line_is_not_a_limit_error` → `test_bulleted_prose_error_line_is_not_a_limit_error`(계약 반전, 아래) | — |

### 계약 반전 1건 — 공백만 들여쓴 `Error:`

키트 `38030b2`(Phase 15 후속)는 「들여쓴 산출물 `Error:` 는 배너가 아니다」 를 음성 픽스처
`"    Error: rate limit backoff …"` 로 고정했다. backend 실측 배너가 `\033[2m  \033[1mError:`(공백 포함)라
이 계약을 유지하면 실제 한도 오류를 놓친다. 미탐(성공으로 위장한 실패 → 폴백 미발동 → 조용히 실패한 페이즈)이
오탐(불필요한 폴백 1회)보다 훨씬 비싸므로 backend 쪽을 택했다. 음성 픽스처는 앵커가 여전히 막는 표면
(불릿 `"  - Error: …"`)으로 바꿨다. console(`e9cf270` 2026-09-04)도 같은 앵커를 쓴다.
**근거는 한쪽 실측뿐이다** — 반대편(공백만 들여쓴 산출물 `Error:` 줄이 FAIL_RE 낱말과 함께 나오는 빈도)은
미측정이며, 「미탐 비용 > 오탐 비용」 판단으로 받아들였다(PR #19 리뷰 지적, 고치지 않음).

## DoD

- [x] 4판 `diff` 대조 완료, 이식 항목마다 출처 주석
- [x] RED → GREEN: 키트 판에서 15건 RED(DetectorParity 12 · SignatureAnchor 3) → 이식 후 42/42 · 리뷰 반례 8건 RED(4+4) → 축소 후 51/51, 모듈 137/137
- [x] backend `run-delegation.selftest.sh` 를 키트 스크립트에 겨눠 `SELFTEST_PASS`(23/23)
- [x] 401 단독 음성 케이스 2건(헬퍼·e2e)
- [x] `python3 -m unittest discover -s tests` 회귀 0 · `bash -n` · `hook-selfcheck`
- [ ] draft PR → 리뷰 SIGN OFF + CI 초록 → 홈 세션 병합·마감(큐 K-RD1 `done` · INDEX 갱신)

## 검증 (2026-09-23, 워크트리 루트)

| 검증 | 명령 | 결과 |
|---|---|---|
| RED (테스트 커밋 `a91f229`, 스크립트 미수정) | `python3 -m unittest tests.test_run_delegation.DetectorParityTest tests.test_run_delegation.SignatureAnchorTest` | `Ran 42 tests` / `FAILED (failures=15)` — 양성 이식분 전부 `'quiet' != 'fire'` · e2e 3건 `rc=0` |
| GREEN (구현 커밋 `56b6274`) | 같은 명령 | `Ran 42 tests` / `OK` |
| 리뷰 RED (테스트 커밋 `ae6e346`, 축소 전) | 같은 명령 | `Ran 51 tests` / `FAILED (failures=8)` — 헬퍼 4건 `'fire' != 'quiet'` · e2e 4건 `rc=5 … MODEL_EXHAUSTED` |
| 리뷰 GREEN (축소 커밋 `d4c74f8`) | `python3 -m unittest tests.test_run_delegation` | `Ran 137 tests` / `OK` |
| 전체 테스트 | `python3 -m unittest discover -s tests` | 이식 전 `Ran 468` → 이식 후 `Ran 499`(+31) → 리뷰 반영 후 `Ran 508`(+9). 세 실행 모두 **선재 실패 10건 동일**(`test_install_dashboard_container` 9 + `test_install_container_step` 1 — 워크트리 서브모듈 미초기화, PITFALLS 24 · 워크트리 init 금지 PITFALLS 7 · Phase 17 검증 총괄과 같은 집합). 회귀 0 |
| bash 문법 | `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh core/scripts/run-delegation.sh` | exit 0 |
| 훅 자가진단 | `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |
| 하류 selftest 교차 검증 | backend `scripts/run-delegation.selftest.sh` 를 임시 디렉터리에 복사하고 그 옆에 키트 `core/scripts/run-delegation.sh` 심링크(`TARGET="$SCRIPT_DIR/run-delegation.sh"`)를 두고 실행 | `PASS=23 FAIL=0` / `SELFTEST_PASS` (이식 후 · 리뷰 축소 후 각 1회) |
| SIGPIPE 재현 | 키트 네 정의를 추출해 50줄×4KB 로그에 `model_error_in_log` 50회 | 이식 전 `0/50` → 이식 후 `50/50` |

## PR #19 리뷰 반영 (조건부 SIGN OFF, 2026-09-23)

| # | 등급 | 지적 | 조치 |
|---|---|---|---|
| 1 | HIGH | `limit.*(reached\|exceeded)` · `authentication[[:space:]_-]+.*(expired\|failed\|required)` 가 프로바이더 무관 문장(`connection pool limit exceeded` · `max_connections limit reached` · `authentication test failed` · `user authentication required before checkout`)을 `ERROR` 갈래에서 오탐 | 주어 한정 `(^\|[^[:alnum:]_])(usage\|spending\|rate\|quota\|token\|credit\|monthly\|daily\|weekly\|billing\|plan\|account).{0,40}limit.{0,40}(reached\|exceeded)` · 인접 형태 `authentication[[:space:]_-]+(has[[:space:]_-]+)?(expired\|failed)`. **`required` 는 뺐다** — 어느 판의 selftest 에도 양성 픽스처가 없고 리뷰 반례 4번이 그 문구를 담는다(리뷰 처방 예시와 다른 점). 반례 넷을 두 클래스에 음성 픽스처로 추가, RED→GREEN. backend selftest `limit_reached`(`Error: monthly limit reached`)는 `monthly` 주어로 계속 잡는다 |
| 2 | MEDIUM | frontmatter 에 `compactions`·`interventions` 키 없음 | 두 키 추가(값은 마감 시) |
| 3 | MEDIUM | 들여쓴 `Error:` 반전의 근거가 한쪽 실측뿐 | 코드 주석·이 문서에 「반대편 미측정 · 미탐 비용 > 오탐 비용 판단」 한 줄 명시(고치지 않음) |

## 확신 없는 것

- 주어 한정 목록(usage·spending·rate·quota·token·credit·monthly·daily·weekly·billing·plan·account)은 관측된 배너와
  backend 픽스처에서 귀납한 것이라, 목록 밖 주어의 실제 한도 배너(예 「organization limit reached」)는 놓친다.
  놓치면 그 문구를 픽스처와 함께 목록에 넣는다 — `limit.*(reached|exceeded)` 로 되돌리지 않는다(리뷰 반례 4건이 재발).
- 공백 앵커 계약 반전의 오탐 표면(공백만 들여쓴 산출물 `Error:` + FAIL_RE 낱말)은 실측이 아니라 추정으로 받아들였다.
