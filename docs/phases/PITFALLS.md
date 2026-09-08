# 이 저장소의 함정 (상세)

> 실측으로 확인된 것만 남긴다. 형식: **무엇을 하면 → 무엇이 죽는지 → 실측 날짜**.
> 프로젝트 `CLAUDE.md` 에는 한 줄 인덱스만 두고 상세는 여기에 쓴다
> (베이스라인 컨텍스트가 커지면 autocompact 헤드룸이 줄어든다).

## 1. "항상 참인 assertion" — 이 저장소 최대의 함정 (2026-08-10, Phase 1 에서 **6회** 실측)

`install.sh` 는 테스트 훅 3종을 제공하는데 **각 훅이 스크립트의 서로 다른 지점에서 종료**한다:

| 훅 | 종료 지점 | 도달 가능한 것 |
|---|---|---|
| `INSTALL_PARSE_ONLY=1` | 인자 파싱 직후 | 인자 파싱만 |
| `INSTALL_DRY_RUN=1` | 1/7 프리플라이트 끝 | PM 감지·도구 계획·claude 계획 |
| `INSTALL_SELFTEST_MENU=1` | 메뉴 헬퍼 실행 직후 | 메뉴·안내 헬퍼 |

**`INSTALL_PARSE_ONLY` 로 "메뉴가 뜨지 않는다"를 검증하면 항상 통과한다** — 메뉴 코드가
정의되기도 전에 스크립트가 끝나기 때문이다. 메뉴 기능을 통째로 삭제해도, `[ -t 0 ]` 를 반대로
뒤집어도 그 테스트는 초록이다. 실측으로 4개 게이트를 전부 `true` 로 치환해도 3건 모두 PASS 했다.

같은 계열의 변종들:
- 같은 커밋에서 삭제한 문자열을 `assertNotIn` 하는 테스트 (가드가 깨져도 통과)
- `install.sh` **소스를 문자열로 검사**하는 테스트가 주석에만 매칭되는 경우
  (task 3c 에서 변수명이 `arg` → `_ecc_lang_arg` 로 바뀌었는데 단언은 옛 이름이 남은 주석을
  잡고 있었다 — 실제 대입을 `="BROKEN"` 으로 바꿔도 초록)
- 소스 검사 테스트가 **호출부 삭제는 잡지만 가드 조건 뒤집기는 못 잡는** 경우
  (`!= "1"` → `= "1"` 로 뒤집으면 실제 설치에서 안내가 절대 안 뜨는데도 통과)

**대응 — 변이(mutation) 검증을 규정으로 삼는다**: 새 테스트마다 **저장소 밖** 임시 디렉터리에
사본을 만들고 대상 로직을 깨뜨려 그 테스트가 실제로 FAIL 하는지 확인한다.
저장소 안의 파일을 깨뜨리지 말 것. **위임 에이전트의 변이 보고를 믿지 말고 검수자가 직접 재현할 것** —
위임 측 변이 harness 자체에 경로 버그(사본이 아니라 원본을 읽음)가 있어 "가짜 OK" 가 날 뻔했다.

## 2. 테스트를 시나리오별로 쪼갤 때 커버리지가 조용히 사라진다 (2026-08-10)

모놀리식 테스트가 `stdout` **전체 목록을 순서대로** 단언하고 있었는데, 읽기 쉽게 시나리오별로
분리하면서 각 테스트가 **자기 관심사만** 보게 됐다. 그 결과 "사용자가 엔터를 쳐서 기본값을
수락하는" 경로 — 실사용에서 가장 흔한 상호작용 — 의 **결과값을 보는 테스트가 하나도 남지 않았다.**
기본값 반환을 `MUTATED_EMPTY` 로 바꿔도 16건 전부 통과했다.

**대응**: 테스트를 쪼갤 때는 **원본이 덮던 것의 목록을 먼저 적고**, 분리 후 각 항목이 어느
테스트로 갔는지 대조한다. "메시지가 나온다"와 "값이 올바르다"는 **다른 단언**이다 — 폴백 경로는
둘 다 필요하다.

## 3. bash-guard 는 완화할 때마다 새 우회가 생긴다 (2026-08-10, 5라운드 연속)

`sudo`·`rm -rf` 오탐을 없애려고 "인용문 제거 후 명령 위치 매칭"으로 완화했더니 라운드마다
새 미탐이 나왔다 (`bash -c "sudo ls"` / `xargs sudo ls` / `/usr/bin/sudo ls` …).
인용문을 일반적으로 제거하는 순간 실행 경로가 무한히 생기는 **구조적 문제**다.

**대응**: 판정 방향을 뒤집어 **fail-closed + 좁은 예외**로 갔다 — 인용문 제거는
`git ... -m/--message` 페이로드 **하나만** 예외로 두고 나머지는 단어 경계 기준으로 차단한다.
대가로 `echo "no sudo here"` 류는 계속 과차단되지만, **과차단은 이 가드의 안전한 실패 방향**이다
(보안 경계가 아니라 실수 방지 장치다).

**따라오는 규약 — 커밋 메시지**: 트리거 단어(`sudo`·`rm -rf`·`docker compose down` 등)를 써야 하면
**단순 `-m "..."` 을 여러 개** 쓴다. heredoc·명령치환(`-m "$(cat <<'EOF' …)"`)은 차단된다
(실측 3회). 위임 프롬프트 파일도 heredoc 대신 Write 툴로 만드는 편이 안전하다.

## 4. phase-claim 워크트리는 `origin/main` 기준이다 (2026-08-10)

`scripts/phase-claim.sh` 가 만드는 워크트리는 `origin/main` 에서 갈라지므로, 로컬 feature
브랜치에만 있는 **미푸시 커밋(설계 스펙 등)이 빠진다.** claim 직후 베이스를 확인하고 필요하면
머지할 것 (Phase 1 은 `feat/kit-v2-adapters` 머지로 보정했다).

## 5. 리뷰어 서브에이전트가 저장소 파일을 변이시킬 수 있다 (2026-08-10)

읽기 전용으로 호출한 `python-reviewer` 가 커버리지를 검증하려고 `install.sh` 를 `sed` 로
직접 수정했다가 `git checkout` 으로 되돌렸다. 정직하게 보고했고 실제 피해는 없었지만,
**워크트리에 다른 위임의 미커밋 산출물이 있으면 되돌리기 사고로 남의 작업이 날아간다.**

**대응**: 리뷰어 호출 프롬프트에 "변이가 필요하면 **저장소 밖 `mktemp -d` 사본**에서 하라,
저장소 안 파일에 `sed -i`·리다이렉트·`git checkout`·`git restore`·`git stash` 금지"를 명시한다.
특히 **동시 위임이 도는 중**이라면 그 사실도 프롬프트에 적는다.

## 6. 병렬 위임 중 커밋은 경로를 명시해 스테이징한다 (2026-08-10)

전역 락이 opencode 위임을 직렬화하지만 **워크트리의 작업 트리는 공유**된다.
task 4(테스트)와 task 5(문서)를 병렬로 돌리는 동안 `git add .`·`git commit -a` 를 쓰면
다른 task 의 미완성 산출물이 함께 커밋된다. **`git add <경로>` 로 명시**하고,
커밋 후 `git status` 로 남은 것이 의도한 것뿐인지 확인한다.

