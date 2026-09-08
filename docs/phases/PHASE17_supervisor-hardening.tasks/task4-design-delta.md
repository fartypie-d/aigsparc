# D-8 갱신 문구 초안

이 문서는 설계 문서 §4.1 D-8을 갱신하기 위한 문구 초안이다. 원문은 저장소 밖 홈 경로에 있어 이
세션이 읽지도 쓰지도 못했으므로, 아래 초안은 이 페이즈가 실제로 만든 키트 자산에 근거한다.
반영 주체는 감독이며, 감독은 반드시 설계 원문과 대조해 접합한 뒤 반영한다.

## 제안 문구 — §4.1 D-8

D-8은 **키트 설치 기준**으로 삼는다. 감독 계층 자산의 정본은 키트
(`core/supervisor/PROCEDURE.md` · `core/scripts/supervisor-state.sh` ·
`adapters/claude/global/commands/`)이고, 홈(`~/.claude/supervisor/` · `~/.local/bin/`)은 설치
결과물이다. 홈 사본을 손으로 고치지 않고 키트를 고쳐 재설치한다.

설치 경로의 정본은 `core/install-manifest.tsv`다. 이번 페이즈에서 다음 세 행이 정본이 됐다:
`any file core/scripts/supervisor-state.sh .local/bin/supervisor-state.sh`,
`claude file core/supervisor/PROCEDURE.md .claude/supervisor/PROCEDURE.md`,
`claude tree adapters/claude/global/commands .claude/commands`.

드리프트 판정은 `kit-doctor.sh`가 매니페스트를 순회해 수행한다. 홈 사본과 키트 원본의 차이는
doctor가 보고하고, 사람이 직접 고치지 않고 재설치로 해소한다. 키트로 시작하지 않은 기존 프로젝트의
전파는 새 adopt가 아니라 `adopt-project.sh` 재실행과 `kit-doctor.sh` 드리프트 동기화로 수행한다.

## 감독 확인 필요

- D-8 원문이 "홈 기준"이었다면 방향이 뒤집히므로 원문 대조가 필수다.
- 다른 프로젝트 저장소로의 전파는 이 페이즈 범위 밖이며 감독의 별도 페이즈에서 다룬다.
- codex 어댑터의 동등물은 아직 미구현이며 후속 과제다.
