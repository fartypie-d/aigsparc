---
paths:
  - "src/example-domain/**"
  - "**/*.example.spec.*"
---

# 함정 인덱스 — example (경로 조건부)

> `CLAUDE.md` 「이 저장소의 함정」에서 **문구 그대로** 옮긴 줄이다. 위 경로의 파일을 `Read` 한 세션에만 실린다.
> 상세는 `docs/phases/PITFALLS.md` — 줄의 문구로 검색한다. 이 도메인의 새 함정은 여기에 한 줄 추가한다.
> (예시 파일 — 실제 도메인으로 바꾸고 이 파일은 지운다. 형식은 `.claude/rules/README.md`.)

- **예시: 가짜 타이머 아래서 시한 시그널을 재면** → 「시한이 안 걸렸다」와 「시한을 못 잰다」가 둘 다 조용한 통과라
  판별자가 두 경우에 똑같이 보인다 (YYYY-MM-DD 실측, Phase N). 처방은 PITFALLS.md 해당 항목.
