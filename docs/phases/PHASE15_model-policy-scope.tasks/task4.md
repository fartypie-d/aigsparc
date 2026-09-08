---
task: 4
status: done
---

## Task 4: 남은 문서 표면 — 정책 스코프 서술 동기화

- **에이전트**: `kit-docs`
- **모델**: default
- **대상 파일**: `README.ko.md`, `adapters/claude/global/skills/orchestrate/SKILL.md`,
  `core/project-template/.claude/orchestrate.md` (3개)
- **선행**: Task 3
- **목표**: Task 3 이 영문 `README.md`·`docs/WORKFLOW{,.ko}.md` 를 갱신하면서 남은 세 표면이
  옛 서술("정책 원본 = 호스트 전역 하나")로 남았다. 같은 사실로 맞춘다.

### 왜 이 task 가 생겼나 (스코프 정정)

오케스트레이터가 착수 전 실측을 `README.md docs/WORKFLOW.md docs/WORKFLOW.ko.md` **세 파일로
한정**해서 돌렸다. 저장소 전역으로 다시 재면 `README.ko.md`(영문 README 의 한국어 쌍),
킷이 **배포하는** 스킬 사본, 신규 프로젝트 **템플릿** 로스터가 함께 나온다. Task 3 의 잘못이
아니라 지시서의 실측 누락이며, 그대로 두면 EN/KO 가 어긋나고 킷 사용자가 받는 문서가 틀린다.
(`code-reviewer` 가 Task 3 리뷰에서 🟠 로 지적.)

- **재사용**: 개선 후 재사용 — 기존 서술을 고치는 작업이다. **새 절·새 문서를 만들지 말 것.**
  실측된 위치:
  - `README.ko.md:80`(mermaid 라벨), `:92`(정책 주입 서술), `:275`(생성물 원본 예외 절)
    → 영문 `README.md` 의 대응 문단(현재 커밋 `5361302` 로 갱신됨)과 **내용이 일치**해야 한다.
  - `adapters/claude/global/skills/orchestrate/SKILL.md:190` — "모델 배정 — 중앙 정책 + 자동 폴백" 절
  - `core/project-template/.claude/orchestrate.md:11` — 로스터 상단 인용 블록
- **필독 스킬**: 없음.
- **필수 규칙**:
  - 갱신 내용의 사실 원본은 **코드**다. `core/scripts/run-delegation.sh` 를 직접 읽고 맞춰라.
  - `core/project-template/` 의 `__PROJECT__` 플레이스홀더를 **건드리지 마라**.
  - 수정 금지: `README.md`·`docs/` 전체(Task 3 이 이미 처리), `docs/phases/` 전체, `core/scripts/`,
    `tests/`, 대상 3파일 외 모든 파일.
  - 금지: `git commit`, `git push`, docker 조작, 패키지 설치, sudo.
- **실패 테스트**: 작성 불가 — 문서 전용 변경. 대체 검증은 아래 완료 조건.
- **완료 조건**:
  - `grep -rn 'model-policy' README.ko.md adapters/claude/global/skills/orchestrate/SKILL.md core/project-template/.claude/orchestrate.md` 출력
  - `README.ko.md` 3곳이 영문 `README.md` 의 대응 서술과 **같은 사실**을 말하는지 대조표
  - `python3 -m unittest tests.test_run_delegation 2>&1 | tail -3` (91 tests OK — 회귀 무영향)
