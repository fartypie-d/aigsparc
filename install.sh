#!/usr/bin/env bash
# aigsprac 전역 설치 (멱등) — macOS / Linux
#
# 사용법: ./install.sh [--claude] [--codex] [--doctor] [--add-missing] [--containers=browser,dashboard] \
#                     [--providers=qwen,openai,xai,antigravity] [--plan=<이름>] [ECC 언어 ...]
#
# 기존 파일은 .bak-<날짜>로 백업 후 교체한다 (secrets.env는 절대 덮어쓰지 않음).
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
ECC_REPO="https://github.com/affaan-m/everything-claude-code.git"
ECC_DIR="$HOME/everything-claude-code"
STAMP=$(date +%Y%m%d-%H%M%S)
CDP_PORT="${INSTALL_CDP_PORT:-9222}"
DASH_PORT="${INSTALL_DASH_PORT:-9280}"
. "$KIT_DIR/lib/stamp.sh"

HARNESSES=""
PROVIDERS=""
CONTAINERS=""
CONTAINERS_FROM_FLAG=0
PLAN=""
AUTH_LOGIN=""
AUTH_LOGIN_FAILED=""
CONTAINER_START_FAILED=""
AUTH_LOGIN_ARGV=()
MCP_REGISTER=0
MCP_ADD_ARGV=()
CONTAINER_UP_ARGV=()
DASHBOARD_MOUNTS_GENERATED=0
DASHBOARD_OVERRIDE_PATH=""
DASHBOARD_OVERRIDE_PATH_READY=0
ECC_LANGS=()
ECC_LANG_REJECTED=0
CLAUDE_INSTALL_FAILED=0
MANUAL_STEP_REASONS=""
HARNESS_FROM_FLAG=0
ECC_LANGS_FROM_FLAG=0
PROVIDERS_FROM_FLAG=0
PLAN_FROM_FLAG=0
DOCTOR=0
ADD_MISSING=0

add_ecc_lang() { # <언어> [cli]
  _ecc_lang_arg=$1
  _ecc_lang_source=${2:-menu}
  case "$_ecc_lang_arg" in
    ""|-*) _ecc_lang_valid=0 ;;
    *[!a-zA-Z0-9_-]*) _ecc_lang_valid=0 ;;
    *) _ecc_lang_valid=1 ;;
  esac
  if [ "$_ecc_lang_valid" = "1" ]; then
    ECC_LANGS[${#ECC_LANGS[@]}]="$_ecc_lang_arg"
    return 0
  fi
  ECC_LANG_REJECTED=$((ECC_LANG_REJECTED + 1))
  if [ "$_ecc_lang_source" = "cli" ]; then
    printf '유효하지 않은 ECC 언어: %s (허용: 영문자·숫자·_·-)\n' "${_ecc_lang_arg:-(빈 값)}" >&2
  else
    printf "   ⚠️ 무시: 유효하지 않은 언어 값 '%s'\n" "$_ecc_lang_arg" >&2
  fi
  return 1
}

mark_manual_step() { # <원인: auth|mcp|container>
  _manual_reason=$1
  case " $MANUAL_STEP_REASONS " in
    *" $_manual_reason "*) ;;
    *) MANUAL_STEP_REASONS="${MANUAL_STEP_REASONS:+$MANUAL_STEP_REASONS }$_manual_reason" ;;
  esac
  return 0
}

for arg in "$@"; do
  case "$arg" in
    --claude)       HARNESSES="${HARNESSES:+$HARNESSES }claude"; HARNESS_FROM_FLAG=1 ;;
    --codex)        HARNESSES="${HARNESSES:+$HARNESSES }codex"; HARNESS_FROM_FLAG=1 ;;
    --doctor)       DOCTOR=1 ;;
    --add-missing)  ADD_MISSING=1 ;;
    --providers=*)  PROVIDERS="${arg#--providers=}"; PROVIDERS_FROM_FLAG=1 ;;
    --containers=*) CONTAINERS="${arg#--containers=}"; CONTAINERS_FROM_FLAG=1 ;;
    # --plan 은 Task 11(apply-plan-profile)이 소비한다
    --plan=*)       PLAN="${arg#--plan=}"; PLAN_FROM_FLAG=1 ;;
    -*)             echo "알 수 없는 옵션: $arg" >&2; exit 64 ;;
    *)
      if ! add_ecc_lang "$arg" cli; then
        exit 64
      fi
      ;;
  esac
done
if [ "${#ECC_LANGS[@]}" -gt 0 ]; then
  ECC_LANGS_FROM_FLAG=1
fi
if [ "$ADD_MISSING" = "1" ] && [ "$DOCTOR" != "1" ]; then
  echo "--add-missing 은 --doctor 와 함께만 사용할 수 있습니다." >&2
  exit 64
fi
if [ "$DOCTOR" = "1" ] && { [ "$CONTAINERS_FROM_FLAG" = "1" ] || [ "$PROVIDERS_FROM_FLAG" = "1" ] || [ "$PLAN_FROM_FLAG" = "1" ] || [ "$ECC_LANGS_FROM_FLAG" = "1" ]; }; then
  echo "--doctor 와 함께 설치 옵션을 사용할 수 없습니다." >&2
  [ "$CONTAINERS_FROM_FLAG" = "1" ] && echo "거부된 옵션: --containers=$CONTAINERS" >&2
  [ "$PROVIDERS_FROM_FLAG" = "1" ] && echo "거부된 옵션: --providers=$PROVIDERS" >&2
  [ "$PLAN_FROM_FLAG" = "1" ] && echo "거부된 옵션: --plan=$PLAN" >&2
  [ "$ECC_LANGS_FROM_FLAG" = "1" ] && echo "거부된 옵션: ${ECC_LANGS[*]}" >&2
  exit 64
fi
if [ "$DOCTOR" = "1" ] && [ "${INSTALL_PARSE_ONLY:-0}" != "1" ]; then
  set --
  case " $HARNESSES " in *" claude "*) set -- "$@" --claude ;; esac
  case " $HARNESSES " in *" codex "*) set -- "$@" --codex ;; esac
  [ "$ADD_MISSING" = "1" ] && set -- "$@" --add-missing
  exec bash "$KIT_DIR/core/scripts/kit-doctor.sh" "$@"
fi

if [ "${INSTALL_SELFTEST_MENU:-0}" != "1" ] && [ "${INSTALL_SELFTEST_KEYPARSE:-0}" != "1" ] && [ "${INSTALL_SELFTEST_TUI:-0}" != "1" ] && [ "${INSTALL_SELFTEST_WIZARD:-0}" != "1" ] && [ "${INSTALL_SELFTEST_MCP:-0}" != "1" ]; then
  [ -n "$HARNESSES" ] || HARNESSES="$(stamp_detect_harness)" || exit 64
fi

if [ "${INSTALL_PARSE_ONLY:-0}" = "1" ]; then
  echo "HARNESSES=$HARNESSES"
  echo "PROVIDERS=$PROVIDERS"
  echo "CONTAINERS=$CONTAINERS"
  echo "PLAN=$PLAN"
  echo "ECC_LANGS=${ECC_LANGS[*]:-}"
  echo "DOCTOR=$DOCTOR"
  exit 0
fi

say()  { printf '\n\033[1m== %s\033[0m\n' "$1"; }
note() { printf '   %s\n' "$1"; }

# 설치 동의는 놓치면 안 되어 /dev/tty를 보조로 쓰지만, 선택 메뉴는 파이프 입력을
# 소비하지 않고 안전한 기본값으로 진행해야 하므로 표준 입력이 터미널일 때만 연다.
is_interactive_menu() { if [ -t 0 ]; then return 0; fi; return 1; }

read_line_interactive() { # <결과 변수명>
  _line_var=$1
  _line_answer=""
  if [ "${INSTALL_SELFTEST_MENU:-0}" = "1" ] || [ "${INSTALL_SELFTEST_WIZARD:-0}" = "1" ]; then
    if [ "${INSTALL_SELFTEST_WIZARD:-0}" = "1" ] && [ -n "${_interactive_selftest_file:-}" ]; then
      if ! IFS= read -r -u 9 _line_answer; then
        return 1
      fi
    else
      case "${_interactive_selftest_inputs:-}" in
        *'|'*)
          _line_answer=${_interactive_selftest_inputs%%|*}
          _interactive_selftest_inputs=${_interactive_selftest_inputs#*|}
          ;;
        *)
          _line_answer=${_interactive_selftest_inputs:-}
          _interactive_selftest_inputs=""
          ;;
      esac
    fi
    if [ "$_line_answer" = "__READ_FAILURE__" ]; then
      _interactive_selftest_inputs=""
      return 1
    fi
    printf -v "$_line_var" '%s' "$_line_answer"
    return 0
  fi
  if [ -t 0 ]; then
    if [ -n "${INSTALL_MENU_IDLE_LIMIT-}" ]; then
      if ! read -r -t "$INSTALL_MENU_IDLE_LIMIT" "$_line_var"; then
        return 1
      fi
    elif ! read -r "$_line_var"; then
      return 1
    fi
  elif [ -r /dev/tty ]; then
    if [ -n "${INSTALL_MENU_IDLE_LIMIT-}" ]; then
      if ! read -r -t "$INSTALL_MENU_IDLE_LIMIT" "$_line_var" </dev/tty; then
        return 1
      fi
    elif ! read -r "$_line_var" </dev/tty; then
      return 1
    fi
  else
    return 2
  fi
}

prompt_yes_no() { # <프롬프트> <기본값: yes|no>
  _prompt=$1
  _default=$2
  _answer=""
  case "$_default" in
    yes) _hint="Y/n" ;;
    no)  _hint="y/N" ;;
    *) echo "잘못된 기본 동의값: $_default" >&2; return 2 ;;
  esac
  printf '%s [%s] ' "$_prompt" "$_hint" >&2
  if read_line_interactive _answer; then
    :
  else
    _read_status=$?
    if [ "$_read_status" = "2" ]; then
      echo "대화형 입력이 없어 동의를 받지 못했다." >&2
    else
      echo "동의 입력을 읽지 못했다." >&2
    fi
    return 1
  fi
  case "$_answer" in
    "") [ "$_default" = "yes" ] ;;
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

