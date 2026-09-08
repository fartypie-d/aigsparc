#!/usr/bin/env bash
#
# skillpack-update-check.sh
# -------------------------
# 스킬 팩(Claude 플러그인·git 저장소형 룰 팩)의 업스트림 업데이트를 감지해
# 알림 파일(NOTICE.md)에 기록한다. 감지만 하고 자동 적용은 하지 않는다.
#
# 하루 한 번 cron 실행을 전제로 설계했다. 수동 실행도 안전하다.
#
#   설정   : ~/.config/skillpack-update/packs.conf   (TSV, 아래 형식 참조)
#   알림   : ~/.local/state/skillpack-update/NOTICE.md (대기 중 업데이트, 없으면 최신)
#   로그   : ~/.local/state/skillpack-update/check.log
#   잠금   : ~/.local/state/skillpack-update/.lock
#
# packs.conf 형식 (탭 구분, # 주석):
#   plugin	<표시명>	<plugin@marketplace>	<github owner/repo>
#   repo	<표시명>	<로컬 경로>	<업스트림 ref (예: origin/main)>
#
# macOS 기본 bash 3.2 호환: mapfile·연관배열을 사용하지 않는다.
set -uo pipefail

# cron 의 최소 PATH 대비.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

CONF_FILE="${SKILLPACK_CONF:-$HOME/.config/skillpack-update/packs.conf}"
STATE_DIR="${SKILLPACK_STATE:-$HOME/.local/state/skillpack-update}"
NOTICE_FILE="$STATE_DIR/NOTICE.md"
LOG_FILE="$STATE_DIR/check.log"
LOCK_FILE="$STATE_DIR/.lock"
PLUGINS_JSON="$HOME/.claude/plugins/installed_plugins.json"

mkdir -p "$STATE_DIR"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE" >&2; }

# --- 중복 실행 방지 ----------------------------------------------------------
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "이미 실행 중인 인스턴스가 있어 종료"
  exit 0
fi

# --- 의존성 확인 --------------------------------------------------------------
for bin in gh jq git; do
  command -v "$bin" >/dev/null 2>&1 || { log "ERROR: '$bin' 을 PATH 에서 찾지 못함"; exit 1; }
done

if [ ! -f "$CONF_FILE" ]; then
  log "ERROR: 설정 파일 없음: $CONF_FILE"
  exit 1
fi

log "점검 시작 — 설정: $CONF_FILE"

PENDING=""   # NOTICE.md 본문에 쌓을 항목들
PENDING_COUNT=0

