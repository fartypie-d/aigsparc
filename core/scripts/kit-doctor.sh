#!/usr/bin/env bash
# 키트 전역 설치 자산과 필수 도구를 읽기 전용으로 점검한다.
# macOS 기본 bash 3.2 호환: mapfile·연관배열을 사용하지 않는다.
set -uo pipefail

# 규약: $0 심링크를 bash 3.2 호환 루프로 푼 뒤 cap|readlink|cd|missing 사유로 비정상 종료한다.
# 부모가 core 이고 그 부모에 킷 마커(core/install-manifest.tsv) 가 있으면
# 한 단계 더 올라간다. 아니면 부모가 곧 프로젝트 루트다(설치된 프로젝트 배치).
# KIT_DOCTOR_SELFTEST_RESOLVE=<경로> 를 주면 본체와 동일한 해석 코드로 해석 후 즉시 종료.

# 심링크 해석 함수 — 본체와 자가검증이 공유하는 단일 소스.
# 성공 시 _KIT_RESOLVED 에 실경로 전체(파일) 를 쓰고 return 0.
# 실패 시 _KIT_RESOLVE_FAIL 에 사유(cap|readlink|cd|missing) 를 쓰고 return 1.
_kit_resolve_to_real_path() {
    _KIT_RESOLVED=""
    _KIT_RESOLVE_FAIL=""
    _kr_path="$1"
    if [ ! -e "$_kr_path" ] && [ ! -L "$_kr_path" ]; then
        _KIT_RESOLVE_FAIL="missing"
        return 1
    fi
    _kr_iter=0
    while [ -L "$_kr_path" ] && [ "$_kr_iter" -lt 40 ]; do
        _kr_link_dir=$(CDPATH= cd -- "$(dirname -- "$_kr_path")" 2>/dev/null && pwd)
        if [ -z "$_kr_link_dir" ]; then
            _KIT_RESOLVE_FAIL="cd"
            return 1
        fi
        _kr_target=$(readlink "$_kr_path")
        if [ -z "$_kr_target" ]; then
            _KIT_RESOLVE_FAIL="readlink"
            return 1
        fi
        case "$_kr_target" in
            /*) _kr_path="$_kr_target" ;;
            *)  _kr_path="$_kr_link_dir/$_kr_target" ;;
        esac
        # 후행 슬래시 제거 — POSIX 에서 [ -L "경로/" ] 는 심링크여도 항상 거짓이다.
        # 제거하지 않으면 루프가 해석 완료를 오판하고 조용히 틀린 결과를 낸다.
        while :; do
            case "$_kr_path" in ?*/) _kr_path="${_kr_path%/}" ;; *) break ;; esac
        done
        _kr_iter=$((_kr_iter + 1))
    done
    if [ -L "$_kr_path" ]; then
        _KIT_RESOLVE_FAIL="cap"
        return 1
    fi
    if [ ! -e "$_kr_path" ]; then
        _KIT_RESOLVE_FAIL="missing"
        return 1
    fi
    _KIT_RESOLVED="$_kr_path"
    return 0
}

# 자가검증 훅: KIT_DOCTOR_SELFTEST_RESOLVE=<경로> 가 있으면 본체 진입 전 결과만 출력 후 종료.
if [ -n "${KIT_DOCTOR_SELFTEST_RESOLVE:-}" ]; then
    if _kit_resolve_to_real_path "$KIT_DOCTOR_SELFTEST_RESOLVE"; then
        _selftest_dir=$(CDPATH= cd -- "$(dirname -- "$_KIT_RESOLVED")" 2>/dev/null && pwd)
        if [ -z "$_selftest_dir" ]; then
            echo "RESOLVE_FAIL cd"
            exit 1
        fi
        echo "RESOLVE_OK $_selftest_dir"
        exit 0
    else
        echo "RESOLVE_FAIL ${_KIT_RESOLVE_FAIL:-unknown}"
        exit 1
    fi
fi

# $0 심링크 해석 (본체)
if ! _kit_resolve_to_real_path "$0"; then
    echo "진입점 해석 실패 ($_KIT_RESOLVE_FAIL)" >&2
    exit 1
fi
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$_KIT_RESOLVED")" 2>/dev/null && pwd)
if [ -z "$SCRIPT_DIR" ]; then
    echo "진입점 해석 실패 (cd)" >&2
    exit 1
