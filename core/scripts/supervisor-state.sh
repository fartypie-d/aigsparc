#!/usr/bin/env bash
# 감독 상태 파일의 충돌 감지 갱신과 owner 리스 판정을 제공한다.
# macOS 기본 bash 3.2 호환을 위해 연관배열과 mapfile을 사용하지 않는다.
set -u

STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/orchestrate"

usage() {
  echo "사용법: supervisor-state.sh {get|set|patch|owner-check|owner-take} <project> ..." >&2
}

valid_project() {
  case "$1" in
    ''|*[!A-Za-z0-9._-]*) return 1 ;;
    *) return 0 ;;
  esac
}

state_file_for() {
  printf '%s/supervisor/%s.json' "$STATE_ROOT" "$1"
}

state_directory_is_contained() {
  # 단독 설치되는 스크립트라 런타임에 없는 lib/stamp.sh를 source하지 않고 자체 검사한다.
  python3 - "$STATE_FILE" "$STATE_ROOT" <<'PY'
import os
import sys

actual = os.path.realpath(os.path.dirname(sys.argv[1]))
expected = os.path.join(os.path.realpath(sys.argv[2]), 'supervisor')
if actual != expected:
    sys.stderr.write('상태 디렉터리가 봉쇄 경로 밖을 가리킨다: %s (기대: %s)\n' %
                     (actual, expected))
    sys.exit(1)
PY
}

require_state() {
  STATE_FILE=$(state_file_for "$1")
  state_directory_is_contained || return $?
  if [ -L "$STATE_FILE" ]; then
    echo "상태 파일이 심링크라 거부했다: $STATE_FILE" >&2
    return 1
  fi
  if [ ! -f "$STATE_FILE" ]; then
    echo "상태 파일이 없다: $STATE_FILE" >&2
    return 2
  fi
  return 0
}

state_hash() {
  python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
}

validate_object() {
  python3 - "$1" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], 'rb') as source:
        value = json.load(source)
except (OSError, ValueError) as error:
    sys.stderr.write("유효한 JSON을 읽을 수 없다: %s\n" % error)
    sys.exit(1)
if not isinstance(value, dict):
    sys.stderr.write("상태 JSON은 객체여야 한다\n")
    sys.exit(1)
PY
}

make_temp() {
  _temp_command="$1"
  _temp_dir="$2"
  mktemp "$_temp_dir/.supervisor-state.XXXXXX" || {
    echo "상태 임시 파일을 만들 수 없다 (${_temp_command}): $_temp_dir" >&2
    return 1
  }
}

set_state() { # <project> <json-file> <baseline> <subcommand>
  _set_project="$1"
  _set_source="$2"
  _set_baseline="$3"
  _set_command="$4"
  require_state "$_set_project" || return $?
  _set_file="$STATE_FILE"
  _set_dir=$(dirname -- "$_set_file")
  _set_current=$(state_hash "$_set_file") || return 1
  if [ "$_set_baseline" != "$_set_current" ]; then
    echo "충돌: 현재 상태 해시는 $_set_current 이다" >&2
    return 3
  fi
  validate_object "$_set_source" || return 1
  _set_temp=$(make_temp "$_set_command" "$_set_dir") || return 1
  if ! cat "$_set_source" > "$_set_temp"; then
    rm -f "$_set_temp"
    echo "상태 임시 파일을 쓸 수 없다 (${_set_command}): $_set_dir" >&2
    return 1
  fi
  # 검증과 복사 사이의 변경도 교체 직전에 다시 확인한다.
  _set_current=$(state_hash "$_set_file") || {
    rm -f "$_set_temp"
    return 1
  }
  if [ "$_set_baseline" != "$_set_current" ]; then
    rm -f "$_set_temp"
    echo "충돌: 현재 상태 해시는 $_set_current 이다" >&2
    return 3
  fi
  if [ -L "$_set_file" ]; then
    rm -f "$_set_temp"
    echo "상태 파일이 심링크라 거부했다: $_set_file" >&2
    return 1
  fi
  if ! mv "$_set_temp" "$_set_file"; then
    rm -f "$_set_temp"
    echo "상태 파일을 원자적으로 교체할 수 없다" >&2
    return 1
  fi
  return 0
}

command_get() {
  require_state "$1" || return $?
  cat "$STATE_FILE"
}

