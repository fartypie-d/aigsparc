---
task: 5
status: done
---

## Task 5: events 계약 `reject_cause` + exit 8 문서화

- **에이전트**: `kit-docs`
- **모델**: `default` (문서 task — 낮은 위험)
- **대상 파일**: `adapters/claude/global/skills/orchestrate/SKILL.md` (1개)
- **선행**: **Task 4** (로스터의 `kit-docs` 범위에 `adapters/**/skills/**/*.md`가 추가된 뒤에야
  이 위임이 로스터상 적법하다)
- **목표**: 이번 페이즈가 만든 두 계약을 오케스트레이션 절차 문서에 반영한다.

### 배경 (왜 필요한가)

리뷰 반려율이 heavy tier(terra) 51% vs default(luna) 0%로 갈렸는데(Fisher p=0.014),
**반려 원인이 기록되지 않아** 모델 능력 문제인지 지시서 결함인지 판별할 수 없다.
현재 tier 정책("⚠️ 도메인은 처음부터 heavy")에는 이를 뒷받침하는 데이터가 없다.
`reject_cause`는 그 정책을 데이터로 다시 정하기 위한 최소 계측이다.

- **재사용**: `개선 후 재사용 adapters/claude/global/skills/orchestrate/SKILL.md`의
  **"이벤트 로그 (events.jsonl)" 절 이벤트 표**와 **"6-B 직접 위임" 절 exit 코드 표**.
  새 절·새 문서를 만들지 말 것 — 기존 두 표에 행/필드를 추가한다.

### 반영할 내용

1. **이벤트 표 — `review_verdict` 행의 추가 필드**에 `reject_cause` 추가.
   `verdict`가 `reject`일 때만 기록하며 값은 다음 넷 중 하나:
   - `model` — 모델이 지시를 따를 능력이 부족했다 (같은 지시서로 상위 모델이 통과)
   - `instruction` — 지시서 결함 (누락된 제약·모호한 완료 조건)
   - `spec` — 스펙 자기모순 (지시서대로 하면 다른 요구와 충돌)
   - `unknown` — 판별 불가
2. **exit 코드 표에 `8` 행 추가**: `WALLCLOCK_CAP — 총 벽시계 상한 초과
   (기본 3600초, ORCHESTRATE_DELEGATION_MAX_SEC로 조정)` / 대응: 로그 확인 후 범위를 쪼개
   재위임. 폴백하지 않으므로 침묵 재시도 금지.
3. **`.wrapper` 로그 안내 한 줄** — 6-B의 실행 절에, 래퍼 진단 신호가
   `<로그>.wrapper`에도 남으므로 폴백·락 대기 사후 확인은 그 파일을 볼 것.

### 완료 조건 (문서 task — 테스트 대체 검증)

1. 세 항목이 **기존 표 안에** 반영됐는지 `grep -n 'reject_cause' `·`grep -n 'WALLCLOCK_CAP'`·
   `grep -n 'wrapper'` 로 확인하고 출력을 보고에 첨부
2. 문서가 참조하는 exit 코드·환경변수 이름이 `core/scripts/run-delegation.sh` 실제 구현과
   일치하는지 `grep`으로 대조 (Task 3 산출물 기준 — **문서가 앞서가지 않게**)
3. `python3 -m unittest discover -s tests` 가 여전히 전부 PASS (문서 변경이 테스트를 깨지 않음)

### 금지

- 대상 파일 외 수정. **설치본 `~/.claude/skills/orchestrate/SKILL.md`를 건드리지 말 것** —
  저장소 소스만 고친다 (설치본 반영은 오케스트레이터가 `install.sh`/`kit-doctor`로 별도 수행).
- 문서 본문을 임의로 요약·재구성하지 말 것 — 기존 표에 행·필드만 추가한다.
- 모델 이름·한도 수치 하드코딩 금지 (실측 원칙).
- `git commit`·`git push`.

> **오케스트레이터 후속**: 전제 실측 결과 설치본과 저장소 소스가 현재 동일하다.
> 이 task 병합 후 설치본에 반영해야 실제 절차가 바뀐다 — 페이즈 마감 체크리스트에 포함할 것.
