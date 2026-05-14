#!/bin/sh
set -e

# Render provides PORT environment variable automatically.
# Default to 8000 if not set.
PORT="${PORT:-8000}"

# Default SERVICE_TYPE to 'api' for Render Web Services.
SERVICE_TYPE="${SERVICE_TYPE:-api}"

echo "[Prism] Starting service: $SERVICE_TYPE on port $PORT"

# Start Next.js standalone in the background (Internal port 3000)
if [ -f "/app/webapp/web/standalone/server.js" ]; then
  echo "[Prism] Starting Frontend (standalone) on port 3000..."
  PORT=3000 HOSTNAME=0.0.0.0 node /app/webapp/web/standalone/server.js &
else
  echo "[Prism] Frontend build not found, skipping internal proxy setup."
fi

case "$SERVICE_TYPE" in
  api)
    # Start FastAPI with Uvicorn
    exec uvicorn webapp.api.main:app --host 0.0.0.0 --port "$PORT"
    ;;
  bot)
    # Start Telegram Bot
    exec python -m telegram_bot.run_bot
    ;;
  both)
    # Run both (for minimal free tier setups)
    # API in background, Bot in foreground
    uvicorn webapp.api.main:app --host 0.0.0.0 --port "$PORT" &
    exec python -m telegram_bot.run_bot
    ;;
  *)
    echo "Unknown SERVICE_TYPE=$SERVICE_TYPE (expected 'api', 'bot', or 'both')" >&2
    exit 1
    ;;
esac
