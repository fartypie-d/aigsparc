---
description: 감독 세션 재시작 준비 — 진행 중인 것 점검, 싼 잔손질 마무리, 재개 지시 기록, owner 반납
argument-hint: [project] [--check-only]
---

이 세션을 **새 컨텍스트로 재시작할 수 있는 상태**로 정리한다. 감독 세션 전용이다.

인자: $ARGUMENTS

## 0. 전제

- **감독 세션에서만 실행한다.** 이 세션이 `/supervise-<project>`(또는 `/supervise <project>`)로 시작한 감독 세션이 아니면
  아무것도 쓰지 말고 "감독 세션이 아니다"라고 보고하고 끝낸다.
- 프로젝트는 `$1`. 비어 있으면 **이 세션이 감독 중인 프로젝트**로 본다. 맥락상 모호하면 되묻는다.
  한 세션이 두 프로젝트를 정리하지 않는다 — owner 잠금이 프로젝트당 하나다.
- `--check-only` 가 있으면 **1~2 단계만** 수행하고 보고 후 끝낸다. 아무것도 쓰지 않는다.
- 이 커맨드는 **감독 재시작이 곧 파트 사살**이라는 전제 위에 있다. 살아 있는 파트를 기다려 주지 않는다.
- 경로: 프로젝트 루트·문서 디렉터리는 레지스트리 `~/.local/state/orchestrate/registry/<project>.json` 의 `root`·`docs_dir` 를 따른다.
  아래의 `<root>` 는 그 값이다.

## 1. 진행 중인 것 점검 (읽기 전용, 전부 조회로)

기억으로 채우지 말 것 — 아래를 실제로 돌린다.

- **상태**: `~/.local/bin/supervisor-state.sh get <project>` → `status` · `child` · `phases_since_review` · 비용
- **파트 생존**: `child` 가 가리키는 `<워크트리>/.orchestrate/part<N>-<k>.json` 이 비어 있는지,
  그리고 자식 세션 jsonl 의 나이. 나이는 `stat -c %Y <파일>` 과 `date +%s` 의 차로 잰다.
  🔴 `pgrep`·`grep -c` 로 프로세스를 세지 않는다(자기 명령줄이 매칭된다).
- **메인 체크아웃 미커밋**: `git -C <root> status --porcelain`
- **워크트리**: `git -C <root> worktree list` → 각 워크트리의 `status --porcelain` 과
  `git log --oneline @{u}..HEAD`(미푸시)
- **열린 PR·CI**: `gh pr list --repo <owner>/<repo> --json number,title,isDraft,headRefName`.
  CI 상태는 체크 API(REST `/repos/<owner>/<repo>/commits/<sha>/check-runs`)로 본다 — 「호스트별 주의」 참조.
- **레지스트리**: `~/.local/state/orchestrate/registry/<project>.json` 의 `active` claim
- **파트 결과 미확인분**: 최근 파트 결과 JSON 의 `permission_denials` 중 `actions` 에 안 남은 것

## 2. 분류와 판정

점검 결과를 두 통으로 가른다.

**🔴 비싼 진행 — 커맨드가 끝내지 않는다. 보고만 한다.**

| 항목 | 지금 재시작하면 |
|---|---|
| 살아 있는 파트 | **죽는다.** 헤드리스 자식은 감독이 사라지면 결과를 넘길 데가 없다 |
| CI 대기 중인 PR | 안 죽지만 **아무도 안 본다** — 재개 지시에 명시해야 한다 |
| 열린 페이즈(`running`/`closing`) | 다음 세션이 §4 표대로 재개해야 한다 |

**살아 있는 파트가 하나라도 있으면 여기서 멈춘다.** "파트 N-k 가 살아 있다 / 마지막 활동 M분 전 /
지금 재시작하면 이 파트가 죽는다"를 보고하고, 사용자가 명시적으로 강행을 지시할 때만 3단계로 간다.

**🟢 싼 잔손질 — 3단계에서 마무리한다.** 미커밋 감독 변경 · 미푸시 브랜치 · 기록 누락
(`HANDOFF`·`actions`·`decisions.jsonl`·`permission_denials`).

## 3. 싼 잔손질 마무리

- **감독이 만든** 미커밋 변경만 커밋한다(계약 스냅샷 재동기화·로스터·문서 등). conventional commits.
  🔴 **파트 워크트리의 미커밋 변경은 건드리지 않는다** — 파트 소유다. 보고만 하고 남긴다.
- 미푸시 브랜치는 **브랜치 이름을 명시해서** 푸시한다.
- 이번 세션에서 내렸는데 `decisions.jsonl` 에 없는 결정을 지금 append 한다
  (`{"ts","project","phase","part","kind","question","chosen","why","escalated"}`).
- 기록 안 된 `permission_denials` 는 명령 원문 그대로 `actions-<project>.md` 에 남긴다.

## 4. 실측 재집계

재개 지시에 쓸 숫자를 **지금 조회해서** 다시 센다. 기억·이전 세션 문장을 옮기지 않는다.

`origin/<기본 브랜치>` sha · 열린 PR 수 · 워크트리 수 · 파트 수 · `status` · `phases_since_review` ·
큐 approved·미착수 수(`approved` 는 접두일치 `^true` 로 센다 — `docs/phases/QUEUE.md` 머리의 규칙).

형제 프로젝트에 걸린 선행이 있으면 **상대 저장소의 `origin/<기본 브랜치>` 원문**과 그쪽
`<docs_dir>/INDEX.md`·레지스트리로 확인한다 — 우리 큐 행 인용을 형제 상태의 근거로 쓰지 않는다.

