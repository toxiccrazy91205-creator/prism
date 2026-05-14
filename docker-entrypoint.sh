#!/bin/sh
set -e

# Render provides PORT environment variable automatically.
# Default to 8000 if not set.
PORT="${PORT:-8000}"

# Default SERVICE_TYPE to 'api' for Render Web Services.
SERVICE_TYPE="${SERVICE_TYPE:-api}"

echo "[Prism] Starting service: $SERVICE_TYPE on port $PORT"

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