is_tui_menu() {
  is_interactive_menu && [ -t 2 ] && { [ "${INSTALL_SELFTEST_MENU:-0}" != "1" ] || [ "${INSTALL_SELFTEST_TUI:-0}" = "1" ]; } && \
    [ "${INSTALL_PLAIN_MENU:-0}" != "1" ] && [ -n "${TERM:-}" ] && [ "${TERM:-}" != "dumb" ]
}

read_menu_key() { # 표준 입력의 키 바이트를 메뉴 동작 토큰으로 변환한다.
  _menu_key=""; _menu_action=back
  if IFS= read -rsn1 -t 1 _menu_key; then
    :
  else
    _menu_status=$?
    if [ "$_menu_status" -gt 128 ]; then
      _menu_action=timeout
    else
      _menu_action=eof
    fi
    printf '%s' "$_menu_action"
    return 0
  fi
  case "$_menu_key" in
    " ") _menu_action=toggle ;;
    ""|$'\r') _menu_action=enter ;;
    $'\033')
      _menu_escape=""
      if IFS= read -rsn1 -t 1 _menu_escape && [ "$_menu_escape" = "[" ]; then
        _menu_arrow=""
        if IFS= read -rsn1 -t 1 _menu_arrow; then
          case "$_menu_arrow" in
            A) _menu_action=up ;;
            B) _menu_action=down ;;
            *) _menu_action=back ;;
          esac
        fi
      fi
      ;;
    *) _menu_action=unknown ;;
  esac
  printf '%s' "$_menu_action"
}

if [ "${INSTALL_SELFTEST_KEYPARSE:-0}" = "1" ]; then
  read_menu_key
  printf '\n'
  exit 0
fi

render_one_tui() { # <프롬프트> <현재 인덱스> <항목>...
  _tui_prompt=$1; _tui_current=$2; shift 2
  printf '\r\033[2K   %s\n' "$_tui_prompt" >&2
  _tui_index=0
  for _tui_item in "$@"; do
    _tui_value=${_tui_item%%:*}; _tui_hint=${_tui_item#*:}
    if [ "$_tui_index" = "$_tui_current" ]; then
      printf '\r\033[2K   \033[7m %s — %s \033[0m\n' "$_tui_value" "$_tui_hint" >&2
    else
      printf '\r\033[2K     %s — %s\n' "$_tui_value" "$_tui_hint" >&2
    fi
    _tui_index=$((_tui_index + 1))
  done
  printf '\r\033[2K   ↑↓ 이동 · Enter 선택\n' >&2
}

choose_one_tui() { # <프롬프트> <기본값> <값:힌트>...
  _tui_prompt=$1; _tui_default=$2; shift 2; _tui_count=$#; _tui_current=0; _tui_index=0
  _tui_idle_limit=${INSTALL_TUI_IDLE_LIMIT:-120}; _tui_idle_count=0
  trap 'stty sane 2>/dev/null; exit 130' INT
  for _tui_item in "$@"; do
    [ "${_tui_item%%:*}" = "$_tui_default" ] && { _tui_current=$_tui_index; break; }
    _tui_index=$((_tui_index + 1))
  done
  _tui_redraw=0
  while :; do
    [ "$_tui_redraw" = "1" ] && printf '\033[%sA' "$((_tui_count + 2))" >&2
    render_one_tui "$_tui_prompt" "$_tui_current" "$@"
    _tui_redraw=1; read_menu_key >/dev/null; _tui_action=$_menu_action
    case "$_tui_action" in
      up) _tui_current=$(((_tui_current + _tui_count - 1) % _tui_count)) ;;
      down) _tui_current=$(((_tui_current + 1) % _tui_count)) ;;
      enter) _tui_index=0; for _tui_item in "$@"; do [ "$_tui_index" = "$_tui_current" ] && { trap - INT; printf '%s' "${_tui_item%%:*}"; return; }; _tui_index=$((_tui_index + 1)); done ;;
      timeout)
        _tui_idle_count=$((_tui_idle_count + 1))
        if [ "$_tui_idle_count" -ge "$_tui_idle_limit" ]; then
          echo "   ${_tui_idle_limit}초 동안 입력이 없어 기본값(\"$_tui_default\")으로 진행한다." >&2
          trap - INT; printf '%s' "$_tui_default"; return 11
        fi
        continue
        ;;
      eof) echo "   입력을 읽지 못해 기본값(\"$_tui_default\")으로 진행한다." >&2; trap - INT; printf '%s' "$_tui_default"; return 11 ;;
      back) trap - INT; return 10 ;;
    esac
    _tui_idle_count=0
  done
}

choose_many_tui() { # <프롬프트> <기본값> <직접 값 허용: 0|1> <값:힌트>...
  _tui_prompt=$1; _tui_default=$2; _tui_allow=$3; shift 3; _tui_count=$#; _tui_total=$_tui_count
  _tui_idle_limit=${INSTALL_TUI_IDLE_LIMIT:-120}; _tui_idle_count=0
  trap 'stty sane 2>/dev/null; exit 130' INT
  [ "$_tui_allow" = "1" ] && _tui_total=$((_tui_total + 1))
  _tui_checked=(); _tui_index=0
  for _tui_item in "$@"; do
    case ",$_tui_default," in *,"${_tui_item%%:*}",*) _tui_checked[${#_tui_checked[@]}]=1 ;; *) _tui_checked[${#_tui_checked[@]}]=0 ;; esac
    _tui_index=$((_tui_index + 1))
  done
  _tui_current=0; _tui_redraw=0
  while :; do
    [ "$_tui_redraw" = "1" ] && printf '\033[%sA' "$((_tui_total + 2))" >&2
    printf '\r\033[2K   %s\n' "$_tui_prompt" >&2; _tui_index=0
    for _tui_item in "$@"; do
      [ "${_tui_checked[$_tui_index]}" = "1" ] && _tui_mark=x || _tui_mark=' '
      if [ "$_tui_index" = "$_tui_current" ]; then printf '\r\033[2K   \033[7m[%s] %s — %s\033[0m\n' "$_tui_mark" "${_tui_item%%:*}" "${_tui_item#*:}" >&2; else printf '\r\033[2K   [%s] %s — %s\n' "$_tui_mark" "${_tui_item%%:*}" "${_tui_item#*:}" >&2; fi
      _tui_index=$((_tui_index + 1))
    done
    if [ "$_tui_allow" = "1" ]; then [ "$_tui_current" = "$_tui_count" ] && printf '\r\033[2K   \033[7m 직접 입력… \033[0m\n' >&2 || printf '\r\033[2K    직접 입력…\n' >&2; fi
    printf '\r\033[2K   ↑↓ 이동 · 스페이스 선택 · Enter 확정\n' >&2; _tui_redraw=1; read_menu_key >/dev/null; _tui_action=$_menu_action
    case "$_tui_action" in
      up) _tui_current=$(((_tui_current + _tui_total - 1) % _tui_total)) ;;
      down) _tui_current=$(((_tui_current + 1) % _tui_total)) ;;
      toggle) [ "$_tui_current" -lt "$_tui_count" ] && { [ "${_tui_checked[$_tui_current]}" = "1" ] && _tui_checked[$_tui_current]=0 || _tui_checked[$_tui_current]=1; } ;;
      enter)
        if [ "$_tui_allow" = "1" ] && [ "$_tui_current" = "$_tui_count" ]; then
          printf '\033[%sA' "$((_tui_total + 2))" >&2; _tui_index=0; while [ "$_tui_index" -lt "$((_tui_total + 2))" ]; do printf '\r\033[2K\n' >&2; _tui_index=$((_tui_index + 1)); done
          printf '   직접 입력 [%s] ' "${_tui_default:-없음}" >&2
          if read_line_interactive _tui_answer; then
            if [ -n "$_tui_answer" ]; then
              if [ "$_tui_answer" = "b" ] || [ "$_tui_answer" = "B" ]; then trap - INT; return 10; fi
              trap - INT; printf '%s' "$_tui_answer"; return
            fi
          else
            echo "   입력을 읽지 못해 기본값(\"$_tui_default\")으로 진행한다." >&2
            trap - INT; printf '%s' "$_tui_default"; return 11
          fi
        fi
        _tui_result=""; _tui_index=0; for _tui_item in "$@"; do [ "${_tui_checked[$_tui_index]}" = "1" ] && _tui_result="${_tui_result:+$_tui_result,}${_tui_item%%:*}"; _tui_index=$((_tui_index + 1)); done; trap - INT; printf '%s' "$_tui_result"; return ;;
      timeout)
        _tui_idle_count=$((_tui_idle_count + 1))
        if [ "$_tui_idle_count" -ge "$_tui_idle_limit" ]; then
          echo "   ${_tui_idle_limit}초 동안 입력이 없어 기본값(\"$_tui_default\")으로 진행한다." >&2
          trap - INT; printf '%s' "$_tui_default"; return 11
        fi
        continue
        ;;
      eof) echo "   입력을 읽지 못해 기본값(\"$_tui_default\")으로 진행한다." >&2; trap - INT; printf '%s' "$_tui_default"; return 11 ;;
      back) trap - INT; return 10 ;;
    esac
    _tui_idle_count=0
  done
}

