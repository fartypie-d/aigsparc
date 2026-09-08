#!/usr/bin/env bash
# 위임 실행 래퍼. bash 3.2 호환을 유지한다.
#
# v3 (2026-08-12): serve attach가 가능하면 프로젝트별 락으로 프로젝트 간 병렬을 허용한다.
# serve를 보장할 수 없으면 v2의 전역 락·단독 실행으로 명시적으로 폴백한다.
#
# 사용법: bash scripts/run-delegation.sh <에이전트> <프롬프트파일> <로그파일> [tier|provider/model]
# exit: 0 완료 / 2 init 경합 / 3 비관리 프로세스 / 4 락 타임아웃 / 5 모델 체인 전멸 / 6 고아 세션 가능성
#       / 7 에이전트 없음 / 8 총 벽시계 상한 초과 / 64 사용법·정책 파일 문제 / 66 프롬프트 파일 없음
#
# 금지사항(스킬 6단계):
#   - timeout 으로 감싸지 말 것 (SIGTERM 이 opencode 세션 DB 를 오염시켜 다음 실행까지 막는다)
#   - 파이프(| tail)로 받지 말 것 (버퍼링으로 진행이 안 보인다)
#   - 프롬프트를 명령줄에 인라인하지 말 것 (따옴표 이스케이프가 깨진다)

set -uo pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  echo "usage: bash scripts/run-delegation.sh <agent> <prompt-file> <log-file> [tier|provider/model]" >&2
  exit 64
fi

AGENT="$1"
PROMPT_FILE="$2"
LOG_FILE="$3"
TIER="${4:-default}"
WRAPPER_LOG="$LOG_FILE.wrapper"
WRAPPER_LOG_WRITE_FAILED=0
WRAPPER_LOG_WRITE_FAILURE_REPORTED=0
# install은 생성 시 0600으로 열고, 기존 파일도 같은 동작으로 권한을 교정한다.
# `: >` 뒤 chmod의 두 단계는 생성 직후 읽기 가능한 창을 만들므로 사용하지 않는다.
# 로그 경로가 잘못되어도 아래 인자 검증의 정확한 종료 코드를 가리면 안 된다.
if ! install -m 600 /dev/null "$WRAPPER_LOG"; then
  WRAPPER_LOG_WRITE_FAILED=1
  WRAPPER_LOG_WRITE_FAILURE_REPORTED=1
  printf '%s\n' "WRAPPER_LOG_WRITE_FAILED: 래퍼 로그 파일 생성 또는 권한 설정 실패: $WRAPPER_LOG" >&2
fi
emit() {
  printf '%s\n' "$*"
  if [ -n "${WRAPPER_LOG:-}" ]; then
    if [ "$WRAPPER_LOG_WRITE_FAILED" -eq 1 ]; then
      if ! { printf '%s\n' "WRAPPER_LOG_RESUMED_AFTER_GAP" >> "$WRAPPER_LOG"; printf '%s\n' "$*" >> "$WRAPPER_LOG"; } 2>/dev/null; then
        if [ "$WRAPPER_LOG_WRITE_FAILURE_REPORTED" -eq 0 ]; then
          WRAPPER_LOG_WRITE_FAILURE_REPORTED=1
          printf '%s\n' "WRAPPER_LOG_WRITE_FAILED: 래퍼 로그 기록 실패: $WRAPPER_LOG" >&2
        fi
      else
        WRAPPER_LOG_WRITE_FAILED=0
      fi
    elif ! { printf '%s\n' "$*" >> "$WRAPPER_LOG"; } 2>/dev/null; then
      WRAPPER_LOG_WRITE_FAILED=1
      if [ "$WRAPPER_LOG_WRITE_FAILURE_REPORTED" -eq 0 ]; then
        WRAPPER_LOG_WRITE_FAILURE_REPORTED=1
        printf '%s\n' "WRAPPER_LOG_WRITE_FAILED: 래퍼 로그 기록 실패: $WRAPPER_LOG" >&2
      fi
      # 일시적인 권한·마운트 전환은 다음 메시지보다 먼저 회복될 수 있다. 짧게 한 번 더
      # 시도해 결손 표식과 원래 메시지를 함께 남기고, 실패해도 다음 emit에서 계속 재시도한다.
      sleep 1
      if { printf '%s\n' "WRAPPER_LOG_RESUMED_AFTER_GAP" >> "$WRAPPER_LOG"; printf '%s\n' "$*" >> "$WRAPPER_LOG"; } 2>/dev/null; then
        WRAPPER_LOG_WRITE_FAILED=0
      fi
    fi
  fi
  return 0
}
RUN_DIR=$(pwd -P)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
: "${HOME:?HOME 환경변수가 설정되지 않음 — 정책·시크릿 경로를 해석할 수 없음}"
PROJECT_ROOT=$(git -C "$RUN_DIR" rev-parse --show-toplevel 2>/dev/null || true)
if [ -n "$PROJECT_ROOT" ]; then
  PROJECT_POLICY="$PROJECT_ROOT/.claude/model-policy.json"
