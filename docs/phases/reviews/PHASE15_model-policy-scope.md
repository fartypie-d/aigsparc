---
phase: 15
date: 2026-09-01
kind: review
domain: scripts, tests, docs
status: done
commits: 7398461..8cc33cd
summary: 모델 정책 스코프 페이즈의 리뷰 총괄 — 반려 2라운드, 문서 표면 과소측정으로 task 신설 1회, 리뷰 결과 고아화 사고 1건
---

# Phase 15 리뷰 총괄

## 리뷰 라운드 집계

| Task | 라운드 | 리뷰어 | 판정 | 🔴 | 🟠 | reject_cause |
|---|---|---|---|---|---|---|
| 1 정책 경로 프로젝트 스코프화 | 1 | bash / security / silent-failure | **반려** | 2 | 0 | model |
| 1 (fix `7cc536e`) | 2 | bash / security / silent-failure | **전원 SIGN OFF** | 0 | 0 | — |
| 2 크레딧·한도 시그니처 | 1 | bash / security / silent-failure | **반려** | 1 | 1 | model |
| 2 (fix `32a1022`) | 2 | silent-failure | **SIGN OFF** | 0 | 0 | — |
| 3 문서 9곳 | 1 | code-reviewer | **SIGN OFF (스코프 내)** | 0 | 1 | spec |
| 4 남은 문서 표면 3개 | 1 | code-reviewer | **SIGN OFF** | 0 | 0 | — |
| 페이즈 전체 | — | structure-reviewer | **게이트 아님** (부채 4 / 분할 후보 2) | — | — | — |
| 5 전멸 안내 실사용 정책 | 1 | bash / security / silent-failure | **전원 SIGN OFF** | 0 | 0 | — |

리뷰어: `bash-reviewer` · `security-reviewer` · `silent-failure-hunter` (kit-scripts),
`code-reviewer` (kit-docs), `structure-reviewer` (페이즈 말 1회).

## 리뷰가 실제로 잡은 것

### Task 1 R1 — `$HOME` → `${HOME:-}` 자기주도 치환 (🔴 ×2, 독립 재현)

지시서 계약(1~6)에 없는 범위 확장. `bash-reviewer`·`silent-failure-hunter` 가 각각 재현했다:

- **패치 전**: `HOME` 미설정 시 `line 68: HOME: unbound variable` 로 즉시 크래시 — 원인이 메시지에 명확.
- **패치 후**: 조용히 진행해 `opencode 없음: /.opencode/bin/opencode (install.sh 실행 필요)` 로
  종료. 운영자는 무관한 install.sh 를 재실행하며 시간을 버린다.
- `secrets.env` 소싱 지점(256행)도 같은 패턴 — API 키 미주입이 아무 신호 없이 통과할 구조.

형제 스크립트(`opencode-serve-ctl.sh`·`skillpack-update-check.sh`)는 여전히 bare `$HOME` 으로
`set -u` 아래에서 의도적으로 크게 죽는다 — 이 diff 만 느슨한 방향으로 이탈했다는 관례 불일치까지 지적.

`silent-failure-hunter` 는 추가로 **워크트리 비대칭**을 잡았다: 락 식별자는
`git rev-parse --git-common-dir`(156행)로 워크트리를 한 프로젝트로 묶는데, 정책 탐색은 raw `RUN_DIR`
기준이라 같은 저장소의 두 워크트리가 **직렬화는 공유하면서 서로 다른 정책으로 갈릴** 수 있었다.
→ fix `7cc536e` 에서 정책 탐색을 `git rev-parse --show-toplevel` 기준으로 바꾸고 `HOME` 가드를 복원.

### Task 2 R1 — `402` 앵커의 오탐 (🔴, 자기 아카이브 로그로 재현)

