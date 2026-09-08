# __PROJECT__ 오케스트레이터 로스터

> 전역 `/orchestrate` 스킬이 참조하는 프로젝트별 에이전트 목록·리뷰어 매핑·TDD 규정·검증 명령.
> 에이전트 정의: `.opencode/agent/*.md`
> 호출: **`~/.opencode/bin/opencode run --agent <이름> "..."`** (opencode는 PATH에 없을 수 있음 — 전체 경로 사용)
>
> ⚠️ 이 파일은 스캐폴드다. 프로젝트 온보딩 시 `[TODO]`를 전부 채울 것 — 로스터 없이 위임 금지가 스킬 0단계 규칙이다.

## 에이전트 로스터 (구현 = opencode)

> **모델은 프로젝트 정책을 우선하고 host 정책으로 폴백하는 tier 체인으로 배정한다.**
> `scripts/run-delegation.sh`는 먼저 `<git 최상위>/.claude/model-policy.json`을 찾고, Git 저장소가
> 아니면 `<호출 cwd>/.claude/model-policy.json`을 찾은 뒤 `~/.config/opencode/model-policy.json`으로
> 폴백한다. 체인 순서대로 `-m`을 주입하고 한도·무응답과 크레딧 오류 시 자동 폴백하며,
> 실제 정책은 `POLICY_USED=<경로> (project|host)`로 stdout과 `.wrapper` 로그에 기록한다.
> 두 정책 파일이 모두 없으면 exit 64로 종료하며 두 후보 경로를 오류에 표시한다.
> `default` = 일반 task / `heavy` = **large 등급·🔴/⚠️ 위험 도메인 task는 처음부터 heavy** + 🔴 반려 재위임 자동 승격.
> `.opencode/agent/*.md`의 `model:`은 수동 실행용 안전 기본값일 뿐이다.
> 실사용 모델은 스크립트 출력 `MODEL_USED=` 로 확인한다. 특정 task에 특정 모델을 강제하려면
> 지시서 task의 `모델:` 필드에 `provider/model`을 쓴다.

| 에이전트 | 담당 | 위험도 (🔴·⚠️는 heavy 기본) |
|---|---|---|
| `[TODO-에이전트명]` | [TODO: 담당 디렉터리·모듈] | [TODO: 낮음/보통/⚠️/🔴 + 사유] |

> 모델 ID는 `~/.config/opencode/opencode.json`의 `models{}`에 등록된 것만 유효하다.
> 등록 확인: `opencode models`. 예외: `xai/*`는 `/connect` OAuth 빌트인이라 등록 없이 유효.

## task 실행 주체 (standard·large 페이즈)

standard·large 등급에서는 메인이 opencode를 직접 부르지 않고 **task마다
`task-orchestrator` 서브에이전트**(`.claude/agents/task-orchestrator.md`)를 호출한다 —
task당 3~5만 토큰의 위임 출력·로그가 메인에서 요약 2~3천 토큰으로 압축된다.
trivial·small은 메인이 `bash scripts/run-delegation.sh`로 직접 위임한다.
리뷰어 호출·판정·GATE는 메인 전속 (task-orchestrator에는 Agent 툴이 없다).

## 리뷰어 매핑 (검수 = Claude 서브에이전트)

task 하나가 끝날 때마다 해당 도메인의 리뷰어를 **Agent 툴로 호출**한다. 2개 이상이면 **병렬 호출**.

> **flash 계열 원칙**: 실사용 모델(`MODEL_USED=`)이 gemini flash 계열이면 아래 표에 없어도
> `silent-failure-hunter`를 리뷰어에 필수 추가한다 (bake-off 실측 약점 = silent fallback).

| 구현 에이전트 | 리뷰어 (ECC `~/.claude/agents/` 우선) | 출처 |
|---|---|---|
| `[TODO]` | [TODO: 예 `python-reviewer` + `silent-failure-hunter`] | ECC |

- **새 리뷰어를 만들기 전에 ECC 대응물을 먼저 확인**한다. 프로젝트 리뷰어는 ECC에 없는
  도메인에만 만들고, 근거를 여기 한 줄로 남긴다.
- 판정에 🔴 Critical이 하나라도 있으면 **반려** — 같은 에이전트에 **heavy tier로**
  재위임(`run-delegation.sh ... heavy`, 최대 2회).
- 모든 리뷰어 호출에 중복 검사 지시 포함 (`_reuse-rules.md` 참조).

## TDD 게이트

지시서의 각 task에는 **`실패 테스트`** 필드가 있어야 한다. 위임 프롬프트는 항상:
① 실패 테스트 작성·실패 확인 → ② 구현 → ③ 테스트 출력 첨부.

| 도메인 | 테스트 위치 | 러너 |
|---|---|---|
| [TODO] | [TODO] | [TODO: 절대경로 러너 — bare pytest는 PATH에 없을 수 있다] |

### 대체 검증 (테스트를 쓸 수 없는 경우에만 — 불가 사유를 지시서에 명시)

| 상황 | 대체 검증 |
|---|---|
| [TODO] | [TODO] |

## 도메인별 검증 명령 (검수 시 실행)

| 도메인 | 명령 |
|---|---|
| [TODO] | [TODO] |

## 커밋 컨벤션 (검수 통과 후 오케스트레이터가 수행)

conventional commits (`feat:`/`fix:`/...). scope: [TODO]. 기본 브랜치 직접 push 금지.

## 프로젝트 주의사항

- [TODO: 조작 금지 컨테이너·민감 파일·포트 등]
