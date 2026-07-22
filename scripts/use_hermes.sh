#!/usr/bin/env bash
# Full Hermes Agent backend for HackGPT (Linux/macOS/WSL)
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/common.sh

set_env_value MODEL_BACKEND hermes
set_env_value HERMES_BASE_URL http://127.0.0.1:8642/v1
set_env_value HERMES_MODEL hermes-agent
set_env_value HERMES_API_KEY change-me-local-dev
set_env_value HERMES_SESSION_KEY hackgpt-pentest
set_env_value HERMES_SHOW_TOOL_PROGRESS true

HERMES_ENV="${HERMES_HOME:-$HOME/.hermes}/.env"
if [ -f "$HERMES_ENV" ]; then
  if grep -q '^API_SERVER_ENABLED=' "$HERMES_ENV"; then
    # shellcheck disable=SC2016
    awk 'BEGIN{done=0} /^API_SERVER_ENABLED=/{print "API_SERVER_ENABLED=true"; done=1; next} {print} END{if(!done) print "API_SERVER_ENABLED=true"}' "$HERMES_ENV" > "$HERMES_ENV.tmp"
    mv "$HERMES_ENV.tmp" "$HERMES_ENV"
  else
    echo "API_SERVER_ENABLED=true" >> "$HERMES_ENV"
  fi
  if grep -q '^API_SERVER_KEY=' "$HERMES_ENV"; then
    awk 'BEGIN{done=0} /^API_SERVER_KEY=/{print "API_SERVER_KEY=change-me-local-dev"; done=1; next} {print} END{if(!done) print "API_SERVER_KEY=change-me-local-dev"}' "$HERMES_ENV" > "$HERMES_ENV.tmp"
    mv "$HERMES_ENV.tmp" "$HERMES_ENV"
  else
    echo "API_SERVER_KEY=change-me-local-dev" >> "$HERMES_ENV"
  fi
  echo "Updated Hermes API server flags in $HERMES_ENV"
fi

echo ""
echo "Configured HackGPT for full Hermes Agent integration."
echo "Repo: https://github.com/NousResearch/hermes-agent"
echo ""
echo "1. Install (once): curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
echo "2. hermes setup   OR   hermes setup --portal"
echo "3. hermes gateway   # API on http://127.0.0.1:8642/v1"
echo "4. bash scripts/start.sh  then select Hermes Agent"
echo "5. UI: Settings → Hermes status / New Hermes session / tool progress"
echo ""
echo "Features wired: chat completions, session id/key, tool progress, /api/hermes/status"
