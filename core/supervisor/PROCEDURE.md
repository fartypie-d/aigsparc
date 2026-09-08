# 페이즈 감독(supervisor) 세션 시작 절차

> 단일 정본. `/supervise <project>` 와 `/supervise-<project>` 커맨드가 이 파일을 포함한다.
> 상세 설계: `~/docs/2026-09-02-phase-supervisor-design.md` (§4.1 상태 저장소 · §4.3 spawn · §4.4 종료 후 읽기 · §6 루프 · §10 실패 처리)

## 0. 전제 검사 (하나라도 어긋나면 진행하지 말고 보고)

- 커맨드가 지정한 `<project>` 의 레지스트리 `~/.local/state/orchestrate/registry/<project>.json` 이 존재해야 한다.
- 문서 디렉터리와 기본 브랜치는 레지스트리 `~/.local/state/orchestrate/registry/<project>.json` 의 `docs_dir` · `default_branch` 를 따른다. 아래의 `docs/phases/` · `main` 은 그 값으로 읽는다.
- cwd 는 **프로젝트들이 놓인 홈 디렉터리**(`~`) 여야 한다 (`pwd` 로 확인). 프로젝트 디렉터리 안에서 감독을 시작하지 않는다.
- 원격 접근: 감독 세션은 `claude --remote-control --name supervise-<project>` 로 띄우면 claude.ai/code·모바일 앱에 이름으로 뜬다. 별도 클라이언트(음성 입력 단말 등)를 쓴다면 홈 디렉터리를 cwd 로 띄운 세션 목록에서 같은 세션을 재개한다. **같은 세션을 두 기기에서 동시에 열지 않는다**(이중 기록) — 한쪽을 끊고 재개. 같은 세션 ID 재개는 owner 잠금과 충돌하지 않는다.
- 이 세션은 **그 프로젝트만** 다룬다. 다른 프로젝트 요청이 오면 확인 후 거절하고, 그 프로젝트의 `/supervise-<other>` 세션을 따로 띄우라고 안내한다.

## 1. 상태 파일 읽기

`~/.local/state/orchestrate/supervisor/<project>.json` 을 읽는다. 없으면 idle 스키마로 생성한다:

```json
{"project":"<project>","root":"<홈>/<project>","phase":null,"slug":null,"worktree":null,"branch":null,
 "part":null,"status":"idle","child":null,"cost":{"phase_usd":0,"parts":{}},
 "phases_since_review":0,"last_review":"<오늘>","owner":null}
```

## 2. owner 잠금 (프로젝트당 감독 세션은 하나)

리스 단위는 **PID + start_id**다. 세션 ID·jsonl mtime 휴리스틱은 쓰지 않는다. 특히 mtime 30분 추정을 되살리지 않는다 — Phase 17의 🔴 사유였다.

- 내 PID는 Bash 도구의 `$PPID`인 대화형 감독 프로세스다. `start_id`는 ① `~/.claude/sessions/<pid>.json`의 `procStart`(1차 소스, macOS에서도 동작), ② 없으면 `/proc/<pid>/stat`의 마지막 `)` 뒤 22번째 필드로 얻는다. 두 파일은 읽기 전용이며 감독도 파트도 쓰지 않는다.
- 판정은 `~/.local/bin/supervisor-state.sh owner-check <project>`로 한다. 매니페스트가 `core/scripts/supervisor-state.sh`를 `.local/bin/supervisor-state.sh`로 설치하며, 런타임에 `lib/`가 없어도 단독 실행되는 스크립트다.

| stdout 첫 낱말 | 종료코드 | 뜻 | 감독의 행동 |
|---|---:|---|---|
| `alive` | 0 | `owner.pid`가 살아 있고 start_id가 일치 | **잡지 않는다.** 사용자에게 보고하고 끝낸다 |
| `reclaimable` | 1 | owner 없음 · PID 죽음 · PID 재사용(start_id 불일치) · owner 필드 손상 · 봉쇄/심링크 위반 | `owner-take`로 회수 |
| — (stderr) | 2 | 상태 파일 없음 | §1로 돌아가 idle 스키마로 생성 |
| — (stderr) | 3 | `set`의 baseline 불일치(CAS 충돌) | 상태를 다시 읽고 baseline을 새로 계산해 재시도 |
| `unverified` | 4 | PID는 살아 있으나 start_id를 어디서도 못 얻음 | **자동 복구 없음** — 아래 수동 해제 |

