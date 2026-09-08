#!/usr/bin/env bash
# 프로젝트 스캐폴드 공통 함수 — new-project.sh 와 adopt-project.sh 가 공유한다.
# macOS 기본 bash 3.2 호환: mapfile·연관배열 미사용.

# 설치된 하네스 CLI 를 감지한다. stdout: "claude" | "codex" | "claude codex"
stamp_detect_harness() {
  _found=""
  command -v claude >/dev/null 2>&1 && _found="claude"
  command -v codex  >/dev/null 2>&1 && _found="${_found:+$_found }codex"
  if [ -z "$_found" ]; then
    echo "claude·codex CLI 를 찾을 수 없다 — --claude 또는 --codex 로 명시할 것" >&2
    return 1
  fi
  echo "$_found"
}

# 대상 부모(아직 없는 경로 포함)의 물리 경로가 봉쇄 루트 아래인지 확인한다.
# kit-doctor.sh 와 stamp_supervisor 가 함께 쓰는 단일 구현이다.
write_parent_is_within_root() { # <ROOT> <TARGET>
  _write_root_path="$1"; _write_target_path="$2"
  _write_parent_path=$(dirname -- "$_write_target_path")

  while [ ! -e "$_write_parent_path" ] && [ ! -L "$_write_parent_path" ]; do
    _write_next_parent=$(dirname -- "$_write_parent_path")
    [ "$_write_next_parent" != "$_write_parent_path" ] || return 1
    _write_parent_path="$_write_next_parent"
  done
  [ -d "$_write_parent_path" ] || return 1
  _write_root_physical=$(CDPATH= cd -P -- "$_write_root_path" 2>/dev/null && pwd) || return 1
  _write_parent_physical=$(CDPATH= cd -P -- "$_write_parent_path" 2>/dev/null && pwd) || return 1
  case "$_write_parent_physical/" in
    "$_write_root_physical/"*) return 0 ;;
    *) return 1 ;;
  esac
}

# core/project-template + 선택 하네스의 adapters/<h>/project 를 TARGET 에 복사한다.
# 기존 파일은 절대 덮지 않는다 (rsync --ignore-existing 과 동일 의미).
# 이번 호출에서 "실제로 새로 복사된" 파일 목록을 TARGET/.orchestrate/.stamp-copied
# 에 기록한다 (매 호출마다 덮어써 초기화). stamp_placeholders 가 이 목록만 치환
# 대상으로 삼아, 대상 저장소가 원래부터 갖고 있던 파일은 절대 건드리지 않는다 —
# 키트 자신을 대상(adopt)으로 실행하면 core/project-template/ 원본, 문서 코드블록
# 등에 __PROJECT__ 문자열이 정당하게 존재할 수 있으므로 전체 트리 grep 은 위험하다.
stamp_copy() { # <KIT_DIR> <TARGET> <HARNESSES>
  _kit="$1"; _target="$2"; _harnesses="$3"
  mkdir -p "$_target/.orchestrate"
  _stamp_manifest="$_target/.orchestrate/.stamp-copied"
  : > "$_stamp_manifest"
  _stamp_copy_tree "$_kit/core/project-template" "$_target"
  _stamp_copy_tree "$_kit/core/scripts" "$_target/scripts"
  for _h in $_harnesses; do
    [ -d "$_kit/adapters/$_h/project" ] && _stamp_copy_tree "$_kit/adapters/$_h/project" "$_target"
  done
}

# cp -R 은 기존 파일을 덮으므로 파일 단위로 존재 여부를 확인하며 복사한다.
# 실제로 복사한 파일만 $_stamp_manifest 에 append 한다 ($_stamp_manifest 는
# stamp_copy 가 미리 설정해 둔 전역 변수 — while 이 파이프의 서브셸에서 돌아도
# 파일 append 는 서브셸 경계와 무관하게 디스크에 그대로 반영된다).
_stamp_copy_tree() { # <SRC_DIR> <DST_DIR>
  _src="$1"; _dst="$2"
  [ -d "$_src" ] || return 0
  mkdir -p "$_dst"
  ( cd "$_src" && find . -type d ) | while IFS= read -r _d; do
    mkdir -p "$_dst/$_d"
  done
  ( cd "$_src" && find . -type f ) | while IFS= read -r _f; do
    if [ ! -e "$_dst/$_f" ]; then
      cp "$_src/$_f" "$_dst/$_f"
      echo "$_dst/$_f" >> "$_stamp_manifest"
    fi
  done
}