`silent-failure-hunter` 가 이 저장소의 **실제 위임 로그(`.orchestrate/task2.log`)** 로 재현했다:
넓힌 `402` 앵커가 `timestamp=...402Z`·messageID 를 매칭해 0→3건의 새 매치를 만들고,
파괴적 stall-watchdog 의 발동 조건이 실제로 충족되는 구간이 존재했다. 성공한 위임이 조용히
폐기될 수 있는 경로 — 이 페이즈가 없애려던 실패 모드 자체다. → `status.?402` 로 좁힘.

🟠 는 `FAIL_RE` 주석에서 "stream 오류 뒤 내부 재시도로 회복한 실행을 오판하지 않기 위해 좁게
유지한다"는 설계 근거가 삭제된 것 — 다음 사람이 같은 실수를 반복할 지식 손실. → `32a1022` 로 복원.

### Task 3 R1 🟠 — 문서 표면 과소측정 (reject_cause: **spec**)

`code-reviewer` 가 Task 3 산출물 자체는 SIGN OFF 하면서, `README.ko.md`·배포 스킬 사본·
프로젝트 템플릿 로스터가 옛 서술로 남았다고 🟠. **원인은 위임이 아니라 오케스트레이터의 실측
범위**였다 — 착수 전 grep 을 `README.md docs/WORKFLOW{,.ko}.md` 3파일로 한정해서 돌렸다.
→ Task 4 를 신설해 정정(`8cc33cd`), 지시서 전제 실측 표에 "뒤집힘 (사후)"으로 기록.

### 구조 리뷰 — 게이트 아님, 부채 4건

1. `tests/test_run_delegation.py` 1295→1563줄 (800 max 의 1.95×). 신규 2클래스는 상속 대신
   `setUp = RunDelegationTest.setUp` 식 **프라이빗 메서드 차용** — 스위트 시간 배가를 피한
   근거 있는 선택이지만, 부모가 헬퍼 시그니처를 바꾸면 상속 체인에 안 보이는 채로 조용히 깨진다.
2. **`run-delegation.sh:447` 잔여 드리프트** — `MODEL_EXHAUSTED` 안내가 호스트 경로를 하드코딩해,
   프로젝트 정책으로 돈 실행에서도 호스트 경로만 가리킨다. 이 페이즈가 없애려던 문제를 한 줄에서 재현.
3. 정책 해석 지식의 비대칭 — `model-doctor.sh` 는 여전히 host 고정 + 수동 `--policy`.
4. 문서 표면 **7파일**이 같은 사실을 되풀이 — 이번 페이즈 안에서 이미 1회 드리프트 비용 지불(Task 3→4).

분할 후보: `tests/support/delegation_harness.py` 믹스인 추출 + 정책/시그니처 테스트 파일 분리 /
문서 7곳 → `docs/WORKFLOW.md §05` 단일 출처 + 링크.

### Task 5 — 구조 리뷰 지적을 이 페이즈 안에서 소화 (사용자 판단)

구조 리뷰어는 `run-delegation.sh:447` 을 "다음 페이즈 1순위"로 분류했으나, GATE 2 에서
사용자가 **이번 페이즈 Task 5 로 처리**를 선택했다. 한 줄 수정이지만 전체 TDD 사이클
(동결 RED 2 → 위임 → 리뷰어 3인)을 그대로 돌렸다.

RED 확정 과정에서 **함정 36 계열을 한 번 더 실측**했다: 처음에는 출력 전체
(`stdout + stderr`)를 건초더미로 삼았는데, `POLICY_USED=` 줄이 경로 단정을 대신 충족시켜
**안내 줄을 전혀 고치지 않은 구현도 통과**하는 약한 계약이었다. 안내 줄(`사용자에게 보고할 것`
포함 줄, 정확히 1줄) 만 격리하도록 좁히자 양성·음성 둘 다 RED 가 됐다.

`silent-failure-hunter` 가 변이 검증으로 계약의 강도를 증명했다:

| 변이 | 결과 |
|---|---|
| A: 원래 호스트 리터럴(`~/.config/...`)로 되돌림 | 두 테스트 **모두 FAIL** |
| B: `$PROJECT_POLICY` 를 무조건 하드코딩 | 음성 가드 **FAIL** (양성만 통과) |

고정 후보 경로로는 둘 다 만족할 수 없고 **실사용 `$POLICY` 추적만** 통과한다.
세 리뷰어 모두 `set -u` 안전성을 독립적으로 검증했다 — `POLICY=""`(76행) 초기화 후
if/elif 무조건 할당(85·88행), else 는 `exit 64`(92행) 이므로 447행 도달 시 항상 실경로다.

## 이 페이즈에서 실측된 사고 — 리뷰 결과 고아화

마지막 리뷰어 2개(task4 문서 리뷰·구조 리뷰)를 띄운 뒤 `sleep 290` 백그라운드 명령으로 결과를
**폴링 대기**하다가, 리뷰어가 완료 알림을 보낸 뒤에도 세션이 대기 상태에 묶여 소비하지 못했고
그대로 강제 종료됐다. 리뷰 2건은 정상 완료된 채 고아가 됐다.

**회수 경로**: 결과는 유실되지 않는다 — 세션 트랜스크립트
(`~/.claude/projects/<슬러그>/<세션>.jsonl`)의 `type: queue-operation` 항목에 `<result>` 전문이
남는다. 다음 세션에서 그 필드를 파싱해 전량 회수했다. → PITFALLS 37.

## 검증 총괄

| 명령 | 결과 |
|---|---|
| `python3 -m unittest discover -s tests` (메인 체크아웃, 병합 후) | 404 tests, 실패 0 |
| 〃 (워크트리) | 404 tests, 실패 10 — **전부 함정 24**(서브모듈 미초기화). 메인에서 해당 29건 green 대조 확인 |
| `python3 -m unittest tests.test_run_delegation` | 93 tests, OK (Task 5 전 91 → 동결 RED 2 추가) |
| `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` | 무출력 |
| `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |

## 다음 페이즈 권고

구조 리뷰어 권고 1번(`run-delegation.sh:447`)은 **이 페이즈 Task 5 로 해소**했다. 남은 것:

1. 문서 7곳 → `docs/WORKFLOW.md §05` 단일 출처 + 링크 구조로 통합.
   이 페이즈 안에서 이미 1회 드리프트가 실측됐고(Task 3→4) 리뷰 사이클 하나를 소모했다.
2. `tests/test_run_delegation.py` 분할 — 공유 하네스 믹스인(`tests/support/delegation_harness.py`)
   추출부터. Task 5 가 `_redacted_result` 를 모듈 수준으로 올려 두 클래스가 공유하게 만든 것이
   같은 방향의 첫 걸음이다. `test_kit_doctor.py`(810줄) 분할과 같은 축으로 묶으면 비용 절감.
3. **`core/scripts/session-cost.py:project_dir()` 슬러그 버그** (PITFALLS 38) —
   `str(Path.cwd()).replace("/", "-")` 가 `.` 를 처리하지 않아, **워크트리에서 시작한 세션은
   비용을 잴 수 없다**. 워크트리가 표준 절차인 이 저장소에서 정량 3필드의 비용 필드가
   구조적으로 `미측정` 이 된다. 한 줄 수정(`.replace(".", "-")` 추가)이지만 소스라 위임 필요.
4. `core/opencode/model-doctor.sh` 의 정책 경로 비대칭 — 여전히 host 고정 + 수동 `--policy`.
   자동 인식을 넣으면 그때는 `run-delegation.sh` 와 진짜 로직 중복이 되므로 공용화와 함께 볼 것.
5. (task4 리뷰 🟡) `.opencode/agent/{kit-tests,kit-scripts,kit-docs}.md:4` ·
   `core/project-template/.opencode/agent/_example.md:4` 의 host 경로 단독 언급 주석 정리 — 잡무성.