choose_one() { # <프롬프트> <기본값> <값:힌트>...
  if is_tui_menu; then choose_one_tui "$@"; return $?; fi
  _choose_prompt=$1
  _choose_default=$2
  shift 2
  _choose_count=$#
  _choose_items=()
  _choose_index=1
  for _choose_item in "$@"; do
    _choose_items[${#_choose_items[@]}]=$_choose_item
    _choose_value=${_choose_item%%:*}
    _choose_hint=${_choose_item#*:}
    printf '   %s) %s — %s\n' "$_choose_index" "$_choose_value" "$_choose_hint" >&2
    _choose_index=$((_choose_index + 1))
  done
  _choose_attempt=0
  while [ "$_choose_attempt" -lt 3 ]; do
    printf '   %s [%s] ' "$_choose_prompt" "${_choose_default:-없음}" >&2
    if ! read_line_interactive _choose_answer; then
      echo "   입력을 읽지 못해 기본값(\"$_choose_default\")으로 진행한다." >&2
      printf '%s' "$_choose_default"
      return 11
    fi
    [ -n "$_choose_answer" ] || { printf '%s' "$_choose_default"; return 0; }
    case "$_choose_answer" in b|B) return 10 ;; esac
    case "$_choose_answer" in
      *[!0-9]*) _choose_valid=0 ;;
      *)
        if [ "$_choose_answer" -ge 1 ] 2>/dev/null && [ "$_choose_answer" -le "$_choose_count" ] 2>/dev/null; then
          _choose_valid=1
        else
          _choose_valid=0
        fi
        ;;
    esac
    if [ "$_choose_valid" = "1" ]; then
      _choose_index=1
      for _choose_item in "$@"; do
        if [ "$_choose_index" = "$_choose_answer" ]; then
          printf '%s' "${_choose_item%%:*}"
          return 0
        fi
        _choose_index=$((_choose_index + 1))
      done
    fi
    echo "   1부터 $_choose_count 사이의 번호를 입력할 것" >&2
    _choose_attempt=$((_choose_attempt + 1))
  done
  echo "   입력 3회 실패 — 기본값(\"$_choose_default\")으로 진행한다." >&2
  printf '%s' "$_choose_default"
}

choose_many() { # <프롬프트> <기본값> <직접 값 허용: 0|1> <값:힌트>...
  if is_tui_menu; then choose_many_tui "$@"; return $?; fi
  _choose_prompt=$1
  _choose_default=$2
  _choose_allow_values=$3
  shift 3
  _choose_count=$#
  _choose_items=()
  _choose_index=1
  for _choose_item in "$@"; do
    _choose_items[${#_choose_items[@]}]=$_choose_item
    _choose_value=${_choose_item%%:*}
    _choose_hint=${_choose_item#*:}
    printf '   %s) %s — %s\n' "$_choose_index" "$_choose_value" "$_choose_hint" >&2
    _choose_index=$((_choose_index + 1))
  done
  _choose_attempt=0
  while [ "$_choose_attempt" -lt 3 ]; do
    printf '   %s [%s] ' "$_choose_prompt" "${_choose_default:-없음}" >&2
    if ! read_line_interactive _choose_answer; then
      echo "   입력을 읽지 못해 기본값(\"$_choose_default\")으로 진행한다." >&2
      printf '%s' "$_choose_default"
      return 11
    fi
    [ -n "$_choose_answer" ] || { printf '%s' "$_choose_default"; return 0; }
    case "$_choose_answer" in b|B) return 10 ;; esac
    _choose_words=$(printf '%s' "$_choose_answer" | tr ',' ' ')
    _choose_result=""
    _choose_valid=1
    _choose_old_ifs=$IFS
    IFS=' '
    set -f
    set -- $_choose_words
    set +f
    IFS=$_choose_old_ifs
    for _choose_token in "$@"; do
      if [ -z "$_choose_token" ]; then
        _choose_valid=0
        break
      fi
      case "$_choose_token" in
        *[!0-9]*)
          if [ "$_choose_allow_values" = "1" ]; then
            _choose_value=$_choose_token
          else
            _choose_valid=0
            break
          fi
          ;;
        *)
          if [ "$_choose_token" -lt 1 ] 2>/dev/null || [ "$_choose_token" -gt "$_choose_count" ] 2>/dev/null; then
            _choose_valid=0
            break
          fi
          _choose_value=${_choose_items[$((_choose_token - 1))]%%:*}
          ;;
      esac
      if [ -z "$_choose_value" ]; then
        _choose_valid=0
        break
      fi
      case ",$_choose_result," in
        *,"$_choose_value",*) ;;
        *) _choose_result="${_choose_result:+$_choose_result,}$_choose_value" ;;
      esac
    done
    if [ "$_choose_valid" = "1" ] && [ -n "$_choose_result" ]; then
      printf '%s' "$_choose_result"
      return 0
    fi
    echo "   유효한 번호를 입력할 것" >&2
    _choose_attempt=$((_choose_attempt + 1))
  done
  echo "   입력 3회 실패 — 기본값(\"$_choose_default\")으로 진행한다." >&2
  printf '%s' "$_choose_default"
}

if [ "${INSTALL_SELFTEST_TUI:-0}" = "1" ]; then
  if _tui_selftest_choice=$(choose_one "요금제" skip "pro:Sonnet" "skip:건드리지 않음"); then true; else true; fi
  printf 'SELFTEST TUI ONE=%s\n' "$_tui_selftest_choice"
  if _tui_selftest_choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독"); then true; else true; fi
  printf 'SELFTEST TUI MANY=%s\n' "$_tui_selftest_choice"
  exit 0
fi

notify_noninteractive_harness() {
  note "비대화형 실행 — 하네스 자동 감지값($HARNESSES)을 사용한다. 명시하려면 --claude 또는 --codex." >&2
}

report_plan_skip() {
  note "요금제 미선택 — 모델·토큰 설정을 건드리지 않는다. 지정하려면 --plan=pro|max5|max20." >&2
}

report_ecc_lang_skip() {
  if [ "$ECC_LANG_REJECTED" -gt 0 ]; then
    note "입력한 언어가 모두 무효하여 ECC 설치를 건너뛴다 (허용: 영문자·숫자·_·-)" >&2
  else
    note "언어 인자 없음 — ECC 설치 스킵 (예: ./install.sh --claude typescript python)" >&2
  fi
}

detect_pm() {
  PM="none"
  PM_INSTALL=""
  PM_SYNC=""
  PM_SUDO=0
  _uname=$(uname -s)
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_UNAME:-}" ]; then
    _uname=$INSTALL_TEST_UNAME
  fi
  case "$_uname" in
    Linux)
      _os_id=""
      if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_OS_ID:-}" ]; then
        _os_id=$INSTALL_TEST_OS_ID
      elif [ -f /etc/os-release ]; then
        . /etc/os-release
        _os_id=${ID:-}
      fi
      case "$_os_id" in
        ubuntu|debian) PM="apt-get"; PM_SYNC="update"; PM_INSTALL="install -y"; PM_SUDO=1 ;;
        fedora|rhel|centos) PM="dnf"; PM_INSTALL="install -y"; PM_SUDO=1 ;;
        arch|manjaro) PM="pacman"; PM_INSTALL="-Sy --needed --noconfirm"; PM_SUDO=1 ;;
        alpine) PM="apk"; PM_SYNC="update"; PM_INSTALL="add"; PM_SUDO=1 ;;
        opensuse*|sles) PM="zypper"; PM_INSTALL="--non-interactive install"; PM_SUDO=1 ;;
      esac
      ;;
    Darwin)
      if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_UNAME:-}" ]; then
        PM="brew"
        PM_INSTALL="install"
      elif command -v brew >/dev/null 2>&1; then
        PM="brew"
        PM_INSTALL="install"
      fi
      ;;
  esac
}

install_command() {
  if [ "$PM" = "none" ] || [ -z "$MISSING" ]; then
    printf '없음'
  else
    printf '%s %s %s' "$PM" "$PM_INSTALL" "$MISSING"
  fi
}

sync_command() {
  if [ -z "$PM_SYNC" ] || [ "$PM" = "none" ] || [ -z "$MISSING" ]; then
    printf '없음'
  else
    printf '%s %s' "$PM" "$PM_SYNC"
  fi
}

print_manual_install() {
  if [ "$PM" = "none" ]; then
    echo "수동 설치 명령: 사용하는 패키지 관리자로 $MISSING 를 설치한 뒤 다시 실행할 것" >&2
  else
    echo "수동 설치 명령: $(install_command)" >&2
  fi
}

privilege_method() {
  if [ "$(id -u)" = "0" ]; then
    printf 'root'
  elif command -v sudo >/dev/null 2>&1 && sudo -n true; then
    printf 'sudo-nopass'
  else
    printf 'sudo-consent'
  fi
}

run_privileged() {
  case "$(privilege_method)" in
    root) "$@" ;;
    sudo-nopass) sudo "$@" ;;
    sudo-consent)
      if prompt_yes_no "관리자 권한으로 도구를 설치할까요?" no; then
        sudo "$@"
      else
        echo "관리자 권한 동의를 받지 못해 설치를 중단한다." >&2
        return 1
      fi
      ;;
  esac
}

dry_run_privilege() {
  if [ "$PM" = "none" ] || [ -z "$MISSING" ] || [ "$PM_SUDO" = "0" ]; then
    printf 'none'
  else
    privilege_method
  fi
}

is_claude_harness() {
  case " $HARNESSES " in
    *" claude "*) return 0 ;;
    *) return 1 ;;
  esac
}

claude_is_available() {
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ "${INSTALL_TEST_NO_CLAUDE:-0}" = "1" ]; then
    return 1
  fi
  command -v claude >/dev/null 2>&1
}

npm_is_available() {
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ "${INSTALL_TEST_NO_NPM:-0}" = "1" ]; then
    return 1
  fi
  command -v npm >/dev/null 2>&1
}

node_download_url() {
  _node_os=$(uname -s)
  _node_arch=$(uname -m)
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_NODE_UNAME:-}" ]; then
    _node_os=$INSTALL_TEST_NODE_UNAME
  fi
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ -n "${INSTALL_TEST_NODE_ARCH:-}" ]; then
    _node_arch=$INSTALL_TEST_NODE_ARCH
  fi
  case "$_node_os" in
    Linux) _node_os=linux ;;
    Darwin) _node_os=darwin ;;
    *) printf '미지원 운영체제: %s' "$_node_os"; return 1 ;;
  esac
  case "$_node_arch" in
    x86_64) _node_arch=x64 ;;
    aarch64|arm64) _node_arch=arm64 ;;
    *) printf '미지원 아키텍처: %s' "$_node_arch"; return 1 ;;
  esac
  printf 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-%s-%s.tar.xz' \
    "$_node_os" "$_node_arch"
}

