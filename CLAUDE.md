# aigsprac — Claude 오케스트레이터 가이드

## 역할

이 프로젝트에서 claude는 **오케스트레이터**다.

- 기획안·작업 지시서 작성, 작업 분해(플랜 수립)를 담당한다.
- 오케스트레이션 절차는 **`/orchestrate` 스킬**(전역, `~/.claude/skills/orchestrate/`)을 따른다:
  인터뷰 → task 세분화 → `scripts/run-delegation.sh` 위임 → 도메인 리뷰어 검수.
- 에이전트 로스터·검증 명령: **`.claude/orchestrate.md`** (에이전트 정의는 `.opencode/agent/*.md`)
- 소스 코드는 직접 수정하지 않는다 — 위임한다. 직접 수정 가능: `docs/phases/`, `.claude/`.

## 세션 운영

- **프로젝트 확인 가드**: 요청이 이 프로젝트(aigsprac)와 무관해 보이면 — 다른 프로젝트의
  파일을 다뤄야 하면 — 진행하지 말고 AskUserQuestion으로 먼저 확인한다. 원격 클라이언트가 직전에
  쓰던 다른 프로젝트 세션에 붙은 채로 요청이 들어와 엉뚱한 프로젝트에서 페이즈가 수행된 실측
  사례가 있다 (2026-07-27).
- **페이즈 경계 = 세션 경계**: 페이즈 완료(지시서 아카이브 + 리뷰 문서 커밋) 후에는 세션을 정리하고,
  다음 페이즈는 **새 세션**으로 시작하도록 안내한다. 상태는 `docs/phases/PHASE*.md`와 `docs/phases/INDEX.md`에
  외부화되어 있으므로 새 세션 재시동 비용이 낮다. auto-compaction이 반복되는 장수 세션은 요약
  품질을 통제할 수 없고 비용도 크다 — 컴팩션에 의존하지 말고 명시적으로 끊을 것.
- **병렬 세션**: 같은 프로젝트에서 두 번째 세션이 동시에 작업해야 하면 메인 체크아웃이 아니라
  `.claude/worktrees/phase<N>-<slug>` 워크트리에서 진행한다 (전역 /orchestrate 스킬 "병렬 세션" 절).
  워크트리가 격리하는 건 파일뿐 — opencode 위임은 `scripts/run-delegation.sh`의 락이 직렬화한다
  (v3: serve attach 시 **프로젝트별 락** — 같은 프로젝트끼리만 직렬, 프로젝트 간 병렬.
  standalone 폴백 시에만 전역 락).

## 프로젝트 개요

오케스트레이터(claude/codex) → opencode 위임 개발환경을 어떤 머신에든 재현하는 부트스트랩 키트.
`core/`(하네스 무관: 스크립트·opencode 설정·프로젝트 템플릿) + `adapters/<하네스>/`(스킬·훅·설정) +
`containers/browser`(브라우저 CDP·우회 fetch — 서브모듈 insane-cloak) 구조. 기술 스택: bash 3.2 호환 셸 스크립트,
python3 unittest, jq, docker compose. 서비스 포트 없음(설치 키트).
이 저장소 자신이 키트의 첫 사용자다(도그푸딩) — `scripts/*`는 `core/scripts/*` 심링크.

## 검증 명령 (위임 결과 검수 시 필수)

```bash
python3 -m unittest discover -s tests -v   # 저장소 루트에서 (python3는 PATH에 있음)
bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh   # bash 문법
bash scripts/hook-selfcheck.sh             # 훅 자가진단 (HOOK_SELFCHECK_PASS 기대)
```

## 브랜치 규칙

- 기본 브랜치 `main` — 직접 push 금지. 작업은 `feat/*`·`fix/*` 브랜치에서 진행 후 병합한다.

## 이 저장소의 함정 (반복 금지)

> 실측으로 확인된 함정만 남긴다. 페이즈 중 새 함정이 실측되면 완료 보고 때 여기 append한다.
> (형식: 무엇을 하면 → 무엇이 죽는지 → 실측 날짜) — **상세는 `docs/phases/PITFALLS.md`**