command_set() {
  _command_project="$1"
  _command_source="$2"
  shift 2
  if [ "$#" -ne 2 ] || [ "$1" != "--baseline" ] || [ -z "$2" ]; then
    echo "set에는 --baseline <sha256>가 필요하다" >&2
    return 1
  fi
  _command_baseline="$2"
  if [ "$_command_source" = "-" ]; then
    require_state "$_command_project" || return $?
    _command_dir=$(dirname -- "$STATE_FILE")
    _command_temp=$(make_temp "set" "$_command_dir") || return 1
    if ! cat > "$_command_temp"; then
      rm -f "$_command_temp"
      echo "상태 임시 파일을 쓸 수 없다 (set): $_command_dir" >&2
      return 1
    fi
    set_state "$_command_project" "$_command_temp" "$_command_baseline" "set"
    _command_result=$?
    rm -f "$_command_temp"
    return "$_command_result"
  fi
  if [ ! -f "$_command_source" ]; then
    echo "입력 JSON 파일이 없다: $_command_source" >&2
    return 1
  fi
  set_state "$_command_project" "$_command_source" "$_command_baseline" "set"
}

command_patch() {
  _patch_project="$1"
  shift
  require_state "$_patch_project" || return $?
  _patch_file="$STATE_FILE"
  _patch_baseline=$(state_hash "$_patch_file") || return 1
  _patch_dir=$(dirname -- "$_patch_file")
  _patch_temp=$(make_temp "patch" "$_patch_dir") || return 1
  if ! python3 - "$_patch_file" "$@" > "$_patch_temp" <<'PY'
import json
import sys

with open(sys.argv[1], 'r') as source:
    state = json.load(source)
if not isinstance(state, dict):
    raise ValueError('상태 JSON은 객체여야 한다')
for assignment in sys.argv[2:]:
    if '=' not in assignment:
        raise ValueError('patch 값은 key=value 형식이어야 한다: %s' % assignment)
    key, value = assignment.split('=', 1)
    if not key:
        raise ValueError('patch 키가 비어 있다')
    state[key] = value
json.dump(state, sys.stdout, ensure_ascii=False, separators=(',', ':'))
PY
  then
    rm -f "$_patch_temp"
    echo "상태 patch를 만들 수 없다" >&2
    return 1
  fi
  set_state "$_patch_project" "$_patch_temp" "$_patch_baseline" "patch"
  _patch_result=$?
  rm -f "$_patch_temp"
  return "$_patch_result"
}

owner_fields() { # <state-file>: pid, start_id를 탭으로 출력한다.
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], 'r') as source:
    state = json.load(source)
owner = state.get('owner') if isinstance(state, dict) else None
if not isinstance(owner, dict):
    print('\t')
else:
    pid = owner.get('pid')
    start_id = owner.get('start_id')
    print('%s\t%s' % ('' if pid is None else pid, '' if start_id is None else start_id))
PY
}

session_start_id() { # ⓐ 하네스 세션 파일은 읽기 전용이다.
  _session_file="$HOME/.claude/sessions/$1.json"
  [ -f "$_session_file" ] || return 1
  python3 - "$_session_file" <<'PY'
import json
import sys
try:
    with open(sys.argv[1], 'r') as source:
        value = json.load(source).get('procStart')
except (OSError, ValueError, AttributeError):
    sys.exit(1)
if value is None:
    sys.exit(1)
print(value)
PY
}

proc_start_id() { # ⓑ Linux /proc stat의 마지막 ')' 뒤 22번째 필드.
  [ -r "/proc/$1/stat" ] || return 1
  python3 - "/proc/$1/stat" <<'PY'
import sys
try:
    raw = open(sys.argv[1], 'r').read()
    fields = raw.rsplit(')', 1)[1].split()
    print(fields[19])
except (OSError, IndexError):
    sys.exit(1)
PY
}