node_bootstrap_plan() {
  if ! _node_url=$(node_download_url); then
    printf '%s' "$_node_url"
    return 0
  fi
  printf 'curl -fsSL %s → %s/.local/opt/node' "$_node_url" "$HOME"
}

prepare_claude_dry_run_plan() {
  CLAUDE_STATE=skipped
  CLAUDE_INSTALL_PLAN=없음
  NODE_BOOTSTRAP_PLAN=없음
  if ! is_claude_harness; then
    return 0
  fi
  if claude_is_available; then
    CLAUDE_STATE=present
    return 0
  fi
  CLAUDE_STATE=missing
  CLAUDE_INSTALL_PLAN='npm i -g @anthropic-ai/claude-code'
  if ! npm_is_available; then
    NODE_BOOTSTRAP_PLAN=$(node_bootstrap_plan)
  fi
}

print_claude_manual_install() {
  _claude_manual_reason=${1:-npm}
  case "$_claude_manual_reason" in
    node)
      note "⚠️ Claude CLI 설치를 완료하지 못했다 — Node.js/npm을 먼저 설치: https://nodejs.org/"
      note "   설치 후 실행: npm i -g @anthropic-ai/claude-code"
      ;;
    unsupported)
      note "⚠️ Claude CLI 설치를 완료하지 못했다 — 현재 OS/아키텍처용 Node.js를 https://nodejs.org/ 에서 설치할 것"
      note "   Node.js/npm 설치 후 실행: npm i -g @anthropic-ai/claude-code"
      ;;
    *)
      note "⚠️ Claude CLI 설치를 완료하지 못했다 — 수동 설치: npm i -g @anthropic-ai/claude-code"
      ;;
  esac
}

bootstrap_user_node() {
  NODE_BOOTSTRAP_FAILURE_REASON=node
  _node_dir="$HOME/.local/opt/node"
  if [ -x "$_node_dir/bin/node" ] && "$_node_dir/bin/node" --version >/dev/null 2>&1; then
    PATH="$_node_dir/bin:$PATH"
    export PATH
    NODE_PATH_ADDED=1
    note "기존 유저공간 Node 확인됨: $_node_dir"
    return 0
  fi
  if ! _node_url=$(node_download_url); then
    note "⚠️ $_node_url — Node.js를 설치한 뒤 다시 실행할 것"
    NODE_BOOTSTRAP_FAILURE_REASON=unsupported
    return 1
  fi
  _node_dir="$HOME/.local/opt/node"
  _node_parent=$(dirname "$_node_dir")
  _node_tmp=$(mktemp -d "${TMPDIR:-/tmp}/orchestrate-node.XXXXXX") || {
    note "⚠️ Node 임시 디렉터리를 만들지 못했다" >&2
    return 1
  }
  _node_archive="$_node_tmp/node.tar.xz"
  _node_name=${_node_url##*/}
  _node_name=${_node_name%.tar.xz}
  note "npm 없음 — 유저공간 Node를 내려받는다: $_node_url"
  if ! curl -fsSL "$_node_url" -o "$_node_archive"; then
    note "⚠️ Node 다운로드 실패: $_node_url" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if ! tar -xJf "$_node_archive" -C "$_node_tmp"; then
    note "⚠️ Node 압축 해제 실패: $_node_archive" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if [ ! -x "$_node_tmp/$_node_name/bin/node" ] || [ ! -x "$_node_tmp/$_node_name/bin/npm" ]; then
    note "⚠️ 압축 해제한 Node에서 node 또는 npm 바이너리를 찾지 못했다" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if ! mkdir -p "$_node_parent"; then
    note "⚠️ 유저공간 Node 상위 디렉터리를 만들지 못했다: $_node_parent" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  if [ -e "$_node_dir" ]; then
    if ! mv "$_node_dir" "$_node_dir.bak-$STAMP"; then
      note "⚠️ 기존 유저공간 Node 백업 실패: $_node_dir" >&2
      rm -rf "$_node_tmp"
      return 1
    fi
    note "백업: $_node_dir → $_node_dir.bak-$STAMP"
  fi
  if ! mv "$_node_tmp/$_node_name" "$_node_dir"; then
    note "⚠️ 유저공간 Node 배치 실패: $_node_dir" >&2
    rm -rf "$_node_tmp"
    return 1
  fi
  rm -rf "$_node_tmp"
  PATH="$_node_dir/bin:$PATH"
  export PATH
  NODE_PATH_ADDED=1
  return 0
}

ensure_claude_cli() {
  NODE_PATH_ADDED=0
  CLAUDE_INSTALL_FAILED=0
  if ! is_claude_harness; then
    return 0
  fi
  if claude_is_available; then
    note "claude CLI 확인됨"
    return 0
  fi
  printf '   \033[1m⚠️ claude 하네스가 선택되었지만 Claude CLI가 없다 — 스킬과 훅이 동작하지 않는다.\033[0m\n'
  if ! prompt_yes_no "지금 설치할까요?" yes; then
    CLAUDE_INSTALL_FAILED=1
    print_claude_manual_install
    return 0
  fi
  if ! npm_is_available; then
    if ! bootstrap_user_node; then
      CLAUDE_INSTALL_FAILED=1
      print_claude_manual_install "$NODE_BOOTSTRAP_FAILURE_REASON"
      return 0
    fi
  fi
  note "Claude CLI 설치: npm i -g @anthropic-ai/claude-code"
  if ! npm i -g @anthropic-ai/claude-code; then
    CLAUDE_INSTALL_FAILED=1
    note "⚠️ Claude CLI npm 설치 실패"
    print_claude_manual_install
    return 0
  fi
  if claude_is_available; then
    note "Claude CLI 설치 후 확인됨"
  else
    CLAUDE_INSTALL_FAILED=1
    note "⚠️ npm 설치 후에도 claude CLI를 찾지 못했다"
    print_claude_manual_install
  fi
  return 0
}

ensure_tools() {
  MISSING=""
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ] && [ "${INSTALL_TEST_MISSING+x}" = "x" ]; then
    MISSING=$INSTALL_TEST_MISSING
  else
    for c in git curl python3 jq; do
      command -v "$c" >/dev/null 2>&1 || MISSING="${MISSING:+$MISSING }$c"
    done
  fi

  detect_pm
  if [ "${INSTALL_DRY_RUN:-0}" = "1" ]; then
    echo "DRY_RUN PM=$PM"
    echo "DRY_RUN MISSING=$MISSING"
    echo "DRY_RUN SYNC_CMD=$(sync_command)"
    echo "DRY_RUN INSTALL_CMD=$(install_command)"
    echo "DRY_RUN PRIVILEGE=$(dry_run_privilege)"
    prepare_claude_dry_run_plan
    echo "DRY_RUN CLAUDE=$CLAUDE_STATE"
    echo "DRY_RUN CLAUDE_INSTALL=$CLAUDE_INSTALL_PLAN"
    echo "DRY_RUN NODE_BOOTSTRAP=$NODE_BOOTSTRAP_PLAN"
    if [ "$PM" = "none" ] && [ -n "$MISSING" ]; then
      print_manual_install
    fi
    return 0
  fi

  [ -n "$MISSING" ] || return 0
  echo "누락: $MISSING" >&2
  if [ "$PM" = "none" ]; then
    echo "지원하는 패키지 관리자를 찾지 못했다." >&2
    print_manual_install
    exit 1
  fi
  echo "설치 명령: $(install_command)" >&2
  # 새 이미지의 패키지 목록은 비어 있을 수 있다. 실패해도 기존 인덱스로 설치를 시도한다.
  if [ -n "$PM_SYNC" ]; then
    echo "인덱스 동기화 명령: $(sync_command)" >&2
    if [ "$PM_SUDO" = "1" ]; then
      if ! run_privileged "$PM" $PM_SYNC; then
        echo "패키지 인덱스 동기화 실패 — 기존 인덱스로 설치를 시도한다." >&2
      fi
    elif ! "$PM" $PM_SYNC; then
      echo "패키지 인덱스 동기화 실패 — 기존 인덱스로 설치를 시도한다." >&2
    fi
  fi
  if [ "$PM_SUDO" = "1" ]; then
    if ! run_privileged "$PM" $PM_INSTALL $MISSING; then
      echo "필수 도구 설치에 실패했다." >&2
      print_manual_install
      exit 1
    fi
  elif ! "$PM" $PM_INSTALL $MISSING; then
    echo "필수 도구 설치에 실패했다." >&2
    print_manual_install
    exit 1
  fi
  for c in $MISSING; do
    if ! command -v "$c" >/dev/null 2>&1; then
      echo "설치 후에도 필수 도구를 찾지 못했다: $c" >&2
      print_manual_install
      exit 1
    fi
  done
}

backup_and_copy() { # <src> <dst>
  if [ -f "$2" ] && ! cmp -s "$1" "$2"; then
    cp "$2" "$2.bak-$STAMP"
    note "백업: $2 → $2.bak-$STAMP"
  fi
  mkdir -p "$(dirname "$2")"
  cp "$1" "$2"
  note "배치: $2"
}

