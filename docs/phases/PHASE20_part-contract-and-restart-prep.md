---
phase: 20
date: 2026-09-23
kind: task
domain: template, commands, tests, docs
status: done
commits: cc5bcc8..dbed45f (+ 마감 커밋)
cost: 미측정 — 홈 세션이 Claude 서브에이전트로 수행(구현 ≈190K·후속 ≈60K·리뷰 ≈100K 토큰, session-cost.py 경로 밖)
compactions: 0 (서브에이전트 보고 기준)
interventions: 1 (리뷰 SIGN OFF + MEDIUM 1건 후속 커밋 → 재검수)
summary: 파트 계약 파일 수선(죽은 허용목록 3줄 은퇴·프로토콜 일반 규율 4건 이식·rules/ 컨벤션·QUEUE 템플릿) + /restart-prep 커맨드 키트 자산화
---

# 작업 지시서 — 파트 계약 수선 + /restart-prep 키트 자산화 (2026-09-23)

## 근거

tobuilder 4저장소(backend·bot·console·infra)가 2026-09-16~22 사이에 파트 계약 파일에서 실측한 것 중
**저장소에 묶이지 않은 일반 규율**을 키트 템플릿으로 승격한다. 각 항목의 출처는 「변경 목록」에 적었다.
홈 세션 손 설치본인 `~/.claude/commands/restart-prep.md` 는 키트에 원본이 없어 감독 재시작 절차가 호스트마다
따로 놀 수 있었다 — Phase 17 이 `supervise*.md` 를 이관한 것과 같은 결로 옮긴다.

## 템플릿 위치 확정 (실측)

| 대상 | 위치 | 근거 |
|---|---|---|
| 파트 허용 목록·프로토콜·`.claude/rules/` | `adapters/claude/project/.claude/` | `lib/stamp.sh` `stamp_copy` 가 `core/project-template` → `core/scripts` → `adapters/<harness>/project` 순으로 복사(`lib/stamp.sh:42-52`). `.claude/` 는 claude 전용이라 어댑터 쪽 |
| `docs/phases/QUEUE.md` | `core/project-template/docs/phases/` | 하네스 무관 문서라 core. codex 단독 스탬프에도 찍힌다(테스트로 고정) |
| `/restart-prep` 커맨드 | `adapters/claude/global/commands/` | 매니페스트 행 `claude tree adapters/claude/global/commands .claude/commands`(`core/install-manifest.tsv:12`) 하나로 `supervise.md`·`supervise-PROJECT.md.tpl` 과 같이 깔린다 — 새 행 불필요 |

## 범위

1. `part-allowed-tools.txt`: `.orchestrate/` 를 겨냥한 죽은 3줄을 `Bash[...]` 로 은퇴 + 머리 주석 4줄(주석은 은퇴가 아니다).
2. `part-protocol.md`: 일반 규율 넷 이식 — 삭제·이동은 `kind: blocked` 에스컬레이션 · `;`/`&&` 금지(리뷰어 프롬프트 한 줄 포함) ·
   `ts` 는 `date -Iseconds` 두 명령 · `| tail` 금지(종료코드 가림).
3. `.claude/rules/README.md` + `pitfalls-example.md` 신설(경로 조건부 함정 인덱스 컨벤션).
4. `core/project-template/docs/phases/QUEUE.md` 신설(빈 7열 표 · 상태 어휘 · `^true` 접두일치 계수 규칙).
5. `adapters/claude/global/commands/restart-prep.md` 신설(호스트 전용 값 0).
6. 테스트: `tests/test_stamp.py` +2 · `tests/test_kit_doctor.py` `SupervisorManifestTest` 단언 추가.

## 비범위 (넣지 않은 것과 이유)