fi

# 프로젝트 루트 판정: 부모가 'core' 이고 킷 마커 있으면 한 단계 더 올라감
_root_parent=$(CDPATH= cd -- "$SCRIPT_DIR/.." 2>/dev/null && pwd)
if [ -z "$_root_parent" ]; then
    echo "루트 판정 실패 (cd parent)" >&2
    exit 1
fi
_root_parent_name=$(basename -- "$_root_parent")
KIT_DIR="$_root_parent"
if [ "$_root_parent_name" = "core" ]; then
    _root_gp=$(CDPATH= cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd)
    if [ -z "$_root_gp" ]; then
        echo "루트 판정 실패 (cd grandparent)" >&2
        exit 1
    fi
    if [ -f "$_root_gp/core/install-manifest.tsv" ]; then
        KIT_DIR="$_root_gp"
    fi
fi

HOME_DIR="$HOME"
MANIFEST="$KIT_DIR/core/install-manifest.tsv"
SELECTED_HARNESSES=""
HARNESS_DETECTION_FAILED=0
OK_COUNT=0
WARN_COUNT=0
DRIFT_COUNT=0
FAIL_COUNT=0
ADDED_COUNT=0
ADD_MISSING=0

usage() {
  echo "사용법: $0 [--home <경로>] [--kit <경로>] [--manifest <경로>] [--claude] [--codex] [--add-missing]" >&2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --home)
      [ $# -ge 2 ] || { usage; exit 64; }
      HOME_DIR="$2"
      shift 2
      ;;
    --kit)
      [ $# -ge 2 ] || { usage; exit 64; }
      KIT_DIR="$2"
      shift 2
      ;;
    --manifest)
      [ $# -ge 2 ] || { usage; exit 64; }
      MANIFEST="$2"
      shift 2
      ;;
    --claude)
      SELECTED_HARNESSES="${SELECTED_HARNESSES:+$SELECTED_HARNESSES }claude"
      shift
      ;;
    --codex)
      SELECTED_HARNESSES="${SELECTED_HARNESSES:+$SELECTED_HARNESSES }codex"
      shift
      ;;
    --add-missing)
      ADD_MISSING=1
      shift
      ;;
    *)
      echo "알 수 없는 옵션: $1" >&2
      exit 64
      ;;
  esac
done

if [ ! -r "$KIT_DIR/lib/stamp.sh" ]; then
  echo "공통 봉쇄 함수를 읽을 수 없다: $KIT_DIR/lib/stamp.sh" >&2
  exit 1
fi
. "$KIT_DIR/lib/stamp.sh"

report_ok() {
  echo "OK   $1: $2"
  OK_COUNT=$((OK_COUNT + 1))
}

report_warn() {
  echo "WARN $1: $2 — $3"
  WARN_COUNT=$((WARN_COUNT + 1))
}

report_fail() {
  echo "FAIL $1: $2 — $3"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

report_drift() {
  echo "DRIFT $1: $2 — 킷 원본과 다르다 (갱신: ./install.sh 재실행)"
  DRIFT_COUNT=$((DRIFT_COUNT + 1))
}

report_added() {
  echo "ADDED $1: $2"
  ADDED_COUNT=$((ADDED_COUNT + 1))
}

check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    report_ok "도구" "$1"
  else
    report_fail "도구" "$1" "필수 도구가 없다"
  fi
}

for tool in git curl python3 jq; do
  check_command "$tool"
done

for tool in docker claude; do
  if command -v "$tool" >/dev/null 2>&1; then
    report_ok "도구" "$tool"
  else
    report_warn "도구" "$tool" "선택 도구가 없다"
  fi
done

OPENCODE_BIN="$HOME_DIR/.opencode/bin/opencode"
if [ -x "$OPENCODE_BIN" ]; then
  report_ok "도구" "$OPENCODE_BIN"
else
  report_warn "도구" "$OPENCODE_BIN" "선택 CLI 가 없거나 실행할 수 없다"
fi

if [ -z "$SELECTED_HARNESSES" ]; then
  # 공통 감지 함수를 그대로 사용하되, 감지 실패는 진단 전체를 중단하지 않는다.
  SELECTED_HARNESSES=$(stamp_detect_harness 2>/dev/null) || SELECTED_HARNESSES=""
  if [ -z "$SELECTED_HARNESSES" ]; then
    HARNESS_DETECTION_FAILED=1
    report_warn "하네스" "자동 감지" "감지하지 못해 any 항목만 점검한다"
  else
    report_ok "하네스" "$SELECTED_HARNESSES"
  fi