run_install_wizard() {
  WIZARD_STEPS_SHOWN=""
  _wizard_history=()
  _wizard_step=1
  _wizard_revisiting=0
  while :; do
    _wizard_back=0
    _wizard_rc=0
    case "$_wizard_step" in
      1)
        if [ "$HARNESS_FROM_FLAG" = "1" ]; then
          _wizard_step=2
          continue
        fi
        case "$HARNESSES" in
          "claude codex") _harness_default=both ;;
          *) _harness_default=$HARNESSES ;;
        esac
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }harness"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=1
        fi
        if _harness_choice=$(choose_one "오케스트레이터 하네스를 고른다 (실행자 opencode는 공통 설치)" "$_harness_default" "claude:Claude Code에서 오케스트레이션" "codex:Codex CLI에서 오케스트레이션" "both:둘 다"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ]; then
          _wizard_back=1
        else
          case "$_harness_choice" in
            both) HARNESSES="claude codex" ;;
            *) HARNESSES=$_harness_choice ;;
          esac
          _wizard_revisiting=0
          _wizard_step=2
        fi
        ;;
      2)
        if [ "${#ECC_LANGS[@]}" -gt 0 ] && [ "$ECC_LANGS_FROM_FLAG" = "1" ]; then
          _wizard_step=3
          continue
        fi
        _wizard_old_ifs=$IFS
        IFS=,
        _wizard_ecc_default="${ECC_LANGS[*]}"
        IFS=$_wizard_old_ifs
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }ecc"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=2
        fi
        if _ecc_choices=$(choose_many "ECC 언어를 고른다 (직접 입력도 가능)" "$_wizard_ecc_default" 1 "typescript:TypeScript" "python:Python" "golang:Go" "vue:Vue" "react-native:React Native"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ]; then
          _wizard_back=1
        else
          ECC_LANGS=()
          if [ -n "$_ecc_choices" ]; then
            _ecc_old_ifs=$IFS
            IFS=,
            set -f
            for _ecc_lang in $_ecc_choices; do
              if ! add_ecc_lang "$_ecc_lang"; then
                :
              fi
            done
            set +f
            IFS=$_ecc_old_ifs
          fi
          _wizard_revisiting=0
          _wizard_step=3
        fi
        ;;
      3)
        if [ -n "$PROVIDERS" ] && [ "$PROVIDERS_FROM_FLAG" = "1" ]; then
          _wizard_step=4
          continue
        fi
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }providers"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=3
        fi
        if _wizard_providers=$(choose_many "프로바이더를 고른다" "$PROVIDERS" 0 "openai:구독 또는 키" "xai:구독" "qwen:키" "antigravity:키+로컬프록시"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ]; then
          _wizard_back=1
        else
          PROVIDERS=$_wizard_providers
          _wizard_revisiting=0
          _wizard_step=4
        fi
        ;;
      4)
        _wizard_auth_default=""
        _wizard_auth_items=()
        _wizard_old_ifs=$IFS
        IFS=,
        set -f
        for _wizard_provider in $PROVIDERS; do
          case "$_wizard_provider" in
            openai) _wizard_auth_item="openai:구독" ;;
            xai) _wizard_auth_item="xai:구독" ;;
            *) continue ;;
          esac
          _wizard_auth_items[${#_wizard_auth_items[@]}]=$_wizard_auth_item
          _wizard_auth_default="${_wizard_auth_default:+$_wizard_auth_default,}$_wizard_provider"
        done
        set +f
        IFS=$_wizard_old_ifs
        if [ "${#_wizard_auth_items[@]}" -eq 0 ]; then
          AUTH_LOGIN=""
          _wizard_step=5
          continue
        fi
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }auth"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=4
        fi
        if _wizard_auth_choices=$(choose_many "설치 후 바로 로그인할 구독 프로바이더를 고른다" "$_wizard_auth_default" 0 "${_wizard_auth_items[@]}"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ]; then
          _wizard_back=1
        elif [ "$_wizard_rc" = "11" ]; then
          AUTH_LOGIN=""
        else
          AUTH_LOGIN=""
          _wizard_old_ifs=$IFS
          IFS=,
          set -f
          for _wizard_provider in $PROVIDERS; do
            case ",$_wizard_auth_choices," in
              *,"$_wizard_provider",*) AUTH_LOGIN="${AUTH_LOGIN:+$AUTH_LOGIN }$_wizard_provider" ;;
            esac
          done
          set +f
          IFS=$_wizard_old_ifs
          _wizard_revisiting=0
          _wizard_step=5
        fi
        ;;
      5)
        if [ "$CONTAINERS_FROM_FLAG" = "1" ]; then
          _wizard_step=6
          continue
        fi
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }containers"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=5
        fi
        if is_claude_harness; then
          _wizard_container_items=("browser:스텔스 브라우저 컨테이너 (CDP·우회 fetch)" "mcp:chrome-devtools-mcp 를 사용자 레벨에 등록" "dashboard:세션 사용량 대시보드 (usage-dashboard)")
        else
          _wizard_container_items=("browser:스텔스 브라우저 컨테이너 (CDP·우회 fetch)" "dashboard:세션 사용량 대시보드 (usage-dashboard)")
        fi
        if _wizard_containers=$(choose_many "설치할 컨테이너를 고른다" "$CONTAINERS" 0 "${_wizard_container_items[@]}"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ]; then
          _wizard_back=1
        elif [ "$_wizard_rc" = "11" ]; then
          CONTAINERS=""
          MCP_REGISTER=0
        else
          case ",$_wizard_containers," in
            *,mcp,*) MCP_REGISTER=1 ;;
            *) MCP_REGISTER=0 ;;
          esac
          CONTAINERS=""
          case ",$_wizard_containers," in
            *,browser,*) CONTAINERS=browser ;;
          esac
          case ",$_wizard_containers," in
            *,dashboard,*) CONTAINERS="${CONTAINERS:+$CONTAINERS,}dashboard" ;;
          esac
          case ",$CONTAINERS," in
            *,browser,*) ;;
            *)
              if [ "$MCP_REGISTER" = "1" ]; then
                note "⚠️ chrome-devtools-mcp 등록은 browser 컨테이너가 필요해 선택을 해제한다." >&2
                MCP_REGISTER=0
              fi
              ;;
          esac
          _wizard_revisiting=0
          _wizard_step=6
        fi
        ;;
      6)
        if [ -n "$PLAN" ] && [ "$PLAN_FROM_FLAG" = "1" ]; then
          _wizard_step=7
          continue
        fi
        if ! is_claude_harness; then
          _wizard_step=7
          continue
        fi
        printf '   토큰 예산(사고 10000 · 압축 75%%)은 세 프로파일 공통이다 — 요금제는 모델만 가른다.\n' >&2
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }plan"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=6
        fi
        if _wizard_plan=$(choose_one "요금제를 고른다" "${PLAN:-skip}" "pro:메인 sonnet · worker haiku" "max5:메인 opus · worker haiku" "max20:메인 유지 · worker sonnet" "skip:건드리지 않음"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ]; then
          _wizard_back=1
        else
          PLAN=$_wizard_plan
          _wizard_revisiting=0
          _wizard_step=7
        fi
        ;;
      7)
        WIZARD_STEPS_SHOWN="${WIZARD_STEPS_SHOWN:+$WIZARD_STEPS_SHOWN }summary"
        if [ "$_wizard_revisiting" != "1" ]; then
          _wizard_history[${#_wizard_history[@]}]=7
        fi
        printf '   선택 요약: 하네스=%s · ECC=%s · 프로바이더=%s · 요금제=%s · 로그인=%s\n' "$HARNESSES" "${ECC_LANGS[*]}" "$PROVIDERS" "$PLAN" "$AUTH_LOGIN" >&2
        if _wizard_summary=$(choose_one "설정을 확인한다" start "start:이 설정으로 설치를 시작한다" "back:이전 단계로 돌아간다"); then
          _wizard_rc=0
        else
          _wizard_rc=$?
        fi
        if [ "$_wizard_rc" = "10" ] || [ "$_wizard_summary" = "back" ]; then
          _wizard_back=1
        else
          return 0
        fi
        ;;
    esac
    if [ "$_wizard_rc" = "11" ]; then
      if [ "$_wizard_step" -le 6 ] && is_claude_harness && [ "$PLAN_FROM_FLAG" != "1" ]; then
        PLAN=${PLAN:-skip}
      fi
      printf '   입력을 읽지 못해 남은 선택을 기본값으로 확정했다: 하네스=%s · ECC 언어=%s · 프로바이더=%s · 요금제=%s\n' \
        "$HARNESSES" "${ECC_LANGS[*]}" "$PROVIDERS" "$PLAN" >&2
      printf '   최종 확인(요약) 단계를 건너뛰고 설치를 진행한다.\n' >&2
      return 0
    fi
    if [ "$_wizard_back" = "1" ]; then
      if [ "${#_wizard_history[@]}" -gt 0 ]; then
        _wizard_last=$((${#_wizard_history[@]} - 1))
        unset "_wizard_history[$_wizard_last]"
      fi
      if [ "${#_wizard_history[@]}" -gt 0 ]; then
        _wizard_step=${_wizard_history[${#_wizard_history[@]}-1]}
      fi
      _wizard_revisiting=1
      case "$_wizard_step" in
        1)
          [ "$ECC_LANGS_FROM_FLAG" = "1" ] || ECC_LANGS=()
          [ "$PROVIDERS_FROM_FLAG" = "1" ] || PROVIDERS=""
          AUTH_LOGIN=""
          [ "$CONTAINERS_FROM_FLAG" = "1" ] || CONTAINERS=""
          MCP_REGISTER=0
          [ "$PLAN_FROM_FLAG" = "1" ] || PLAN=""
          ;;
        2)
          [ "$PROVIDERS_FROM_FLAG" = "1" ] || PROVIDERS=""
          AUTH_LOGIN=""
          [ "$CONTAINERS_FROM_FLAG" = "1" ] || CONTAINERS=""
          MCP_REGISTER=0
          [ "$PLAN_FROM_FLAG" = "1" ] || PLAN=""
          ;;
        3)
          AUTH_LOGIN=""
          [ "$CONTAINERS_FROM_FLAG" = "1" ] || CONTAINERS=""
          MCP_REGISTER=0
          [ "$PLAN_FROM_FLAG" = "1" ] || PLAN=""
          ;;
        4)
          [ "$CONTAINERS_FROM_FLAG" = "1" ] || CONTAINERS=""
          MCP_REGISTER=0
          [ "$PLAN_FROM_FLAG" = "1" ] || PLAN=""
          ;;
        5) MCP_REGISTER=0; [ "$PLAN_FROM_FLAG" = "1" ] || PLAN="" ;;
      esac
    fi
  done
}

build_auth_login_argv() { # <프로바이더>
  AUTH_LOGIN_ARGV=()
  case "$1" in
    xai) AUTH_LOGIN_ARGV=(auth login -p xai) ;;
    openai) AUTH_LOGIN_ARGV=(auth login -p openai -m 'ChatGPT Pro/Plus (headless)') ;;
    *) return 1 ;;
  esac
}

