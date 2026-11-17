#!/bin/bash
# Recreates the local PostGIS database for VW Trip Planner: starts Docker if needed,
# runs the db container (docker-compose.yml), applies migrations + seed, checks the tables.
# Double-click in Finder, or run: ./db/setup_local_db.command
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== VW Trip Planner: local database setup =="
echo "Folder: $(pwd)"

if ! docker info >/dev/null 2>&1; then
  echo "Starting Docker Desktop..."
  open -a Docker || true
  for i in $(seq 1 90); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || { echo "Docker did not start. Open Docker Desktop and run this again."; read -r -p "Press Enter to close"; exit 1; }
fi

echo "Starting PostGIS container (first time downloads the image)..."
docker compose up -d db
echo -n "Waiting for the database"
for i in $(seq 1 60); do
  if docker exec vw_postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; then echo " ready."; break; fi
  echo -n "."; sleep 2
done

if [ ! -x .venv/bin/python ]; then
  echo "Creating Python environment in .venv..."
  python3 -m venv .venv
fi
echo "Installing Python packages (quiet)..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "Applying migrations and seed..."
.venv/bin/python apply_migration.py

TABLES=$(docker exec vw_postgres psql -U postgres -d postgres -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name <> 'spatial_ref_sys'")
if [ "${TABLES:-0}" -lt 5 ]; then
  echo "!! Migrations did not create the tables (see errors above)."
  read -r -p "Press Enter to close"; exit 1
fi
echo "Tables in the database:"
docker exec vw_postgres psql -U postgres -d postgres -c "\dt public.*"
docker exec vw_postgres psql -U postgres -d postgres -tAc "SELECT 'campings: '||count(*) FROM campings UNION ALL SELECT 'trips: '||count(*) FROM trips UNION ALL SELECT 'users: '||count(*) FROM users;"
echo
echo "== DONE =="
read -r -p "Press Enter to close"