- **저장소별 도구 줄**(npm·docker·terraform·psql 등): 4저장소 교집합 − 키트 = **0 줄**(실측 `comm`) — 공통이면서 키트에 없는 줄이 없다.
- backend 허용목록의 `Bash(node .orchestrate/:*)`·`Bash(./node_modules/.bin/:*)`·`git check-ignore` 등: 한두 저장소에만 있어 프로젝트 사본 몫.
- infra 프로토콜의 「파이썬 린터 8종 부재」 고지·`git rm` 을 «열지 않기로 한 사용자 결정»·Phase/파트 번호·측정 표본 수의 저장소 이름: 호스트·프로젝트 전용.
- console 프로토콜의 「삭제(`git rm`)·이동은 오케스트레이터가 직접 한다」: console 허용목록에 `git rm` 이 있어 성립하는 저장소별 규칙. 키트 기본 허용목록엔 없으므로 infra 판(에스컬레이션)을 일반형으로 택했다.
- bot 프로토콜의 「이벤트 최소 집합」(`part_start`·`delegation_*` …)·console 의 `events:check` 검증기: 유용하지만 이번 범위(넷)에 없고 스키마 결정이 필요해 후속 후보로만 남긴다.
- `restart-prep.md` 의 CTO 인박스 절: 키트에 CTO 계층이 없어 「인박스 파일이 있으면 한 줄」 조건부로 축약.
- 기존 프로젝트로의 전파(adopt 재실행): 프로젝트별 감독 세션 소관.
- `docs/phases/QUEUE.md`·`INDEX.md`(키트 자기 것): 지시대로 미수정.

## DoD

- [x] 죽은 3줄이 소괄호 형태로 남아 있지 않고(`grep` 0), 대괄호 은퇴 줄 3 + 머리 주석 4줄 이내.
- [x] 프로토콜 템플릿에 프로젝트 명사·큐 id·Phase 번호 없음(`grep -nE 'tobuilder|Phase [0-9]|파트 [0-9]+-[0-9]|/home/jh|\b[CFIK]-[0-9]+'` 0줄).
- [x] `restart-prep.md` 에 `tobuilder|/home/jh|-home-jh` 0줄(테스트로도 고정).
- [x] `new-project.sh` 실물 스탬프에서 새 파일 셋(`rules/README.md`·`rules/pitfalls-example.md`·`docs/phases/QUEUE.md`)이 나오고 `__PROJECT__` 치환됨.
- [x] 테스트 회귀 0 (기준선 468 → 아래 표).
- [ ] draft PR · 리뷰 SIGN OFF · CI 초록 (감독 몫).

## 검증 (2026-09-23, 워크트리 루트, 한 줄씩)

| 검증 | 명령 | 결과 |
|---|---|---|
| 전체 테스트 | `python3 -m unittest discover -s tests` | 기준선 `Ran 468` / `FAILED (failures=10)` → **`Ran 470`** / `FAILED (failures=10)` — **회귀 0**, 선재 실패 10건은 동일 집합(`test_install_dashboard_container` 9 + `test_install_container_step` 1, 서브모듈 미초기화 — PHASE17 검증 총괄과 같다) |
| 페이즈가 더한 테스트 | — | `test_stamp.py` 7 → 9 (+2). `test_kit_doctor.py` 는 기존 테스트 안에 단언 추가(개수 불변) |
| bash 문법 | `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` | exit 0 |
| 훅 자가진단 | `bash scripts/hook-selfcheck.sh` | `HOOK_SELFCHECK_PASS` |
| 실물 스탬프 | `HOME=<scratch>/fakehome bash new-project.sh <scratch>/stampdemo demoproj --claude` | exit 0. 새 파일 5종 존재, 플레이스홀더 잔존 0, 은퇴 줄 3. (감독 자산은 가짜 HOME 이 봉쇄 범위 밖이라 의도대로 거부 — 스캐폴드와 무관) |
| 매니페스트 설치 | `SupervisorManifestTest` (`--add-missing` 격리 HOME) | `restart-prep.md` 설치 확인 |

## 변경 목록 (출처)