else
  PROJECT_POLICY="$RUN_DIR/.claude/model-policy.json"
fi
HOST_POLICY="$HOME/.config/opencode/model-policy.json"
POLICY=""
POLICY_SOURCE=""
OPENCODE_BIN="$HOME/.opencode/bin/opencode"
SERVE_ENV_FILE="${OPENCODE_SERVE_ENV_FILE:-$HOME/.config/opencode/serve.env}"
LOCK_DIR="${ORCHESTRATE_STATE_DIR:-$HOME/.local/state/orchestrate}"
LOCK_WAIT_MAX=1800

[ -f "$PROMPT_FILE" ] || { emit "프롬프트 파일 없음: $PROMPT_FILE" >&2; exit 66; }
if [ -f "$PROJECT_POLICY" ]; then
  POLICY="$PROJECT_POLICY"
  POLICY_SOURCE="project"
elif [ -f "$HOST_POLICY" ]; then
  POLICY="$HOST_POLICY"
  POLICY_SOURCE="host"
else
  emit "정책 파일 없음: $PROJECT_POLICY 또는 $HOST_POLICY" >&2
  exit 64
fi
emit "POLICY_USED=$POLICY ($POLICY_SOURCE)"
[ -x "$OPENCODE_BIN" ] || { emit "opencode 없음: $OPENCODE_BIN (install.sh 실행 필요)" >&2; exit 64; }

CHAIN=()
if [ "${TIER#*/}" != "$TIER" ]; then
  CHAIN=("$TIER")
  while IFS= read -r model; do [ "$model" = "$TIER" ] || CHAIN[${#CHAIN[@]}]="$model"; done < <(jq -r '.tiers.default[]' "$POLICY")
else
  while IFS= read -r model; do CHAIN[${#CHAIN[@]}]="$model"; done < <(jq -r --arg tier "$TIER" '.tiers[$tier] // [] | .[]' "$POLICY")
  [ "${#CHAIN[@]}" -gt 0 ] || { emit "알 수 없는 tier: $TIER (정책 파일의 tiers 키 확인: $POLICY)" >&2; exit 64; }
fi

# 총 벽시계는 모델별 시도가 아니라 위임 체인 전체에 적용한다. 빈 값과 0은 계약상
# 명시적인 비활성 형태이며, 그 밖의 손상된 값은 위임을 시작하기 전에 거부한다.
DELEGATION_MAX_SEC="${ORCHESTRATE_DELEGATION_MAX_SEC-3600}"
DELEGATION_CAP_ENABLED=0
case "$DELEGATION_MAX_SEC" in
  ''|0) ;;
  *[!0-9]*) emit "WALLCLOCK_CAP_INVALID: 총 벽시계 상한은 양의 정수, 빈 값 또는 0이어야 함: $DELEGATION_MAX_SEC" >&2; exit 64 ;;
  *)
    DELEGATION_MAX_SEC_NORMALIZED="$DELEGATION_MAX_SEC"
    while [ "${DELEGATION_MAX_SEC_NORMALIZED#0}" != "$DELEGATION_MAX_SEC_NORMALIZED" ]; do
      DELEGATION_MAX_SEC_NORMALIZED="${DELEGATION_MAX_SEC_NORMALIZED#0}"
    done
    if [ -z "$DELEGATION_MAX_SEC_NORMALIZED" ]; then
      DELEGATION_MAX_SEC=0
    elif [ "${#DELEGATION_MAX_SEC_NORMALIZED}" -gt 10 ] || { [ "${#DELEGATION_MAX_SEC_NORMALIZED}" -eq 10 ] && [ "$DELEGATION_MAX_SEC_NORMALIZED" \> "2147483647" ]; }; then
      emit "WALLCLOCK_CAP_INVALID: 총 벽시계 상한이 허용 범위를 벗어남: $DELEGATION_MAX_SEC" >&2
      exit 64
    else
      DELEGATION_MAX_SEC="$DELEGATION_MAX_SEC_NORMALIZED"
      DELEGATION_CAP_ENABLED=1
    fi
    ;;
esac

# ensure의 헬스체크·기동 정책은 serve ctl만 담당한다. 실패 사유는 ctl의 stderr와 아래
# 폴백 메시지로 남긴다. 성공 뒤에는 동일 환경 파일을 읽어 attach 클라이언트에 포트·PW를 준다.
MODE="standalone"
# bash로 호출하므로 실행 비트는 불필요하며, 저장소의 644 추적 스크립트도 발견해야 한다.
if [ ! -f "$SCRIPT_DIR/opencode-serve-ctl.sh" ]; then
  emit "SERVE_FALLBACK: standalone 모드 (serve 제어 스크립트 없음)"
elif SERVE_CTL_ERROR=$(bash "$SCRIPT_DIR/opencode-serve-ctl.sh" ensure 2>&1); then
  MODE="attach"
    # attach URL에는 포트만 필요하다. 인증정보 검증과 API 요청은 ctl이 단독 소유하며,
    # 존재 확인 뒤에는 워커 자식 프로세스에 비밀번호를 상속하지 않는다.
    unset OPENCODE_SERVE_PORT OPENCODE_SERVER_PASSWORD
    set -a
    # shellcheck disable=SC1090
    . "$SERVE_ENV_FILE"
    set +a
    PORT="${OPENCODE_SERVE_PORT:-}"
    [ -n "$PORT" ] || { emit "SERVE_FALLBACK: standalone 모드 (serve 환경 포트 없음)"; MODE="standalone"; }
    [ -n "${OPENCODE_SERVER_PASSWORD:-}" ] || { emit "SERVE_FALLBACK: standalone 모드 (서버 인증정보 없음)"; MODE="standalone"; }
    SERVE_PASSWORD="${OPENCODE_SERVER_PASSWORD:-}"
    unset OPENCODE_SERVER_PASSWORD
else
  case "$SERVE_CTL_ERROR" in
    *OPENCODE_SERVE_PORT*) emit "SERVE_FALLBACK: standalone 모드 (serve 환경 포트 없음)" ;;
    *OPENCODE_SERVER_PASSWORD*) emit "SERVE_FALLBACK: standalone 모드 (서버 인증정보 없음)" ;;
    *) emit "SERVE_FALLBACK: standalone 모드 (serve 기동 실패)" ;;
  esac
