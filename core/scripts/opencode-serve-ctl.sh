#!/usr/bin/env bash
# opencode serve 데몬의 기동·상태·종료를 한곳에서 관리한다.
# bash 3.2 호환: flock이 없는 macOS에서는 mkdir 락을 사용한다.

set -uo pipefail

usage() {
  echo "사용법: bash scripts/opencode-serve-ctl.sh {ensure|status|start|stop|sessions|session|create|abort}" >&2
  exit 64
}

[ "$#" -eq 1 ] || usage
ACTION="$1"
case "$ACTION" in ensure|status|start|stop|sessions|session|create|abort) ;; *) usage ;; esac

# 테스트 및 격리 실행에는 아래 환경 변수로 실제 사용자 경로를 대체할 수 있다.
ENV_FILE="${OPENCODE_SERVE_ENV_FILE:-$HOME/.config/opencode/serve.env}"
SECRETS_FILE="${OPENCODE_SECRETS_ENV_FILE:-$HOME/.config/opencode/secrets.env}"
STATE_DIR="${OPENCODE_SERVE_STATE_DIR:-$HOME/.local/state/orchestrate}"
START_TIMEOUT="${OPENCODE_SERVE_START_TIMEOUT:-30}"
POLL_INTERVAL="${OPENCODE_SERVE_POLL_INTERVAL:-1}"
LOG_FILE="$STATE_DIR/serve.log"
PID_FILE="$STATE_DIR/serve.pid"

case "$START_TIMEOUT:$POLL_INTERVAL" in
  *[!0-9:]*|:*|*:)
    echo "기동 대기 시간은 0 이상의 정수여야 합니다." >&2
    exit 64
    ;;
esac
WAIT_INCREMENT="$POLL_INTERVAL"
[ "$WAIT_INCREMENT" -gt 0 ] || WAIT_INCREMENT=1
LOCK_WAIT_MAX=$((START_TIMEOUT + 10))

# 권한 검사는 두 파일에 같은 규칙으로 적용한다. bash 3.2 호환을 위해 함수로만 묶는다.
check_env_perm() {
  CHECK_FILE="$1"
  CHECK_MODE=$(ls -ld "$CHECK_FILE") || { echo "serve 환경 파일 검사 실패: $CHECK_FILE" >&2; exit 64; }
  # 공백 분할(set --) 대신 첫 공백 뒤를 제거해 ls의 첫 토큰만 안전하게 취한다.
  CHECK_MODE=${CHECK_MODE%% *}
  case "$CHECK_MODE" in
    [-dlbcps][r-][w-][xsS-][r-][w-][xsS-][r-][w-][xsStT-]|[-dlbcps][r-][w-][xsS-][r-][w-][xsS-][r-][w-][xsStT-][@+.])
      ;;
    *)
      echo "serve 환경 파일 권한 형식 인식 실패: $CHECK_FILE" >&2
      exit 64
      ;;
  esac
  case "$CHECK_MODE" in
    ????[rw]*|?????[rw]*|???????[rw]*|????????[rw]*)
      echo "serve 환경 파일 권한이 너무 열려 있습니다(그룹/기타 읽기·쓰기 금지): $CHECK_FILE" >&2
      exit 64
      ;;
  esac
}

[ -f "$ENV_FILE" ] || {
  echo "serve 환경 파일 없음: $ENV_FILE" >&2
  exit 64
}
check_env_perm "$ENV_FILE"
# 프로바이더 키는 serve 프로세스가 직접 읽는다. v3 serve+attach 부터 모델 호출이
# run-delegation.sh 의 자식이 아니라 상주 데몬 안에서 일어나므로, 위임 직전 주입만으로는
# opencode.json 의 {env:...} 참조가 데몬에서 빈 값이 된다 (2026-09-03·09-04 실측:
# antigravity `Unauthorized` · qwencloud `No API-key provided.` — 후자는 KF-18).
# 권한 검사는 `set -a` 밖에서 끝낸다 — 함수 지역변수까지 export 되면 안 된다.
LOAD_SECRETS=0
if [ -f "$SECRETS_FILE" ]; then
  check_env_perm "$SECRETS_FILE"
  LOAD_SECRETS=1
