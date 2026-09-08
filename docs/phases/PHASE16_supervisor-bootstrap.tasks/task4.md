---
task: 4
status: done
---

## Task 4: 마감 — 검증 총괄·structure-reviewer·frontmatter·INDEX
- **에이전트**: 오케스트레이터 직접 (docs/phases 편집 허용 범위)
- **선행**: 1b·2b·3 전부 done
- **목표**: 페이즈를 홈 감독이 push·PR·병합할 수 있는 상태로 만든다.
- **절차**:
  1. `python3 -m unittest discover -s tests -v; echo "exit=$?"` 전체 초록 · `bash scripts/hook-selfcheck.sh` PASS · `git stash list` 비어 있음 · `git status --short` 비어 있음(미커밋 없음).
  2. `structure-reviewer`를 **1회** 호출 (Agent, 읽기 전용) — 전달물: `git diff main..HEAD --stat`와 누적 diff. 산출물은 게이트가 아니다 → 인덱스 "후속 제안"에 요약.
  3. 인덱스 frontmatter: `status: done`, `commits:` (task 커밋 SHA 목록, 병합 커밋 제외), `cost:` = `python3 scripts/session-cost.py --json` 실측(이 파트 세션 ID는 프롬프트에 주어짐 — `--session <id>`), `compactions:`·`interventions:` 수기.
  4. task 목록 표 상태를 `tasks 16` JSON과 일치시키고, 새 함정이 있으면 `docs/phases/PITFALLS.md` append + CLAUDE.md 한 줄 인덱스.
  5. `python3 scripts/docs-index.py` → INDEX 재생성. `HANDOFF.md` 삭제.
  6. 커밋: `docs(phase16): 페이즈 마감 — status done, 정량 3필드, 구조 리뷰 요약` (경로 명시 `git add docs/phases CLAUDE.md`).
  7. 마지막 메시지 마지막 줄: `PART_DONE 16-2 next=none`. **push·PR 생성 금지** — 홈 감독이 한다.
- **완료 조건**: 위 6까지 완료 + `git log --oneline main..HEAD`에 마감 커밋 포함.

## 실행 기록 (파트 16-2, 2026-09-02)

1. 검증 총괄 — 인덱스 `## 검증 총괄` 표 참조. `git stash list` 비어 있음, `git status --short` 마감 커밋 직전 비어 있음.
   "전체 초록"은 **미달성**: 선재 실패 10건(서브모듈 미초기화, 함정 24)은 워크트리에서 init 하면
   `phase-close` 가 크래시하므로(함정 7) 남겼다. 파트 16-1 목록과 동일 → 회귀 0.
2. `structure-reviewer` 1회 호출 완료 — 부채 5 / 분할 후보 4, 요약은 인덱스 `## 구조 리뷰`·`## 후속 제안`.
3. frontmatter: `status: done`, `commits: 16825fa..b5f98ba (+ 마감 커밋)`, 정량 3필드 기입.
   **비용 측정 방법**: 이 파트 세션은 워크트리에서 시작해 `session-cost.py --project .` 이 실패한다(PITFALLS 38).
   점 자리에 `-` 를 넣은 유사 경로로 슬러그를 맞춰 실측했다 —
   `--project /home/jh/aigsprac/-claude/worktrees/phase16-supervisor-bootstrap`:
   전체 4파일 $15.31 / 파트 16-1(54679ff8) $8.42 / 파트 16-2(22a81052) $3.20(마감 시점) / 1회차 프로브 2건 $3.68.
   메인 슬러그(`--json` 기본) 는 `{"files": 3, "usd": 62.476472, "usd_complete": true}` — 홈 감독 세션 누적이며
   이 페이즈 외 작업이 섞여 있어 분리 불가. 감독이 기록한 파트 16-1 $20.05(1회차 $3.14+$1.04)와
   스크립트 실측 $8.42 는 **어긋난다** — 집계 기준(캐시 토큰·서브에이전트 포함 여부)이 다른 것으로 보이며 미해소, 양쪽 병기.
