# aigsprac 오케스트레이터 로스터

> 전역 `/orchestrate` 스킬이 참조하는 프로젝트별 에이전트 목록·리뷰어 매핑·TDD 규정·검증 명령.
> 에이전트 정의: `.opencode/agent/*.md`
> 호출: **`~/.opencode/bin/opencode run --agent <이름> "..."`** (opencode는 PATH에 없을 수 있음 — 전체 경로 사용)

## 에이전트 로스터 (구현 = opencode)

> **모델은 정책 파일의 tier 체인으로 배정한다** — 저장소 최상위의 `.claude/model-policy.json`이
> 있으면 그것이, 없으면 호스트 전역 `~/.config/opencode/model-policy.json`이 원본이다.
> 실제 쓰인 정책은 스크립트 출력 `POLICY_USED=<경로> (project|host)`로 확인한다.
> `scripts/run-delegation.sh`(v2)가 체인 순서대로 `-m`을 주입하고 한도·무응답 시 자동 폴백한다.
> `default` = 일반 task / `heavy` = **large 등급·🔴/⚠️ 위험 도메인 task는 처음부터 heavy** + 🔴 반려 재위임 자동 승격.
> `.opencode/agent/*.md`의 `model:`은 수동 실행용 안전 기본값일 뿐이다.
> 실사용 모델은 스크립트 출력 `MODEL_USED=` 로 확인한다. 특정 task에 특정 모델을 강제하려면
> 지시서 task의 `모델:` 필드에 `provider/model`을 쓴다.

| 에이전트 | 담당 | 위험도 (🔴·⚠️는 heavy 기본) |
|---|---|---|
| `kit-scripts` | `install.sh`, `new-project.sh`, `adopt-project.sh`, `lib/`, `core/opencode/*.sh`, `core/scripts/*` (`*.sh`·`*.py` 모두 — `phase-tools.py`·`docs-index.py` 포함), `adapters/**/*.sh` | ⚠️ — 설치 스크립트가 사용자 홈(`~/.claude`, `~/.config`)을 건드린다 |
| `kit-tests` | `tests/*.py` | 낮음 |
| `kit-docs` | `README.md`, `docs/`, `core/project-template/**/*.md`, `containers/**/README.md`, `adapters/**/skills/**/*.md` | 낮음 |

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
| `kit-scripts` | `bash-reviewer` + `security-reviewer` + `silent-failure-hunter` (대상이 `core/scripts/*.py` 면 `bash-reviewer` 대신 `python-reviewer`) | 프로젝트 신설 + ECC |
| `kit-tests` | `python-reviewer` | ECC |
| `kit-docs` | `code-reviewer` | ECC |

- **새 리뷰어를 만들기 전에 ECC 대응물을 먼저 확인**한다. 프로젝트 리뷰어는 ECC에 없는
  도메인에만 만들고, 근거를 여기 한 줄로 남긴다.
- `bash-reviewer` 신설 근거: ECC 68개 에이전트에 shell 전용 리뷰어가 없음(2026-08-07 실측).
  이 저장소는 코드의 대부분이 bash 다.
- `structure-reviewer` 신설 근거: ECC 에 **읽기 전용 구조 리뷰어**가 없음(2026-08-19 실측).
  `architect`·`code-architect` 는 읽기 전용이나 설계 산출물 **생성**용이고,
  `code-simplifier`·`refactor-cleaner` 는 Write/Edit 를 가져 리뷰어로 쓰면 PITFALLS 26 이 재발한다.
- 판정에 🔴 Critical이 하나라도 있으면 **반려** — 같은 에이전트에 **heavy tier로**
  재위임(`run-delegation.sh ... heavy`, 최대 2회).
- 모든 리뷰어 호출에 중복 검사 지시 포함 (`_reuse-rules.md` 참조).

### `structure-reviewer` — 페이즈 마감 시 1회 (task별 호출 아님)

`.claude/agents/structure-reviewer.md`. **task 검수 리뷰어가 아니다.** 페이즈의 모든 task 가
끝난 뒤 GATE 2 전에 **한 번** 호출하고, 전달물은 **페이즈 누적 diff**
(`git diff <페이즈 시작 커밋>..HEAD`)와 변경된 파일 목록이다.
task 단위 diff 로는 구조를 판단할 수 없다 — 한 task 의 +40 줄은 언제나 정당해 보인다.

**게이트가 아니다.** 🔴 로 마감을 막지 않으며, 산출물(구조 부채·분할 후보·다음 페이즈 권고)은
페이즈 완료 보고의 "후속 제안"과 다음 페이즈 지시서의 입력으로 쓴다.

## TDD 게이트

지시서의 각 task에는 **`실패 테스트`** 필드가 있어야 한다. 위임 프롬프트는 항상:
① 실패 테스트 작성·실패 확인 → ② 구현 → ③ 테스트 출력 첨부.

| 도메인 | 테스트 위치 | 러너 |
|---|---|---|
| 전체 | `tests/*.py` | `python3 -m unittest discover -s tests -v` |
| bash 문법 | — | `bash -n <파일>` (실행 없이 파싱만) |

### 대체 검증 (테스트를 쓸 수 없는 경우에만 — 불가 사유를 지시서에 명시)

| 상황 | 대체 검증 |
|---|---|
| 문서(markdown)만 수정 | 링크·경로 실재 확인 (`ls`·`grep`) + 리뷰어 검수 |
| docker compose 파일 | `docker compose config` 파싱 통과 |

## 도메인별 검증 명령 (검수 시 실행)

| 도메인 | 명령 |
|---|---|
| 전체 테스트 | `python3 -m unittest discover -s tests -v` |
| bash 문법 | `bash -n install.sh new-project.sh adopt-project.sh lib/stamp.sh` |
| 훅 자가진단 | `bash scripts/hook-selfcheck.sh` |

## 커밋 컨벤션 (검수 통과 후 오케스트레이터가 수행)

conventional commits (`feat:`/`fix:`/...). scope: `install`·`stamp`·`policy`·`profile`·`containers`·`docs`. `main` 직접 push 금지.

## 프로젝트 주의사항

- `scripts/*` 는 `core/scripts/*` 로의 심링크다. **작업용을 직접 고치지 말 것** — 원본을 고친다.
- 설치 스크립트를 테스트할 때 실제 `~/.claude`·`~/.config` 를 건드리지 말 것.
  주입 플래그(`--agents-dir`·`--settings`·`--policy`)나 임시 디렉터리를 쓴다.
- `core/project-template/`·`docs/plans/` 에는 `__PROJECT__` 플레이스홀더가 정당하게 존재한다 —
  일괄 치환 금지 (2026-08-08 도그푸딩에서 실제 클로버 사고).
- 자기 소유가 아니거나 이미 운영 중인 라이브 CDP 컨테이너·세션은 조작 금지한다. 이 킷의
  `containers/browser` 번들을 본인이 직접 띄운 경우는 해당하지 않는다.