fi
unset CHECK_FILE CHECK_MODE

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
if [ "$LOAD_SECRETS" -eq 1 ]; then
  # shellcheck disable=SC1090
  . "$SECRETS_FILE"
fi
set +a
unset LOAD_SECRETS

PORT="${OPENCODE_SERVE_PORT:-}"
PW="${OPENCODE_SERVER_PASSWORD:-}"
[ -n "$PORT" ] && case "$PORT" in *[!0-9]*) false ;; *) true ;; esac || {
  echo "OPENCODE_SERVE_PORT가 없거나 올바르지 않습니다: $ENV_FILE" >&2
  exit 64
}
case "$PW" in *'"'*|*\\*|*"
"*)
  echo "OPENCODE_SERVER_PASSWORD에 따옴표, 역슬래시 또는 개행을 사용할 수 없습니다: $ENV_FILE" >&2
  exit 64
  ;;
esac

server_request() {
  # 비밀번호는 stdin으로 전달한 curl 설정에만 넣어 프로세스 목록에 노출하지 않는다.
  REQUEST_PATH="$1"
  REQUEST_METHOD="${2:-GET}"
  REQUEST_OUTPUT="${3:-body}"
  case "$REQUEST_OUTPUT" in body|code|bodycode) ;; *) return 64 ;; esac
  if [ "$REQUEST_OUTPUT" = "code" ]; then
    curl --config - --silent --show-error --output /dev/null --write-out '%{http_code}' \
      --request "$REQUEST_METHOD" --max-time 5 <<EOF
user = "opencode:$PW"
url = "http://127.0.0.1:$PORT$REQUEST_PATH"
EOF
  elif [ "$REQUEST_OUTPUT" = "body" ]; then
    curl --config - --silent --show-error --request "$REQUEST_METHOD" --max-time 5 <<EOF
user = "opencode:$PW"
url = "http://127.0.0.1:$PORT$REQUEST_PATH"
EOF
  else
    curl --config - --silent --show-error --request "$REQUEST_METHOD" --max-time 5 --write-out '\n%{http_code}' <<EOF
user = "opencode:$PW"
url = "http://127.0.0.1:$PORT$REQUEST_PATH"
EOF
  fi
}

health_check() {
  HTTP_CODE=$(server_request "/global/health" GET code)
  HEALTH_CURL_STATUS=$?
  if [ "$HEALTH_CURL_STATUS" -ne 0 ]; then
    echo "opencode 헬스체크 curl 실패(종료 코드: $HEALTH_CURL_STATUS)" >&2
    return 1
  fi
  [ "$HTTP_CODE" = "200" ] || { echo "opencode 헬스체크 HTTP 응답: ${HTTP_CODE:-없음}" >&2; return 1; }
}

require_session_id() {
  SESSION_ID="${OPENCODE_SERVE_ACTION_ID:-}"
  case "$SESSION_ID" in ''|*[!A-Za-z0-9_-]*)
    echo "OPENCODE_SERVE_ACTION_ID가 없거나 올바르지 않습니다." >&2
    exit 64
    ;;
  esac
}