4. 새 함정 2건: PITFALLS 38 **갱신**(절반 해소 + 유사 경로 우회), PITFALLS **39 신설**
   (`tasks` 가 접미사 task 를 조회에서 누락하고 `--set 1a=` 를 거부 — `complete` 거짓 완료 위험).
   CLAUDE.md 한 줄 인덱스 3건 갱신/추가(PITFALLS 33 해소 표기 포함).
5. `python3 scripts/docs-index.py` 재생성. **`HANDOFF.md` 는 삭제하지 않고 갱신했다** — 감독 프롬프트의
   명시 지시(파트 종료 시 HANDOFF 갱신·커밋). 페이즈 마감 삭제는 홈 감독이 병합·`phase-close` 시 수행한다.
6. 마감 커밋(경로 명시).

## 구조 리뷰 상세 (structure-reviewer, 2026-09-02 — 게이트 아님)

대상: `git diff main..HEAD` 18파일 +1171/-23. 코드 변경은 `core/scripts/phase-tools.py`(+36, 724→750줄)와
`core/scripts/session-cost.py`(+86/-23, 97→153줄) 둘뿐이고 나머지는 문서·템플릿.

**부채 5건**

1. **`find_root()`(phase-tools.py:54-60) ↔ `main_checkout()`(session-cost.py:28-42) 중복** — 둘 다
   `git rev-parse --git-common-dir` 로 메인 체크아웃을 푼다. 이번 페이즈가 두 번째 구현을 새로 썼다.
   견고성이 갈렸다: `main_checkout()` 은 `start` 를 명시로 받고 `git -C` 를 쓰며 `FileNotFoundError` 를
   잡아 cwd 로 폴백한다(테스트 `test_missing_git_binary_falls_back_to_cwd`). `find_root()` 는 cwd 암묵
   참조에 예외를 그대로 전파 — PATH 없는 환경에서 `tasks` 가 트레이스백으로 죽는다.
2. **`session-cost.py:main()` 35→65줄(1.3×)** — 전량 이번 페이즈 기여. argparse 추가 + `--json`/표
   이중 출력 분기가 `print` 마다 인라인돼 파싱·해석·집계·직렬화 2종이 한 함수에 섞였다.
3. **`phase-tools.py:cmd_tasks` 73→84줄(1.68×)** — 이미 초과한 함수에 폴백 재탐색·stderr 통지를 더했다.
4. **`phase-tools.py` 파일 724→750줄(0.94×)** — 상한 800 근접. `cmd_close`(1.66×)·
   `cmd_dashboard_mounts`(1.8×)·`_janitor_inner`(2.12×) 등 기존 초과 함수 4개를 안은 채 계속 커진다.
5. **`.claude/part-protocol.md` ↔ 어댑터 사본이 바이트 동일 수동 복사** — 다음 수정에서 드리프트가 난다.
   (`part-allowed-tools.txt` 의 차이는 감독 결정에 따른 **의도적 분기**임을 리뷰어가 확인.)

**분할 후보 4건**: `core/scripts/_gitroot.py` 신설(호출부 2, 난이도 낮음) ·
`session-cost.py` 에 `_emit_json`/`_emit_table` 추출(파일이 153줄이라 새 파일은 과함) ·
`cmd_tasks` 를 `apply_task_status()`/`list_tasks()` 로 분리 ·
`part-protocol.md` 단일 소스화(stamp 생성 또는 등가성 체크).

**긍정 판정**: 신규 테스트(`WorktreeTasksTest` 9 + `test_session_cost.py` 8)가 출력 문자열 정확일치가
아니라 경로·provenance·exit code 계약이다(PITFALLS 29 교훈 적용 확인). 함수 비대는 리뷰 반려 대응으로
"폴백 무신호"·"경로 탈출"·"침묵 $0" 을 잡은 대가 — 무규율 축적이 아니라는 근거로 기록.