fi

harness_selected() {
  [ "$1" = "any" ] && return 0
  for selected in $SELECTED_HARNESSES; do
    [ "$selected" = "$1" ] && return 0
  done
  return 1
}

path_is_contained() {
  case "$1" in
    /*) return 1 ;;
  esac
  case "/$1/" in
    */../*) return 1 ;;
  esac
  return 0
}

parent_is_within_root() {
  root_path="$1"
  target_path="$2"
  parent_path=$(dirname -- "$target_path")

  [ -d "$parent_path" ] || return 0
  root_physical=$(CDPATH= cd -P -- "$root_path" 2>/dev/null && pwd) || return 1
  parent_physical=$(CDPATH= cd -P -- "$parent_path" 2>/dev/null && pwd) || return 1
  case "$parent_physical/" in
    "$root_physical/"*) return 0 ;;
    *) return 1 ;;
  esac
}

# stamp_copy 는 프로젝트 스캐폴드 전용이므로, 전역 HOME 자산도 같은 무덮어쓰기 정책을 여기서 적용한다.
# 쓰기 전에는 아직 없는 부모를 위로 거슬러 올라가 실제 생성될 물리 경로도 HOME 안인지 확인한다.
add_missing_file() {
  local source_path="$1"
  local destination_path="$2"
  local destination_label="$3"
  local is_seed="$4"
  local destination_parent staging_path copy_status substitution destination_root
  substitution="${5:-}"
  destination_root="${6:-$HOME_DIR}"

  # cp 는 기존 대상을 덮을 수 있으므로, 복사 직전에 반드시 존재 여부를 확인한다.
  [ -e "$destination_path" ] && return 0
  if [ -L "$destination_path" ]; then
    report_warn "자산" "$destination_label" "심링크다"
    return 1
  fi
  if ! write_parent_is_within_root "$destination_root" "$destination_path"; then
    report_fail "매니페스트" "$destination_label" "경로가 봉쇄 범위를 벗어난다"
    return 1
  fi
  destination_parent=$(dirname -- "$destination_path")
  if ! mkdir -p "$destination_parent" 2>/dev/null; then
    report_fail "자산" "$destination_label" "상위 디렉터리를 만들 수 없다"
    return 1
  fi
  if ! write_parent_is_within_root "$destination_root" "$destination_path"; then
    report_fail "매니페스트" "$destination_label" "경로가 봉쇄 범위를 벗어난다"
    return 1
  fi
  [ -e "$destination_path" ] && return 0
  staging_path="${destination_path}.kit-partial.$$"
  if ! write_parent_is_within_root "$destination_root" "$staging_path"; then
    report_fail "매니페스트" "$staging_path" "스테이징 경로가 봉쇄 범위를 벗어난다"
    return 1
  fi
  # cp 직전에도 목적지 심링크를 다시 확인해, 기존 파일을 링크 타깃에 쓰지 않는다.
  if [ -L "$destination_path" ]; then
    report_warn "자산" "$destination_label" "심링크다"
    return 1
  fi
  if [ -L "$staging_path" ]; then
    report_warn "자산" "$staging_path" "심링크다"
    return 1
  fi
  if [ -d "$source_path" ]; then
    cp -R "$source_path" "$staging_path" 2>/dev/null
    copy_status=$?
  else
    cp "$source_path" "$staging_path" 2>/dev/null
    copy_status=$?
  fi
  if [ "$copy_status" -ne 0 ]; then
    if [ -e "$staging_path" ] || [ -L "$staging_path" ]; then
      report_fail "자산" "$staging_path" "스테이징 잔재가 남아 있다"
    fi
    report_fail "자산" "$destination_label" "파일을 복사할 수 없다"
    return 1
  fi
  if [ -n "$substitution" ] && ! STAMP_SUPERVISOR_NAME="$substitution" perl -pi -e 's/__PROJECT__/$ENV{STAMP_SUPERVISOR_NAME}/g' "$staging_path"; then
    report_fail "자산" "$destination_label" "플레이스홀더를 치환할 수 없다"
    report_fail "자산" "$staging_path" "스테이징 잔재가 남아 있다"
    return 1
  fi
  if [ "$is_seed" = "1" ] && ! chmod 600 "$staging_path" 2>/dev/null; then
    report_fail "자산" "$destination_label" "seed 파일 권한을 600으로 설정할 수 없다"
    report_fail "자산" "$staging_path" "스테이징 잔재가 남아 있다"
    return 1
  fi
  if [ -e "$destination_path" ] || [ -L "$destination_path" ]; then
    report_warn "자산" "$destination_label" "복사 중 생성되어 덮어쓰지 않았다"
    report_fail "자산" "$staging_path" "스테이징 잔재가 남아 있다"
    return 1
  fi
  if ! mv "$staging_path" "$destination_path" 2>/dev/null; then
    report_fail "자산" "$staging_path" "스테이징 파일을 배치할 수 없다"
    report_fail "자산" "$staging_path" "스테이징 잔재가 남아 있다"
    return 1
  fi
  report_added "자산" "$destination_label"
  return 0
}

# 이전 실행의 스테이징 잔재는 읽기 전용 진단에서도 항상 알린다.
check_staging_leftovers() {
  local destination_path="$1"
  local partial_path

  for partial_path in "${destination_path}.kit-partial"*; do
    [ -e "$partial_path" ] || [ -L "$partial_path" ] || continue
    report_warn "자산" "$partial_path" "이전 복사 시도가 남긴 잔재다 (직접 삭제해도 안전하다)"
  done
}

check_seed_permissions() {
  local destination_path="$1"
  local destination_label="$2"
  local permission_mode permission_tail bsd_permission

  bsd_permission=$(stat -f '%Lp' "$destination_path" 2>/dev/null)
  case "$bsd_permission" in
    [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) permission_mode="$bsd_permission" ;;
    *)
      permission_mode=$(stat -c '%a' "$destination_path" 2>/dev/null) || {
        report_warn "자산" "$destination_label" "권한 비트를 확인할 수 없다"
        return 1
      }
      ;;
  esac
  permission_mode=${permission_mode#0}
  case "$permission_mode" in
    ???) ;;
    *)
      report_warn "자산" "$destination_label" "권한 비트를 해석할 수 없다 ($permission_mode)"
      return 1
      ;;
  esac
  permission_tail=${permission_mode#?}
  case "$permission_tail" in
    *[2467]*)
      report_warn "자산" "$destination_label" "권한이 600 보다 넓다 (0$permission_mode)"
      return 1
      ;;
  esac
  return 0
}

# 세 자산 mode가 공통으로 매니페스트 경로와 목적지 심링크를 검사한다.
prepare_asset_paths() {
  source_relative="$1"
  destination_relative="$2"
  destination_label="$3"

  if ! path_is_contained "$source_relative" || ! path_is_contained "$destination_relative"; then
    report_fail "매니페스트" "$destination_label" "경로가 봉쇄 범위를 벗어난다"
    return 1
  fi

  source_path="$KIT_DIR/$source_relative"
  destination_path="$HOME_DIR/$destination_relative"
  if ! parent_is_within_root "$KIT_DIR" "$source_path" || ! parent_is_within_root "$HOME_DIR" "$destination_path"; then
    report_fail "매니페스트" "$destination_label" "경로가 봉쇄 범위를 벗어난다"
    return 1
  fi
  if [ -L "$destination_path" ]; then
    report_warn "자산" "$destination_label" "심링크다"
    return 1
  fi
  return 0
}

check_file() {
  source_path="$1"
  destination_path="$2"
  destination_label="$3"

  check_staging_leftovers "$destination_path"

  if [ ! -e "$destination_path" ]; then
    if [ "$ADD_MISSING" -eq 1 ]; then
      add_missing_file "$source_path" "$destination_path" "$destination_label" 0
    else
      report_fail "자산" "$destination_label" "파일이 없다"
    fi
  elif [ ! -r "$source_path" ] || [ ! -r "$destination_path" ]; then
    report_warn "자산" "$destination_label" "파일을 읽을 수 없다"
  else
    cmp -s "$source_path" "$destination_path" 2>/dev/null
    compare_status=$?
    case "$compare_status" in
      0) report_ok "자산" "$destination_label" ;;
      1) report_drift "자산" "$destination_label" ;;
      *) report_warn "자산" "$destination_label" "파일 비교에 실패했다 (exit $compare_status)" ;;
    esac
  fi
}

check_seed() {
  source_path="$1"
  destination_path="$2"
  destination_label="$3"

  check_staging_leftovers "$destination_path"
  if [ ! -e "$destination_path" ]; then
    if [ "$ADD_MISSING" -eq 1 ]; then
      add_missing_file "$source_path" "$destination_path" "$destination_label" 1
    else
      report_warn "자산" "$destination_label" "seed 파일이 없다"
    fi
  else
    permission_ok=0
    check_seed_permissions "$destination_path" "$destination_label" && permission_ok=1
    if [ ! -r "$destination_path" ]; then
      report_warn "자산" "$destination_label" "파일을 읽을 수 없다"
    elif [ "$permission_ok" -eq 1 ]; then
      report_ok "자산" "$destination_label"
    fi
  fi
}

check_tree() {
  source_path="$1"
  destination_path="$2"
  destination_label="$3"
  if [ ! -d "$source_path" ] || [ ! -r "$source_path" ]; then
    report_warn "자산" "$destination_label" "킷 원본 트리를 읽을 수 없다"
    return
  fi
  if [ -e "$destination_path" ] && [ ! -d "$destination_path" ]; then
    report_fail "자산" "$destination_label" "디렉터리여야 하는데 일반 파일이다"
    return
  fi

  for source_entry in "$source_path"/* "$source_path"/.[!.]* "$source_path"/..?*; do
    [ -e "$source_entry" ] || continue
    entry_name=${source_entry##*/}
    destination_entry="$destination_path/$entry_name"
    destination_entry_label="$destination_label/$entry_name"
    check_staging_leftovers "$destination_entry"
    if [ ! -e "$destination_entry" ]; then
      if [ "$ADD_MISSING" -eq 1 ]; then
        add_missing_file "$source_entry" "$destination_entry" "$destination_entry_label" 0
      else
        report_fail "자산" "$destination_entry_label" "항목이 없다"
      fi
    elif [ ! -r "$source_entry" ] || [ ! -r "$destination_entry" ]; then
      report_warn "자산" "$destination_entry_label" "항목을 읽을 수 없다"
    else
      diff -r -q "$source_entry" "$destination_entry" >/dev/null 2>&1
      diff_status=$?
      case "$diff_status" in
        0) report_ok "자산" "$destination_entry_label" ;;
        1) report_drift "자산" "$destination_entry_label" ;;
        *) report_warn "자산" "$destination_entry_label" "트리 비교에 실패했다 (exit $diff_status)" ;;
      esac
    fi
  done
}

