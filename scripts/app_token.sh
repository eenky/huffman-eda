#!/usr/bin/env bash
# Mint a short-lived (1 h) installation token for a GitHub App, using only openssl + curl.
#
#   export GH_TOKEN=$(APP_ID=123456 APP_KEY=~/.hermes/author.pem scripts/app_token.sh eenky/huffman-eda)
#
# Each Hermes profile keeps its OWN key file and mints its own token. The author profile
# must never be able to read the reviewer key (and neither should hold your personal token).
set -euo pipefail
REPO="${1:?usage: app_token.sh OWNER/REPO}"
: "${APP_ID:?set APP_ID}"
: "${APP_KEY:?set APP_KEY (path to the .pem private key of the app)}"

b64() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
now=$(date +%s)
header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64)
payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now - 60)) $((now + 540)) "$APP_ID" | b64)
sig=$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$APP_KEY" -binary | b64)
jwt="$header.$payload.$sig"

api() { curl -fsS -H "Authorization: Bearer $jwt" -H "Accept: application/vnd.github+json" "$@"; }
inst=$(api "https://api.github.com/repos/$REPO/installation" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
api -X POST "https://api.github.com/app/installations/$inst/access_tokens" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])'
