#!/usr/bin/env bash
# 이미 작업 중인 프로젝트에 오케스트레이션 스캐폴드를 stamp — macOS / Linux
#
# 사용법: ./adopt-project.sh <프로젝트경로> [--claude|--codex|--both]
#   기존 파일은 절대 덮어쓰지 않는다. 충돌하는 설정 파일은 *.kit-suggested 로 나란히 둔다.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$KIT_DIR/lib/stamp.sh"

TARGET=""
HARNESSES=""
for arg in "$@"; do
  case "$arg" in
    --claude) HARNESSES="claude" ;;
    --codex)  HARNESSES="codex" ;;
    --both)   HARNESSES="claude codex" ;;
    -*) echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *) [ -z "$TARGET" ] && TARGET="$arg" ;;
  esac
done

[ -n "$TARGET" ] || { echo "usage: ./adopt-project.sh <프로젝트경로> [--claude|--codex|--both]" >&2; exit 64; }
[ -d "$TARGET" ] || { echo "디렉터리 없음: $TARGET" >&2; exit 66; }
TARGET="$(cd "$TARGET" && pwd)"
NAME="$(basename "$TARGET")"
[ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)"

echo "== 기존 프로젝트 온보딩: $TARGET (하네스: $HARNESSES)"

# 저장소 상태 보고 — 진행을 막지는 않는다 (기존 파일을 덮지 않으므로 안전).
if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  if [ -n "$(git -C "$TARGET" status --porcelain)" ]; then
    echo "   ⚠️ 커밋되지 않은 변경이 있다 — stamp 결과와 섞이지 않게 먼저 커밋하길 권한다."
  fi
else
  echo "   ⚠️ git 저장소가 아니다 — 되돌리기가 어려우므로 백업을 권한다."
fi

# 충돌 가능한 설정 파일은 먼저 .kit-suggested 로 빼둔다. stamp_copy 는 기존 파일을
# 건드리지 않으므로, 이렇게 해야 키트 권장본을 사용자가 비교할 수 있다.
SUGGESTED=""
for rel in ".claude/settings.json" "opencode.json"; do
  for h in $HARNESSES core; do
    case "$h" in
      core) src="$KIT_DIR/core/project-template/$rel" ;;
      *)    src="$KIT_DIR/adapters/$h/project/$rel" ;;
    esac
    if [ -f "$src" ] && [ -f "$TARGET/$rel" ]; then
      cp "$src" "$TARGET/$rel.kit-suggested"
      SUGGESTED="$SUGGESTED $rel"
    fi
  done
done

stamp_copy "$KIT_DIR" "$TARGET" "$HARNESSES"
stamp_placeholders "$TARGET" "$NAME"
stamp_finalize "$TARGET"
for harness in $HARNESSES; do
  if [ "$harness" = "claude" ]; then
    stamp_supervisor "$KIT_DIR" "$TARGET" "$NAME" || echo "   ⚠️ 감독 자산은 만들지 못했다 (위 사유). 나머지 설치는 정상 완료했다." >&2
  fi
done

echo
echo "기본 설치 완료."
if [ -n "$SUGGESTED" ]; then
  echo
  echo "다음 파일은 기존 것을 유지했다. 키트 권장본이 .kit-suggested 로 함께 있으니 병합할 것:"
  for rel in $SUGGESTED; do echo "   $rel  ←  $rel.kit-suggested"; done
fi
cat <<EOF

다음 단계: 프로젝트 루트에서 하네스를 열고 \`/orchestrate-onboard\` 를 실행한다.
  → 프로젝트를 분석해 로스터·에이전트·가드 등급을 채우고, 필요한 스킬을 제안한다.
  → 반드시 사용 가능한 가장 똑똑한 모델로 실행할 것 (명령이 모델을 확인하고 미달 시 중단한다).
EOF
