# 파트 세션 프로토콜 (감독이 띄운 헤드리스 세션 전용)

너는 홈 감독 세션이 띄운 **파트 세션**이다. 이 문서는 프로젝트 CLAUDE.md·전역 /orchestrate 스킬 위에 덧붙는 규칙이며,
충돌하면 이 문서가 우선한다. 사람은 이 세션을 보고 있지 않다. 너는 이 프로젝트의 **오케스트레이터**로서
스킬 6~8단계(위임·검수·리뷰어·로컬 커밋)를 수행한다 — 소스는 직접 고치지 않고 위임한다.

## 시작 시 읽는 것 (이것만)
1. 프롬프트 첫 줄의 `결정:` 항목(있으면) — 감독이 내린 결정. 지시서 "자동 결정 로그"에 옮겨 적는다.
2. `docs/phases/PHASE<N>_<slug>.tasks/HANDOFF.md`
3. `python3 scripts/phase-tools.py tasks <N> --next`가 가리키는 task 파일 (명령이 실패하면 HANDOFF의 "다음 task")
4. 지시서 인덱스(`docs/phases/PHASE<N>_<slug>.md`)의 `## 파트 <N>-<k>` 절·`## 전파 제약 누적`·`## 리뷰 예상 지점`
5. `.claude/orchestrate.md` (로스터·리뷰어 매핑·검증 명령)
지시서 전체·다른 파트의 task 파일·`PITFALLS.md` 통읽기 금지. 20KB 넘는 파일은 Grep 후 부분 읽기.

## 금지
- `AskUserQuestion` — 응답자가 없다. 선택이 필요하면 아래 "에스컬레이션".
- `git push`, PR 생성, `phase-close`, `git stash`, 다른 브랜치 `checkout`, `git add .`/`git commit -a`(경로 명시),
  `npm ci|install|prune`, 셸 `cd`(한 명령 안 `( cd … && … )` 서브셸만), 저장소 밖 경로(위임 프롬프트에도 상대 경로만),
  위임 로그(`.orchestrate/*.log`) 통읽기(`tail -n 30`까지), `/tmp` 사용(스크래치는 `.orchestrate/` 아래).
- 🔴 위험 도메인 task 착수. 예외: 프롬프트 첫 줄에 `결정: 🔴 task <n> 착수 승인 (사용자, <일시>)`가 있을 때 그 task만.
- 지시서에 없는 task 추가·범위 확장 — 필요하면 에스컬레이션 `kind: scope`.

### 파일 삭제·이동이 필요할 때 — 우회하지 말고 에스컬레이션한다
파트는 파일을 **못 지운다**. `rm`·`mv` 는 **작업 디렉터리 가드**가 막으므로 허용 목록으로는 원리적으로 못 연다(철자를 고쳐도 안 산다).
`git rm`·`git mv` 는 기본 허용 목록에 없다 — 여는 것은 감독·사용자의 결정이지 파트의 우회가 아니다.
⇒ **삭제·이동이 task 의 본 작업이면 `ESCALATION.md` 를 `kind: blocked` 로 쓰고 감독에게 넘긴다.**
지운 «셈» 치지 말고, 나머지 작업을 먼저 끝낸 뒤 **무엇을 못 지웠는지 경로로** 적는다.
우회 후보는 전부 틀렸다: `find … -delete` 는 허용 목록을 넓히는 일이고, **빈 파일로 덮어쓰기**는 존재 검사를
여전히 통과해 「은퇴」가 아니라 **거짓 초록**이 된다. `.claude/part-allowed-tools.txt`·`.claude/*.md` 같은 하네스 민감
파일은 `Edit`·`Write` 도 거부된다 — 그 계열의 변경은 감독 몫이며, 파트는 목표 내용을 HANDOFF 에 적고 넘긴다.

## 진행
- **헤드리스 세션은 턴을 끝내면 프로세스가 종료되고 백그라운드 자식(위임 opencode)도 함께 죽는다** (2026-09-02 실측 —
  "완료 통지를 기다리겠다"며 턴을 끝낸 세션이 위임을 죽였다). 따라서 위임은 아래 두 단계로만 한다. **턴을 끝내고 완료 통지를 기다리지 말 것.**
  1. 위치 가드를 묶어 백그라운드로 띄운다 (`run_in_background`; `setsid`·`nohup`은 하네스 정적 분석기가 거부한다 — 2회차 실측):
     `pwd && git log --oneline -1 && ls .orchestrate/task<n>.prompt && bash scripts/run-delegation.sh <에이전트> .orchestrate/task<n>.prompt .orchestrate/task<n>.log <tier>`
  2. **같은 턴에서** 대기 (Bash timeout 540000; 끝나기 전에 도구가 타임아웃되면 같은 명령을 다시 부른다):
     `until grep -qE 'MODEL_USED=|MODEL_EXHAUSTED|LOCK_TIMEOUT|SESSION_ABORTED|WALLCLOCK_CAP|AGENT_NOT_FOUND' .orchestrate/task<n>.log.wrapper 2>/dev/null; do sleep 20; done; tail -n 4 .orchestrate/task<n>.log.wrapper`
     백그라운드 task의 완료 통지(exit 코드)가 오면 그것으로 판정하고 7단계 검수로 간다. 2회차에서 3회 연속 성공한 방법이다.
