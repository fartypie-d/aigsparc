---
task: 3
status: done
---

## Task 3: 문서 — 정책 원본 서술 갱신

- **에이전트**: `kit-docs`
- **모델**: default
- **대상 파일**: `README.md`, `docs/WORKFLOW.md`, `docs/WORKFLOW.ko.md` (3파일)
- **선행**: Task 1, Task 2
- **목표**: "위임 모델 정책의 원본 = 호스트 전역 `~/.config/opencode/model-policy.json`" 이라는
  현행 서술을 **"프로젝트 `.claude/model-policy.json` 이 있으면 그것이 우선, 없으면 호스트 전역"**
  으로 갱신한다. 실제 쓰인 정책은 로그의 `POLICY_USED=` 로 확인한다는 점도 함께 적는다.

- **재사용**: 개선 후 재사용 — 기존 서술 9곳을 고치는 작업이다. **새 문서·새 절을 만들지 말 것**.
  실측된 9곳 (`grep -rn 'model-policy' README.md docs/WORKFLOW.md docs/WORKFLOW.ko.md`):
  - `README.md:93`(mermaid 다이어그램 라벨), `:107`(정책 주입 서술), `:298`(생성물 원본 예외 절)
  - `docs/WORKFLOW.md:12`, `:144`, `:265`
  - `docs/WORKFLOW.ko.md:10`, `:122`, `:231`
  **9곳 각각에 대해 "수정함 / 수정 불필요(사유)"를 보고에 명시**할 것 — 다이어그램 라벨이나
  매핑표 서술처럼 손댈 필요가 없는 곳이 있을 수 있고, 그 판단이 이 task 의 산출물이다.
- **필수 규칙**:
  - **영문(README.md·WORKFLOW.md)과 한국어(WORKFLOW.ko.md)의 내용이 일치**해야 한다.
  - `core/project-template/`·`docs/plans/` 의 `__PROJECT__` 플레이스홀더를 건드리지 말 것.
  - `docs/phases/` 아래는 수정 금지 (오케스트레이터 전속).
  - 대상 파일 외 수정 금지. `git commit` 금지.
- **실패 테스트**: 작성 불가 — 문서(markdown) 전용 변경이다.
  **대체 검증**(로스터의 대체 검증 표): ① 문서에 나오는 경로·명령이 실재하는지
  `ls`·`grep` 으로 확인 ② `python3 -m unittest discover -s tests` 회귀 무영향 확인
  ③ `code-reviewer` 검수.
- **완료 조건**:
  - `grep -rn 'model-policy' README.md docs/WORKFLOW.md docs/WORKFLOW.ko.md` 출력 첨부
  - 9곳 각각의 "수정함 / 수정 불필요(사유)" 표
  - `python3 -m unittest discover -s tests 2>&1 | tail -3` 통과 출력