- **`INSTALL_PARSE_ONLY` 로 메뉴 동작을 검증하지 말 것** — 메뉴 코드가 정의되기 전에 종료되므로
  기능을 통째로 지워도 통과하는 "항상 참" 테스트가 된다. 메뉴는 `INSTALL_SELFTEST_MENU` 로 검증하고,
  **새 테스트마다 저장소 밖 사본에서 변이 검증**을 할 것 (2026-08-10 Phase 1 에서 6회 실측).
- **커밋 메시지에 heredoc·명령치환을 쓰지 말 것** — bash-guard 가 차단한다.
  트리거 단어가 필요하면 단순 `-m "..."` 여러 개를 쓴다 (2026-08-10 실측 3회).
- **병렬 위임 중 `git add .`·`git commit -a` 금지** — 워크트리 작업 트리는 공유되므로 다른 task 의
  미완성 산출물이 함께 커밋된다. 경로를 명시할 것 (2026-08-10).
- **서브모듈을 init 한 워크트리는 phase-close 가 크래시한다** — `worktree remove` 가 rc=128 거부.
  병합 확인 후 `git worktree remove --force --force` 수동 제거 → close 재실행 (2026-08-11).
- **위임 에이전트에게 `/tmp` 에 쓰라고 하지 말 것** — `external_directory` 자동 거부로 런이
  보고 없이 종료된다. 변이·스크래치 사본은 `.orchestrate/mut<task>/`(gitignore)에 (2026-08-11).
- **RED 단계(`<N>a`) task 에 변이 검증을 요구하지 말 것** — 변이시킬 구현이 아직 없어
  항상 참인 검증이 된다. 변이 검증은 구현 task(`<N>b`)의 완료 조건에 (2026-08-11).

- **`pgrep -f`로 위임 프로세스를 폴링하지 말 것** — 감시 루프 자신의 명령줄이 패턴에 매칭되어
  무한 루프가 된다. `scripts/run-delegation.sh`(launch PID 대기)를 쓸 것.
- **`timeout N opencode run`으로 위임을 죽이지 말 것** — opencode 전역 세션 DB 트랜잭션이
  오염되어 다음 실행이 init에서 무한 대기하고 연쇄된다.
- **위임 프롬프트에 프로젝트 밖 절대경로를 "읽어라"고 쓰지 말 것** — opencode가
  `external_directory` 권한으로 차단하고 에이전트가 그 자리에서 포기한다. 외부 파일 내용은
  오케스트레이터가 읽어서 프롬프트에 인라인할 것.
- **`scripts/` 는 `core/scripts/` 로의 심링크다** — 작업용을 고치면 vendored 원본과 갈라진다.
  항상 `core/scripts/` 를 고칠 것.
- **설치 스크립트 테스트가 실제 홈을 오염시킬 수 있다** — `apply-plan-profile.sh` 는 기본값이
  `~/.claude/agents` 다. 테스트에서는 반드시 `--agents-dir`·`--settings` 주입 플래그를 쓸 것.
- **락 없이 `opencode run` 을 동시에 띄우면 토큰 0개·exit 0 으로 침묵사한다** — 위임은 반드시
  `scripts/run-delegation.sh` 경유 (PITFALLS 9).
- **없는 에이전트 이름은 실패가 아니라 기본 에이전트 조용 폴백(rc=0)이다** — 래퍼가 exit 7 로 끊는다 (PITFALLS 10).
- **위임 스크립트를 고치는 페이즈에서는 그 스크립트로 위임하지 말 것** — 안정본 사본을 얼려 쓴다 (PITFALLS 13).
- **회귀 테스트는 오케스트레이터가 작성·동결하고 위임의 `tests/` 수정을 금지한다** — 위임에 맡기면
  단정이 약화된다(같은 계열 7회 실측, PITFALLS 14).
- **변이 검증은 `.orchestrate/mutation/` 에 저장소 전체를 복사해서** — `/tmp` 는 거부되고,
  스크립트만 복사하면 테스트가 원본을 참조해 변이가 무효다 (PITFALLS 15).
- **워크트리 위임 프롬프트에는 상대 경로만 쓸 것** — 부모 체크아웃은 외부 디렉터리로 거부되고
  에이전트가 파일을 하나도 고치지 않은 채 `DONE` 으로 끝난다. 검수는 `git status` 부터 (PITFALLS 16).