# __PROJECT__ 플레이스홀더를 프로젝트명으로 치환한다 (perl 은 macOS/Linux 공통).
# 치환 범위는 stamp_copy 가 방금 실제로 복사한 파일(.orchestrate/.stamp-copied
# 목록)로 한정한다 — 대상 트리 전체를 grep 하지 않으므로, 대상이 원래부터
# 가지고 있던 __PROJECT__ 포함 파일은 절대 건드리지 않는다.
stamp_placeholders() { # <TARGET> <NAME>
  _target="$1"; _name="$2"
  _stamp_manifest="$_target/.orchestrate/.stamp-copied"
  [ -f "$_stamp_manifest" ] || return 0
  while IFS= read -r _f; do
    [ -f "$_f" ] || continue
    grep -q '__PROJECT__' "$_f" 2>/dev/null || continue
    perl -pi -e "s/__PROJECT__/$_name/g" "$_f"
  done < "$_stamp_manifest"
  return 0
}

# 실행 권한·작업 디렉터리·gitignore 를 정리한다. 중복 없이 append 하므로 멱등이다.
stamp_finalize() { # <TARGET>
  _target="$1"
  chmod +x "$_target"/scripts/*.sh 2>/dev/null || true
  chmod +x "$_target"/.claude/hooks/*.sh 2>/dev/null || true
  mkdir -p "$_target/.orchestrate"
  touch "$_target/.gitignore"
  for _line in ".orchestrate/" ".claude/settings.local.json" ".DS_Store"; do
    grep -qxF "$_line" "$_target/.gitignore" || echo "$_line" >> "$_target/.gitignore"
  done
}

# JSON 문자열로 안전하게 쓸 수 없는 값은 거부한다.
stamp_supervisor_name_is_valid() {
  case "$1" in
    ""|"."|".."|*[!A-Za-z0-9._-]*) return 1 ;;
  esac
  return 0
}

stamp_json_value_is_safe() {
  case "$1" in
    *\"*|*\\*) return 1 ;;
  esac
  if LC_ALL=C printf '%s' "$1" | LC_ALL=C grep -q '[[:cntrl:]]'; then
    return 1
  fi
  return 0
}

# 감독 자산의 목적지와 스테이징 경로를 안전하게 준비한다.
stamp_supervisor_prepare() { # <DESTINATION> <ROOT> <LABEL>
  _supervisor_destination="$1"; _supervisor_root="$2"; _supervisor_label="$3"
  _supervisor_parent=$(dirname -- "$_supervisor_destination")
  _supervisor_staging="${_supervisor_destination}.kit-partial.$$"

  if [ -L "$_supervisor_destination" ]; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 목적지가 심링크다" >&2
    return 1
  fi
  if ! write_parent_is_within_root "$_supervisor_root" "$_supervisor_destination"; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 경로가 봉쇄 범위를 벗어난다" >&2
    return 1
  fi
  if ! mkdir -p "$_supervisor_parent" 2>/dev/null; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 상위 디렉터리를 만들 수 없다" >&2
    return 1
  fi
  if ! write_parent_is_within_root "$_supervisor_root" "$_supervisor_destination"; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 경로가 봉쇄 범위를 벗어난다" >&2
    return 1
  fi
  if ! write_parent_is_within_root "$_supervisor_root" "$_supervisor_staging"; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 스테이징 경로가 봉쇄 범위를 벗어난다" >&2
    return 1
  fi
  if [ -L "$_supervisor_destination" ] || [ -L "$_supervisor_staging" ]; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 목적지 또는 스테이징 경로가 심링크다" >&2
    return 1
  fi
  if [ -e "$_supervisor_destination" ]; then
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 생성 중인 파일이 있어 덮어쓰지 않았다" >&2
    return 1
  fi
}

# 이미 작성된 스테이징 파일을 목적지에 원자적으로 배치한다.
stamp_supervisor_commit() { # <DESTINATION> <LABEL> <STAGING>
  _supervisor_destination="$1"; _supervisor_label="$2"; _supervisor_staging="$3"
  if [ -e "$_supervisor_destination" ] || [ -L "$_supervisor_destination" ]; then
    rm -f "$_supervisor_staging"
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 생성 중인 파일이 있어 덮어쓰지 않았다" >&2
    return 1
  fi
  if ! mv "$_supervisor_staging" "$_supervisor_destination" 2>/dev/null; then
    rm -f "$_supervisor_staging"
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 스테이징 파일을 배치할 수 없다" >&2
    return 1
  fi
}

# 내용을 목적지 스테이징 파일에 쓴 뒤 원자적으로 배치한다.
stamp_supervisor_add_content() { # <DESTINATION> <ROOT> <LABEL> <CONTENT>
  _supervisor_destination="$1"; _supervisor_root="$2"; _supervisor_label="$3"; _supervisor_content="$4"
  [ -e "$_supervisor_destination" ] && return 0
  stamp_supervisor_prepare "$_supervisor_destination" "$_supervisor_root" "$_supervisor_label" || return 1
  if ! printf '%s' "$_supervisor_content" > "$_supervisor_staging"; then
    rm -f "$_supervisor_staging"
    echo "감독 자산을 만들지 않았다 ($_supervisor_label): 스테이징 파일을 쓸 수 없다" >&2
    return 1
  fi
  stamp_supervisor_commit "$_supervisor_destination" "$_supervisor_label" "$_supervisor_staging"
}

# Claude 감독 커맨드와 프로젝트별 상태 파일을 없을 때만 만든다.
stamp_supervisor() { # <KIT_DIR> <TARGET> <NAME>
  _kit="$1"; _target="$2"; _name="$3"
  if ! stamp_supervisor_name_is_valid "$_name"; then
    echo "감독 자산만 만들지 않았다: 프로젝트명은 영문자·숫자·.·_·- 만 사용할 수 있다 ($_name)" >&2
    return 1
  fi
  if ! stamp_json_value_is_safe "$_target"; then
    echo "감독 자산을 만들지 않았다: 프로젝트 경로에 JSON 에 쓸 수 없는 문자가 있다" >&2
    return 1
  fi
  _commands="$HOME/.claude/commands"
  _command="$_commands/supervise-$_name.md"
  _state_root="${XDG_STATE_HOME:-$HOME/.local/state}/orchestrate"
  _supervisor="$_state_root/supervisor"
  _state="$_supervisor/$_name.json"
  _actions="$_supervisor/actions-$_name.md"

  # 상태 루트가 아직 없을 수 있으므로 HOME 기준으로 먼저 안전하게 만든다.
  if ! write_parent_is_within_root "$HOME" "$_state_root/.kit-supervisor-probe"; then
    echo "감독 자산을 만들지 않았다: 상태 경로가 봉쇄 범위를 벗어난다" >&2
    return 1
  fi
  if ! mkdir -p "$_state_root" 2>/dev/null; then
    echo "감독 자산을 만들지 않았다: 상태 상위 디렉터리를 만들 수 없다" >&2
    return 1
  fi
  if ! write_parent_is_within_root "$_state_root" "$_state"; then
    echo "감독 자산을 만들지 않았다: 상태 경로가 봉쇄 범위를 벗어난다" >&2
    return 1
  fi

  if [ ! -e "$_command" ] && [ ! -L "$_command" ]; then
    stamp_supervisor_prepare "$_command" "$HOME" "command" || return 1
    if ! STAMP_SUPERVISOR_NAME="$_name" perl -pe 's/__PROJECT__/$ENV{STAMP_SUPERVISOR_NAME}/g' "$_kit/adapters/claude/global/commands/supervise-PROJECT.md.tpl" > "$_supervisor_staging"; then
      rm -f "$_supervisor_staging"
      echo "감독 자산을 만들지 않았다 (command): 템플릿을 쓸 수 없다" >&2
      return 1
    fi
    stamp_supervisor_commit "$_command" "command" "$_supervisor_staging" || return 1
  elif [ -L "$_command" ]; then
    echo "감독 자산을 만들지 않았다 (command): 목적지가 심링크다" >&2
    return 1
  fi

  _state_content='{"project":"'"$_name"'","root":"'"$_target"'","phase":null,"slug":null,"worktree":null,"branch":null,"part":null,"status":"idle","child":null,"cost":{"phase_usd":0,"parts":{}},"phases_since_review":0,"last_review":"'"$(date +%F)"'","owner":null}'
  _state_ok=1
  stamp_supervisor_add_content "$_state" "$_state_root" "state" "$_state_content" || _state_ok=0
  _actions_ok=1
  stamp_supervisor_add_content "$_actions" "$_state_root" "actions" "" || _actions_ok=0
  [ "$_state_ok" -eq 1 ] && [ "$_actions_ok" -eq 1 ]
}
