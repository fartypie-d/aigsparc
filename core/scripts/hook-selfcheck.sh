#!/usr/bin/env bash
# 훅 생존 점검 — 훅을 실제 페이로드로 직접 실행해 기대 동작(차단/통과)을 확인한다.
# 근거: ECC 실측 사고(2026-07-28) — 훅이 조용히 죽으면 가드가 사라진 채 경고가 없다.
# 규약: $0 심링크를 bash 3.2 호환 루프로 푼 뒤 cap|readlink|cd|missing 사유로 비정상 종료한다.
# 부모가 core 이고 그 부모에 킷 마커(core/install-manifest.tsv) 가 있으면
# 한 단계 더 올라간다. 아니면 부모가 곧 프로젝트 루트다(설치된 프로젝트 배치).
set -uo pipefail

# --- $0 심링크 해석 + 검증 (bash 3.2 호환, readlink -f 금지) ---
_hs_path="$0"
_hs_fail=""

if [ ! -e "$_hs_path" ] && [ ! -L "$_hs_path" ]; then
    _hs_fail="missing"
fi

_hs_iter=0
while [ -z "$_hs_fail" ] && [ -L "$_hs_path" ] && [ "$_hs_iter" -lt 40 ]; do
    _hs_link_dir=$(CDPATH= cd -- "$(dirname -- "$_hs_path")" 2>/dev/null && pwd)
    if [ -z "$_hs_link_dir" ]; then
        _hs_fail="cd"
        break
    fi
    _hs_target=$(readlink "$_hs_path")
    if [ -z "$_hs_target" ]; then
        _hs_fail="readlink"
        break
    fi
    case "$_hs_target" in
        /*) _hs_path="$_hs_target" ;;
        *)  _hs_path="$_hs_link_dir/$_hs_target" ;;
    esac
    # 후행 슬래시 제거 — POSIX 에서 [ -L "경로/" ] 는 심링크여도 항상 거짓이다.
    # 제거하지 않으면 루프가 해석 완료를 오판하고 조용히 틀린 결과를 낸다.
    while :; do
        case "$_hs_path" in ?*/) _hs_path="${_hs_path%/}" ;; *) break ;; esac
    done
    _hs_iter=$((_hs_iter + 1))
done

# 상한 도달 후 여전히 심링크인지 확인
if [ -z "$_hs_fail" ] && [ -L "$_hs_path" ]; then
    _hs_fail="cap"
fi
# 최종 경로 존재 확인
if [ -z "$_hs_fail" ] && [ ! -e "$_hs_path" ]; then
    _hs_fail="missing"
fi
if [ -n "$_hs_fail" ]; then
    echo "HOOK_SELFCHECK_FAIL: 진입점 해석 실패 ($_hs_fail)" >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$_hs_path")" 2>/dev/null && pwd)
if [ -z "$SCRIPT_DIR" ]; then
    echo "HOOK_SELFCHECK_FAIL: 진입점 해석 실패 (cd)" >&2
    exit 1
fi

# --- 프로젝트 루트 판정: 부모가 'core' 이고 킷 마커 있으면 한 단계 더 올라감 ---
_root_parent=$(CDPATH= cd -- "$SCRIPT_DIR/.." 2>/dev/null && pwd)
if [ -z "$_root_parent" ]; then
    echo "HOOK_SELFCHECK_FAIL: 루트 판정 실패 (cd parent)" >&2
    exit 1
fi
_root_parent_name=$(basename -- "$_root_parent")
PROJECT_ROOT="$_root_parent"
if [ "$_root_parent_name" = "core" ]; then
    _root_gp=$(CDPATH= cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd)
    if [ -z "$_root_gp" ]; then
        echo "HOOK_SELFCHECK_FAIL: 루트 판정 실패 (cd grandparent)" >&2
        exit 1
    fi
    if [ -f "$_root_gp/core/install-manifest.tsv" ]; then
        PROJECT_ROOT="$_root_gp"
    fi
fi

cd "$PROJECT_ROOT" || exit 1
FAIL=0
check() { # <설명> <기대exit> <실제exit>
  if [ "$2" -eq "$3" ]; then echo "OK   $1"; else echo "FAIL $1 (기대 exit $2, 실제 $3)"; FAIL=1; fi
}

echo '{"tool_input":{"command":"sudo ls"}}' | bash .claude/hooks/bash-guard.sh >/dev/null 2>&1
check "bash-guard: sudo 차단" 2 $?
echo '{"tool_input":{"command":"rm -rf /tmp/x"}}' | bash .claude/hooks/bash-guard.sh >/dev/null 2>&1
check "bash-guard: rm -rf 차단" 2 $?
echo '{"tool_input":{"command":"git status"}}' | bash .claude/hooks/bash-guard.sh >/dev/null 2>&1
check "bash-guard: git status 통과" 0 $?

T_OK=$(mktemp /tmp/hookcheck-ok-XXXXXX.py); echo 'x = 1' > "$T_OK"
printf '{"tool_input":{"file_path":"%s"}}' "$T_OK" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: 정상 py 통과" 0 $?
T_BAD=$(mktemp /tmp/hookcheck-bad-XXXXXX.py); echo 'def broken(:' > "$T_BAD"
printf '{"tool_input":{"file_path":"%s"}}' "$T_BAD" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: 문법 오류 py 차단" 2 $?
T_DOCS=$(mktemp -d /tmp/hookcheck-docs-XXXXXX)
mkdir -p "$T_DOCS/docs/phases"
echo 'def broken(:' > "$T_DOCS/docs/phases/skip.py"
printf '{"tool_input":{"file_path":"%s"}}' "$T_DOCS/docs/phases/skip.py" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: docs/phases 하위 py 검사 제외" 0 $?
echo 'def broken(:' > "$T_DOCS/docs/check.py"
printf '{"tool_input":{"file_path":"%s"}}' "$T_DOCS/docs/check.py" | bash .claude/hooks/post-edit-check.sh >/dev/null 2>&1
check "post-edit-check: docs 직하 py 문법 오류 차단" 2 $?
rm -f "$T_OK" "$T_BAD"
rm -rf "$T_DOCS"

if [ "$FAIL" -ne 0 ]; then
  echo "HOOK_SELFCHECK_FAIL: 훅이 기대대로 동작하지 않는다 — 원인 확인 전 위임 금지" >&2
  exit 1
fi
echo "HOOK_SELFCHECK_PASS"
