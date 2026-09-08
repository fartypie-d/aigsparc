---
task: 4
status: done
---

## Task 4: structure-reviewer 신설 + 로스터 반영

- **주체**: **오케스트레이터 직접 작성** (`.claude/`는 직접 수정 허용 영역 — 위임 아님)
- **모델**: —
- **대상 파일**: `.claude/agents/structure-reviewer.md`, `.claude/orchestrate.md`
- **선행**: 없음 (Task 1~3과 병행 가능)
- **목표**: 구조·모듈화 축을 담당하는 읽기 전용 리뷰어를 만들고 로스터에 호출 규정을 넣는다.

### 배경 (왜 필요한가)

기존 리뷰어 5종(`bash-reviewer`·`security-reviewer`·`silent-failure-hunter`·
`python-reviewer`·`code-reviewer`)은 전부 정확성·보안·침묵실패 축이다. 실측:

| 대상 | 실측 | ECC `common/coding-style.md` | 배수 |
|---|---|---|---|
| `install.sh` | 1,810줄 | 800 max | 2.3× |
| `run_mcp_registration()` | 496줄 | 함수 <50줄 | 9.9× |
| `run_install_wizard()` | 294줄 | 함수 <50줄 | 5.9× |
| `core/scripts/phase-tools.py` | 724줄 | 400 typical | 1.8× |

**리뷰 56회 중 이를 지적한 판정 0건.** PITFALLS 23(메뉴 번호 하드코딩 8건)·29(출력 정확일치
단정)는 이 구조 부채의 증상이며, 지금은 테스트 규율로 상환하고 있다.

### ECC 대응물 확인 (로스터 규정 — 신설 근거를 남긴다)

- `architect`·`code-architect`: 읽기 전용이나 **설계 산출물 생성용**. 변경분의 구조 부채를
  임계값으로 판정하는 계약이 없다.
- `code-simplifier`·`refactor-cleaner`: **Write/Edit 보유** → 리뷰어로 쓰면 PITFALLS 26
  (리뷰어가 작업 트리를 흔든 실측 사고) 재발.
- → ECC에 읽기 전용 **구조 리뷰어**가 없으므로 프로젝트 리뷰어로 신설한다
  (`bash-reviewer`와 동일한 근거 구조).

### 에이전트 정의 요건

- `tools: Read, Grep, Glob, Bash` — **Bash는 읽기 전용 git·`wc`·`grep`만**.
  `git stash`·`git checkout`·`git reset` 금지를 프롬프트에 명시 (PITFALLS 26).
- 판정 대상: **페이즈 누적 diff**(`git diff <페이즈 시작>..HEAD`) + 변경된 파일의 **최종 크기**.
  task 단위 diff로는 구조를 판단할 수 없다 — 한 task의 +40줄은 언제나 정당해 보인다.
- 임계: 파일 800줄 max / 400줄 typical, 함수 50줄, 중첩 4단계.
- 출력: 🔴/🟠 게이트가 **아니라** ① 이번 페이즈가 추가한 구조 부채 ② 분할 후보(경로·경계 제안)
  ③ 다음 페이즈 권고. **게이트로 만들지 말 것** — 마감이 막힌다.

### 로스터 반영 (`.claude/orchestrate.md`)

1. 리뷰어 매핑 절에 항목 추가: **`structure-reviewer` — 페이즈 마감 시 1회, 페이즈 누적 diff 대상.
   task별 호출 아님.** 신설 근거 한 줄 포함.
2. 에이전트 로스터 표의 `kit-docs` 담당 범위에 **`adapters/**/skills/**/*.md`** 를 추가한다
   (전제 실측에서 담당 없음이 확인됨 — Task 5의 선행 조건).

### 완료 조건

1. `.claude/agents/structure-reviewer.md` 존재 + frontmatter `tools:`에 `Write`·`Edit` 없음
2. `.claude/orchestrate.md`에 호출 시점·신설 근거·`kit-docs` 범위 확장 반영
3. `bash scripts/hook-selfcheck.sh` → `HOOK_SELFCHECK_PASS`
4. **위임 산출물과 별도 커밋** (PITFALLS 27) — 메시지
   `feat(orchestrate): structure-reviewer 신설 + 로스터 반영 (오케스트레이터)`