build_mcp_add_argv() { # <서버명>
  MCP_ADD_ARGV=()
  case "$1" in
    chrome-devtools) MCP_ADD_ARGV=(claude mcp add -s user chrome-devtools -- npx -y chrome-devtools-mcp@latest --browserUrl http://127.0.0.1:$CDP_PORT) ;;
    *) return 1 ;;
  esac
}

mcp_add_command() { # <서버명>
  build_mcp_add_argv "$1" || return 1
  _mcp_rendered=""
  for _mcp_arg in "${MCP_ADD_ARGV[@]}"; do
    case "$_mcp_arg" in
      *' '*) _mcp_piece="\"$_mcp_arg\"" ;;
      *) _mcp_piece=$_mcp_arg ;;
    esac
    _mcp_rendered="${_mcp_rendered:+$_mcp_rendered }$_mcp_piece"
  done
  printf '%s' "$_mcp_rendered"
}

auth_login_command() { # <프로바이더>
  build_auth_login_argv "$1" || return 1
  printf '%s' '~/.opencode/bin/opencode'
  for _auth_arg in "${AUTH_LOGIN_ARGV[@]}"; do
    case "$_auth_arg" in
      *' '*) printf ' "%s"' "$_auth_arg" ;;
      *) printf ' %s' "$_auth_arg" ;;
    esac
  done
}

build_container_up_argv() {
  CONTAINER_UP_ARGV=()
  case "$1" in
    browser) CONTAINER_UP_ARGV=(docker compose -f "$KIT_DIR/containers/browser/docker-compose.yml" up -d) ;;
    dashboard)
      if [ "$DASHBOARD_OVERRIDE_PATH_READY" = "0" ]; then
        if [ "${INSTALL_DRY_RUN:-0}" != "1" ] && [ "$DASHBOARD_MOUNTS_GENERATED" = "0" ]; then
          DASHBOARD_MOUNTS_GENERATED=1
          if command -v python3 >/dev/null 2>&1; then
            if ! python3 "$KIT_DIR/core/scripts/phase-tools.py" dashboard-mounts >/dev/null; then
              note "⚠️ dashboard-mounts 생성 실패 — 기존 마운트 설정으로 계속 진행" >&2
            fi
          fi
        fi
        if [ "${INSTALL_DRY_RUN:-0}" != "1" ] && command -v python3 >/dev/null 2>&1; then
          if DASHBOARD_OVERRIDE_PATH=$(python3 "$KIT_DIR/core/scripts/phase-tools.py" dashboard-mounts --print-path); then
            if [ -z "$DASHBOARD_OVERRIDE_PATH" ]; then
              note "⚠️ dashboard-mounts 경로 확인 결과가 비어 있음 — 폴백 경로로 계속 진행" >&2
            fi
          else
            DASHBOARD_OVERRIDE_PATH=""
            note "⚠️ dashboard-mounts 경로 확인 실패 — 폴백 경로로 계속 진행" >&2
          fi
        fi
        if [ -z "$DASHBOARD_OVERRIDE_PATH" ]; then
          if [ -n "${ORCH_STATE_DIR:-}" ]; then
            _dashboard_state_dir=$ORCH_STATE_DIR
          else
            _dashboard_state_dir=${HOME:-}/.local/state/orchestrate
          fi
          DASHBOARD_OVERRIDE_PATH=$_dashboard_state_dir/dashboard-compose.override.yml
        fi
        DASHBOARD_OVERRIDE_PATH_READY=1
      fi
      CONTAINER_UP_ARGV=(docker compose -f "$KIT_DIR/components/usage-dashboard/docker-compose.yml")
      if [ -f "$DASHBOARD_OVERRIDE_PATH" ]; then
        CONTAINER_UP_ARGV[${#CONTAINER_UP_ARGV[@]}]=-f
        CONTAINER_UP_ARGV[${#CONTAINER_UP_ARGV[@]}]="$DASHBOARD_OVERRIDE_PATH"
      fi
      CONTAINER_UP_ARGV[${#CONTAINER_UP_ARGV[@]}]=up
      CONTAINER_UP_ARGV[${#CONTAINER_UP_ARGV[@]}]=-d
      ;;
    *) return 1 ;;
  esac
}

container_up_command() { # <컨테이너>
  build_container_up_argv "$1" || return 1
  _container_rendered=""
  for _container_arg in "${CONTAINER_UP_ARGV[@]}"; do
    case "$_container_arg" in
      *' '*) _container_piece="\"$_container_arg\"" ;;
      *) _container_piece=$_container_arg ;;
    esac
    _container_rendered="${_container_rendered:+$_container_rendered }$_container_piece"
  done
  printf '%s' "$_container_rendered"
}

run_auth_logins() {
  [ -n "$AUTH_LOGIN" ] || return 0
  if [ "${INSTALL_SELFTEST_AUTH:-0}" != "1" ] && [ ! -x "$HOME/.opencode/bin/opencode" ]; then
    note "⚠️ opencode 실행 파일이 없어 인증 로그인을 건너뜀 — 남은 수동 단계를 확인할 것" >&2
    AUTH_LOGIN_FAILED=$AUTH_LOGIN
    mark_manual_step auth
    return 0
  fi
  _auth_old_ifs=$IFS
  IFS=' '
  set -f
  for _auth_provider in $AUTH_LOGIN; do
    if ! build_auth_login_argv "$_auth_provider"; then
      note "⚠️ 알 수 없는 인증 프로바이더: $_auth_provider — 로그인을 건너뜀" >&2
      continue
    fi
    if [ "${INSTALL_SELFTEST_AUTH:-0}" = "1" ]; then
      case " ${INSTALL_AUTH_FAIL:-} " in
        *" $_auth_provider "*)
          case " $AUTH_LOGIN_FAILED " in
            *" $_auth_provider "*) ;;
            *) AUTH_LOGIN_FAILED="${AUTH_LOGIN_FAILED:+$AUTH_LOGIN_FAILED }$_auth_provider" ;;
          esac
          printf 'AUTH_LOGIN_FAILED=%s\n' "$_auth_provider"
          continue
          ;;
      esac
      printf 'AUTH_LOGIN_WOULD_RUN=%s %s\n' "$_auth_provider" "$(auth_login_command "$_auth_provider")"
      continue
    fi
    if ! "$HOME/.opencode/bin/opencode" "${AUTH_LOGIN_ARGV[@]}"; then
      case " $AUTH_LOGIN_FAILED " in
        *" $_auth_provider "*) ;;
        *) AUTH_LOGIN_FAILED="${AUTH_LOGIN_FAILED:+$AUTH_LOGIN_FAILED }$_auth_provider" ;;
      esac
      mark_manual_step auth
      note "⚠️ $_auth_provider 로그인 실패 — 남은 수동 단계를 확인할 것" >&2
    fi
  done
  set +f
  IFS=$_auth_old_ifs
  return 0
}

run_mcp_registration() {
  [ "$MCP_REGISTER" = "1" ] || return 0
  if ! command -v claude >/dev/null 2>&1; then
    note "⚠️ claude CLI가 없어 chrome-devtools MCP 등록을 건너뜀 — README MCP 절을 따라 수동 등록할 것" >&2
    return 0
  fi
  if claude mcp list 2>/dev/null | grep -q 'chrome-devtools'; then
    note "chrome-devtools MCP가 이미 등록되어 있어 건너뜀"
    return 0
  fi
  if ! build_mcp_add_argv chrome-devtools; then
    note "⚠️ chrome-devtools MCP 명령을 구성하지 못함 — README MCP 절을 확인할 것" >&2
    return 0
  fi
  if ! "${MCP_ADD_ARGV[@]}"; then
    mark_manual_step mcp
    note "⚠️ chrome-devtools MCP 등록 실패 — README MCP 절을 따라 수동 등록할 것" >&2
  fi
  return 0
}

if [ "${INSTALL_SELFTEST_WIZARD:-0}" = "1" ]; then
  _interactive_selftest_inputs=${INSTALL_SELFTEST_INPUTS:-}
  _interactive_selftest_file=$(mktemp "${TMPDIR:-/tmp}/orchestrate-wizard.XXXXXX")
  printf '%s\n' "$_interactive_selftest_inputs" | tr '|' '\n' > "$_interactive_selftest_file"
  exec 9< "$_interactive_selftest_file"
  run_install_wizard
  exec 9<&-
  rm -f "$_interactive_selftest_file"
  printf 'SELFTEST WIZARD HARNESSES=%s\n' "$HARNESSES"
  printf 'SELFTEST WIZARD ECC=%s\n' "${ECC_LANGS[*]}"
  printf 'SELFTEST WIZARD PROVIDERS=%s\n' "$PROVIDERS"
  printf 'SELFTEST WIZARD AUTH=%s\n' "$AUTH_LOGIN"
  printf 'SELFTEST WIZARD CONTAINERS=%s\n' "$CONTAINERS"
  if is_claude_harness; then
    printf 'SELFTEST WIZARD MCP=%s\n' "$MCP_REGISTER"
  fi
  printf 'SELFTEST WIZARD PLAN=%s\n' "$PLAN"
  printf 'SELFTEST WIZARD STEPS=%s\n' "$WIZARD_STEPS_SHOWN"
  exit 0
fi

if [ "${INSTALL_SELFTEST_AUTH:-0}" = "1" ]; then
  AUTH_LOGIN=${INSTALL_AUTH_LOGIN:-}
  run_auth_logins
  exit 0
fi