## 5. `actions-<project>.md` 갱신

`~/.local/state/orchestrate/supervisor/actions-<project>.md` 를 연다.

**(a) 맨 위 요약 한 줄**을 4단계 실측값으로 덮는다:

> 최종 갱신 `<날짜 시각 타임존>`. main **`<sha>`** · status **`<status>`** · 열린 PR **N** · 워크트리 **N** ·
> 파트 **N** · `phases_since_review` **N** · **owner 반납(`null`) — 세션 재시작 준비 완료**.
> 재시작은 이 세션을 `/exit` 한 뒤 **런처 재시작 명령**(이 호스트에서 감독 세션을 띄우는 그 명령 — 없으면 `claude` 를 새로 띄워 `/supervise-<project>`)으로 새 세션을 연다.
> 재개는 아래 **「▶ 재개 지시 (최종)」 절 하나만** 읽으면 된다.

**(b) 「▶ 재개 지시 (최종)」 절을 요약 바로 아래, 파일 맨 위에 하나만 둔다.**
옛 ▶ 절이 있으면 `▶ (구) 재개 지시 YYYY-MM-DD` 로 제목을 바꿔 아래로 강등한다.
위치는 **항상 맨 위**로 통일한다 — 프로젝트마다 "맨 위"/"맨 아래"로 갈리면 다음 세션이 헤맨다.

재개 지시에 담을 것 네 가지만:
1. **다음 첫 행동 하나** — 명령 또는 읽을 파일까지 구체적으로
2. 그 전에 읽을 것(§3 컨텍스트 목록 중 이번에 실제로 필요한 것만)
3. **사용자 조치 대기 항목** — 없으면 "없음"
4. **하지 말 것** — 이번 세션에서 이미 기각·확인된 경로

## 6. owner 반납

`patch` 로는 풀 수 없다(값이 문자열 `"null"` 이 된다). `get`+`set` 으로, `/tmp` 를 쓰지 않는다.

```bash
~/.local/bin/supervisor-state.sh get <project> > supervisor-state-<project>.json
baseline=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' supervisor-state-<project>.json)
# supervisor-state-<project>.json 에서 owner 를 JSON null 로 고친 뒤
~/.local/bin/supervisor-state.sh set <project> - --baseline "$baseline" < supervisor-state-<project>.json
rm -f supervisor-state-<project>.json
```

`set` 이 exit 3 이면 그 사이 상태가 바뀐 것이다 — 덮지 말고 `get` 부터 다시 한다.

owner 반납이 끝나면, **감독 위 계층의 인박스 파일이 있으면**(예 `~/.local/state/orchestrate/supervisor/cto/inbox.jsonl`)
`{ts,project,event:"restart_prep",phase,sha,psr,next,note}` 한 줄을 append 한다 — 파일이 없으면 만들지 않고 건너뛴다(실패해도 진행).

## 7. 메모리 갱신

이 감독 세션의 자동 메모리(`~/.claude/projects/<감독 cwd 를 경로 인코딩한 디렉터리>/memory/`)에
프로젝트 항목이 있으면 그 본문과 `MEMORY.md` 의 그 프로젝트 줄을 4단계 실측값으로 맞춘다.
재개 진입점은 "actions 맨 위 「▶ 재개 지시 (최종)」" 하나로 쓴다.

## 8. 보고 (5줄 이내)

1. 정리한 것 (커밋·푸시·기록)
2. **남은 진행 중** — 없으면 "없음", 있으면 재시작 시 무엇이 날아가는지
3. owner 반납 여부
4. 재시작 명령: `/exit` → 런처 재시작 명령(§5 (a)와 같은 것)
5. 🔴 `claude --continue` 로 재개하지 않는다 — 옛 대화를 되살리고, 감독이 전부 같은 홈 cwd 라
   다른 감독 세션을 잡을 수 있다.

## 함정 (이 커맨드를 도는 동안 밟기 쉬운 것)

- `pgrep`·`grep -c` 로 파트를 센다 → 자기 명령줄이 매칭된다. **나열해서 눈으로 본다.**
- `supervisor-state.sh patch` 로 owner 해제 → 문자열 `"null"`.
- **exit 0 · running · 초록은 존재의 증거가 아니다.** 정리했다고 적기 전에 그 증상이 사라졌는지 본다.

### 호스트별 주의 — 너의 호스트에서 확인하라

아래는 한 호스트에서 실측된 것이다. 같은 이름의 도구라도 구현·버전이 다르면 다르게 행동하므로,
처음 이 커맨드를 돌리는 호스트에서는 각 항목을 한 번씩 직접 확인하고 결과를 `actions-<project>.md` 에 남긴다.

- `find -newermt` — `find` 가 GNU findutils 가 아니면(예: bfs) `Invalid timestamp` 로 거부할 수 있고, `2>/dev/null` 이 그걸
  삼키면 정상 진행을 "정체"로 보고한다. 나이는 `stat -c %Y` 로 재는 편이 이식성이 높다.
- `gh pr checks --json` — 오래된 `gh` 는 미지원이라 거짓 "체크 없음"을 낸다. `gh --version` 을 보고, 의심되면 REST 체크 API 로 본다.
- 런처 CLI(터미널 멀티플렉서·세션 매니저)의 종료코드만 보고 갈리지 마라 — 서버 오류와 문법 오류가 코드로 안 갈리는 도구가 있다.
  오류 본문(`stderr`)을 읽는다.
