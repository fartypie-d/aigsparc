#!/usr/bin/env bash
# 모델 체인 실측 검증 — 설치 마지막 단계이자 언제든 재실행 가능.
#
# 확인 항목:
#   1. model-policy.json 의 각 항목이 `opencode models` 등록분에 실재하는가
#   2. 체인 프로바이더의 키/OAuth 인증 상태를 보고하는가 (인증 누락만으로는 실패하지 않음)
#   3. tier 당 1회 스모크 호출 (--skip-smoke 로 생략 가능)
#
# 이 검증이 없으면 오타 난 모델 ID 가 조용히 폴백만 소모한다.
set -uo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
POLICY="$HOME/.config/opencode/model-policy.json"
SECRETS="$HOME/.config/opencode/secrets.env"
OPENCODE_BIN="$HOME/.opencode/bin/opencode"
MAPPING="$SCRIPT_DIR/provider-models.json"
SERVE_ENV="$HOME/.config/opencode/serve.env"
SKIP_SMOKE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --policy)       POLICY="$2"; shift 2 ;;
    --secrets)      SECRETS="$2"; shift 2 ;;
    --opencode-bin) OPENCODE_BIN="$2"; shift 2 ;;
    --serve-env)    SERVE_ENV="$2"; shift 2 ;;
    --skip-smoke)   SKIP_SMOKE=1; shift ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 64 ;;
  esac
done

[ -x "$OPENCODE_BIN" ] || { echo "opencode 바이너리 없음: $OPENCODE_BIN" >&2; exit 69; }
[ -f "$POLICY" ] || { echo "정책 파일 없음: $POLICY" >&2; exit 66; }
command -v jq >/dev/null 2>&1 || { echo "jq 가 필요하다" >&2; exit 69; }

if ! jq empty "$POLICY" >/dev/null 2>&1; then
  echo "정책 JSON 손상: $POLICY" >&2
  exit 66
fi

TIER_TYPE=$(jq -r '(.tiers // {}) | type' "$POLICY")
[ "$TIER_TYPE" = "object" ] || { echo "정책의 tiers 가 객체가 아니다 ($TIER_TYPE): $POLICY" >&2; exit 66; }

TIER_COUNT=$(jq -r '(.tiers // {}) | length' "$POLICY")
if [ "$TIER_COUNT" -eq 0 ]; then
  echo "정책에 tier 가 하나도 없다: $POLICY" >&2
  exit 1
fi

echo "== 모델 체인 검증 ($POLICY)"

REGISTERED=$("$OPENCODE_BIN" models 2>/dev/null)
MODELS_STATUS=$?
if [ "$MODELS_STATUS" -ne 0 ]; then
  echo "opencode models 실패 (exit $MODELS_STATUS) — 인증·설치를 확인할 것" >&2
  exit 1
fi
if [ -z "$REGISTERED" ]; then
  echo "   ⚠️ 등록 모델 목록이 비어 있다 — opencode 설치·인증을 먼저 확인할 것" >&2
  exit 1
fi