require_action_dir() {
  ACTION_DIR="${OPENCODE_SERVE_ACTION_DIR:-}"
  case "$ACTION_DIR" in
    /*) ;;
    *)
      echo "OPENCODE_SERVE_ACTION_DIR가 없거나 절대 경로가 아닙니다." >&2
      exit 64
      ;;
  esac
}

show_start_failure() {
  echo "opencode serve 기동 또는 헬스체크 실패. 로그: $LOG_FILE" >&2
  if [ -f "$LOG_FILE" ]; then
    tail -n 20 "$LOG_FILE" >&2 || true
  fi
}

start_server() {
  [ -n "$PW" ] || {
    echo "OPENCODE_SERVER_PASSWORD가 없어 opencode serve 기동을 거부합니다." >&2
    return 64
  }
  mkdir -p "$STATE_DIR" || { echo "상태 디렉터리 생성 실패: $STATE_DIR" >&2; return 1; }
  # flock 파일 기술자가 데몬으로 상속되면 stop이 자신의 락을 영구 대기한다.
  setsid nohup opencode serve --port "$PORT" 9>&- >> "$LOG_FILE" 2>&1 < /dev/null &
  SERVER_PID=$!
  printf '%s\n' "$SERVER_PID" > "$PID_FILE" || { echo "PID 파일 기록 실패: $PID_FILE. 고아 PID $SERVER_PID 를 종료합니다." >&2; kill "$SERVER_PID" 2>/dev/null || true; return 1; }
}

wait_for_health() {
  WAITED=0
  while [ "$WAITED" -lt "$START_TIMEOUT" ]; do health_check && return 0; sleep "$POLL_INTERVAL"; WAITED=$((WAITED + WAIT_INCREMENT)); done
  health_check
}

acquire_serve_lock() {
  mkdir -p "$STATE_DIR" || { echo "상태 디렉터리 생성 실패: $STATE_DIR" >&2; return 1; }
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$STATE_DIR/opencode-serve.lock"
    if ! flock -n 9; then
      echo "LOCK_WAIT: 다른 serve 제어 작업이 실행 중 — 최대 ${LOCK_WAIT_MAX}초 대기 (락: $STATE_DIR/opencode-serve.lock)"
      flock -w "$LOCK_WAIT_MAX" 9 || { echo "serve 락 획득 실패: $STATE_DIR/opencode-serve.lock" >&2; return 1; }
    fi
  else
    MLOCK="$STATE_DIR/opencode-serve.lock.d"
    WAITED=0
    while ! mkdir "$MLOCK" 2>/dev/null; do
      HOLDER=$(cat "$MLOCK/pid" 2>/dev/null || true)
      if [ -n "$HOLDER" ] && ! kill -0 "$HOLDER" 2>/dev/null; then
        rm -rf "$MLOCK" || { echo "스테일 serve 락 삭제 실패: $MLOCK" >&2; return 1; }
        continue
      fi
      [ "$WAITED" -eq 0 ] && echo "LOCK_WAIT: 다른 serve 제어 작업이 실행 중 — 최대 ${LOCK_WAIT_MAX}초 대기 (락: $MLOCK)"
      sleep 1
      WAITED=$((WAITED + 1))
      [ "$WAITED" -lt "$LOCK_WAIT_MAX" ] || { echo "serve 락 획득 실패: $MLOCK" >&2; return 1; }
    done
    printf '%s\n' "$$" > "$MLOCK/pid" || { echo "serve 락 PID 기록 실패: $MLOCK" >&2; rm -rf "$MLOCK"; return 1; }
    trap 'rm -rf "$MLOCK"' EXIT
  fi
}

case "$ACTION" in
  status)
    if health_check; then
      echo "up"
      exit 0
    fi
    echo "down"
    exit 1
    ;;
  start)
    acquire_serve_lock || exit 1
    start_server || exit $?
    wait_for_health || { show_start_failure; exit 1; }
    echo "started"
    ;;
  ensure)
    health_check && exit 0
    acquire_serve_lock || exit 1
    health_check && exit 0
    start_server || exit $?
    wait_for_health || { show_start_failure; exit 1; }
    ;;
  stop)
    acquire_serve_lock || exit 1
    if [ ! -f "$PID_FILE" ]; then
      echo "stopped"
      exit 0
    fi
    SERVER_PID=$(cat "$PID_FILE")
    case "$SERVER_PID" in ''|*[!0-9]*) rm -f "$PID_FILE"; echo "stopped"; exit 0 ;; esac
    # PID 재사용은 pidfile만으로 완전히 방지할 수 없다. 전용 상태 디렉터리의 관리 PID라는 전제다.
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      rm -f "$PID_FILE"
      echo "stopped"
      exit 0
    fi
    echo "경고: 활성 세션이 있으면 종료됩니다. opencode serve PID $SERVER_PID 를 종료합니다." >&2
    kill "$SERVER_PID" || { echo "opencode serve 종료 실패: PID $SERVER_PID" >&2; exit 1; }
    WAITED=0
    while kill -0 "$SERVER_PID" 2>/dev/null && [ "$WAITED" -lt 5 ]; do sleep 1; WAITED=$((WAITED + 1)); done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "opencode serve PID $SERVER_PID 가 SIGTERM 후에도 남아 SIGKILL을 보냅니다." >&2
      kill -KILL "$SERVER_PID" || { echo "opencode serve 강제 종료 실패: PID $SERVER_PID" >&2; exit 1; }
      sleep 1
    fi
    kill -0 "$SERVER_PID" 2>/dev/null && { echo "opencode serve 종료 검증 실패: PID $SERVER_PID" >&2; exit 1; }
    rm -f "$PID_FILE"
    echo "stopped"
    ;;
  sessions)
    SESSIONS_RESPONSE=$(server_request "/session" GET bodycode) || exit 1
    case "$SESSIONS_RESPONSE" in
      *$'\n'*)
        SESSIONS_HTTP_CODE=${SESSIONS_RESPONSE##*$'\n'}
        SESSIONS_BODY=${SESSIONS_RESPONSE%$'\n'*}
        case "$SESSIONS_HTTP_CODE" in 2??) printf '%s' "$SESSIONS_BODY" ;; *) exit 1 ;; esac
        ;;
      *) exit 1 ;;
    esac
    ;;
  session)
    require_session_id
    SESSION_RESPONSE=$(server_request "/session/$SESSION_ID" GET bodycode) || exit 1
    SESSION_HTTP_CODE=${SESSION_RESPONSE##*$'\n'}
    SESSION_BODY=${SESSION_RESPONSE%$'\n'*}
    case "$SESSION_HTTP_CODE" in 2??) printf '%s' "$SESSION_BODY" ;; *) exit 1 ;; esac
    ;;
  create)
    require_action_dir
    CREATE_RESPONSE=$(server_request "/session?directory=$ACTION_DIR" POST bodycode) || exit 1
    case "$CREATE_RESPONSE" in
      *$'\n'*)
        CREATE_HTTP_CODE=${CREATE_RESPONSE##*$'\n'}
        CREATE_BODY=${CREATE_RESPONSE%$'\n'*}
        ;;
      *) exit 1 ;;
    esac
    case "$CREATE_HTTP_CODE" in 2??) ;; *) exit 1 ;; esac
    CREATE_ID=$(printf '%s' "$CREATE_BODY" | jq -er '.id | strings | select(length > 0)') || exit 1
    case "$CREATE_ID" in ''|*[!A-Za-z0-9_-]*) exit 1 ;; esac
    printf '%s\n' "$CREATE_ID"
    ;;
  abort)
    require_session_id
    ABORT_HTTP_CODE=$(server_request "/session/$SESSION_ID/abort" POST code)
    ABORT_CURL_STATUS=$?
    ABORT_HTTP_CODE=${ABORT_HTTP_CODE##*$'\n'}
    if [ "$ABORT_CURL_STATUS" -ne 0 ]; then
      echo "opencode 세션 abort 실패 (curl=$ABORT_CURL_STATUS http=${ABORT_HTTP_CODE:-없음})" >&2
      exit 1
    fi
    case "$ABORT_HTTP_CODE" in
      2??) ;;
      *)
        echo "opencode 세션 abort 실패 (curl=$ABORT_CURL_STATUS http=${ABORT_HTTP_CODE:-없음})" >&2
        exit 1
        ;;
    esac
    echo "aborted"
    ;;
esac