- **마법사 메뉴에 항목을 추가하기 전에 기존 테스트의 번호 하드코딩을 grep 할 것** — 새 항목이
  기존 번호를 밀면 순수 회귀가 난다(8건 실측). 집합 소속을 `[ -z ]` 로 추론하는 가드도 함께
  깨진다 — `case ",$LIST," in *,이름,*)` 로 직접 검사 (PITFALLS 23, 2026-08-14).
- **컨테이너 실기동 테스트는 서브모듈이 초기화된 체크아웃을 전제한다** — 프레시 클론에서는
  먼저 `git submodule update --init containers/browser components/usage-dashboard`. 단 워크트리
  안에서 init 하면 phase-close 가 크래시한다(함정 7) — PITFALLS 24 (2026-08-14).
- **로컬 main 미푸시 상태에서 `phase-claim.sh` 를 실행하지 말 것** — 낡은 origin/main 에서
  분기돼 페이즈 도중 리베이스가 필요해진다. claim 직후 `git merge-base HEAD main` 확인 (PITFALLS 25, 2026-08-17).
- **리뷰어 서브에이전트에게 워크트리를 줄 때는 읽기 전용 git 명령만 허용할 것** — 리뷰어가
  `git stash` 로 오케스트레이터의 미커밋 동결 테스트를 흔든 실측 사고가 있다. 리뷰 호출 전에
  작업을 커밋해 트리를 비우고, 리뷰 후 `git stash list` 로 잔재를 확인한다 (PITFALLS 26, 2026-08-17).
- **위임 산출물과 오케스트레이터의 `tests/` 수정을 한 커밋에 묶지 말 것** — 리뷰어가
  "위임이 동결 테스트를 무단 수정했다"는 🔴 오진을 낸다 (PITFALLS 27, 2026-08-17).
- **`unittest -k` 에 불리언 식(`"A or B"`)을 쓰지 말 것** — 0건 매칭으로 `NO TESTS RAN` + exit 0,
  즉 거짓 그린이 된다. 패턴은 하나씩 주고 `Ran N tests` 의 N 을 확인한다 (PITFALLS 28, 2026-08-17).
- **출력 블록에 필드를 추가하기 전에 정확일치 단정을 grep 할 것** —
  `grep -rn 'assertEqual(\s*result.stdout' tests/`. PITFALLS 23 의 출력 문자열 버전이며
  `DOCTOR=0` 한 줄 추가로 순수 회귀가 났다 (PITFALLS 29, 2026-08-17).
- **GNU `cp` 는 끊어진 심링크 쓰기를 자체 거부한다** — "밖에 파일이 생겼는가"로는 심링크 가드를
  증명할 수 없다(가드를 지워도 Linux 에선 유출 없음). 보고 형태를 단정하고, 변이 검증은
  **부모가 심링크인 경우**로 하라 (PITFALLS 30, 2026-08-17).
- **워크트리에서 만든 프로젝트 에이전트는 그 세션에서 호출되지 않는다** — 레지스트리가
  메인 체크아웃의 `.claude/agents/` 를 보므로 `Agent type not found` 가 난다. 병합 후 또는 새
  세션에서 첫 가동하고, 급하면 `general-purpose` 에 정의를 인라인해 대행 (PITFALLS 31, 2026-08-19).
- **동결 사본(함정 13)을 만들 때 `opencode-serve-ctl.sh` 도 같이 복사할 것** — 안 하면
  `SCRIPT_DIR` 이 어긋나 serve attach 를 잃고 standalone 전역 락으로 떨어진다. 부수 효과로
  그 페이즈의 개선은 그 페이즈 자신의 위임에 적용되지 않는다 (PITFALLS 32, 2026-08-19).
- **~~`phase-tools.py tasks` 를 진행 중 페이즈에 쓰지 말 것~~ (해소, 2026-09-02 Phase 16)** —
  `cmd_tasks` 가 워크트리 cwd 의 문서를 먼저 보고 없을 때만 메인으로 폴백(stderr 통지)하므로
  진행 중에도 조회·`--set` 이 동작한다 (PITFALLS 33 갱신).
- **`tasks` 는 `task<숫자>.md` 만 인식한다** — `task1a.md`·`task2b.md` 같은 접미사 task 는
  조회 JSON 에서 통째로 빠지고 `--set 1a=done` 은 거부된다. 접미사를 쓸 거면 상태 전이는
  frontmatter 직접 편집이고, `complete` 필드를 신뢰하지 말 것 (PITFALLS 39, 2026-09-02).
