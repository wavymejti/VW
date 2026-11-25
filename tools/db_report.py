"""
Read-only database report for diagnosing the trip planner.

Run from the repo root:  .venv/bin/python -m tools.db_report
Writes logs/db_report.md (trips, stay days, chat messages, campsite sources).
Only SELECT queries; no personal data beyond trip titles and short user ids.
"""

import json
import os
from datetime import datetime

from sqlalchemy import text

from tools.db import get_engine

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "db_report.md")


def _q(conn, sql, **params):
    return conn.execute(text(sql), params).fetchall()


def main():
    lines = [f"# DB report — {datetime.now():%Y-%m-%d %H:%M}", ""]
    with get_engine().connect() as conn:
        total = _q(conn, "SELECT count(*) FROM trips")[0][0]
        recent = _q(conn, "SELECT count(*) FROM trips WHERE created_at > now() - interval '48 hours'")[0][0]
        lines += [f"Trips: {total} total, {recent} in the last 48 h", ""]

        lines += ["## Last 20 trips", "",
                  "| created | user | title | start → end | span | days saved | stay days | campsites from DB |",
                  "|---|---|---|---|---|---|---|---|"]
        trips = _q(conn, """
            SELECT id, created_at, user_id, title, start_date, end_date
            FROM trips ORDER BY created_at DESC LIMIT 20""")
        for t in trips:
            rows = _q(conn, "SELECT waypoints, overnight_camping_id FROM daily_schedules WHERE trip_id = :id", id=t[0])
            stays = 0
            for r in rows:
                wps = r[0] if isinstance(r[0], list) else json.loads(r[0] or "[]")
                if wps and all(w.get("type") == "stay" for w in wps):
                    stays += 1
            db_camps = sum(1 for r in rows if r[1])
            span = (t[5] - t[4]).days + 1 if t[4] and t[5] else "?"
            flag = "" if span == len(rows) else " ⚠️"
            lines.append(f"| {t[1]:%m-%d %H:%M} | {str(t[2])[:8]} | {t[3]} | {t[4]} → {t[5]} | {span} | "
                         f"{len(rows)}{flag} | {stays} | {db_camps} |")
        lines.append("")

        lines += ["## Trips whose saved days don't match their dates", ""]
        bad = _q(conn, """
            SELECT t.id, t.title, (t.end_date - t.start_date + 1) AS span, count(d.id) AS saved
            FROM trips t LEFT JOIN daily_schedules d ON d.trip_id = t.id
            GROUP BY t.id HAVING count(d.id) <> (t.end_date - t.start_date + 1)
            ORDER BY max(t.created_at) DESC LIMIT 20""")
        lines += [f"- {str(b[0])[:8]} {b[1]}: span {b[2]}, saved {b[3]}" for b in bad] or ["- none"]
        lines.append("")

        lines += ["## Chat messages", ""]
        cm = _q(conn, """SELECT count(*), count(trip_id), count(*) FILTER (WHERE created_at > now() - interval '48 hours')
                         FROM chat_messages""")[0]
        lines += [f"- total {cm[0]}, with trip_id {cm[1]}, last 48 h {cm[2]}", ""]

        lines += ["## Campsites cached in the DB, by source", ""]
        for s in _q(conn, "SELECT source, count(*) FROM campings GROUP BY source ORDER BY 2 DESC"):
            lines.append(f"- {s[0]}: {s[1]}")
        cons = _q(conn, """SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
                           WHERE conrelid = 'campings'::regclass AND contype = 'c'""")
        lines += ["", "Check constraints on campings:"] + [f"- {c[0]}: `{c[1]}`" for c in cons]
        num = _q(conn, """SELECT column_name, data_type FROM information_schema.columns
                          WHERE table_name = 'campings' AND column_name IN ('lat', 'lng', 'rating')""")
        lines += ["", "Column types: " + ", ".join(f"{n[0]}={n[1]}" for n in num), ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Written {OUT}")


if __name__ == "__main__":
    main()