> 종료코드 3은 `owner-check`가 아니라 `set`/`patch`/`owner-take`의 쓰기 경로에서 난다. 종료코드 1은 정상 reclaimable과 봉쇄/심링크 위반을 뭉친다 — 분리는 다음 페이즈 후보다.

회수는 `~/.local/bin/supervisor-state.sh owner-take <project> --pid <PID> --start-id <ID>`로 한다.
인자는 정확히 `--pid <값> --start-id <값>` 네 개여야 하며 우회 플래그는 없다. `owner-check`가
0(alive)이나 4(unverified)이면 거부되므로 reclaimable(1)일 때만 회수한다. 정체된 owner를
넘겨받았으면 그 사실을 사용자에게 한 줄 보고한다.

### `unverified`(4) 운영자 수동 해제 절차

옛 owner가 죽고 PID가 무관한 프로세스에 재사용됐는데 `~/.claude/sessions/<pid>.json`도
`/proc/<pid>/stat`도 읽지 못하는 경우다. `kill -0`은 통과하므로 스크립트는 "살아 있지만 동일인인지
모른다"로 남는다. `owner-take`가 4를 거부하는 이유는 자동 강탈 시 살아 있는 감독 세션을 뺏을 수
있어 안전 방향으로 막았기 때문이다.

해제는 사용자 확인 사항이다(설계 D-4의 공개 계약/방향 결정에 준한다). AskUserQuestion으로 묻고,
다음 세 가지를 확인한다: ① `ps -o pid,lstart,args -p <owner.pid>`로 무관한 프로세스인지 눈으로 확인
② 같은 프로젝트의 다른 감독 세션이 실제로 도는지 확인 ③ 상태 파일의 `status`·`child`가 진행 중
파트를 가리키는지 확인하고, 가리키면 그 파트부터 정리한다.

확인 뒤 감독 작업 디렉터리에 프로젝트명을 포함한 파일로 `get` 결과를 받고, **편집 전 원본 바이트**의
sha256 16진 소문자를 baseline으로 계산한 다음 owner를 JSON `null`로 고쳐 `set`한다. `/tmp`는 쓰지
않는다. 아래 `python3` 계산은 `state_hash()`와 같은 바이트 단위 sha256 정의다.

```bash
~/.local/bin/supervisor-state.sh get <project> > supervisor-state-<project>.json
baseline=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' supervisor-state-<project>.json)
# supervisor-state-<project>.json에서 owner를 JSON null로 고친 뒤
~/.local/bin/supervisor-state.sh set <project> - --baseline "$baseline" < supervisor-state-<project>.json
rm -f supervisor-state-<project>.json
```

`patch`로 owner를 풀 수 없다. `patch`는 값을 항상 문자열로 저장하므로 `owner=null`은 JSON
`null`이 아니라 문자열 `"null"`이 된다. 반드시 `get`+`set`을 쓴다. 해제했으면 `decisions.jsonl`에
`kind:"option"`으로 한 줄 남긴다.

마지막으로 종료·인계 시 owner를 `null`로 되돌린다(같은 `get`+`set` 절차).

## 3. 컨텍스트 읽기 (이것만)

- `~/.local/state/orchestrate/supervisor/actions-<project>.md` — 사용자가 해야 할 일
- `~/.local/state/orchestrate/supervisor/queue-drafts/<project>.md` — 큐 초안 (저장소에 `QUEUE.md` 가 아직 없을 때)
- `~/<project>/<docs_dir>/QUEUE.md` (있으면) · `INDEX.md`
- `~/.local/state/orchestrate/registry/<project>.json` — `active` 에 감독 상태 파일과 무관한 claim 이 있으면(감독 밖에서 시작된 페이즈) 워크트리 실존·커밋 여부를 확인하고 사용자에게 보고한다
- **제품 정본(북극성)** — 프로젝트 `docs/phases/DESIGN_service-direction-*.md` 최신본. 다른 저장소가 허브면 `CLAUDE.md` 프로젝트 개요 첫 줄의 경로를 따른다(여러 저장소가 한 제품을 이루면 허브 저장소가 정본). 다음 페이즈 선택은 정본 §3 순서를 따르고, 단계 번호 없는 큐 항목은 정본 §4(비목표)인지 먼저 확인한다.
- `~/.local/state/orchestrate/supervisor/decisions.jsonl` 의 이 프로젝트 꼬리
- `blocked_on` 이 있으면 그 선행 조건이 해소됐는지 상대 프로젝트의 `docs/phases/INDEX.md` · 레지스트리를 **읽기 전용**으로 확인한다.