- **변이 검증 사본에서 `.orchestrate` 를 제외할 것** — 제외하지 않으면 사본이 이전 사본을 품어
  재귀 폭발한다(Phase 13 실측 61GB·372만 파일). `phase-close` 의 worktree remove 가 타임아웃으로
  죽는다. `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut<task>/` (PITFALLS 34, 2026-08-19).
- **동결 테스트를 파일 끝에 append 하면 `unittest.main()` 가드 뒤로 간다** — discover 로는 돌지만
  파일 직접 실행 시 그 클래스들이 조용히 누락된다(실패 아님, 건수만 줄어듦). append 후 가드를
  파일 끝으로 옮기고 건수를 확인할 것 (PITFALLS 35, 2026-09-01).
- **동결 픽스처에 실제 마커를 전부 넣을 것** — 빠뜨리면 올바른 구현이 오히려 실패하고 약한 추론이
  통과해, 리뷰 🔴 의 원인이 위임이 아니라 오케스트레이터의 계약이 된다 (PITFALLS 36, 2026-09-01).
- **서브에이전트를 `sleep` 폴링으로 기다리지 말 것** — 완료 알림을 소비하지 못한 채 세션이
  끊기면 리뷰 결과가 고아가 된다. 띄우고 턴을 끝내면 하네스가 깨운다. 이미 고아가 됐다면
  트랜스크립트의 `type: queue-operation` 에 `<result>` 전문이 남아 회수 가능 (PITFALLS 37, 2026-09-01).
- **`session-cost.py` 의 기준은 cwd 가 아니라 메인 체크아웃이다** — Phase 16 이후 `--project`
  미지정 시 `git rev-parse --git-common-dir` 의 부모 슬러그를 쓰므로 **워크트리에서 실행해도
  메인 체크아웃 세션은 정상 집계된다**(구 함정 해소). 다만 **세션 자체가 워크트리에서
  시작·이동한 경우**는 여전히 못 찾는다 — 슬러그가 `.` 를 `-` 로 바꾸지 않기 때문.
  그때는 `--project /<repo>/-claude/worktrees/<디렉터리>` 처럼 **점 자리에 `-` 를 넣은 유사 경로**를
  주면 슬러그가 맞아떨어진다(2026-09-02 실측). `importlib` + `collect([jsonl 경로])` 도 유효
  (PITFALLS 38, 2026-09-01/갱신 2026-09-02).
- **`__PROJECT__` 를 저장소 전역에서 일괄 치환하지 말 것** — `core/project-template/`·`docs/plans/`
  에는 플레이스홀더가 정당하게 존재한다. stamp 치환 범위를 넓히면 템플릿 원본이 클로버된다
  (2026-08-08 도그푸딩 실측 사고 — lib/stamp.sh 가 복사분만 치환하는 이유).
- **문서화된 심링크 진입점으로 동결 테스트를 돌릴 것** — 원본 직접 실행은 `retry-guard` fail-open을 놓친다 (PITFALLS 40, 2026-09-02).
- **위임 중 전체 스위트의 실패를 회귀 기준선으로 삼지 말 것** — 종료 후 오케스트레이터가 판정한다 (PITFALLS 41, 2026-09-02).
- **RED 작성 직후 실제 FAIL을 눈으로 확인할 것** — 이미 통과하는 테스트는 함정이 된다 (PITFALLS 42, 2026-09-02).
- **`retry-guard` 호출부에서 zero-padding을 금지할 것** — `phase`·`part` 문자열 비교가 가드를 fail-open시킨다 (PITFALLS 43, 2026-09-02).

## 주의

- `~/.config/opencode/secrets.env`·`.env` 류는 커밋·외부 전송 금지. 키 이름만 로그에 남긴다.
- 자기 소유가 아니거나 이미 운영 중인 라이브 CDP 컨테이너·세션은 조작 금지. 이 킷의
  `containers/browser` 번들을 본인이 직접 띄운 경우는 해당하지 않는다.
- 실제 `~/.claude`·`~/.config` 를 테스트에서 건드리지 말 것 (테스트는 임시 디렉터리로).