owner_check() {
  require_state "$1" || return $?
  _owner_line=$(owner_fields "$STATE_FILE") || { echo "reclaimable owner를 읽을 수 없다"; return 1; }
  IFS=$'\t' read -r _owner_pid _owner_start <<EOF
$_owner_line
EOF
  if [ -z "$_owner_pid" ]; then
    echo "reclaimable owner가 없다"
    return 1
  fi
  case "$_owner_pid" in
    ''|*[!0-9]*)
      echo "reclaimable owner.pid 가 유효한 PID 가 아니다: $_owner_pid"
      return 1
      ;;
  esac
  if [ "$_owner_pid" -eq 0 ]; then
    echo "reclaimable owner.pid 가 유효한 PID 가 아니다: $_owner_pid"
    return 1
  fi
  if ! kill -0 "$_owner_pid" 2>/dev/null; then
    echo "reclaimable PID가 살아 있지 않다"
    return 1
  fi
  _current_start=$(session_start_id "$_owner_pid" 2>/dev/null)
  if [ -z "$_current_start" ]; then
    _current_start=$(proc_start_id "$_owner_pid" 2>/dev/null)
  fi
  if [ -n "$_current_start" ] && [ -n "$_owner_start" ]; then
    if [ "$_current_start" = "$_owner_start" ]; then
      echo "alive start_id 일치"
      return 0
    fi
    echo "reclaimable start_id 불일치"
    return 1
  fi
  # ⓒ 식별자를 얻지 못하면 mtime은 정보로만 보고하며 소유권을 추정하지 않는다.
  _mtime_age=$(python3 - "$STATE_FILE" <<'PY'
import os
import sys
import time
try:
    print(int(time.time() - os.path.getmtime(sys.argv[1])))
except OSError:
    sys.exit(1)
PY
) || { echo "unverified start_id를 얻을 수 없고 mtime도 읽을 수 없다"; return 4; }
  echo "unverified start_id를 얻을 수 없어 mtime으로만 추정했다 (${_mtime_age}초 전)"
  return 4
}

command_owner_take() {
  _take_project="$1"
  shift
  if [ "$#" -ne 4 ] || [ "$1" != "--pid" ] || [ "$3" != "--start-id" ] || [ -z "$2" ] || [ -z "$4" ]; then
    echo "owner-take에는 --pid <PID> --start-id <ID>가 필요하다" >&2
    return 1
  fi
  _take_pid="$2"; _take_start="$4"
  require_state "$_take_project" || return $?
  _take_file="$STATE_FILE"
  _take_baseline=$(state_hash "$_take_file") || return 1
  owner_check "$_take_project" >/dev/null
  _take_check=$?
  case "$_take_check" in
    0)
      echo "살아 있는 owner 리스는 회수할 수 없다" >&2
      return 1
      ;;
    4)
      echo "검증 불가(mtime 추정)라 회수하지 않았다" >&2
      return 1
      ;;
    2) return 2 ;;
  esac
  _take_dir=$(dirname -- "$_take_file")
  _take_temp=$(make_temp "owner-take" "$_take_dir") || return 1
  if ! python3 - "$_take_file" "$_take_pid" "$_take_start" > "$_take_temp" <<'PY'
import json
import sys

with open(sys.argv[1], 'r') as source:
    state = json.load(source)
if not isinstance(state, dict):
    raise ValueError('상태 JSON은 객체여야 한다')
state['owner'] = {'pid': sys.argv[2], 'start_id': sys.argv[3]}
json.dump(state, sys.stdout, ensure_ascii=False, separators=(',', ':'))
PY
  then
    rm -f "$_take_temp"
    echo "새 owner 상태를 만들 수 없다" >&2
    return 1
  fi
  set_state "$_take_project" "$_take_temp" "$_take_baseline" "owner-take"
  _take_result=$?
  rm -f "$_take_temp"
  return "$_take_result"
}

[ "$#" -ge 2 ] || { usage; exit 1; }
COMMAND="$1"; PROJECT="$2"; shift 2
if ! valid_project "$PROJECT"; then
  echo "프로젝트명은 영문자·숫자·.·_·- 만 사용할 수 있다" >&2
  exit 1
fi
case "$COMMAND" in
  get) [ "$#" -eq 0 ] || { usage; exit 1; }; command_get "$PROJECT" ;;
  set) [ "$#" -ge 1 ] || { usage; exit 1; }; command_set "$PROJECT" "$@" ;;
  patch) [ "$#" -ge 1 ] || { usage; exit 1; }; command_patch "$PROJECT" "$@" ;;
  owner-check) [ "$#" -eq 0 ] || { usage; exit 1; }; owner_check "$PROJECT" ;;
  owner-take) command_owner_take "$PROJECT" "$@" ;;
  *) usage; exit 1 ;;
esac