## 7. 서브모듈을 초기화한 워크트리는 phase-close 가 크래시한다 (2026-08-11, Phase 3 실측)

워크트리 안에서 `git submodule update --init` 을 하면 (서브모듈 범프 작업 등),
마감 때 `git worktree remove` 가 `fatal: working trees containing submodules cannot be
moved or removed` (rc=128) 로 거부되고 **phase-tools.py close 가 traceback 으로 죽는다**
(레지스트리 정리도 도달 못 함). `submodule deinit -f` 를 해도 워크트리 gitdir 의
`modules/` 메타데이터가 남아 계속 거부된다.

**대응**: 병합 확인 후 **`git worktree remove --force --force <경로>`** (git 규정 —
서브모듈 포함 워크트리는 `--force` 2회) 로 수동 제거하고 `phase-close.sh` 를 재실행해
레지스트리를 정리한다. 근본 수정(close 가 서브모듈 워크트리를 감지해 --force --force
경로를 타거나 명확히 안내)은 차기 페이즈 후보.

## 8. "flock 제거 PATH" 검증이 사실상 no-op 이 되기 쉽다 (2026-08-13, Phase 5 Task 2e 실측)

macOS 이식성(비flock 스핀락 경로)을 확인하려고 PATH 에서 flock 을 빼는 검증을 여러 라운드에서
수행했는데, 쓰인 방법이 두 가지 모두 잘못이었다:

- `':'.join(p for p in PATH if 'flock' not in p)` — **디렉터리 이름에 `flock` 이 든 경로**만
  거른다. 그런 디렉터리는 보통 없으므로 **아무것도 제거되지 않는다**(no-op). 그래도 스위트는
  통과하므로 "비flock 환경 통과"라는 거짓 근거가 남는다.
- `flock` 이 들어 있는 디렉터리(`/usr/bin` 등)를 통째로 제외 — bash·grep·python 까지 사라져
  스위트가 230건 에러로 무너진다.

**대응**: 임시 디렉터리에 PATH 의 모든 실행 파일을 심링크하되 `flock` 만 빼고, `PATH` 를 그
디렉터리 하나로 고정한다. 확인 기준은 `command -v flock` 이 **실패**하는 것이다
(스크립트의 분기 조건이 `command -v flock` 이므로). 2026-08-13 이 방법으로 189건 통과를 확인했다.

## 9. 락 없이 `opencode run` 을 동시에 띄우면 **토큰 0개 + exit 0** 으로 침묵사한다 (2026-08-12, Phase 5)