프로젝트 CLAUDE.md · 자식 로그 · `.err` 는 통째로 읽지 않는다.

## 4. status 에 맞는 단계부터 재개 (설계 §6)

| status | 할 일 |
|---|---|
| `idle` | 큐에서 `approved && 선행 done && 🔴 아님` 항목 선택 → 지시서 작성(§7) → phase-claim → running. 없으면 "큐 비었음/전부 blocked" 보고 후 idle 유지 |
| `running` | `child` 가 살아 있는지 확인(PID 파일 또는 `.orchestrate/part<N>-<k>.json` 비어 있음 여부 — `pgrep` 금지). 죽었으면 §4.4 읽기 → 다음 파트 spawn 또는 비정상 종료 처리 |
| `waiting_ci` | `gh pr checks` → 초록 + SIGN OFF + 충돌 없음 + 🔴 미포함이면 `gh pr merge --merge` → `phase-close` → `phases_since_review += 1` → idle. 🔴 포함이면 actions 에 등록 후 `waiting_user` |
| `waiting_user` | actions 항목 해소 여부 확인(`gh pr view --json merged` 등) → 다음 단계 |
| `closing` | 마감 파트 결과 확인 → PR·CI 상태에 따라 `waiting_ci` |

**시작 보고 (사용자에게, 3줄)**: 프로젝트·status·phase/part / 이번에 할 일 / 사용자 확인이 필요한 항목(없으면 "없음").

## 5. 파트 세션 spawn (설계 §4.3, Phase 16 실측 반영)

`run_in_background` 로 한 줄 실행. `cd` 는 서브셸 안에서만. `< /dev/null` 필수(stdin 대기 경고 방지).


```bash
( cd <워크트리> && : > .orchestrate/part<N>-<k>.json && pwd && git log --oneline -1 \
  && ls .orchestrate/part<N>-<k>.prompt \
  && mapfile -t TOOLS < <메인 체크아웃>/.claude/part-allowed-tools.txt \
  && claude -p "$(cat .orchestrate/part<N>-<k>.prompt)" \
       --append-system-prompt-file <메인 체크아웃>/.claude/part-protocol.md \
       --allowedTools "${TOOLS[@]}" --add-dir <메인 체크아웃>/.orchestrate \
       --max-turns 200 --output-format json < /dev/null \
  > .orchestrate/part<N>-<k>.json 2> .orchestrate/part<N>-<k>.err; echo "spawn_exit=$?" )
```

- **허용 도구·파트 프로토콜은 워크트리가 아니라 메인 체크아웃의 `.claude/` 에서 읽는다**(2026-09-07). 워크트리는 claim 시점 스냅샷이라 claim 뒤 고친 허용 목록이 파트에 안 가던 함정(F-20)을 spawn 에서 닫는다. 메인의 미커밋 변경도 즉시 적용되므로 허용 목록 변경은 chore PR 로 곧 병합한다.
- 파트 종료 후 결과 JSON 의 **`permission_denials` 를 반드시 읽는다.** 거부된 명령이 있으면 HANDOFF 와 `actions-<project>.md` 에 명령 원문을 남기고 허용 목록 갱신 후보로 올린다 — 파트의 "미실행" 보고를 감독이 대신 돌리기 전에 원인을 기록한다.
- 완료 감시는 Monitor 로: `.json` 이 비어 있지 않음 + 자식 세션 jsonl mtime 나이(20분+ 정체 경고). 프로세스 이름으로 찾지 말 것.
- 종료 후 읽는 것 6가지만(§4.4): 결과 JSON 꼬리(`result`·`total_cost_usd`·`num_turns`·`is_error`) · `phase-tools.py tasks <N>` JSON · HANDOFF · ESCALATION · events.jsonl 꼬리 20줄 · `git status`/커밋 수.
- 헤드리스 자식은 **턴을 끝내면 죽고 백그라운드 위임도 같이 죽는다.** 자식이 "완료 통지를 기다리겠다" 로 끝났으면 비정상 종료로 처리하고, 산출물 확인 후 재개 프롬프트에 `결정:` 을 주입한다.
- `setsid`/`nohup` 은 하네스가 거부. cwd 밖 파일에 `>>` 쓰기도 거부(`tee -a <절대경로>` 를 허용 도구에 명시).
- 한도: 파트 $40 · 페이즈 $200 · 반려 2회 · 모델 전멸 → 감독 판단(중단/축소/재지시) + `decisions.jsonl` 기록.

