#!/bin/bash
# (Re)starts the VW Trip Planner server on http://localhost:5050.
# Stops a server already listening on 5050, checks the database and HeadTTS, then runs Flask.
# Double-click in Finder, or run: ./start_vw.command
cd "$(dirname "$0")"
PORT="${PORT:-5050}"

OLD=$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$OLD" ]; then
  echo "Stopping the server already running on port $PORT (pid $OLD)..."
  kill $OLD 2>/dev/null; sleep 1
fi

docker exec vw_postgres pg_isready -U postgres -d postgres >/dev/null 2>&1 \
  || echo "!! Database is not running: run db/setup_local_db.command (or docker compose up -d db)."
curl -s -o /dev/null -m 2 http://127.0.0.1:8882 \
  || echo "!! HeadTTS is not running on 8882: Sniffer will move but not speak (~/Documents/GitHub/avw/tts/start.sh)."

[ -x .venv/bin/python ] || { echo "No .venv: run db/setup_local_db.command first."; read -r -p "Press Enter"; exit 1; }
echo "Starting VW Trip Planner on http://localhost:$PORT (Ctrl+C to stop)..."
exec .venv/bin/python tools/server.py