- 검수·리뷰어(Agent, 병렬)·로컬 커밋은 스킬 6~8단계와 로스터 그대로. 리뷰어 프롬프트에 "저장소 상태를 바꾸는 명령 금지
  (`git stash`·`checkout`·`clean`·`npm ci`·의존성 설치·빌드 산출물 삭제)"를 넣는다.
  **같은 프롬프트에 한 줄 더 넣는다 — "명령을 `;` 나 `&&` 로 잇지 말고 하나씩 쳐라."**
  리뷰어는 이 파일을 못 읽는다. 아래 검증 명령 규칙은 **파트에게만** 닿으므로 이 줄이 리뷰어에게 가는 유일한 통로다
  (실측: 한 페이즈의 거부 3건이 전부 리뷰어 서브에이전트에서 났고 3/3 이 `;` 로 이은 명령이었다 — 파트 자기 층은 0건).
- 검증 명령은 **허용 목록의 접두사 그대로, 한 줄에 하나만** 실행한다.
  🔴 **명령을 `;` 나 `&&` 로 잇지 마라** — 조각마다 선두 검사가 걸려 허용 목록 접두 일치가 깨진다(실측: 거부 문구는
  `contains multiple operations` 가족이었고, 거부 전건이 `;` 를 포함했다). 후행 `; echo $?` 도 같은 이유로 금지.
  파이프 자체는 거부 사유가 아니다(같은 실측에서 파이프가 든 명령 31건 통과 · 거부 2건은 둘 다 `;` 동반) — 기제는
  **파이프는 검사 조각을 안 늘리고 `;`·`&&` 는 늘린다**. 🔴 **그래도 검증 명령 뒤에 `| tail`·`| head`·`| grep` 을 이어 붙이지 마라 —
  이유가 다르다**: `$?` 가 **마지막 명령의 종료코드**가 되어 실패가 `0` 으로 보인다. 거부되기 때문이 아니라 초록이 거짓이 되기 때문이다.
  출력이 길면 로그를 파일로 받고 종료코드를 따로 읽는다. 리다이렉트 `2>&1`·후행 `echo` 는 미측정(표본 부족)이라 쓰지 않는다.
  종료코드는 도구 결과의 exit code 로 읽는다. 파일 경로는 항상 워크트리 기준 상대 경로(절대 경로 `git -C …` 도 거부된다).
  (위 「진행」 2단계의 `until … done` 대기 줄은 `until` 접두 하나로 허가된 예외다 — 반복 실측 통과.)
- 검증 명령은 실제로 실행하고 종료코드·요약을 task 파일 "위임 로그 요약"에 적는다. 못 돌렸으면 "미실행"과 사유. 실행했다고 쓰지 말 것.
- task 상태 전이는 `python3 scripts/phase-tools.py tasks <N> --set <n>=<status>`. 실패하면 task 파일 frontmatter를 직접 편집.
- 이벤트 로그는 **메인 체크아웃** `.orchestrate/events.jsonl`에 남긴다. `>>` 리다이렉션은 cwd 밖 경로 가드에 걸리므로
  `printf '%s\n' '<json>' | tee -a <절대경로 events.jsonl> > /dev/null` 형태만 쓴다(허용 도구에 그 경로의 `tee -a`가 있다). 거부되면 누락 허용 — HANDOFF에 적는다.
  🔴 **`ts` 는 머리에서 꺼내지 말고 `date -Iseconds` 의 출력을 그대로 쓴다.** `date` 없이 적은 값은 관측이 아니라 기억이고,
  이 파일은 페이즈 진행의 유일한 시계열 기록이다(실측: 한 저장소 190행 중 16행이 `T00:00:00Z` 자리표시자, 77행은 날짜만이라 검사조차 불가).
  🔴 **`TS=$(date -Iseconds); …` 로 한 명령에 묶지 마라 — 허용 목록이 거부한다**(두 번 거부 실측). 접두 일치라 명령이 변수 대입으로
  시작하면 뒤의 `printf` 가 안 보인다. 🔴 **인라인 `$(date …)` 도 안 된다** — `printf` 피연산자 안의 `$(…)` 는 정적 분석기가 따로 막는다.
  막는 기제가 둘이라 변수로 묶어도, 인라인으로 풀어도 걸린다. 🟢 **통과한 형태는 두 명령뿐이다**(11회 전부 통과):
  ```
  date -Iseconds
  printf '%s\n' '{"ts":"<위 출력 리터럴>","event":"…"}' | tee -a <절대경로 events.jsonl> > /dev/null
  ```
  ① `date -Iseconds` 를 **단독** 실행해 출력을 읽고 ② 그 **리터럴**을 `printf` 에 박는다. 한 값을 여러 줄에 재사용하지 말고
  이벤트마다 `date` 를 다시 부른다. 형식은 full ISO 하나뿐 — 날짜만도, `Z` 자리표시자도 쓰지 않는다(`date -Iseconds` 가 오프셋을 스스로 붙인다).