| 파일 | 변경 | 출처 |
|---|---|---|
| `adapters/claude/project/.claude/part-allowed-tools.txt` | 3줄 `Bash[...]` 은퇴 + 머리 주석 4줄 | `~/tobuilder-backend/.claude/part-allowed-tools.txt` 주석 블록(2026-09-17 실측 · 2026-09-22 3중 대조) · infra 판은 3줄 삭제 · 키트 `core/supervisor/PROCEDURE.md:108` 의 bare `mapfile` 이 주석을 거르지 않음을 확인 |
| `adapters/claude/project/.claude/part-protocol.md` | 106 → 137줄. ① 「파일 삭제·이동」 소절 ② 리뷰어 프롬프트 `;`/`&&` 한 줄 ③ 검증 명령 규칙 정정 ④ `ts` 두 명령 | ① infra `:23-37`(2026-09-21) ② infra `:48-51`(2026-09-20 Phase 35) ③ infra `:55-67` — backend·bot·console 은 옛 키트 문장(「파이프 금지 — 종료코드 가림」) 그대로라 셋 중 실측으로 정정된 infra 판을 택하되 `| tail` 금지는 «거부가 아니라 초록이 거짓» 이유로 유지 ④ infra `:73-96` · backend `:61-64` · bot `:37-57` · console `:57` — 네 판 일치 |
| `adapters/claude/project/.claude/rules/README.md` (신설) | 컨벤션: 파일명 `pitfalls-<도메인>.md` · `paths:` frontmatter · 한 줄 함정 · CLAUDE.md 상시 함정 5줄 이내 · 은퇴 규칙 · `claude -p` 조건부 로드 실측 | `~/tobuilder-backend/.claude/rules/pitfalls-*.md`(7) · `~/tobuilder-bot/.claude/rules/`(2) · backend `CLAUDE.md:154` · 메모리 `tobuilder-scaffold-replay-fixes-2026-09.md`(2026-09-19, claude 2.1.277) |
| `adapters/claude/project/.claude/rules/pitfalls-example.md` (신설) | bot `pitfalls-testing.md` 형식의 예시 | `~/tobuilder-bot/.claude/rules/pitfalls-testing.md` |
| `adapters/claude/project/CLAUDE.md` | 함정 절 인용 블록에 rules 분리 한 줄 | backend `CLAUDE.md:154` |
| `core/project-template/docs/phases/QUEUE.md` (신설) | 머리·빈 7열 표·칸 규약·상태 어휘·`^true` 계수 규칙 | 키트 `docs/phases/QUEUE.md` 머리 형식 · `~/tobuilder-bot/docs/phases/QUEUE.md` 머리 주석(2026-09-20: 완전일치 8 vs 접두일치 111) · bot 메모리(`done` 부분일치 함정) |
| `adapters/claude/global/commands/restart-prep.md` (신설) | 137 → 142줄. 호스트별 주의 소절 격리 · 런처 문구 일반화 · CTO 절 조건부 한 줄 · 메모리·프로젝트 경로 상대화 | `~/.claude/commands/restart-prep.md`(2026-09-23) |
| `.claude/part-allowed-tools.txt`·`.claude/part-protocol.md` (키트 루트 dogfood 사본) | 템플릿과 동기화(리뷰 MEDIUM). 보존한 전용 줄: `Bash(python3 -m unittest:*)`·`Bash(bash -n:*)`·`Bash(cp:*)`·`Bash(diff:*)`·`Bash(rsync:*)`·`tee -a` 절대경로. 프로토콜은 전용 문장 없음 — Phase 17 의 LESSONS.json 절도 이번에 같이 들어옴(루트 사본이 그 전 판이었다) | 리뷰 지적 2026-09-23 |
| `tests/test_stamp.py` | +2 테스트 | — |
| `tests/test_kit_doctor.py` | `SupervisorManifestTest` 에 restart-prep 단언 4 + 설치 단언 1 | — |

## 확신 없는 것

- ~~`Bash[...]` 대괄호의 비허가는 재지 않았다~~ → **리뷰에서 실측됨(2026-09-23, `claude -p --allowedTools` 4건)**: 소괄호 줄 → 허가·실행됨 ·
  `# ` 주석 접두 줄 → 실행됨(주석은 은퇴가 아니다, 확인) · 대괄호 줄 → 거부됨(`permission_denials` 기록) · 대괄호+후행 주석 → 거부됨.
  머리 주석 4줄을 포함한 파일 전체를 `mapfile` 로 넘겨도 spawn 은 죽지 않는다. ⇒ 은퇴 규칙은 추론이 아니라 실측이다.
- 프로토콜 ③의 「`until … done` 대기 줄은 `until` 접두 하나로 허가된 예외」는 기존 문장(「3회 연속 성공」)에서 옮긴 것이지 이번에 다시 재지 않았다.
- `restart-prep.md` 의 REST 체크 API 경로는 원문의 「REST 로 본다」를 구체화한 것으로, 이 워크트리에서 호출해 보지 않았다.