fi

# 상태 디렉터리를 만들 수 없으면 안전한 락 획득 자체가 불가능하므로 락 실패(exit 4)로 처리한다.
mkdir -p "$LOCK_DIR" || { emit "락 디렉터리 생성 실패: $LOCK_DIR" >&2; exit 4; }
chmod 700 "$LOCK_DIR" || { emit "락 디렉터리 권한 설정 실패: $LOCK_DIR" >&2; exit 4; }
if [ "$MODE" = "attach" ]; then
  COMMON_DIR=$(git rev-parse --git-common-dir 2>/dev/null || true)
  if [ -n "$COMMON_DIR" ]; then
    case "$COMMON_DIR" in /*) PROJECT_KEY="$COMMON_DIR" ;; *) PROJECT_KEY="$RUN_DIR/$COMMON_DIR" ;; esac
    PROJECT_KEY=$(cd "$PROJECT_KEY" 2>/dev/null && pwd -P || printf '%s' "$PROJECT_KEY")
    PROJECT_NAME=$(basename "$(dirname "$PROJECT_KEY")")
  else
    PROJECT_KEY="$RUN_DIR"
    PROJECT_NAME=$(basename "$RUN_DIR")
  fi
  # 프로젝트명은 락 경로와 LOCK_WAIT 출력에 함께 쓰인다. 센티널 위조를 막기 위해 제어문자를 제거한다.
  PROJECT_NAME=$(printf '%s' "$PROJECT_NAME" | tr -d '[:cntrl:]')
  PROJECT_HASH=$(printf '%s' "$PROJECT_KEY" | cksum | awk '{print $1}' | cut -c1-6)
  LOCK_FILE="$LOCK_DIR/opencode-${PROJECT_NAME}-${PROJECT_HASH}.lock"
  LOCK_LABEL="project"
else
  LOCK_FILE="$LOCK_DIR/opencode.lock"
  LOCK_LABEL="global"
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    if [ "$LOCK_LABEL" = "project" ]; then emit "LOCK_WAIT(project): 같은 프로젝트의 위임이 실행 중 — 최대 30분 대기 (락: $LOCK_FILE)"
    else emit "LOCK_WAIT: 다른 세션의 위임이 실행 중 — 최대 30분 대기 (락: $LOCK_FILE)"; fi
    flock -w "$LOCK_WAIT_MAX" 9 || { emit "LOCK_TIMEOUT: 30분 내 락 획득 실패 — 위임 포기" >&2; exit 4; }
  fi
else
  MLOCK="$LOCK_FILE.d"; WAITED=0
  while ! mkdir "$MLOCK" 2>/dev/null; do
    HOLDER=$(cat "$MLOCK/pid" 2>/dev/null || true)
    if [ -n "$HOLDER" ] && ! kill -0 "$HOLDER" 2>/dev/null; then rm -rf "$MLOCK"; continue; fi
    if [ "$WAITED" -eq 0 ]; then
      if [ "$LOCK_LABEL" = "project" ]; then emit "LOCK_WAIT(project): 같은 프로젝트의 위임이 실행 중 — 최대 30분 대기 (락: $MLOCK)"
      else emit "LOCK_WAIT: 다른 세션의 위임이 실행 중 — 최대 30분 대기 (락: $MLOCK)"; fi
    fi
    sleep 10; WAITED=$((WAITED + 10))
    [ "$WAITED" -lt "$LOCK_WAIT_MAX" ] || { emit "LOCK_TIMEOUT: 30분 내 락 획득 실패 — 위임 포기" >&2; exit 4; }
  done
  printf '%s\n' "$$" > "$MLOCK/pid" || { emit "락 PID 기록 실패: $MLOCK" >&2; rm -rf "$MLOCK"; exit 4; }
  trap 'rm -rf "$MLOCK"' EXIT
fi

# 총 벽시계 한도는 락을 확보한 뒤부터 모델 체인 전체에 적용한다.
DELEGATION_START=$(date +%s)

if [ "$MODE" = "standalone" ]; then
  # serve 옆 standalone은 DB 경합을 일으키지만, C3의 비관리 run 차단과 달리 설정 복구를
  # 막지는 않는다. 경고 후 실행해 원인을 진단 가능하게 남긴다.
  if ps -eo pid,ppid,pgid,args | awk -v self="$$" '
    {
      count=split($4, path, "/")
      is_opencode=(path[count] == "opencode")
    }
    $1 != self && is_opencode && $5 == "serve" { found=1 }
    END { exit !found }
  '; then
    emit "SERVE_ALIVE_FALLBACK: 살아 있는 serve 옆에서 standalone 모드로 실행 — 세션 DB 경합 위험" >&2
  fi
  # argv 부분문자열은 프롬프트를 담은 셸도 잡는다. 실제 opencode 실행 파일과 첫 인자 run만
  # 후보로 삼고, attach 표기는 해석하지 않는다. 부모는 실행 위치 필드($4)와 셸 호출 시
  # 스크립트 경로 필드($5)만 본다. 뒤 인자는 프롬프트·주석·echo 문자열일 수 있어 이름이
  # 스쳐도 관리 근거가 될 수 없다. 각 필드의 basename이 정본 run-delegation.sh 또는 버전
  # 사본 run-delegation-v<숫자>.sh일 때만 관리 중으로 인정한다. 위임 스크립트를 고치는
  # 페이즈에서는 안정본 사본을 얼려 쓰는 것이 운영 관행이므로 버전 사본도 수용한다.
  # 부모 미상과 PPID=1 고아는 관리 근거가 아니므로 fail-closed 한다.
  # 같은 PGID의 중첩 standalone 위임도 독립 실행이면 차단한다. 2c에서 PGID 제외를 제거한
  # 의도된 수용으로, 비대화형 bash의 부모 PGID 상속으로 드라이버 아래 고아를 놓치지 않는다.
  PREFLIGHT_UNMANAGED=$(ps -eo pid,ppid,pgid,args | awk -v self="$$" '
    {
      parent_executable[$1]=$4
      parent_script[$1]=$5
      count=split($4, path, "/")
      is_opencode=(path[count] == "opencode")
    }
    $1 != self && is_opencode && $5 == "run" {
      candidate_count++
      candidate_ppid[candidate_count]=$2
      candidate_line[candidate_count]=$0
    }
    END {
      for (i=1; i<=candidate_count; i++)
        if (candidate_ppid[i] == 1 || !is_managed_wrapper(candidate_ppid[i])) print candidate_line[i]
    }
    function is_managed_wrapper(ppid, count, path, executable, script) {
      count=split(parent_executable[ppid], path, "/")
      executable=path[count]
      count=split(parent_script[ppid], path, "/")
      script=path[count]
       return executable ~ /^run-delegation(-v[0-9]+)?[.]sh$/ || script ~ /^run-delegation(-v[0-9]+)?[.]sh$/
    }
  ')
  if [ -n "$PREFLIGHT_UNMANAGED" ]; then
    emit "PREFLIGHT_UNMANAGED: 락 없이 도는 opencode 프로세스 발견 — 세션 DB 경합 위험. 정리 후 재시도" >&2
    printf '%s\n' "$PREFLIGHT_UNMANAGED" >&2
    exit 3
  fi
fi

set -a
# shellcheck disable=SC1090
[ -f "$HOME/.config/opencode/secrets.env" ] && . "$HOME/.config/opencode/secrets.env"
set +a

# 한도·프로바이더 장애 시그니처는 에러 라인 마지막 50줄만 검사해, stream 오류 뒤 opencode 내부
# 재시도로 회복한 실행을 실패로 오판하지 않는다. 에이전트 산출물의 우연한 ERROR는 라인 필터만으로
# 막지 못하므로 FAIL_RE를 좁게 유지하며, 402도 status 문맥에서만 잡는다.
# 라인 필터는 대문자 `ERROR`(구조화 로그)와 소문자 `Error:`(클라이언트 배너, ANSI 색상 접두가
# 붙는다)를 함께 본다 — 2026-09-01 실측에서 한도 라인이 후자 형식이라 폴백이 통째로 안 걸렸다.
# 소문자 쪽은 **줄 시작**(ANSI 색상 코드만 앞설 수 있음)으로 앵커한다. 클라이언트 배너는 자기
# 줄을 차지하지만 에이전트 산출물의 "Error:" 는 들여쓰기·박스문자 뒤에 오므로, 앵커가 산출물
# 오탐 표면을 좁힌다. 그래도 줄 시작에 온 영문 산문이 FAIL_RE 키워드를 함께 담으면 오탐이
# 가능하다 — 대문자 `ERROR` 에 이미 있던 한계와 같은 종류이며, FAIL_RE 를 좁게 유지해 막는다.
FAIL_RE='status.?429|rate.?limit|quota|resource_exhausted|insufficient_quota|too.?many.?requests|overloaded|exceeded.*(limit|quota)|AI_APICallError|AI_RetryError|ProviderAuthError|ECONNREFUSED|fetch failed|status.?402|insufficient[[:space:]_-]+credits|credit[[:space:]_-]+balance[[:space:]_-]+is[[:space:]_-]+too[[:space:]_-]+low|usage[[:space:]_-]+limit[[:space:]_-]+(has[[:space:]_-]+been[[:space:]_-]+)?reached'
ERROR_LINE_RE="ERROR|^($(printf '\033')\[[0-9;]*m)*Error:"
error_signature_in_lines() { grep -aE "$ERROR_LINE_RE" | grep -qiE "$FAIL_RE"; }
model_error_in_log() { tail -n 50 "$1" | error_signature_in_lines; }
# 클라이언트는 시작 직후 생 따옴표 형식으로 이 경고를 낸다. 산출물 본문 오탐을 막기 위해
# 배너는 19번째 줄이지만 에이전트 산출물은 43번째 줄부터 관측됐다. 40줄로 낮출 여유가 약 40줄이나,
# 첫 세션 신호까지 자르는 재설계는 이번 범위 밖이므로 현행 60줄을 유지한다. 60줄 창에는 산출물 17줄이
# 들어올 수 있다는 한계를 명시하며, 이전 JSON 로그의 이스케이프 표기도 호환성 때문에 함께 허용한다.
agent_not_found_in_log() { head -n 60 "$1" | grep -aF "agent \"$AGENT\" not found" >/dev/null 2>&1 || head -n 60 "$1" | grep -aF "agent \\\"$AGENT\\\" not found" >/dev/null 2>&1; }
loop_session_count() { grep -ac 'loop session.id' "$1" 2>/dev/null || true; }
SESSION_ID=""
ORPHAN_SESSIONS=""
server_sessions() { bash "$SCRIPT_DIR/opencode-serve-ctl.sh" sessions; }
latest_server_session_id() {
  SERVER_SESSIONS=$(server_sessions) || return 1
  printf '%s' "$SERVER_SESSIONS" | jq -er '[.[] | .id | strings | select(length > 0)] | last // empty'
}
server_progress() {
  SESSION_DETAIL=$(OPENCODE_SERVE_ACTION_ID="$SESSION_ID" bash "$SCRIPT_DIR/opencode-serve-ctl.sh" session) || return 1
  printf '%s' "$SESSION_DETAIL" | jq -er '[.time.updated // "", ((.tokens // 0) | tostring)] | @tsv' >/dev/null || return 1
  printf '%s' "$SESSION_DETAIL" | jq -r '[.time.updated // "", ((.tokens // 0) | tostring)] | @tsv'
}
abort_server_session() {
  [ "$ATTEMPT_MODE" = "attach" ] || return 0
  if [ -z "$SESSION_ID" ]; then
    emit "ORPHAN_SESSION_WARNING: 인증된 서버 세션 ID를 확보하지 못해 abort하지 못함"
    return 1
  fi
  if ! OPENCODE_SERVE_ACTION_ID="$SESSION_ID" bash "$SCRIPT_DIR/opencode-serve-ctl.sh" abort >/dev/null; then
    emit "ORPHAN_SESSION_WARNING: 서버 세션 abort 실패 (session=$SESSION_ID)"
    return 1
  fi
  emit "SESSION_ABORTED=$SESSION_ID"
  return 0
}
abort_or_exit() {
  abort_server_session && return 0
  emit "ORPHAN_SESSION: ${SESSION_ID:-미확보}"
  if [ -n "$ORPHAN_SESSIONS" ]; then ORPHAN_SESSIONS="$ORPHAN_SESSIONS,$SESSION_ID"; else ORPHAN_SESSIONS="${SESSION_ID:-미확보}"; fi
  emit "ORPHAN_SESSIONS=$ORPHAN_SESSIONS"
  exit 6
}
kill_client() { kill "$1" 2>/dev/null || true; sleep 3; kill -0 "$1" 2>/dev/null && kill -9 "$1" 2>/dev/null || true; }

# attach 세션은 기동 전에 서버가 발급한다. 클라이언트 종료 뒤에도 서버 loop가 남을 수 있으므로
# 워치독 종료 전 그 확정 ID에 abort API를 호출한다.
# 파일 고정 로그를 써야 한다. 파이프 수신은 버퍼링으로 워치독의 관측을 깨뜨린다.
FALLBACK_NOTES=""
for MODEL in "${CHAIN[@]}"; do
  case "$MODEL" in antigravity/*)
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8045/v1/models 2>/dev/null || echo 000)
    if [ "$HTTP_CODE" = "000" ]; then emit "MODEL_FALLBACK: $MODEL (antigravity 프록시 :8045 다운) → 다음 모델"; FALLBACK_NOTES="$FALLBACK_NOTES[$MODEL: proxy down] "; continue; fi;; esac
  # install은 생성 시 0600으로 열고, 기존 파일도 같은 동작으로 권한을 교정한다.
  # `: >` 뒤 chmod의 두 단계는 생성 직후 읽기 가능한 창을 만들므로 사용하지 않는다.
  install -m 600 /dev/null "$LOG_FILE" || { emit "로그 파일 생성 또는 권한 설정 실패: $LOG_FILE" >&2; exit 4; }
  SESSION_ID=""
  ATTEMPT_MODE="$MODE"
  if [ "$ATTEMPT_MODE" = "attach" ]; then
    SESSION_ID=$(OPENCODE_SERVE_ACTION_DIR="$RUN_DIR" bash "$SCRIPT_DIR/opencode-serve-ctl.sh" create) || {
      emit "SERVE_FALLBACK: standalone 모드 (서버 세션 생성 실패)"
      ATTEMPT_MODE="standalone"
      SESSION_ID=""
    }
  fi
  # standalone 자식은 서버에 연결하지 않으므로 상속된 인증정보까지 전달하면 안 된다.
  [ "$ATTEMPT_MODE" = "attach" ] || unset OPENCODE_SERVER_PASSWORD
  if [ "$ATTEMPT_MODE" = "attach" ]; then
    emit "SESSION_ID=$SESSION_ID (서버에 생성)"
    # 클라이언트는 서버 인증에 비밀번호가 필요하다. 위임 에이전트는 같은 사용자라 어차피
    # serve.env(600)를 읽을 수 있어 클라이언트에게 숨겨도 방어 효과가 없으므로 이 자식에만 준다.
    OPENCODE_SERVER_PASSWORD="$SERVE_PASSWORD" nohup "$OPENCODE_BIN" run --print-logs --log-level INFO --attach "http://127.0.0.1:$PORT" --session "$SESSION_ID" --dir "$RUN_DIR" --agent "$AGENT" -m "$MODEL" "$(cat "$PROMPT_FILE")" > "$LOG_FILE" 2>&1 &
  else
    nohup "$OPENCODE_BIN" run --print-logs --log-level INFO --agent "$AGENT" -m "$MODEL" "$(cat "$PROMPT_FILE")" > "$LOG_FILE" 2>&1 &
  fi
  OC_PID=$!; emit "OC_PID=$OC_PID AGENT=$AGENT MODEL=$MODEL LOG=$LOG_FILE"
  # attach는 기동 전에 세션을 만들지만, 생성만으로 클라이언트가 실제 일을 시작했다는
  # 증거는 되지 않는다. 초기 한도 안에 단건 세션의 갱신값이 한 번도 바뀌지 않으면
  # 살아 있는 클라이언트도 안전하게 init 스톨로 정리한다.
  # 목록은 진행 판정에 쓰지 않는다. 종료 때만 새로 나타난 서버 세션을 정리하기 위한
  # 기준점이며, 목록 조회 실패는 진행 조회 실패를 가리거나 무한 대기를 만들지 않는다.
  INIT_PROGRESS=""; INIT_PROGRESS_SEEN=0; INIT_PROGRESS_ADVANCED=0; INIT_SESSION_SEEN=0
  [ "$ATTEMPT_MODE" = "attach" ] && latest_server_session_id >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    sleep 10
    agent_not_found_in_log "$LOG_FILE" && { emit "AGENT_NOT_FOUND: 에이전트 '$AGENT'를 찾을 수 없음"; kill_client "$OC_PID"; abort_or_exit; exit 7; }
    if [ "$ATTEMPT_MODE" = "attach" ]; then
      latest_server_session_id >/dev/null 2>&1 && INIT_SESSION_SEEN=1
      INIT_CURRENT=$(server_progress) || INIT_CURRENT=""
      if [ -z "$INIT_CURRENT" ]; then
        # 서버 응답 자체가 없으면 기존 폴링 실패 워치독으로 넘겨 진단 주기를 보존한다.
        INIT_PROGRESS_ADVANCED=1; break
      else
        if [ "$INIT_PROGRESS_SEEN" -eq 0 ]; then
          INIT_PROGRESS="$INIT_CURRENT"; INIT_PROGRESS_SEEN=1
        elif [ "$INIT_CURRENT" != "$INIT_PROGRESS" ]; then
          INIT_PROGRESS_ADVANCED=1; break
        fi
      fi
      # 한도 오류는 기존 재시도 루프 워치독이 담당한다. 이 로그가 난 클라이언트를
      # init 스톨로 먼저 끝내면 429와 서버 폴링 실패의 기존 판정 계약이 사라진다.
      if tail -n 3 "$LOG_FILE" | error_signature_in_lines; then
        INIT_PROGRESS_ADVANCED=1; break
      fi
    elif [ "$(loop_session_count "$LOG_FILE")" -gt 0 ]; then
      break
    fi
    kill -0 "$OC_PID" 2>/dev/null || break
  done
  if kill -0 "$OC_PID" 2>/dev/null && [ "$ATTEMPT_MODE" = "attach" ] && [ "$INIT_PROGRESS_ADVANCED" -eq 0 ]; then
    kill_client "$OC_PID"
    # init 스톨은 산출물이 없다는 뜻이므로 abort 실패도 재위임 차단(exit 6)이 아니라
    # 고아 가능성을 남긴 뒤 기존 init 경합(exit 2) 의미를 유지한다.
    # 초기 관측 내내 없던 세션이 종료 시점에 나타나면, 서버가 실제로 붙인 그 세션을
    # 정리한다. 이미 초기부터 보인 다른 세션은 이 실행의 것이라고 단정하지 않는다.
    INIT_LATE_SESSION=""
    if [ "$INIT_SESSION_SEEN" -eq 0 ]; then INIT_LATE_SESSION=$(latest_server_session_id) || INIT_LATE_SESSION=""; fi
    if [ -n "$INIT_LATE_SESSION" ]; then SESSION_ID="$INIT_LATE_SESSION"; fi
    if [ -z "$INIT_LATE_SESSION" ] || ! abort_server_session; then
      emit "ORPHAN_SESSION: $SESSION_ID"
      emit "ORPHAN_SESSIONS=$SESSION_ID"
    fi
    emit "STALLED_AT_INIT: 초기 세션 진행 미확인 — 세션 생성 뒤 갱신이 없어 산출물 없음. 잔여 opencode 정리 후 재위임할 것"
    exit 2
  elif kill -0 "$OC_PID" 2>/dev/null && [ "$ATTEMPT_MODE" = "standalone" ] && [ "$(loop_session_count "$LOG_FILE")" -eq 0 ]; then
    kill_client "$OC_PID"
    if [ "$ATTEMPT_MODE" = "attach" ]; then abort_or_exit; fi
    emit "STALLED_AT_INIT: 초기 세션 미확인 — 세션 생성 전이라 산출물 없음. 잔여 opencode 정리 후 재위임할 것"
    exit 2
  fi
  STALL_START=0; STALL_REASON=""; POLL_FAILURES=0
  if [ "$ATTEMPT_MODE" = "attach" ]; then LAST_PROGRESS=$(server_progress) || LAST_PROGRESS=""; else LAST_PROGRESS=$(loop_session_count "$LOG_FILE"); fi
  while kill -0 "$OC_PID" 2>/dev/null; do
    sleep 10
    # 에이전트 이름 오류는 재위임 전에 반드시 보여야 한다. abort 실패의 고아 위험(exit 6)이
    # 진단(exit 7)보다 우선하지만, 이 메시지는 종료 전에 먼저 남긴다.
    agent_not_found_in_log "$LOG_FILE" && { emit "AGENT_NOT_FOUND: 에이전트 '$AGENT'를 찾을 수 없음"; kill_client "$OC_PID"; abort_or_exit; exit 7; }
    WALLCLOCK_ELAPSED=$(( $(date +%s) - DELEGATION_START ))
    if [ "$DELEGATION_CAP_ENABLED" -eq 1 ] && [ "$WALLCLOCK_ELAPSED" -ge "$DELEGATION_MAX_SEC" ]; then
      emit "WALLCLOCK_CAP=$WALLCLOCK_ELAPSED/$DELEGATION_MAX_SEC — 총 벽시계 상한 초과로 중단"
      kill_client "$OC_PID"
      [ "$ATTEMPT_MODE" = "attach" ] && abort_or_exit
      exit 8
    fi
    if [ "$ATTEMPT_MODE" = "attach" ]; then
      PROGRESS=$(server_progress) && { POLL_FAILURES=0; if [ "$PROGRESS" != "$LAST_PROGRESS" ]; then LAST_PROGRESS="$PROGRESS"; STALL_START=0; continue; fi; } || {
        POLL_FAILURES=$((POLL_FAILURES + 1))
        [ "$POLL_FAILURES" -ge 3 ] && [ $((POLL_FAILURES % 3)) -eq 0 ] && emit "SERVER_POLL_FAILED (연속 ${POLL_FAILURES}회)"
        if [ "$POLL_FAILURES" -ge 10 ]; then
          kill_client "$OC_PID"; abort_or_exit
          STALL_REASON="서버 폴링 연속 실패 (${POLL_FAILURES}회)"; break
        fi
      }
    else
      PROGRESS=$(loop_session_count "$LOG_FILE")
      if [ "$PROGRESS" -gt "$LAST_PROGRESS" ]; then LAST_PROGRESS="$PROGRESS"; STALL_START=0; continue; fi
    fi
    if tail -n 3 "$LOG_FILE" | error_signature_in_lines && [ "$(tail -n 50 "$LOG_FILE" | grep -acE "$ERROR_LINE_RE")" -ge 3 ]; then
      [ "$STALL_START" -eq 0 ] && STALL_START=$(date +%s)
      # 429 로그 스팸은 실제 작업 진행이 아니다. 12분 이상 멈춘 행을 90초에 끊기 위한 가드다.
      if [ $(( $(date +%s) - STALL_START )) -ge 90 ]; then kill_client "$OC_PID"; abort_or_exit; STALL_REASON="재시도 루프 스톨 (90초 무진행)"; break; fi
    else STALL_START=0; fi
  done
  wait "$OC_PID" 2>/dev/null; OC_RC=$?
  if agent_not_found_in_log "$LOG_FILE"; then
    emit "AGENT_NOT_FOUND: 에이전트 '$AGENT'를 찾을 수 없음"
    abort_or_exit
    exit 7
  fi
  REASON=""
  if [ -n "$STALL_REASON" ]; then REASON="$STALL_REASON"
  elif [ "$ATTEMPT_MODE" = "standalone" ] && [ "$(loop_session_count "$LOG_FILE")" -eq 0 ]; then REASON="세션 미개시 종료 rc=$OC_RC"
  elif model_error_in_log "$LOG_FILE"; then REASON="한도/프로바이더 에러 시그니처 rc=$OC_RC"
  elif [ "$OC_RC" -ne 0 ]; then REASON="비정상 종료 rc=$OC_RC"; fi
  if [ -n "$REASON" ]; then
    SLUG=$(echo "$MODEL" | tr '/' '_'); mv "$LOG_FILE" "$LOG_FILE.failed-$SLUG" 2>/dev/null || true
    emit "MODEL_FALLBACK: $MODEL ($REASON) → 다음 모델 (실패 로그: $LOG_FILE.failed-$SLUG)"; FALLBACK_NOTES="$FALLBACK_NOTES[$MODEL: $REASON] "; continue
  fi
  emit "DONE"; emit "MODEL_USED=$MODEL"; [ -n "$FALLBACK_NOTES" ] && emit "FALLBACK_HISTORY: $FALLBACK_NOTES"; tail -5 "$LOG_FILE"; exit 0
done
emit "MODEL_EXHAUSTED: 체인 전 모델 실패 — $FALLBACK_NOTES" >&2
emit "사용자에게 보고할 것: 프로바이더 한도 확인 필요 ($POLICY)" >&2
exit 5
