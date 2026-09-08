#!/usr/bin/env bash
# 새 프로젝트에 오케스트레이션 스캐폴드를 stamp — macOS / Linux
#
# 사용법: ./new-project.sh <프로젝트경로> [프로젝트명] [--claude|--codex|--both]
#   프로젝트명 생략 시 디렉터리 이름 사용. 하네스 생략 시 설치된 CLI 자동 감지.
#   기존 파일은 절대 덮어쓰지 않는다.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_DIR/lib/stamp.sh"

TARGET=""
NAME=""
HARNESSES=""
for arg in "$@"; do
  case "$arg" in
    --claude) HARNESSES="claude" ;;
    --codex)  HARNESSES="codex" ;;
    --both)   HARNESSES="claude codex" ;;
    -*) echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *) if [ -z "$TARGET" ]; then TARGET="$arg"; elif [ -z "$NAME" ]; then NAME="$arg"; fi ;;
  esac
done

[ -n "$TARGET" ] || { echo "usage: ./new-project.sh <프로젝트경로> [프로젝트명] [--claude|--codex|--both]" >&2; exit 64; }
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"
[ -n "$NAME" ] || NAME="$(basename "$TARGET")"
[ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)"

echo "== 스캐폴드: $TARGET (프로젝트명: $NAME, 하네스: $HARNESSES)"
stamp_copy "$KIT_DIR" "$TARGET" "$HARNESSES"
stamp_placeholders "$TARGET" "$NAME"
stamp_finalize "$TARGET"
for harness in $HARNESSES; do
  if [ "$harness" = "claude" ]; then
    stamp_supervisor "$KIT_DIR" "$TARGET" "$NAME" || echo "   ⚠️ 감독 자산은 만들지 못했다 (위 사유). 나머지 설치는 정상 완료했다." >&2
  fi
done

cat <<EOF

스캐폴드 완료.

다음 단계: 프로젝트 루트에서 하네스를 열고 \`/orchestrate-onboard\` 를 실행한다.
  → 스택 감지·로스터 작성·에이전트 생성·스킬 제안을 자동으로 수행한다.
  → 반드시 사용 가능한 가장 똑똑한 모델로 실행할 것 (명령이 모델을 확인하고 미달 시 중단한다).

수동으로 채우려면: $TARGET/.claude/orchestrate.md 의 [TODO] 를 전부 채울 것 (로스터 없이 위임 금지).
EOF