FAILED_TIERS=""
SEEN_PREFIXES=""
while IFS= read -r tier; do
  echo
  echo "-- tier: $tier"
  valid=0
  first_valid=""
  while IFS= read -r model; do
    prefix=${model%%/*}
    if ! printf '%s\n' "$SEEN_PREFIXES" | grep -qxF "$prefix"; then
      SEEN_PREFIXES="${SEEN_PREFIXES}
$prefix"
    fi
    if printf '%s\n' "$REGISTERED" | grep -qxF "$model"; then
      echo "   OK      $model"
      valid=$((valid + 1))
      [ -n "$first_valid" ] || first_valid="$model"
    else
      echo "   MISSING $model   ← opencode models 에 없다 (오타이거나 인증 미완료)"
    fi
  done < <(jq -r --arg tier "$tier" '.tiers[$tier][]' "$POLICY")

  if [ "$valid" -eq 0 ]; then
    echo "   ❌ 이 tier 에 사용 가능한 모델이 하나도 없다"
    FAILED_TIERS="${FAILED_TIERS:+$FAILED_TIERS }$tier"
  elif [ "$SKIP_SMOKE" -eq 0 ]; then
    echo "   스모크 호출: $first_valid"
    "$OPENCODE_BIN" run -m "$first_valid" "Reply with exactly: OK" >/dev/null 2>&1
    RUN_STATUS=$?
    if [ "$RUN_STATUS" -eq 0 ]; then
      echo "   OK      스모크 통과"
    else
      echo "   ⚠️ 스모크 실패 (exit $RUN_STATUS) — 인증·레이트리밋을 확인할 것 (체인 폴백은 여전히 동작한다)"
    fi
  fi
done < <(jq -r '.tiers | keys[]' "$POLICY")

echo
echo "-- 인증 수단"
AUTH_OUT=$("$OPENCODE_BIN" auth list 2>/dev/null)
AUTH_STATUS=$?
if [ "$AUTH_STATUS" -ne 0 ]; then
  echo "auth list 실행 실패 (exit $AUTH_STATUS)" >&2
fi

# 값은 읽거나 출력하지 않고, 키 이름과 빈 값 여부만 판별한다.
SECRET_KEYS=""
if [ -f "$SECRETS" ]; then
  SECRET_KEYS=$(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "$SECRETS" 2>/dev/null | sed 's/=$//')
fi

while IFS= read -r prefix; do
  [ -n "$prefix" ] || continue
  PROVIDER=$(jq -r --arg prefix "$prefix" '.providers | to_entries[] | select(.value.prefix == $prefix) | .key' "$MAPPING")
  if [ -z "$PROVIDER" ]; then
    echo "   인증 확인 불가: $prefix (매핑표에 없음)"
    continue
  fi
  AUTH_TYPE=$(jq -r --arg provider "$PROVIDER" '.providers[$provider].auth' "$MAPPING")
  CREDENTIAL=$(jq -r --arg provider "$PROVIDER" '.providers[$provider].credential' "$MAPPING")
  if [ "$AUTH_TYPE" = "key" ]; then
    if printf '%s\n' "$SECRET_KEYS" | grep -qxF "$CREDENTIAL"; then
      if grep -qxF "$CREDENTIAL=" "$SECRETS" 2>/dev/null; then
        echo "   인증 누락: $PROVIDER ($CREDENTIAL 이름 있음, 값 비어있음)"
      else
        echo "   인증 OK: $PROVIDER (key)"
      fi
    else
      echo "   인증 누락: $PROVIDER ($CREDENTIAL 미설정)"
    fi
  elif [ "$AUTH_TYPE" = "oauth" ]; then
    if [ "$AUTH_STATUS" -ne 0 ]; then
      echo "   인증 확인 불가: $PROVIDER (auth list 실행 실패)"
    elif printf '%s\n' "$AUTH_OUT" | grep -qiF "$PROVIDER"; then
      echo "   인증 OK: $PROVIDER (oauth)"
    else
      echo "   인증 누락: $PROVIDER (OAuth 인증 미확인)"
    fi
  else
    echo "   인증 확인 불가: $PROVIDER (알 수 없는 인증 방식: $AUTH_TYPE)"
  fi
done <<EOF
$SEEN_PREFIXES
EOF

echo
echo "-- 상주 serve 대조 (설정 파일이 아니라 실제로 위임을 실행하는 프로세스)"
# `opencode models` 는 CLI 가 설정 파일을 그때그때 읽어 만든 목록이다. 위임은 serve
# attach 경로로 가므로, 오래 떠 있는 serve 가 낡은 설정을 들고 있으면 파일은 맞는데
# 위임만 죽는다 (2026-09-01 실측: antigravity 블록 추가 후에도 serve 는 모르는 상태였다).
SERVE_FAILED_TIERS=""
STALE_SEEN=0
# 비밀번호는 `curl --config -` 의 stdin 으로만 넘긴다. `-u` 로 주면 프로세스 인자에 평문으로
# 실려 같은 머신의 다른 사용자가 `ps`·/proc 로 읽는다 — opencode-serve-ctl.sh 와 같은 규약.
serve_providers_request() { # <포트> <비밀번호> — 본문 + 마지막 줄에 HTTP 코드
  curl --config - --silent --show-error --max-time 15 --write-out '\n%{http_code}' <<EOF
user = "opencode:$2"
url = "http://127.0.0.1:$1/config/providers"
EOF
}
if [ ! -f "$SERVE_ENV" ]; then
  echo "   건너뜀 — serve.env 없음"
elif ! command -v curl >/dev/null 2>&1; then
  echo "   건너뜀 — curl 없음"
else
  SERVE_PORT=$(sed -n 's/^OPENCODE_SERVE_PORT=//p' "$SERVE_ENV" | head -1)
  SERVE_PW=$(sed -n 's/^OPENCODE_SERVER_PASSWORD=//p' "$SERVE_ENV" | head -1)
  SERVE_PW_OK=1
  # curl 설정 문법을 깨뜨리는 문자는 거부한다 (serve-ctl 의 검증과 동일 기준).
  case "$SERVE_PW" in *'"'*|*\\*|*"
"*) SERVE_PW_OK=0 ;;
  esac
  if [ -z "$SERVE_PORT" ]; then
    echo "   건너뜀 — serve.env 에 포트 없음"
  elif [ "$SERVE_PW_OK" -eq 0 ]; then
    echo "   건너뜀 — serve.env 비밀번호에 따옴표·역슬래시·개행이 있다 (값은 출력하지 않는다)"
  else
    SERVE_RESPONSE=$(serve_providers_request "$SERVE_PORT" "$SERVE_PW" 2>/dev/null)
    SERVE_CURL_STATUS=$?
    SERVE_CODE=$(printf '%s' "$SERVE_RESPONSE" | tail -n 1)
    SERVE_JSON=$(printf '%s' "$SERVE_RESPONSE" | sed '$d')
    if [ "$SERVE_CURL_STATUS" -ne 0 ]; then
      echo "   건너뜀 — serve 미기동 (다음 위임이 새 설정으로 lazy-start 한다)"
    elif [ "$SERVE_CODE" = "401" ] || [ "$SERVE_CODE" = "403" ]; then
      # 미기동으로 뭉뚱그리면 이 진단이 노리는 드리프트("설정은 맞는데 상주 serve 만 낡음")를
      # 스스로 감춘다. 비밀번호가 바뀐 뒤 serve 를 재활용하지 않은 상태가 바로 이 코드다.
      echo "   ⚠️ serve 인증 불일치 (HTTP $SERVE_CODE) — serve.env 의 비밀번호가 상주 serve 와 다르다"
      echo "      serve 를 재활용해 새 설정으로 다시 띄울 것"
    elif [ "$SERVE_CODE" != "200" ]; then
      echo "   ⚠️ serve 가 예상 밖 응답을 냈다 (HTTP $SERVE_CODE) — 대조를 건너뛴다"
    else
      SERVE_MODELS=$(printf '%s' "$SERVE_JSON" | jq -r '
        (.providers // [])[] as $p | $p.id as $id
        | ($p.models // {} | keys[]) | "\($id)/\(.)"' 2>/dev/null)
      if [ -z "$SERVE_MODELS" ]; then
        echo "   ⚠️ serve 가 모델을 하나도 보고하지 않았다 — 응답 형식 변경 의심"
      else
        while IFS= read -r tier; do
          serve_valid=0
          while IFS= read -r model; do
            if printf '%s\n' "$SERVE_MODELS" | grep -qxF "$model"; then
              serve_valid=$((serve_valid + 1))
            else
              echo "   STALE   $model   ← 상주 serve 가 모른다 (serve 재시작 필요)"
              STALE_SEEN=1
            fi
          done < <(jq -r --arg tier "$tier" '.tiers[$tier][]' "$POLICY")
          if [ "$serve_valid" -eq 0 ]; then
            echo "   ❌ tier '$tier' — 상주 serve 기준 사용 가능한 모델이 0개다"
            SERVE_FAILED_TIERS="${SERVE_FAILED_TIERS:+$SERVE_FAILED_TIERS }$tier"
          fi
        done < <(jq -r '.tiers | keys[]' "$POLICY")
        if [ -z "$SERVE_FAILED_TIERS" ]; then
          if [ "$STALE_SEEN" -eq 1 ]; then
            echo "   ⚠️ 모든 tier 에 serve 기준 유효 모델이 1개 이상 있으나, 위 STALE 항목은"
            echo "      폴백 후보에서 사실상 빠져 있다 — serve 를 재시작해 반영할 것"
          else
            echo "   OK      모든 tier 가 상주 serve 에서도 유효하다"
          fi
        fi
      fi
    fi
  fi
fi

echo
if [ -n "$SERVE_FAILED_TIERS" ]; then
  echo "❌ 상주 serve 기준 사용 불가 tier: $SERVE_FAILED_TIERS"
  echo "   설정 파일은 맞다. serve 를 재시작해야 반영된다:"
  # ctl 위치는 설치 형태마다 다르다 — 있는 것을 찾아 실제 경로를 보여준다.
  SERVE_CTL_HINT="<프로젝트 또는 키트>/scripts/opencode-serve-ctl.sh"
  for candidate in "$SCRIPT_DIR/opencode-serve-ctl.sh" \
                   "$SCRIPT_DIR/../scripts/opencode-serve-ctl.sh" \
                   "$HOME/aigsprac/scripts/opencode-serve-ctl.sh"; do
    [ -f "$candidate" ] && { SERVE_CTL_HINT=$candidate; break; }
  done
  echo "     bash $SERVE_CTL_HINT status   # 진행 중 위임이 없는지 먼저 확인"
  echo "     bash $SERVE_CTL_HINT stop     # 다음 위임이 새 설정으로 lazy-start"
  exit 1
fi

echo
if [ -n "$FAILED_TIERS" ]; then
  echo "❌ 사용 불가 tier: $FAILED_TIERS — model-policy.json 을 고치거나 인증을 완료할 것"
  exit 1
fi
if [ "$SKIP_SMOKE" -eq 1 ]; then
  echo "⏭ 스모크 생략됨 (--skip-smoke) — 모델 ID 존재만 확인, 실제 호출 미검증"
  echo "✅ 모든 tier 에 사용 가능한 모델이 있다 (스모크 생략)"
else
  echo "✅ 모든 tier 에 사용 가능한 모델이 있다 (스모크 수행)"
fi
exit 0