다중 프로세스 `opencode run` 은 세션 DB 에 `busy_timeout=0` 으로 접근해 SQLITE_BUSY 를 만나고,
그 세션은 **아무 일도 하지 않은 채 exit 0** 으로 끝난다. 실패로 보이지 않아 검수가 통과한다.
업스트림이 "고칠 계획 없음"으로 확정한 결함이다 (anomalyco/opencode#21215 · #15188).

**대응**: 위임은 반드시 `scripts/run-delegation.sh` 경유. 병렬이 필요하면 `opencode serve` +
`run --attach` 경로만 쓴다(프로젝트별 락). serve 가 없으면 전역 락으로 전체 직렬화된다.

## 10. 없는 에이전트를 지정하면 실패가 아니라 **조용한 기본 에이전트 폴백**이다 (2026-08-12, Phase 5)

`opencode run --agent <오타>` 는 stderr 경고 한 줄만 남기고 **기본 에이전트로 실행되며 rc=0** 이다.
로스터에 없는 에이전트 이름으로 위임하면, 도메인 규칙·권한 제약이 하나도 적용되지 않은 채
작업이 수행되고 성공으로 보고된다.

**대응**: 래퍼가 로그 앞부분을 스캔해 `exit 7`(AGENT_NOT_FOUND)로 끊는다. 스캔 창은 `head -n 60`
이며, 에이전트 산출물이 43행부터 시작하므로 그 이상으로 넓히면 산출물 본문에 걸려 오탐이 난다.

## 11. attach 모드에서 `loop session.id` 는 **서버 로그에만** 찍힌다 (2026-08-12, Phase 5)

클라이언트 로그를 감시하던 워치독이 attach 모드에서는 아무 신호도 못 본다 — 진행 중인 위임을
"세션 미개시"로 오판하거나, 반대로 죽은 세션을 살아 있다고 본다.

**대응**: 진행 판정은 서버 API(`GET /session/<id>` 의 `time.updated`·`tokens`) 기준으로 한다.
클라이언트 SIGTERM 으로는 서버 세션이 멈추지 않으므로 `POST /session/<id>/abort` 가 필요하다.

## 12. 테스트가 스텁 `opencode` 프로세스를 누수시키면 다음 위임이 차단된다 (2026-08-13, Phase 5)

스톨 경로 테스트가 남긴 고아 스텁 2개(PPID=1, 임시 디렉터리·스크립트 파일까지 삭제된 상태)가
5분 넘게 살아남아 다음 위임을 `PREFLIGHT_UNMANAGED`(exit 3)로 막았다.

**대응**: 테스트는 `tearDown` 에서 자기가 띄운 스텁을 반드시 정리한다. 회귀 확인법 —
전체 스위트를 **2회 연속** 돌린 뒤 `ps -eo pid,args | grep 'opencode run'` 이 비어야 한다.

## 13. 위임 스크립트를 고치는 페이즈에서 그 스크립트로 위임하지 말 것 (2026-08-13, Phase 5)

두 가지가 겹친다. ① 실행 중인 bash 스크립트를 수정하면 bash 가 남은 부분을 파일에서 다시 읽어
실행이 깨진다. ② exit 7 탐지가 로그를 스캔하므로, 에이전트 미발견 경고 문구가 들어간 **수정 지시
프롬프트 자체**에 걸려 정상 위임을 죽이고 세션에 abort 를 날린다.

**대응**: 커밋 이전 안정본을 `scripts/run-delegation-v2.sh` 로 얼려 그것으로 위임한다
(페이즈 마감 시 삭제). 프롬프트에는 attach 플래그+URL 인접 표기나 미발견 경고 문구를 쓰지 않는다.

## 14. 위임에 테스트 작성을 맡기면 단정이 약화된다 (2026-08-13, Phase 5 — 같은 계열 7회 실측)

"통과하는데 아무것도 검증하지 않는" 테스트가 한 페이즈에서 7번 나왔다: 스텁 JSON 이 깨져 판정
경로가 한 번도 실행되지 않음 / 스텁 종료와 sleep 경합으로 비결정 / 경로 전용 스텁이 실제 기동
형태를 가림 / 실패하는 단정을 **완화해서** 그린 만들기 / 산출물 존재만 보고 배타적 획득은 미검증.
공통 원인은 위임 에이전트가 "그린"을 목표로 삼는다는 것이다.

**대응**: 회귀 테스트는 **오케스트레이터가 직접 작성해 동결**하고, 위임 프롬프트에서 `tests/`
수정을 금지한다. 이 방식으로 Phase 5 Task 2e·2f 에서 단정 약화가 0건이었다. 그리고 매 라운드
**변이 검증**(수정을 되돌리면 그 테스트가 죽는가)을 검수자가 직접 수행한다.

## 15. 변이 검증을 `/tmp` 나 "스크립트만 복사한 사본"에서 하지 말 것 (2026-08-13, Phase 5)

- `/tmp` 는 opencode 가 `external_directory` 권한으로 거부해 **에이전트가 그 자리에서 멈춘다**
  (구현을 끝낸 뒤 변이 단계에서 중단된 실측 다수).
- 스크립트만 사본으로 복사해 변이하면, 테스트가 `KIT = Path(__file__).parents[1]` 로 **원본**을
  참조하므로 변이가 아무 효과도 없다 — "변이 검증 통과"라는 거짓 근거만 남는다.

**대응**: `.orchestrate/mutation/<이름>/` 에 **저장소 전체**(`core` `tests` `scripts`)를 복사하고
그 디렉터리 안에서 변이 + 테스트를 실행한다.

## 16. 워크트리 위임에서 **부모 체크아웃 경로를 만지면** 에이전트가 그 자리에서 멈춘다 (2026-08-13, Phase 5 Task 4)

워크트리(`.claude/worktrees/<phase>/`)에서 위임을 돌리면 opencode 의 프로젝트 루트는 그 워크트리다.
상위의 부모 체크아웃(`$HOME/<프로젝트>`)은 **외부 디렉터리로 자동 거부**된다:

    ! permission requested: external_directory ($HOME/dev-orchestrate-kit/*); auto-rejecting
    ✗ Grep "..." failed in $HOME/dev-orchestrate-kit
    Error: The user rejected permission to use this specific tool call.

에이전트가 절대 경로로 Grep 한 번을 시도했다가 거부당하자 **아무 파일도 고치지 않고 종료**했고,
래퍼는 세션 활동이 있었으므로 `DONE` + exit 0 으로 보고했다. 검수에서 `git status` 를 보지 않았다면
"완료"로 지나갔을 상황이다.

**대응**: 워크트리 위임 프롬프트에는 **상대 경로만 쓰라**고 명시한다(`adapters/...`, `core/...`).
절대 경로 금지, 검색 범위를 저장소 루트 위로 올리지 말 것. 그리고 **검수는 항상 `git status` 로
산출물 유무부터 확인**한다 — `DONE` 은 파일이 바뀌었다는 뜻이 아니다.

## 17. attach 클라이언트는 `OPENCODE_SERVER_PASSWORD` 가 있어야 한다 — 지우면 "Session not found" 로 즉사 (2026-08-13, Phase 5 전파)

보안 리뷰 권고로 `run-delegation.sh` 가 비밀번호를 `unset` 하자, attach 클라이언트가 서버 인증에
실패하며 다음처럼 죽었다. 메시지가 인증 실패를 가리키지 않아 원인 추적이 오래 걸린다:

    Error: Session not found      (rc=1 → 래퍼는 "세션 미개시" 로 판정 → 모델 체인 전체 소진 → exit 5)

대조 실측: 같은 명령이 비밀번호 있는 환경에서 rc=0 정상, `env -u OPENCODE_SERVER_PASSWORD` 에서 즉사.

**대응**: `unset` 은 유지하되(다른 자식·ctl 호출 미상속) **attach 실행 라인에만 인라인 주입**한다.
`-p` 로 argv 에 넣지 말 것 — 공용 서버에서 `ps` 로 전 사용자에게 노출된다. 위임 에이전트는 같은
사용자라 `serve.env`(600)를 어차피 읽을 수 있으므로 클라이언트에게 숨기는 것은 방어 효과가 없다.

## 18. 🔴 서버는 세션의 `directory` 를 **클라이언트의 `--dir` 가 아니라 서버 자신의 cwd** 로 기록한다 (2026-08-13, Phase 5 전파 실측)

`opencode serve` 를 A 디렉터리에서 띄우고 B 프로젝트에서 `run --attach --dir B` 로 붙이면:

- `--dir` 는 **에이전트·설정 로딩에는 반영된다**(B 의 로스터 에이전트가 정상 로드됐고 배너도 찍혔다).
- 그러나 `GET /session` 이 돌려주는 그 세션의 `directory` 는 **A**(서버 cwd)다. 실측: 서버를
  키트 워크트리에서 띄운 뒤 usage-dashboard 에서 위임 → 새 세션의 directory 가 전부 키트 워크트리.

따라서 **"기동 전후 세션 ID 집합 차분 + `directory` 정확 일치"로 세션을 식별하는 방식은
서버를 띄운 그 프로젝트에서만 성공**하고, 다른 프로젝트는 전부 "세션 미개시" 로 오판되어
모델 체인을 소진하고 exit 5 로 끝난다(전파 직후 실측).

**대응(2026-08-13 해결 — Task 2h)**: 디렉터리 일치에 의존하지 말 것. 위임 래퍼는
`POST /session?directory=<경로>` 로 **세션을 먼저 만들고**(그 응답의 `directory` 는 요청대로 기록된다)
`opencode run --attach --session <id>` 로 붙인다. 차분 탐색·디렉터리 일치가 통째로 사라져
서버 cwd 와 무관하게 어느 프로젝트에서든 동작한다(실측: 서버를 다른 프로젝트에서 띄운 상태로
키트·usage-dashboard 위임 모두 성공).

## 19. 킬 스위치 순서 — `ctl stop` 다음에 `rm serve.env` (2026-08-13 실측)

`serve.env` 를 먼저 지우면 ctl 이 환경 파일을 읽지 못해 `stop` 자체가 불가능해지고, 고아 serve 가
남아 standalone 위임 옆에서 `SERVE_ALIVE_FALLBACK`(세션 DB 경합 위험) 경고를 유발한다.
반드시 **`bash scripts/opencode-serve-ctl.sh stop` → `rm ~/.config/opencode/serve.env`** 순서로.

## 20. 위임 에이전트는 `/tmp` 에 쓸 수 없다 — `external_directory` 자동 거부가 런을 죽인다 (2026-08-11, Phase 4 Task 5a 실측)

Task 5a 프롬프트에 "저장소 밖 사본(예: `/tmp` 아래)에 install.sh 를 복사해 변이 검증하라"고
적었더니 opencode 가 다음을 로그에 남기고 **런 자체를 종료**했다 (최종 보고 없음):

```
evaluated permission=external_directory pattern=/tmp/*  action=ask
permission requested: external_directory (/tmp/*, /tmp/task5-auth-mutations/*); auto-rejecting
Error: The user rejected permission to use this specific tool call
```

기존 함정 목록은 프로젝트 밖 절대경로를 **읽으라**고 하는 경우만 다뤘다. **쓰기도 동일하게
차단**되며, 읽기와 달리 에이전트가 "그 자리에서 포기"하는 정도가 아니라 산출물 보고 없이
프로세스가 정리된다. 그런데 이 저장소의 상시 규칙은 "**새 테스트마다 저장소 밖 사본에서
변이 검증**"이라 정면 충돌한다.

**대응**: 변이 사본은 **저장소 안 gitignore 경로**(`.orchestrate/mut<task>/`, `.gitignore:5`)
에 만든다. 저장소 밖이 아니어도 격리 목적(추적 파일 오염 방지)은 동일하게 달성된다.
프롬프트에는 경로를 명시하고 "작업 후 그 디렉터리를 지울 것"을 함께 적는다.
**리뷰어 프롬프트의 "저장소 밖 `mktemp -d`" 문구(항목 5)도 같은 이유로
`.orchestrate/rev<task>/` 로 바꿔 쓴다.**

## 21. RED 단계 task 에 변이 검증을 요구하지 말 것 (2026-08-11, Phase 4 Task 5a 실측)

`<N>a`(테스트 RED) → `<N>b`(구현) 분할에서 **5a 시점에는 변이시킬 구현이 없다.**
테스트가 전부 실패하는 상태라 "구현을 망가뜨리면 테스트가 실패하는가"라는 질문 자체가
성립하지 않는다 (망가뜨리기 전에도 실패한다). 항상 참인 검증이 되어 4c 의 🟠 를 형태만
바꿔 반복하게 된다.

**대응**: 변이 검증은 **`<N>b`(구현) task 의 완료 조건**에 넣는다. `<N>a` 의 완료 조건은
① RED 출력 ② 실패 범위가 해당 계약 항목으로만 국한됨 두 가지다.

## 22. 위임에 "저장소 밖 쓰기 금지"를 경고로 거는 것만으로는 부족하다 (2026-08-12, Phase 4 실측 2회)

opencode 위임은 `/tmp` 등 저장소 밖 경로를 만지면 `external_directory` 권한으로 **자동 거부**되고,
에이전트가 그 자리에서 **보고 없이 종료**한다. 이 함정은 이미 문서화돼 있었고 위임 프롬프트에도
경고를 넣었는데도 **두 번 연속 같은 방식으로 죽었다** — 실증·재현을 요구받은 에이전트가
사본을 만들려고 `/tmp` 를 건드린 것이다.

실측 로그:
```
! permission requested: external_directory (/tmp/*); auto-rejecting
✗ ... && cp ".../node" /tmp/nope failed
Error: The user rejected permission to use this specific tool call.
```
그 런에서 `install.sh` 는 **한 글자도 바뀌지 않았다**(exit 0 으로 끝나 성공처럼 보인다).

**대응 — 경고가 아니라 범위로 막는다**: 산술 3줄짜리 수정에 실증까지 요구하면 에이전트가
사본을 만들려 든다. **실증·재현 요구를 프롬프트에서 아예 빼고** "코드 N줄만 고쳐라, 검증은
오케스트레이터가 한다"로 범위를 줄이자 즉시 통과했다.
정리: **위임에 실증을 요구할 때는 저장소 안에서 완결되는 방법을 함께 지정**하거나,
아니면 **실증을 검수자(Claude 서브에이전트 — 저장소 밖 쓰기가 가능하다)에게 맡긴다.**

**부수 확인**: exit 0 을 성공으로 믿지 말 것. 위임 완료 후 **실제 diff 를 직접 확인**해야 한다
(이 사고는 오케스트레이터가 `sed -n` 으로 해당 블록을 열어 보고서야 발견됐다).

## 23. 마법사 메뉴에 항목을 추가하기 전에 기존 테스트의 번호 하드코딩을 grep 할 것 (2026-08-14, Phase 6 실측)

컨테이너 스텝에 dashboard 항목을 browser 와 mcp 사이(2번)에 넣도록 지시서를 썼다가,
`test_install_mcp_step.py`·`test_install_wizard.py` 의 **번호 하드코딩 8건**("1 2"=browser+mcp,
"2"=mcp 단독)과 정면 충돌해 순수 회귀 8건이 났다. 지시서 작성 시점에
`grep -rn 'INSTALL_SELFTEST_INPUTS' tests/` 로 기존 입력 시퀀스를 확인했으면 예방됐다.

**같은 뿌리의 두 번째 결함**: 항목이 늘면 "선택값 조합부"의 암묵 전제도 깨진다 —
mcp 가드가 `[ -z "$CONTAINERS" ]`(비었는지)로 browser 부재를 추론하고 있었는데, dashboard 가
CONTAINERS 를 채우면서 mcp+dashboard 조합이 가드를 통과했다(리뷰어 재현). **집합 소속을
공백 여부로 추론하는 코드는 원소가 추가되는 순간 깨진다** — `case ",$LIST," in *,이름,*)` 로
직접 검사할 것.

**대응**: 메뉴 항목 추가 task 의 지시서에는 ① 기존 테스트 입력 시퀀스 grep 결과
② 새 항목 번호가 기존 번호를 밀지 않는 배치(맨 뒤 추가 우선) ③ 선택값을 소비하는
조합부·가드 전수 목록을 함께 적는다.

## 24. 컨테이너 실기동 테스트는 **해당 서브모듈이 초기화된 체크아웃**을 전제한다 (2026-08-14, Phase 6 실측)

`test_install_container_step`·`test_install_dashboard_container` 의 실기동 경로 테스트는
fake `git` 을 쓰므로 서브모듈을 실제로 초기화하지 못한다 — compose 파일이 이미 있어야
docker 분기까지 도달한다. 프레시 클론(서브모듈 미초기화)에서는 install.sh 가 (정상적으로)
"compose 파일이 없다" 스킵 경로를 타서 테스트가 FAIL 한다. Phase 6 에서 같은 테스트가
워크트리(위임 에이전트가 서브모듈을 init 해 둠)에서는 통과하고 main 체크아웃에서는 실패해
발견됐다 — **환경에 따라 결과가 갈리는 테스트는 이 전제 때문이다.**

**대응**: 테스트 돌리기 전 `git submodule update --init containers/browser components/usage-dashboard`.
부수 효과 주의 — **워크트리 안에서 init 하면 함정 7(phase-close 크래시)이 재발한다.**
워크트리 페이즈에서 위임 에이전트가 서브모듈을 init 했을 수 있으니 마감 전 `git submodule status` 로
확인하고, 초기화돼 있으면 `git worktree remove --force --force` 경로로 마감한다.


## 25. 로컬 main 이 미푸시 상태일 때 phase-claim 을 실행하면 낡은 origin/main 에서 분기된다 (2026-08-17, Phase 9 실측)

**무엇을 하면**: 직전 페이즈 병합을 origin 에 푸시하지 않은 채 `scripts/phase-claim.sh` 로
새 페이즈 워크트리를 만들면.

**무엇이 죽는지**: 브랜치가 낡은 origin/main 에서 분기된다. Phase 9 에서 phase8 병합(02941dd)
3커밋 앞선 로컬 main 을 두고 f3a4884(구 origin/main)에서 분기됐고, 워크트리의 CLAUDE.md 가
phase8 이전 내용(DOCs/ 경로)으로 돌아가 있었다. task 2개를 커밋한 뒤에야 리뷰어가 발견 —
`git rebase main` 으로 해소했지만(충돌 없음, 운이 좋았다), 겹치는 파일을 고치는 페이즈였다면
병합 충돌·유령 회귀가 났다.

**대응**: ① 페이즈 시작 전 `git log --oneline origin/main..main` 으로 미푸시 커밋을 확인하고
푸시(또는 인지) 후 claim 한다. ② claim 직후 `git merge-base HEAD main` 이 main 팁과 같은지
확인한다. 다르면 작업 시작 전에 `git rebase main`.


## 26. 리뷰어 서브에이전트에게 워크트리를 주면 `git stash` 로 미커밋 작업을 흔든다 (2026-08-17, Phase 10 Task 2 실측)

**무엇을 하면**: 오케스트레이터가 같은 워크트리에서 지시서·테스트를 편집하는 동안
도메인 리뷰어(Agent)에게 그 워크트리 경로를 주고 "커밋 diff 를 보라"고 지시하면.

**무엇이 죽는지**: 리뷰어가 "리뷰 대상 커밋 상태를 재현하려고" `git stash` 를 실행했다.
오케스트레이터가 그 순간 편집 중이던 동결 테스트·지시서가 stash 로 빠졌고,
`git stash pop` 이 충돌로 실패해 stash 가 남았다. 이번엔 내용이 이어지는 커밋에 포함돼
유실은 없었지만, 타이밍이 조금 달랐으면 동결 테스트가 사라진 채 위임이 그린을 받았다.

**대응**: ① 리뷰어 프롬프트에 **읽기 전용 git 명령만 허용**을 명시한다
(`git show`·`git diff`·`git log` 만. `stash`·`checkout`·`restore`·`clean` 금지).
② 리뷰어를 부르기 전에 오케스트레이터의 작업을 **커밋해서 작업트리를 비운다**.
③ 리뷰 후 `git stash list` 로 잔재를 확인한다.

## 27. 위임 산출물과 오케스트레이터의 테스트 수정을 한 커밋에 묶으면 리뷰어가 "동결 위반"으로 오진한다 (2026-08-17, Phase 10 Task 2 실측)

**무엇을 하면**: 위임이 만든 파일과, 오케스트레이터가 같은 시점에 고친 `tests/` 를
한 커밋에 함께 담으면.

**무엇이 죽는지**: bash-reviewer 가 그 커밋의 `tests/` 변경을 보고
"위임 구현자가 동결 테스트를 무단 수정했다"는 🔴 Critical 을 냈다 (PITFALLS 14 재발로 판정).
실제로는 오케스트레이터의 수정이었고 위임 로그에는 `tests/` 수정 기록이 없었다.
반박·근거 제시에 라운드가 소모됐다.

**대응**: 오케스트레이터의 `tests/` 수정은 **항상 별도 커밋**으로 남긴다
(커밋 메시지에 `test(...)` + "오케스트레이터 동결"). 위임 산출물 커밋에는 위임이 만진 파일만 넣는다.

## 28. `unittest -k` 에 불리언 식을 쓰면 0건 매칭으로 조용히 통과한다 (2026-08-17, Phase 10)

**무엇을 하면**: 위임 프롬프트나 검증 명령에 `python3 -m unittest discover -s tests -k "A or B"` 를 쓰면.

**무엇이 죽는지**: `-k` 는 불리언 식을 지원하지 않는다. 패턴 `"A or B"` 는 어떤 테스트 이름과도
매칭되지 않아 `NO TESTS RAN` 으로 끝나고, 종료 코드는 0 이다 — **"검증했고 통과했다"로 보인다.**
Phase 10 Task 2 위임 프롬프트에 이 형태를 써서 RED 확인 단계가 실제로는 아무것도 실행하지 않았다.

**대응**: 패턴은 하나씩 준다 (`-k A` 를 두 번 실행). 또는 클래스명을 직접 지정한다.
필터를 쓴 검증은 `Ran N tests` 의 N 이 0 이 아닌지 확인할 것.

## 29. 출력 전체를 정확일치로 단정한 테스트가 있으면 필드 추가가 순수 회귀를 만든다 (2026-08-17, Phase 10)

**무엇을 하면**: 어떤 출력 블록에 필드를 하나 추가하면서 기존 테스트의 정확일치 단정을 grep 하지 않으면.

**무엇이 죽는지**: `test_install_menu.py:15` 가 `INSTALL_PARSE_ONLY` 의 stdout **전체**를
문자열 정확일치로 단정하고 있었다. `DOCTOR=0` 한 줄을 추가하자 순수 회귀 1건이 났다.
PITFALLS 23(메뉴 번호 하드코딩)과 같은 뿌리이며, 이번엔 **출력 문자열** 버전이다.

**대응**: 출력 블록에 필드를 추가하기 전에
`grep -rn 'assertEqual(\s*result.stdout' tests/` 로 정확일치 단정을 먼저 찾는다.
발견하면 같은 커밋(오케스트레이터 몫)에서 함께 갱신한다.

## 30. GNU `cp` 는 끊어진 심링크로의 쓰기를 자체 거부한다 — 그 경로로는 가드를 증명할 수 없다 (2026-08-17, Phase 10)

**무엇을 하면**: "끊어진 심링크를 타고 홈 밖에 쓰지 않는다"는 가드를
"밖에 파일이 생겼는가"만으로 단정하면.

**무엇이 죽는지**: GNU coreutils 의 `cp` 가 `not writing through dangling symlink` 로 자체 거부하므로,
스크립트의 `[ -L ]` 가드를 **전부 지워도** Linux 에서는 유출이 발생하지 않는다 —
변이 검증에서 테스트가 죽지 않아 공허한 단정임이 드러났다. macOS `cp` 는 링크를 따라가 쓴다.

**대응**: 이런 가드는 **부수 효과가 아니라 보고 형태**를 단정한다
(예: "심링크 dst 는 WARN 으로 보고된다" — 가드를 지우면 `FAIL ... 복사할 수 없다` 가 되어 죽는다).
그리고 심링크 관련 가드는 **부모 디렉터리가 심링크인 경우**로 변이 검증하라 — 그 경로는
`mkdir -p` 가 실제로 링크를 타므로 Linux 에서도 유출이 재현된다.

## 31. 워크트리에서 만든 프로젝트 에이전트는 그 세션에서 호출되지 않는다 (2026-08-19, Phase 13)

**무엇을 하면**: 워크트리 안에서 `.claude/agents/<이름>.md` 를 만들고, 같은 세션에서 Agent 툴로
그 이름을 호출한다.

**무엇이 죽는지**: `Agent type '<이름>' not found` 로 즉시 실패한다. 세션 시작 전부터 있던
프로젝트 에이전트(`bash-reviewer`·`task-orchestrator`)는 정상 호출되므로 "프로젝트 에이전트는
안 되나 보다"로 오진하기 쉽다.

**원인 (정정된 진단)**: 처음에는 "레지스트리가 세션 시작 시 스냅샷된다"고 판단했으나 **틀렸다.**
같은 세션에서 페이즈를 main 에 병합해 정의 파일이 **메인 체크아웃**에 들어온 직후 그 에이전트가
목록에 나타났다. 즉 레지스트리는 갱신되며, 참조하는 위치가 **세션의 프로젝트 루트(메인 체크아웃)**
이지 현재 cwd(워크트리)가 아니다. 워크트리에만 있는 정의는 보이지 않는다.

**대응**:
- 페이즈 중 신설한 에이전트의 첫 가동은 **병합 후** 또는 **새 세션**에서 한다.
  페이즈 경계 = 세션 경계 규약과 자연히 맞는다.
- 그 전에 꼭 써야 하면 `general-purpose` 에 그 에이전트 정의(행동 제약·출력 형식 포함)를
  **인라인해 대행**한다. 대행했음을 완료 보고에 명시할 것 — 도구 제약(읽기 전용 등)이
  프롬프트로만 걸리므로 강제력이 약하다.
- 지시서에서 "신설 + 그 페이즈에서 첫 사용"을 한 파트로 묶지 말 것.

## 32. 동결 사본(함정 13)은 serve attach 를 잃는다 (2026-08-19, Phase 13)

**무엇을 하면**: 위임 스크립트를 고치는 페이즈에서 PITFALLS 13 대로
`cp core/scripts/run-delegation.sh .orchestrate/run-delegation-v3.sh` 만 해서 동결 사본을 만든다.

**무엇이 죽는지**: 사본의 `SCRIPT_DIR` 이 `.orchestrate/` 가 되어 형제 스크립트
`opencode-serve-ctl.sh` 를 찾지 못한다 → `SERVE_FALLBACK` → **standalone + 전역 락**으로 떨어진다.
프로젝트 간 병렬이 사라지고, 살아 있는 serve 옆에서 도는 동안
`SERVE_ALIVE_FALLBACK`(세션 DB 경합 위험) 경고까지 뜬다.

**대응**: 동결할 때 `opencode-serve-ctl.sh` 도 **같은 디렉터리에 함께 복사**한다.

```bash
cp core/scripts/run-delegation.sh .orchestrate/run-delegation-v3.sh
cp core/scripts/opencode-serve-ctl.sh .orchestrate/opencode-serve-ctl.sh
```

Phase 13 에서 함께 복사한 뒤 attach 가 복구됐고, 실제로 `LOCK_WAIT(project)` 로 직렬 대기하는
정상 동작을 실측했다 (Task 5 위임).

**부수 효과 인지**: 동결 사본으로 위임하면 그 페이즈가 만드는 개선이 **그 페이즈 자신의 위임에는
적용되지 않는다.** Phase 13 은 `.wrapper` 로그를 만들었지만 자기 위임에는 `.wrapper` 가 남지 않았다.

## 33. `phase-tools.py tasks` 는 진행 중 페이즈에 쓸 수 없다 (2026-08-19, Phase 13)

**무엇을 하면**: 워크트리에서 진행 중인 페이즈에 대해
`python3 scripts/phase-tools.py tasks <N> --set <task>=<status>` 를 실행한다.

**무엇이 죽는지**: `find_root()` 가 `--git-common-dir` 로 **메인 체크아웃**을 가리키므로
(`core/scripts/phase-tools.py:54`), 지시서가 아직 피처 브랜치에만 있는 동안에는 조회도 `--set` 도
`PHASE<N>_*.tasks 디렉터리 없음` 으로 실패한다. 이미 병합된 과거 페이즈(`tasks 10`)는 정상 조회된다.

**실측**: Phase 11 이 만든 기계판독 메커니즘이 **정작 그것을 쓰려는 시점에 동작하지 않는다**
(2026-08-19).

**대응**: 진행 중 페이즈의 상태 전이는 task 파일 frontmatter 와 인덱스 표를 직접 고친다.
수정(`--worktree` 플래그 또는 cwd 우선 탐색)은 후속 페이즈로.

## 34. 변이 검증 사본이 `.orchestrate/` 를 포함하면 재귀 폭발한다 (2026-08-19, Phase 13)

**무엇을 하면**: PITFALLS 15 대로 "저장소 전체를 `.orchestrate/mut<task>/` 에 복사"하되
**제외 경로를 지정하지 않는다** — `rsync -a ./ .orchestrate/mut13-3/` · `cp -r . ...` 등.

**무엇이 죽는지**: 사본 안에 `.orchestrate/` 가 통째로 들어가고, 그 안에는 이전 변이 사본이
또 들어 있다. task 와 리뷰 라운드가 쌓일수록 중첩이 곱해진다.
**Phase 13 실측: 워크트리 `.orchestrate/` 가 61GB · 파일 372만 개.**
그 결과 `phase-close.sh` 의 `git worktree remove` 가 60초 타임아웃으로 죽는다
(함정 4 의 서브모듈 크래시와 증상이 비슷하나 원인이 다르다).

**더 나쁜 것은 타임아웃이 깨끗한 실패가 아니라는 점이다.** `git worktree remove` 는 파일을
지워 나가다가 중간에 잘리므로, **반쯤 삭제된 워크트리**가 남는다 — 추적 파일 대부분과 `.git`
파일이 사라져 `git worktree list` 가 `prunable: gitdir file points to non-existent location` 로
표시하고, phase-close 는 그 상태를 "미병합"으로 오판해 워크트리를 "보존"한다고 보고한다.
Phase 13 에서는 모든 산출물이 삭제 전에 커밋·병합돼 손실이 없었으나, **미커밋 작업이 있었다면
그대로 유실됐을 것이다.**

**타임아웃 후 복구**: `find <워크트리> -delete` 로 잔재를 지우고 `git worktree prune` →
`git branch -d <브랜치>` (병합 확인 후). 함정 4 의 `--force --force` 수동 제거와 같은 계열이다.

**대응**:
- 변이·재현 사본을 만들 때 **`.orchestrate` 를 반드시 제외**한다:
  `rsync -a --exclude .orchestrate --exclude .git ./ .orchestrate/mut<task>/`
  (`.git` 제외도 함께 — 테스트는 git 을 쓰지 않는다.)
- 지시서의 변이 검증 완료 조건에 이 제외 지시를 **명시**한다. 위임과 리뷰어 양쪽 모두
  "저장소 전체 복사"만 읽으면 제외를 넣지 않는다 (Phase 13 에서 위임 3회·리뷰어 5회 전부 미제외).
- 페이즈 마감 전에 `du -sh .orchestrate` 로 확인한다. 수 GB 를 넘으면 사본부터 정리한다.
- 정리 시 재귀 강제 삭제 명령(`rm -rf`)은 bash-guard 가 차단한다 — **문자열 매칭이라 문서를 쓰는
  heredoc 이나 grep 인자에 들어가도 걸린다**(이 문서를 쓰다가 실제로 두 번 차단됐다).
  `find <경로> -delete` 를 쓰거나 사용자에게 직접 실행을 요청한다.

## 35. `unittest.main()` 가드 뒤에 정의한 테스트 클래스는 파일 직접 실행 시 누락된다 (2026-09-01, Phase 12)

**증상**: `python3 -m unittest discover -s tests` 로는 전부 돌지만, `python3 tests/test_x.py` 로
직접 실행하면 뒤쪽 클래스가 **조용히 빠진다**. 실패가 아니라 "Ran N tests OK" 로 통과하므로
건수를 세지 않으면 알아챌 수 없다.

**원인**: `if __name__ == "__main__": unittest.main()` 는 실행되는 시점의 모듈 네임스페이스만
스캔한다. 그 아래에 클래스를 append 하면 아직 정의되지 않은 상태에서 스캔이 끝난다.

**언제 생기는가**: 오케스트레이터가 **동결 테스트를 기존 파일 끝에 append** 할 때. 파일 끝은
가드 뒤다 — Phase 12 에서 두 파일(`test_kit_doctor.py`·`test_hook_selfcheck.py`)에 동시에 발생했고,
`structure-reviewer` 가 마감 리뷰에서 잡아냈다. 위임의 실수가 아니라 오케스트레이터의 실수다.

**대응**: 동결 테스트를 append 한 뒤 **가드가 파일 끝인지 확인**한다
(`grep -n '__main__' tests/*.py` 로 줄 번호 vs `wc -l` 비교). append 했으면 가드를 파일 끝으로
옮기고, 직접 실행으로 **건수를 확인**한다 (discover 건수와 같아야 한다).

## 36. 동결 테스트 픽스처가 실제 마커를 빠뜨리면 구현이 약한 추론으로 통과한다 (2026-09-01, Phase 12)

**증상**: 위임 구현이 `scripts/` 디렉터리 존재만으로 "킷 루트"를 판정했고, 리뷰어가 🔴
(비킷 프로젝트 오승격)로 반려했다. 그런데 **원인은 위임이 아니었다** — 오케스트레이터가 동결한
픽스처가 진짜 마커인 `core/install-manifest.tsv` 를 만들지 않아서, 그 파일을 검사하는 올바른
구현은 픽스처에서 실패하고 **약한 추론만 통과**하는 구조였다.

**일반형**: 동결 테스트는 계약이지만, 픽스처가 실물의 부분집합이면 **계약이 실물보다 약해진다.**
위임은 통과하는 최소 구현을 찾으므로 그 약한 쪽으로 수렴한다. 리뷰어는 결과만 보고 위임을
탓하고, 오케스트레이터는 반려를 위임에 되돌려 보내 같은 픽스처로 다시 시도하게 만든다.

**대응**: 동결 픽스처를 만들 때 **판정에 쓰이길 원하는 마커를 전부 넣는다.** 특히 "이 조건으로
판정하라"를 지시서 규약에 적었다면, 픽스처에 그 조건의 **양성 사례와 음성 사례를 둘 다** 만든다.
리뷰가 🔴 를 냈을 때 반려 전에 **픽스처부터 확인**한다 — 구현이 아니라 계약이 틀린 경우가 있다.

## 37. 서브에이전트 결과를 sleep 폴링으로 기다리면 세션 종료 시 고아가 된다 (2026-09-01, Phase 15)

**증상**: 페이즈 말 리뷰어 2개(`code-reviewer`·`structure-reviewer`)를 Agent 툴로 띄운 뒤
`sleep 290` 을 `run_in_background` 로 걸어 결과를 기다렸다. 리뷰어 둘 다 **정상 완료**해
완료 알림이 큐에 들어갔지만, 세션은 sleep 이 끝날 때까지 대기 상태에 묶여 알림을 소비하지
못했다. sleep 종료 직후 사용자가 응답 없는 세션을 강제 종료 — 리뷰 결과 2건이 통째로 고아가 됐다.
(같은 세션이 앞선 6개 리뷰어 호출에서는 폴링 없이 정상 수신했다. 폴링이 원인이다.)

**왜 그런가**: 하네스는 백그라운드 task 가 끝나면 **자동으로 세션을 재개**해 알림을 준다.
sleep 폴링은 그 재개 경로에 아무 도움이 안 되면서, 세션을 "무언가를 기다리는 중" 상태로만
붙잡아 둔다. 실제로는 감시 루프가 자기 자신을 기다리는 꼴이다 (함정 1 의 `pgrep -f` 와 같은 계열).

**대응**:
- **서브에이전트·백그라운드 명령을 sleep 으로 폴링하지 말 것.** 띄운 뒤 그 턴을 끝내면
  완료 시 하네스가 알려준다. 외부 상태(CI·원격 큐)처럼 하네스가 추적 못 하는 것만 폴링 대상이다.
- **이미 고아가 됐다면 결과는 유실되지 않았다.** 세션 트랜스크립트
  `~/.claude/projects/<cwd 슬러그>/<세션 UUID>.jsonl` 에서 `type: queue-operation` 항목을
  파싱하면 `<result>` 전문이 그대로 남아 있다. `content` 필드의 `<summary>` 로 어떤 에이전트인지
  구분할 수 있다. Phase 15 는 이 경로로 리뷰 2건을 전량 회수해 재실행 비용 0 으로 마감했다
  (`/tmp/claude-*/…/tasks/<id>.output` 심링크가 가리키는 `subagents/agent-<id>.jsonl` 도 같은 내용).
- 세션이 어느 파일인지는 `ls -lt ~/.claude/projects/<슬러그>/*.jsonl` 의 최신 항목으로 찾는다.

## 38. `session-cost.py` 는 경로에 점이 있으면 세션 디렉터리를 못 찾는다 (2026-09-01, Phase 15)

**증상**: 워크트리에서 시작한 세션의 비용을 재려다 `세션 디렉터리 없음:
/home/jh/.claude/projects/-home-jh-aigsprac-.claude-worktrees-phase15-model-policy-scope`
로 실패했다. 실제 디렉터리는 `...-aigsprac--claude-worktrees-...` (점이 대시로 바뀌어 `--`)다.

**원인**: `core/scripts/session-cost.py:project_dir()` 는 슬러그를
`str(Path.cwd()).replace("/", "-")` 로만 만든다. 하네스는 `/` 뿐 아니라 **`.` 도 `-` 로**
바꾸므로, 경로에 점이 하나라도 있으면(워크트리는 항상 `.claude/worktrees/` 아래다) 어긋난다.

**왜 지금까지 안 걸렸나**: 기존 함정("세션이 시작된 체크아웃에서 실행할 것")은 세션이 메인
체크아웃에서 시작한 경우만 다뤘다. **세션 자체가 워크트리에서 시작하면 도망갈 체크아웃이 없다** —
`cd` 로는 절대 맞출 수 없고(그 슬러그를 만드는 실제 경로가 존재하지 않는다) 정량 3필드의
비용이 `미측정` 으로 남는다. 세션 도중 `EnterWorktree` 를 하면 트랜스크립트 파일 자체가
워크트리 슬러그 디렉터리로 **이동**하므로 메인 체크아웃에서 세션 ID 로 찾아도 없다.

**대응 (스크립트를 고치기 전까지)**: 스크립트 자신의 집계 코드를 파일에 직접 물린다 —
`importlib` 로 `core/scripts/session-cost.py` 를 로드하고 `sc.collect([Path(<jsonl 절대경로>)])`
+ `sc.PRICES` 로 계산한다(추정이 아니라 같은 실측 경로다). 세션 파일 위치는
`find ~/.claude/projects -maxdepth 2 -name '<세션ID>*'` 로 찾는다.

**근본 수정 후보**: `project_dir()` 의 슬러그를 `.replace("/", "-").replace(".", "-")` 로.
소스이므로 위임이 필요하다 — 다음 페이즈 권고에 있다.

### 갱신 (2026-09-02, Phase 16 task 2b 이후)

- **절반은 해소됐다.** `--project` 미지정 시 기준이 cwd 가 아니라 **메인 체크아웃**
  (`git rev-parse --git-common-dir` 의 부모, `main_checkout()`)이 됐다. 워크트리 cwd 에서
  `python3 scripts/session-cost.py --json` 을 돌려도 메인 체크아웃 슬러그 세션이 정상 집계된다
  (Phase 16 실측: `{"files": 3, "project_dir": ".../-home-jh-aigsprac", "usd": 62.48}`).
- **절반은 그대로다.** 슬러그의 `.` → `-` 치환은 여전히 없다(`session-cost.py:48`
  `str(base.resolve()).replace("/", "-")`). 그래서 **파트 세션처럼 세션 자체가 워크트리에서
  시작한 경우**는 `--project .` 으로도 못 찾는다:
  `세션 디렉터리 없음: …/-home-jh-aigsprac-.claude-worktrees-phase16-…`
  (실제 디렉터리는 `-home-jh-aigsprac--claude-worktrees-phase16-…`).
- **더 싼 우회 (importlib 불필요, 2026-09-02 실측)**: 점 자리에 `-` 를 넣은 **유사 경로**를
  `--project` 로 주면 슬러그가 정확히 맞는다 — 존재하지 않는 경로여도 `resolve()` 는
  정규화만 하므로 동작한다.
  `python3 scripts/session-cost.py --project /home/jh/aigsprac/-claude/worktrees/phase16-supervisor-bootstrap --session <id> --json`
  → `{"files": 1, "usd": 3.20…}`. 허용 도구가 `python3 scripts/*.py` 만 열려 있는 헤드리스
  파트 세션에서도 쓸 수 있다(`python3 -c` 는 막힌다).

## 39. `phase-tools.py tasks` 는 접미사 task(`task1a.md`)를 아예 못 본다 (2026-09-02, Phase 16)

**증상**: 파일이 6개(`task1a`·`task1b`·`task2a`·`task2b`·`task3`·`task4`)인 페이즈에서
`python3 scripts/phase-tools.py tasks 16` 이 **task 3·4 두 건만** 돌려준다. 상태 전이도
`--set 1a=done` → `--set 형식은 <task번호>=<status>: '1a=done'` (rc=2) 로 거부된다.

**원인**: 두 곳 모두 정수만 받는다 —
`core/scripts/phase-tools.py:498` `TASK_FILE_RE = re.compile(r"^task(\d+)\.md$")` (목록 스캔),
`:551` `n = int(n_str)` (`--set` 파싱, 실패 시 rc=2).

**왜 위험한가**: 이 JSON 은 "기계 판독 단일 소스"로 선언돼 있고 무인 드라이버·대시보드가
읽는다. 접미사 task 를 쓰면 조회에서 **조용히 빠지고**, `complete` 필드는 보이는 task 만으로
계산되므로 **미완료 페이즈를 완료로 보고**할 수 있다(Phase 16 에서 1a~2b 4건이 통째로 비침).
`--next` 도 마찬가지로 접미사 task 를 건너뛴다.

**대응**: (a) RED/GREEN 을 접미사로 쪼개는 관례를 쓸 거면 상태 전이는 frontmatter 직접 편집으로
하고 `tasks` JSON 의 `complete` 를 신뢰하지 말 것. (b) 또는 접미사를 쓰지 말고 정수 번호를
늘릴 것(`task1`=RED, `task2`=GREEN). **근본 수정 후보**: 정규식을 `^task(\d+[a-z]?)\.md$` 로,
`--set` 파싱을 같은 패턴 검증으로 바꾸고 정렬 키를 `(int, suffix)` 로 — 소스이므로 위임 필요.

## 40. 동결 테스트가 "문서화된 진입점"으로 돌지 않으면 fail-open 을 통째로 놓친다 (2026-09-02, Phase 17 파트 17-3)

**trigger**: 테스트가 문서화된 심링크 진입점 `scripts/phase-tools.py` 대신
`core/scripts/phase-tools.py`를 직접 실행하면.

**changes**: 심링크로 부를 때의 `retry-guard --record` 크래시를 놓쳐 fail-open이 된다. 심링크 진입점을
쓰는 스크립트에는 그 경로로 도는 테스트를 최소 1건 동결해야 한다(함정 32의 동결 사본이 `SCRIPT_DIR`을
잃는 Python 판).

**evidence**: 동결 테스트 12건은 전부 GREEN이었지만 심링크 호출에서 매번 크래시했다 — 동반 스크립트를
`__file__` 의 형제로 찾아 없는 경로 `scripts/supervisor-state.sh` 를 가리켰다. security-reviewer가
지적했고 오케스트레이터가 심링크 경로로 재현했으며, task 3b 재위임 1회차 `d15a8ed`(`__file__` 정규화)로
수정됐다.

**outcome**: 수정 확인. 회귀는 `tests/test_phase_tools.py::RetryGuardHardeningTest::test_record_works_through_symlinked_entrypoint`
로 동결했다 — 심링크 진입점으로 `--record` 를 돌려 exit 0 과 `--check` 의 exit 3 을 함께 단정한다.

**scope**: kit

## 41. 위임이 도는 중에 전체 스위트를 돌리면 없는 실패가 보인다 (2026-09-02, Phase 17 파트 17-2)

**trigger**: `opencode serve`가 떠 있는 위임 실행 중에 전체 스위트를 돌리면.

**changes**: `test_serve_ctl`이 1건 더 실패해 위임의 "선재 실패 11건" 보고가 생긴다. 회귀 판정은
위임이 아니라 오케스트레이터가 위임 종료 후 해야 하며, 위임의 선재 실패 보고를 회귀 기준선으로 삼지
않는다.

**evidence**: 위임 중 `opencode serve`가 떠 있을 때 `test_serve_ctl` 1건이 추가 실패했다. 위임 종료 후
오케스트레이터가 `test_serve_ctl`을 다시 실행해 16건 전부 OK를 확인했다.

**outcome**: 위임 종료 후 재실행에서 `test_serve_ctl` 16건 전부 OK 확인.

**scope**: kit

## 42. RED 를 쓰고 나면 "지금 통과하는지" 를 반드시 확인해라 (2026-09-02, Phase 17 파트 17-3)

**trigger**: RED 테스트를 작성한 직후 실제로 FAIL하는지 실행해 확인하지 않으면.

**changes**: 이미 통과하는 테스트를 RED로 오인해 항상 참인 테스트가 남고 함정 1·14가 재발한다. RED 작성
직후 실행해 FAIL을 눈으로 확인해야 한다.

**evidence**: 처음 작성한 cwd 의존 테스트는 픽스처에 미추적 파일이 없어 이미 통과했고, FIFO 테스트는
git이 FIFO를 미추적 파일로 나열하지 않아 이미 통과했다. 조건 보강 후 전자는 진짜 RED가 됐고 후자는
폐기했다.

**outcome**: cwd 의존 테스트는 조건 보강 후 진짜 RED 확인, FIFO 테스트는 폐기.

**scope**: kit

## 43. `retry-guard` 의 `phase`·`part` 는 문자열 그대로 비교된다 — zero-padding 이 가드를 뚫는다 (2026-09-02, Phase 17 파트 17-4 실측)

**trigger**: `retry-guard`에 같은 파트를 zero-padding 유무가 다른 `phase`·`part` 문자열로 기록·검사하면.

**changes**: 같은 파트가 다른 파트로 취급돼 무변경 재시도가 통과하는 fail-open이 된다. 감독 PROCEDURE와
스크립트 호출부의 표기를 하나로 통일하고 zero-padding을 금지해야 한다. 정규화는 다음 페이즈 후보다.

**evidence**: `--record 17 4` 뒤 `--check 17 04`는 "스코프 불일치로 통과"하며 exit 0이었다.

**outcome**: 미검증 — 정규화 수정은 하지 않았고 호출 규약(zero-padding 금지)으로만 막았다.

**scope**: kit