if [ ! -r "$MANIFEST" ]; then
  report_fail "매니페스트" "$MANIFEST" "매니페스트를 읽을 수 없다"
else
  tab=$(printf '\t')
  DATA_ROW_COUNT=0
  while IFS="$tab" read -r harness mode src dst extra || [ -n "$harness" ]; do
    case "$harness" in
      ""|\#*) continue ;;
    esac
    if [ -n "${extra:-}" ] || [ -z "$mode" ] || [ -z "$src" ] || [ -z "$dst" ]; then
      report_warn "매니페스트" "$MANIFEST" "잘못된 행을 건너뛴다"
      continue
    fi
    DATA_ROW_COUNT=$((DATA_ROW_COUNT + 1))
    if ! harness_selected "$harness"; then
      if [ "$HARNESS_DETECTION_FAILED" -eq 1 ] && [ "$harness" != "any" ]; then
        report_warn "자산" "$dst" "하네스를 감지하지 못해 점검하지 못했다"
      fi
      continue
    fi
    prepare_asset_paths "$src" "$dst" "$dst" || continue
    case "$mode" in
      file) check_file "$source_path" "$destination_path" "$dst" ;;
      seed) check_seed "$source_path" "$destination_path" "$dst" ;;
      tree) check_tree "$source_path" "$destination_path" "$dst" ;;
      *) report_warn "매니페스트" "$dst" "알 수 없는 mode: $mode" ;;
    esac
  done < "$MANIFEST"
  if [ "$DATA_ROW_COUNT" -eq 0 ]; then
    report_warn "매니페스트" "$MANIFEST" "점검할 항목이 없다"
  fi