add_pending() {
  # $1=표시명 $2=요약 $3=적용 방법
  PENDING="${PENDING}## $1

$2

적용:
\`\`\`bash
$3
\`\`\`

"
  PENDING_COUNT=$((PENDING_COUNT + 1))
}

# --- plugin 팩 점검 ------------------------------------------------------------
check_plugin() {
  # $1=표시명 $2=plugin@marketplace $3=owner/repo
  name="$1"; key="$2"; repo="$3"

  if [ ! -f "$PLUGINS_JSON" ]; then
    log "$name: installed_plugins.json 없음 — 건너뜀"
    return
  fi
  installed=$(jq -r --arg k "$key" '.plugins[$k][0].version // empty' "$PLUGINS_JSON" 2>/dev/null)
  installed_sha=$(jq -r --arg k "$key" '.plugins[$k][0].gitCommitSha // empty' "$PLUGINS_JSON" 2>/dev/null)
  if [ -z "$installed" ] && [ -z "$installed_sha" ]; then
    log "$name: 설치 정보 없음($key) — 건너뜀"
    return
  fi

  # `claude plugin update` 는 마켓플레이스 HEAD 에서 설치하므로 커밋 SHA 비교가
  # 진실이다. 릴리스 태그는 HEAD 보다 낡을 수 있어(실측: evenhub v0.0.2 태그가
  # HEAD 이전) 버전 표기 장식으로만 쓴다. SHA 를 못 구할 때만 태그로 폴백.
  head_sha=$(gh api "repos/$repo/commits" -q '.[0].sha' 2>/dev/null)
  latest=$(gh api "repos/$repo/releases/latest" -q '.tag_name' 2>/dev/null | sed 's/^v//')
  marketplace="${key#*@}"

  if [ -n "$installed_sha" ] && [ -n "$head_sha" ]; then
    if [ "$head_sha" != "$installed_sha" ]; then
      ver_note=""
      [ -n "$latest" ] && [ "$latest" != "$installed" ] && ver_note=" (v$installed → v$latest)"
      log "$name: 업데이트 감지 — 커밋 ${installed_sha:0:8} → ${head_sha:0:8}$ver_note"
      add_pending "$name (plugin)" \
        "설치 커밋 \`${installed_sha:0:8}\` → 업스트림 HEAD \`${head_sha:0:8}\` ($repo)$ver_note" \
        "claude plugin marketplace update $marketplace
claude plugin update $key"
    else
      log "$name: 최신 (커밋 ${installed_sha:0:8})"
    fi
    return
  fi

  # SHA 를 못 구하면 릴리스 태그 버전으로 폴백한다.
  if [ -z "$latest" ]; then
    log "$name: 업스트림 조회 실패($repo) — 건너뜀"
    return
  fi
  if [ "$latest" != "$installed" ]; then
    log "$name: 업데이트 감지 — 설치 $installed → 최신 $latest"
    add_pending "$name (plugin)" \
      "설치본 \`v$installed\` → 업스트림 최신 릴리스 \`v$latest\` ($repo)" \
      "claude plugin marketplace update $marketplace
claude plugin update $key"
  else
    log "$name: 최신 ($installed)"
  fi
}

# --- repo 팩 점검 ---------------------------------------------------------------
check_repo() {
  # $1=표시명 $2=로컬 경로 $3=업스트림 ref
  name="$1"; path="$2"; ref="$3"
  case "$path" in "~/"*) path="$HOME/${path#\~/}" ;; esac

  if [ ! -d "$path/.git" ]; then
    log "$name: git 저장소 아님($path) — 건너뜀"
    return
  fi
  if ! git -C "$path" fetch --quiet 2>/dev/null; then
    log "$name: fetch 실패($path) — 건너뜀"
    return
  fi
  behind=$(git -C "$path" rev-list --count "HEAD..$ref" 2>/dev/null)
  if [ -z "$behind" ]; then
    log "$name: ref 확인 실패($ref) — 건너뜀"
    return
  fi
  if [ "$behind" -gt 0 ]; then
    ahead=$(git -C "$path" rev-list --count "$ref..HEAD" 2>/dev/null || echo 0)
    latest_line=$(git -C "$path" log "$ref" -1 --format='%h %ci %s' 2>/dev/null)
    extra=""
    [ "$ahead" -gt 0 ] && extra=" (로컬 커밋 ${ahead}개 ahead — rebase 필요)"
    log "$name: 업데이트 감지 — $ref 대비 ${behind}커밋 behind$extra"
    add_pending "$name (repo)" \
      "\`$path\` 가 \`$ref\` 대비 **${behind}커밋 behind**${extra}
업스트림 최신: \`$latest_line\`" \
      "git -C $path pull --rebase   # 이후 룰/스킬 재설치 필요 여부 확인"
  else
    log "$name: 최신 ($ref 동기화됨)"
  fi
}

# --- 설정 파일 순회 --------------------------------------------------------------
while IFS=$'\t' read -r ptype pname f3 f4; do
  case "$ptype" in
    ''|'#'*) continue ;;
    plugin) check_plugin "$pname" "$f3" "$f4" ;;
    repo)   check_repo   "$pname" "$f3" "$f4" ;;
    *)      log "알 수 없는 타입 무시: $ptype ($pname)" ;;
  esac
done < "$CONF_FILE"

# --- 알림 파일 갱신 --------------------------------------------------------------
if [ "$PENDING_COUNT" -gt 0 ]; then
  {
    echo "# 스킬 팩 업데이트 대기 (${PENDING_COUNT}건)"
    echo
    echo "> $(date '+%Y-%m-%d %H:%M:%S') 점검 기준. 자동 적용하지 않음 — 아래 명령으로 직접 적용."
    echo
    printf '%s' "$PENDING"
  } > "$NOTICE_FILE"
  log "점검 종료 — ${PENDING_COUNT}건 대기: $NOTICE_FILE"
else
  rm -f "$NOTICE_FILE"
  log "점검 종료 — 모든 팩 최신"
fi