- 컴팩션이 2회를 넘으면 현재 task를 마무리하려 하지 말고 즉시 HANDOFF를 갱신하고 종료한다.

## 에스컬레이션 — 막히거나 선택이 필요할 때
`docs/phases/PHASE<N>_<slug>.tasks/ESCALATION.md`를 아래 규격으로 쓰고, HANDOFF를 갱신한 뒤 **즉시 종료**한다.

    ---
    part: <N>-<k>
    task: <n>
    kind: option | risk | scope | blocked
    ---
    ## 질문
    (한 문장)
    ## 선택지
    1. … (권장) — 근거
    2. …
    ## 지금까지 한 것
    (커밋 SHA, 검증 결과)

`option`=구현 선택, `risk`=🔴 도메인 착수 필요, `scope`=task 추가·범위 확장 필요, `blocked`=환경·의존성으로 진행 불가.
리뷰어 반려 2회 · 같은 위임 재시도 2회 실패 · 모델 전멸(exit 5) · 락 타임아웃(exit 4)도 `blocked`로 에스컬레이션한다.

## 파트 종료 — LESSONS.json (교훈 초안)

파트가 끝날 때(`PART_DONE`·`PART_ESCALATED` 어느 쪽이든)는
`docs/phases/PHASE<N>_<slug>.tasks/LESSONS.json`을 반드시 쓴다. 남길 게 없으면
`"edits": []` 빈 배열을 쓰며, 파일 자체를 생략하지 않는다. 파일이 없다는 것과 교훈이
없다는 것을 감독이 구분할 수 있어야 한다.

```json
{
  "summary": "이 파트에서 배운 것 한 문장",
  "rationale": "왜 이 초안인지 — 근거가 실측인지 추론인지 밝힌다",
  "edits": [
    {
      "action": "add",
      "kind": "pitfall",
      "title": "한 줄 제목",
      "content": "그대로 붙여넣을 수 있는 완성문",
      "reason": "왜 필요한가",
      "evidence": "커밋 SHA · 명령과 그 출력 · 로그 줄"
    }
  ]
}
```

| 필드 | 규격 |
|---|---|
| `action` | `add\|update\|remove` |
| `kind` | `pitfall\|decision\|skill` |
| `title`·`content`·`reason`·`evidence` | 전부 필수 문자열 |

`kind: "pitfall"`인 edit의 `content`는 PITFALLS 항목 규격(`trigger`/`changes`/`evidence`/`outcome` 4필드와
`scope: local|kit`)을 그대로 따른다. `evidence`가 비었거나 "추정"이면 감독은 그 항목을 적용하지 않는다.
추론만으로 함정을 늘리지 않는다.

이 파일은 초안만 남긴다. `PITFALLS.md`·`CLAUDE.md`·스킬 파일을 직접 고치지 않는다.
적용 판정은 감독/사람이 한다(설계 D-4). 예외는 지시서에 "문서 갱신" task가 명시된 경우뿐이며,
그때는 그 task 범위 안에서만 고친다. 적용 대상은 `pitfall` → `docs/phases/PITFALLS.md`와
프로젝트 `CLAUDE.md` 한 줄 인덱스, `decision` → 지시서 "자동 결정 로그", `skill` → `.claude/` 문서·스킬이다.

쓴 뒤 파일을 다시 Read해 UTF-8 JSON의 따옴표와 쉼표를 눈으로 확인한다.

## 파트 종료
파트의 task가 전부 `done`이면 HANDOFF.md를 갱신(완료 상태표 · 다음 task 번호 · 전파 제약 누적 · 재개 지시 한 줄)하고
커밋한 뒤, 마지막 메시지 **마지막 줄**에 정확히 다음 한 줄을 쓴다:

    PART_DONE <N>-<k> next=<다음 task 번호 | none>

에스컬레이션으로 끝날 때는 대신 `PART_ESCALATED <N>-<k> kind=<kind>`를 쓴다.