fi

# 레지스트리에 등록된 Claude 프로젝트는 개별 감독 시작 자산도 갖춰야 한다.
if harness_selected "claude"; then
  STATE_HOME_DIR="${XDG_STATE_HOME:-$HOME_DIR/.local/state}"
  STATE_ROOT="$STATE_HOME_DIR/orchestrate"
  REGISTRY_DIR="$STATE_ROOT/registry"
  SUPERVISOR_DIR="$STATE_ROOT/supervisor"
  for registry_path in "$REGISTRY_DIR"/*.json; do
    [ -f "$registry_path" ] || continue
    project_name=${registry_path##*/}
    project_name=${project_name%.json}
    if ! stamp_supervisor_name_is_valid "$project_name"; then
      report_warn "자산" "supervisor/$project_name" "프로젝트명이 허용 문자 범위를 벗어난다"
      continue
    fi
    project_root=$(sed -n 's/.*"root"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$registry_path" | head -n 1)
    case "$project_root" in
      ""|[^/]*)
        report_warn "자산" "supervisor/$project_name" "레지스트리 root 가 절대 경로가 아니다"
        continue
        ;;
    esac
    if ! stamp_json_value_is_safe "$project_root"; then
      report_warn "자산" "supervisor/$project_name" "레지스트리 root 에 JSON 에 쓸 수 없는 문자가 있다"
      continue
    fi
    command_path="$HOME_DIR/.claude/commands/supervise-$project_name.md"
    state_path="$SUPERVISOR_DIR/$project_name.json"
    actions_path="$SUPERVISOR_DIR/actions-$project_name.md"
    project_label="supervisor/$project_name"

    check_staging_leftovers "$command_path"
    check_staging_leftovers "$state_path"
    check_staging_leftovers "$actions_path"

    if [ ! -e "$command_path" ]; then
      if [ "$ADD_MISSING" -eq 1 ]; then
        add_missing_file "$KIT_DIR/adapters/claude/global/commands/supervise-PROJECT.md.tpl" "$command_path" "$project_label command" 0 "$project_name"
      else
        report_drift "자산" "$project_label command"
      fi
    else
      report_ok "자산" "$project_label command"
    fi

    if [ ! -e "$state_path" ]; then
      if [ "$ADD_MISSING" -eq 1 ]; then
        if ! write_parent_is_within_root "$STATE_HOME_DIR" "$state_path"; then
          report_fail "매니페스트" "$project_label state" "경로가 봉쇄 범위를 벗어난다"
        elif ! mkdir -p "$STATE_ROOT" 2>/dev/null; then
          report_fail "자산" "$project_label state" "상위 디렉터리를 만들 수 없다"
        elif ! write_parent_is_within_root "$STATE_HOME_DIR" "$STATE_ROOT/.kit-doctor-state.XXXXXX"; then
          report_fail "매니페스트" "$project_label state" "경로가 봉쇄 범위를 벗어난다"
        elif ! state_source=$(mktemp "$STATE_ROOT/.kit-doctor-state.XXXXXX"); then
          report_fail "자산" "$project_label state" "상태 임시 파일을 만들 수 없다"
        elif ! printf '%s\n' '{"project":"'"$project_name"'","root":"'"$project_root"'","phase":null,"slug":null,"worktree":null,"branch":null,"part":null,"status":"idle","child":null,"cost":{"phase_usd":0,"parts":{}},"phases_since_review":0,"last_review":"'"$(date +%F)"'","owner":null}' > "$state_source"; then
          rm -f "$state_source"
          report_fail "자산" "$project_label state" "상태 임시 파일을 쓸 수 없다"
        else
          add_missing_file "$state_source" "$state_path" "$project_label state" 0 "" "$STATE_HOME_DIR"
          rm -f "$state_source"
        fi
      else
        report_drift "자산" "$project_label state"
      fi
    else
      report_ok "자산" "$project_label state"
    fi

    if [ ! -e "$actions_path" ]; then
      if [ "$ADD_MISSING" -eq 1 ]; then
        add_missing_file /dev/null "$actions_path" "$project_label actions" 0 "" "$STATE_HOME_DIR"
      else
        report_drift "자산" "$project_label actions"
      fi
    else
      report_ok "자산" "$project_label actions"
    fi
  done
fi

echo "KIT_DOCTOR: ok=$OK_COUNT warn=$WARN_COUNT drift=$DRIFT_COUNT fail=$FAIL_COUNT added=$ADDED_COUNT"
[ "$FAIL_COUNT" -eq 0 ] && exit 0
exit 1