if [ "${INSTALL_SELFTEST_CONTAINERS:-0}" = "1" ]; then
  CONTAINERS=${INSTALL_CONTAINERS:-}
  _container_fake=${INSTALL_CONTAINER_FAKE:-ok}
  _container_consent=${INSTALL_CONTAINER_CONSENT:-y}
  _container_old_ifs=$IFS
  IFS=,
  set -f
  for _container_name in $CONTAINERS; do
    if ! build_container_up_argv "$_container_name"; then
      printf '⚠️ 알 수 없는 컨테이너: %s\n' "$_container_name" >&2
      continue
    fi
    printf 'CONTAINER_SUBMODULE_WOULD_INIT=%s\n' "$_container_name"
    case "$_container_fake" in
      submodule_missing) printf 'CONTAINER_INSTALL_SKIPPED=%s reason=unknown\n' "$_container_name" ;;
      docker_missing) printf 'CONTAINER_INSTALL_SKIPPED=%s reason=docker_missing\n' "$_container_name" ;;
      port_busy) printf 'CONTAINER_INSTALL_SKIPPED=%s reason=port_busy\n' "$_container_name" ;;
      ok)
        if [ "$_container_consent" = "y" ]; then
          _rendered=$(container_up_command "$_container_name")
          printf 'CONTAINER_INSTALL_WOULD_RUN=%s %s\n' "$_container_name" "$_rendered"
        else
          printf 'CONTAINER_INSTALL_SKIPPED=%s reason=declined\n' "$_container_name"
        fi
        ;;
      *) printf 'CONTAINER_INSTALL_SKIPPED=%s reason=unknown\n' "$_container_name" ;;
    esac
  done
  set +f
  IFS=$_container_old_ifs
  exit 0
fi

if [ "${INSTALL_SELFTEST_MCP:-0}" = "1" ]; then
  _mcp_fake=${INSTALL_MCP_FAKE:-ok}
  case "$_mcp_fake" in
    ok) printf 'MCP_REGISTER_WOULD_RUN=chrome-devtools %s\n' "$(mcp_add_command chrome-devtools)" ;;
    no_cli) printf 'MCP_REGISTER_SKIPPED=chrome-devtools reason=no_cli\n' ;;
    exists) printf 'MCP_REGISTER_SKIPPED=chrome-devtools reason=exists\n' ;;
    fail) printf 'MCP_REGISTER_FAILED=chrome-devtools\n'; note "⚠️ chrome-devtools MCP 등록 실패 — README MCP 절을 따라 수동 등록할 것" >&2 ;;
    *) printf 'MCP_REGISTER_FAILED=chrome-devtools\n'; note "⚠️ chrome-devtools MCP 등록 실패 — README MCP 절을 따라 수동 등록할 것" >&2 ;;
  esac
  exit 0
fi

if [ "${INSTALL_SELFTEST_MENU:-0}" = "1" ]; then
  if is_interactive_menu; then
    echo "SELFTEST INTERACTIVE=1"
  else
    echo "SELFTEST INTERACTIVE=0"
  fi
  _interactive_selftest_inputs='1,3'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='1 3'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='1,3,'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='1,3,1'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs=''
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='9|9|9'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='x|x|x'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='2'
  if _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음"); then true; else true; fi
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs=''
  if _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음"); then true; else true; fi
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='9|9|9'
  if _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음"); then true; else true; fi
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='x|x|x'
  if _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음"); then true; else true; fi
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='__READ_FAILURE__'
  if _choice=$(choose_many "프로바이더" qwen 0 "qwen:키" "openai:구독" "xai:구독"); then true; else true; fi
  echo "SELFTEST CHOICE=$_choice"
  _interactive_selftest_inputs='__READ_FAILURE__'
  if _choice=$(choose_one "요금제" skip "pro:Sonnet" "max5:Opus" "max20:Sonnet worker" "skip:건드리지 않음"); then true; else true; fi
  echo "SELFTEST PLAN=$_choice"
  _interactive_selftest_inputs='typescript,--config,/tmp/evil.json'
  if _ecc_choices=$(choose_many "ECC 언어" "" 1 "typescript:TypeScript"); then true; else true; fi
  _ecc_old_ifs=$IFS
  IFS=,
  set -f
  for _ecc_lang in $_ecc_choices; do
    if ! add_ecc_lang "$_ecc_lang"; then
      :
    fi
  done
  set +f
  IFS=$_ecc_old_ifs
  echo "SELFTEST ECC=${ECC_LANGS[*]:-}"
  notify_noninteractive_harness
  report_plan_skip
  ECC_LANGS=()
  ECC_LANG_REJECTED=0
  report_ecc_lang_skip
  if ! add_ecc_lang '--config'; then
    :
  fi
  if ! add_ecc_lang '/tmp/evil.json'; then
    :
  fi
  report_ecc_lang_skip
  exit 0
fi

note "이 설치는 $HOME 전역 설정(~/.claude, ~/.config/opencode)을 배치한다."
note "킷 클론 디렉토리에는 설치하지 않으며, 프로젝트 적용은 ./new-project.sh · ./adopt-project.sh 로 한다."
if [ "${INSTALL_DRY_RUN:-0}" != "1" ] && is_interactive_menu; then
  run_install_wizard
fi

if [ "$HARNESS_FROM_FLAG" = "0" ] && [ "${INSTALL_DRY_RUN:-0}" != "1" ] && is_interactive_menu; then
  :
elif [ "$HARNESS_FROM_FLAG" = "0" ] && [ "${INSTALL_DRY_RUN:-0}" != "1" ]; then
  notify_noninteractive_harness
fi

say "1/7 필수 도구 확인"
ensure_tools
if [ "${INSTALL_DRY_RUN:-0}" = "1" ]; then
  exit 0
fi
ensure_claude_cli
if [ "$CLAUDE_INSTALL_FAILED" = "1" ]; then
  note "Claude CLI 설치 실패 — 아래 남은 수동 단계를 확인할 것"
else
  note "OK"
fi

say "2/7 opencode"
if [ -x "$HOME/.opencode/bin/opencode" ]; then
  note "이미 설치됨: $("$HOME/.opencode/bin/opencode" --version 2>/dev/null || echo '?')"
else
  curl -fsSL https://opencode.ai/install | bash
fi

say "3/7 ECC (everything-claude-code)"
if [ "${#ECC_LANGS[@]}" -eq 0 ]; then
    report_ecc_lang_skip
fi
if [ "${#ECC_LANGS[@]}" -gt 0 ]; then
  if [ -d "$ECC_DIR/.git" ]; then
    git -C "$ECC_DIR" pull --ff-only || note "⚠️ ECC pull 실패 — 기존 체크아웃으로 진행" >&2
  else
    git clone "$ECC_REPO" "$ECC_DIR"
  fi
  ( cd "$ECC_DIR" && ./install.sh "${ECC_LANGS[@]}" )
fi

say "4/7 superpowers 플러그인"
case " $HARNESSES " in
  *" claude "*)
    if command -v claude >/dev/null 2>&1; then
      if claude plugin list 2>/dev/null | grep -q 'superpowers@superpowers-dev'; then
        note "이미 설치됨 — 스킵"
      else
        if claude plugin marketplace list 2>/dev/null | grep -q 'superpowers-dev'; then
          note "마켓플레이스 이미 등록됨 — 스킵"
        else
          if claude plugin marketplace add obra/superpowers; then
            note "마켓플레이스 등록: superpowers-dev"
          else
            note "⚠️ superpowers 마켓플레이스 등록 실패 — 수동 설치: claude plugin install superpowers@superpowers-dev" >&2
          fi
        fi
        if claude plugin install superpowers@superpowers-dev; then
          note "설치됨"
        else
          note "⚠️ superpowers 플러그인 설치 실패 — 수동 설치: claude plugin install superpowers@superpowers-dev" >&2
        fi
      fi
    else
      note "claude CLI 없음 — 스킵"
    fi
    ;;
  *) note "claude 하네스 미선택 — 스킵" ;;
esac

say "5/7 전역 자산 배치 (하네스: $HARNESSES)"

# v1 레이아웃 잔재 정리 — 구 경로에서 설치된 스킬은 그대로 두되 안내만 한다.
if [ -d "$KIT_DIR/global" ]; then
  note "⚠️ 구 global/ 디렉터리가 남아 있다 — v2 는 adapters/ 를 쓴다" >&2
fi