### 파트 실패 처리 — retry-guard

파트가 실패(비정상 종료·`PART_ESCALATED`·산출물 없음)했으면 **재시도 전에** 워크트리에서 다음을 실행한다:
`python3 scripts/phase-tools.py retry-guard <N> <k> --check`.

| 상황 | 종료코드 | stdout 첫 낱말 |
|---|---:|---|
| 통과 — 변경 있음 · 기록 없음 · 스코프 불일치 | 0 | (없음) |
| 무변경 재시도 — **막는다** | 3 | `retry_exhausted` |
| 상태 파일 없음 | 2 | — |
| `--record` baseline(CAS) 충돌 | 4 | — |
| 그 밖의 오류 — JSON 손상 · git 실패 · `phase` 비정수 | 1 | — |

3이면 같은 파트를 그대로 다시 띄우지 않는다. 프롬프트에 `결정:`을 주입하거나 범위를 줄이거나
사용자에게 에스컬레이션한다. 파트 실패를 확정했으면 `python3 scripts/phase-tools.py retry-guard <N> <k> --record`로
스냅샷을 기록한다. 기록이 0이 아니면 실패 처리를 중단하고 원인을 먼저 해결한다. 기록이 없으면
다음 `--check`가 무조건 통과해 가드가 무력화된다.

스냅샷 대상은 호출된 워크트리(`git rev-parse --show-toplevel`)이고 상태 파일은 메인 체크아웃
이름(`<project>.json`)이다. 여러 워크트리가 상태 파일을 공유하지만 재시도 판정은 자기 워크트리다.
호출부의 `phase`·`part` 표기는 zero-padding 없이 일관되게 쓴다. 문자열 정규화 없이 비교하므로
`4`와 `04`는 다른 파트로 취급되어 통과(fail-open)한다(2026-09-02 실측: `--record 17 4` 뒤
`--check 17 04`는 스코프 불일치로 통과, exit 0).

## 6. 결정 권한 (D-4 · D-5)

- **사용자 확인 필수는 두 가지뿐**: 🔴 위험 도메인 task 착수 · 공개 계약/방향 결정(큐에 없는 페이즈 신설 포함). 이때만 AskUserQuestion.
- 그 외(비용·실패 한도·푸시·병합·선택지)는 감독이 결정하고 `decisions.jsonl` 에 한 줄 append:
  `{"ts","project","phase","part","kind":"option|limit|merge|scope","question","chosen","why","escalated":false}`
- 자동 병합 조건: CI 초록 + 리뷰 SIGN OFF + 충돌 없음 + 🔴 미포함 → `gh pr merge --merge` → `phase-close`. 🔴 포함 페이즈는 사용자 병합.
- 정기 점검 보고서에는 **"제품 정본 §3 대비 이탈 페이즈 수"** 항목을 넣는다(정본이 있는 프로젝트).
- `phases_since_review == 5` 면 설계 §8 정기 점검을 먼저 수행하고 `supervisor/reviews/YYYY-MM-DD-<project>.md` 에 남긴다.

## 7. 상태 갱신 규칙

- 상태 전이·비용 갱신·`child` 기록은 전부 `~/.local/bin/supervisor-state.sh`로 한다. 상태 파일을 손으로 통째 다시 쓰지 않는다.
- `set <project> - --baseline <sha256>`에서 `--baseline`은 필수이고 우회 플래그가 없다. 해시는 원본 바이트의 sha256 16진 소문자다(python3 `hashlib` 기준). baseline이 다르면 exit 3으로 거부하며 조용한 덮어쓰기는 없다.
- `patch <project> <key>=<value>`는 read-modify-write 편의 명령이며 값이 항상 문자열로 저장된다. 숫자·`null`·객체 필드에는 쓰지 말고 `get`+`set`을 쓴다.
- 사용자가 해야 할 일은 `actions-<project>.md` 에만 적는다(다른 프로젝트 파일 건드리지 않음).
- 세션을 끝내거나 인계할 때 owner 를 `null` 로 되돌리고, 마지막 보고에 status·다음 할 일을 남긴다.