for h in $HARNESSES; do
  case "$h" in
    claude)
      mkdir -p "$HOME/.claude/skills"
      for d in "$KIT_DIR"/adapters/claude/global/skills/*/; do
        [ -d "$d" ] || continue
        name=$(basename "$d")
        rm -rf "$HOME/.claude/skills/$name"
        cp -R "$d" "$HOME/.claude/skills/$name"
        note "스킬: ~/.claude/skills/$name"
      done
      ;;
    codex)
      mkdir -p "$HOME/.codex/prompts"
      for f in "$KIT_DIR"/adapters/codex/global/prompts/*.md; do
        [ -f "$f" ] || continue
        backup_and_copy "$f" "$HOME/.codex/prompts/$(basename "$f")"
      done
      note "codex config.toml 권장 설정은 자동 병합하지 않는다 — 남은 수동 단계 안내 참조"
      ;;
  esac
done

# 온보딩 절차 본문은 하네스 무관 — 두 어댑터의 래퍼가 모두 이 경로를 읽는다.
backup_and_copy "$KIT_DIR/core/onboard/ONBOARD-PROCEDURE.md" \
                "$HOME/.config/orchestrate/ONBOARD-PROCEDURE.md"
backup_and_copy "$KIT_DIR/core/opencode/opencode.json" "$HOME/.config/opencode/opencode.json"
backup_and_copy "$KIT_DIR/core/opencode/model-doctor.sh" "$HOME/.config/opencode/model-doctor.sh"
backup_and_copy "$KIT_DIR/core/opencode/provider-models.json" "$HOME/.config/opencode/provider-models.json"
chmod +x "$HOME/.config/opencode/model-doctor.sh"

if [ ! -f "$HOME/.config/opencode/secrets.env" ]; then
  cp "$KIT_DIR/core/opencode/secrets.env.example" "$HOME/.config/opencode/secrets.env"
  chmod 600 "$HOME/.config/opencode/secrets.env"
  note "생성: ~/.config/opencode/secrets.env (키 입력 필요)"
else
  note "유지: ~/.config/opencode/secrets.env (덮어쓰지 않음)"
fi

# 스킬 팩(플러그인·룰 팩) 업데이트 감지기 — 알림만 하고 자동 적용하지 않는다.
mkdir -p "$HOME/.local/bin" "$HOME/.config/skillpack-update"
backup_and_copy "$KIT_DIR/core/scripts/skillpack-update-check.sh" \
                "$HOME/.local/bin/skillpack-update-check.sh"
chmod +x "$HOME/.local/bin/skillpack-update-check.sh"
if [ ! -f "$HOME/.config/skillpack-update/packs.conf" ]; then
  cp "$KIT_DIR/core/skillpack/packs.conf.example" "$HOME/.config/skillpack-update/packs.conf"
  chmod 600 "$HOME/.config/skillpack-update/packs.conf"
  note "생성: ~/.config/skillpack-update/packs.conf (점검 대상 편집 가능)"
else
  note "유지: ~/.config/skillpack-update/packs.conf (덮어쓰지 않음)"
fi
if command -v crontab >/dev/null 2>&1 && \
   ! crontab -l 2>/dev/null | grep -q 'skillpack-update-check.sh'; then
  note "크론 미등록 — 일일 점검을 원하면: (crontab -l; echo '40 5 * * * \$HOME/.local/bin/skillpack-update-check.sh >/dev/null 2>&1') | crontab -"
fi

say "6/7 모델 프로바이더"
if [ -z "$PROVIDERS" ]; then
  if ! is_interactive_menu; then
    echo "   비대화형 실행 — --providers= 로 명시하거나 나중에 gen-policy.sh 를 직접 실행할 것" >&2
  fi
fi
if [ -n "$PROVIDERS" ]; then
  POLICY="$HOME/.config/opencode/model-policy.json"
  if [ -f "$POLICY" ]; then
    cp "$POLICY" "$POLICY.bak-$STAMP" || {
      echo "백업 실패 — 정책 덮어쓰기를 중단한다" >&2
      exit 73
    }
    note "백업: $POLICY.bak-$STAMP"
  fi
  bash "$KIT_DIR/core/opencode/gen-policy.sh" "$PROVIDERS" "$POLICY" || {
    note "⚠️ 체인 생성 실패 — core/opencode/gen-policy.sh 를 직접 실행해 원인을 확인할 것" >&2
  }
else
  note "프로바이더 미선택 — model-policy.json 을 건드리지 않는다"
fi

run_auth_logins

if [ -n "$CONTAINERS" ]; then
  say "컨테이너 설치"
  old_ifs="$IFS"
  IFS=','
  set -f
  for c in $CONTAINERS; do
    if ! build_container_up_argv "$c"; then
      note "⚠️ 알 수 없는 컨테이너: $c" >&2
      continue
    fi
    case "$c" in
      browser)
        _container_dir=containers/browser
        _container_port=$CDP_PORT
        ;;
      dashboard)
        _container_dir=components/usage-dashboard
        _container_port=$DASH_PORT
        ;;
    esac
    if [ ! -f "$KIT_DIR/$_container_dir/docker-compose.yml" ]; then
      if ! git -C "$KIT_DIR" submodule update --init "$_container_dir"; then
        note "$c: 서브모듈 초기화 실패 — 수동으로 확인할 것" >&2
        note "$c: $(container_up_command "$c") 를 직접 실행할 것"
        continue
      fi
      if [ ! -f "$KIT_DIR/$_container_dir/docker-compose.yml" ]; then
        case " $CONTAINER_START_FAILED " in
          *" $c "*) ;;
          *) CONTAINER_START_FAILED="${CONTAINER_START_FAILED:+$CONTAINER_START_FAILED }$c" ;;
        esac
        mark_manual_step container
        note "$c: 서브모듈은 초기화됐지만 compose 파일이 없다 — 수동으로 확인할 것" >&2
        note "$c: $(container_up_command "$c") 를 직접 실행할 것"
        continue
      fi
    fi
    if ! command -v docker >/dev/null 2>&1; then
      note "$c: docker를 찾지 못해 자동 기동을 건너뜀" >&2
      note "$c: $(container_up_command "$c") 를 직접 실행할 것"
      continue
    fi
    if ! docker compose version >/dev/null 2>&1; then
      note "$c: compose를 사용할 수 없어 자동 기동을 건너뜀" >&2
      note "$c: $(container_up_command "$c") 를 직접 실행할 것"
      continue
    fi
    if ( : >/dev/tcp/127.0.0.1/"$_container_port" ) >/dev/null 2>&1; then
      note "$c: $_container_port 포트가 사용 중이라 자동 기동을 건너뜀" >&2
      note "$c: $(container_up_command "$c") 를 직접 실행할 것"
      continue
    fi
    if ! prompt_yes_no "$c 를 지금 기동할까요? 이미지 빌드에 수 분이 걸릴 수 있다." no; then
      note "$c: 동의를 받지 못해 자동 기동을 건너뜀" >&2
      note "$c: $(container_up_command "$c") 를 직접 실행할 것"
      continue
    fi
    if ! "${CONTAINER_UP_ARGV[@]}"; then
      case " $CONTAINER_START_FAILED " in
        *" $c "*) ;;
        *) CONTAINER_START_FAILED="${CONTAINER_START_FAILED:+$CONTAINER_START_FAILED }$c" ;;
      esac
      mark_manual_step container
      note "$c: 자동 기동 실패 — 수동으로 확인할 것" >&2
      note "$c: $(container_up_command "$c") 를 직접 실행할 것"
    fi
  done
  set +f
  IFS="$old_ifs"
fi

run_mcp_registration

case " $HARNESSES " in
  *" claude "*)
    say "Claude 요금제 프로파일"
    [ "$PLAN" = "skip" ] && PLAN=""
    if [ -n "$PLAN" ]; then
      bash "$KIT_DIR/adapters/claude/global/apply-plan-profile.sh" "$PLAN" \
        || note "⚠️ 프로파일 적용 실패 (위 stderr 참조)"
    else
      report_plan_skip
    fi
    ;;
esac

say "7/7 검증"
if [ -f "$HOME/.config/opencode/model-policy.json" ]; then
  # 설치 직후 인증 미완은 정상이라 model-doctor 실패를 종료 코드에 전파하지 않는다.
  bash "$HOME/.config/opencode/model-doctor.sh" --skip-smoke || \
    note "⚠️ 체인 검증 실패 — 인증을 완료한 뒤 ~/.config/opencode/model-doctor.sh 를 다시 실행할 것" >&2
fi

say "남은 수동 단계"
cat <<'EOF'
   1) 키 기반 프로바이더: ~/.config/opencode/secrets.env 에 값 입력 (chmod 600)
   2) 구독 기반 프로바이더 로그인 (대화형 — 스크립트가 대신할 수 없다):
EOF
printf '      xai:    %s\n' "$(auth_login_command xai)"
printf '      openai: %s\n' "$(auth_login_command openai)"
cat <<'EOF'
              → auth.openai.com/codex/device 에 출력된 코드 입력 (원격·헤드리스 서버용)
    3) 인증 후 재검증: ~/.config/opencode/model-doctor.sh
   3-1) ECC 를 갱신했다면 요금제 프로파일을 재적용한다 (ECC 가 에이전트 파일을 덮는다):
        bash adapters/claude/global/apply-plan-profile.sh <pro|max5|max20>
    4) codex 사용자: ~/.codex/config.toml 권장 설정을 adapters/codex/project/.codex/config.toml
      에서 확인해 수동 병합 (자동 병합하지 않는다)
   5) 프로젝트 온보딩:
      신규: ./new-project.sh <경로> [이름]
      기존: ./adopt-project.sh <경로>
      → 이후 하네스에서 /orchestrate-onboard 실행
EOF
if [ "$CLAUDE_INSTALL_FAILED" = "1" ]; then
  cat <<'EOF'
    6) Claude CLI 수동 설치: npm i -g @anthropic-ai/claude-code
       npm이 없다면 Node.js/npm을 먼저 설치: https://nodejs.org/
EOF
fi
if [ "${NODE_PATH_ADDED:-0}" = "1" ]; then
  cat <<EOF
    7) 유저공간 Node 경로를 셸 rc 파일에 영구 등록:
       export PATH="$HOME/.local/opt/node/bin:\$PATH"
EOF
fi
if [ -n "$MANUAL_STEP_REASONS" ]; then
  _manual_step_number=6
  if [ "${NODE_PATH_ADDED:-0}" = "1" ]; then
    _manual_step_number=8
  elif [ "$CLAUDE_INSTALL_FAILED" = "1" ]; then
    _manual_step_number=7
  fi
  case " $MANUAL_STEP_REASONS " in
    *" auth "*)
      _manual_auth_old_ifs=$IFS
      IFS=' '
      set -f
      for _manual_auth_provider in $AUTH_LOGIN_FAILED; do
        printf '    %s) %s 로그인 재시도: %s\n' "$_manual_step_number" "$_manual_auth_provider" "$(auth_login_command "$_manual_auth_provider")"
        _manual_step_number=$((_manual_step_number + 1))
      done
      set +f
      IFS=$_manual_auth_old_ifs
      ;;
  esac
  case " $MANUAL_STEP_REASONS " in
    *" mcp "*)
      printf '    %s) chrome-devtools MCP 등록 재시도: %s\n' "$_manual_step_number" "$(mcp_add_command chrome-devtools)"
      _manual_step_number=$((_manual_step_number + 1))
      ;;
  esac
  case " $MANUAL_STEP_REASONS " in
    *" container "*)
      _manual_container_old_ifs=$IFS
      IFS=' '
      set -f
      for _manual_container_name in $CONTAINER_START_FAILED; do
        printf '    %s) %s 컨테이너 기동 재시도: %s\n' "$_manual_step_number" "$_manual_container_name" "$(container_up_command "$_manual_container_name")"
        _manual_step_number=$((_manual_step_number + 1))
      done
      set +f
      IFS=$_manual_container_old_ifs
      ;;
  esac
fi
echo
if [ "$CLAUDE_INSTALL_FAILED" = "1" ] || [ -n "$MANUAL_STEP_REASONS" ]; then
  echo "설치 완료 (일부 항목 수동 조치 필요)."
else
  echo "설치 완료."
fi
