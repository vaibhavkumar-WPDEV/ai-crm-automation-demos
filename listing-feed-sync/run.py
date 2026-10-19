"""Listing feed sync demo: import by unique listing ID, no duplicates, safe removals.

Mirrors what a WP All Import / custom importer job must do for a housing feed:
- upsert on the feed's unique listing ID (no duplicates, updates in place)
- mark listings missing from the feed as unavailable instead of deleting
- SAFEGUARD: if the feed fails or looks broken (empty / big drop), change nothing
Plain Python + SQLite with a made-up feed. Not connected to HousingFeed or WordPress.
"""
import html, json, pathlib, sqlite3
BASE = pathlib.Path(__file__).parent; OUT = BASE / "output"; OUT.mkdir(exist_ok=True)
DB = OUT / "listings.db"; DB.unlink(missing_ok=True)
MAX_DROP = 0.30   # refuse to remove more than 30% of live inventory in one run

def feed(day):
    """Made-up feed snapshots. Day 3 simulates a broken (empty) response."""
    base = [
     {"id": "HF-1001", "city": "Baltimore", "zip": "21201", "rent": 1450, "beds": 2, "baths": 1, "title": "Sunny 2BR near Harbor", "source": "SampleFeed"},
     {"id": "HF-1002", "city": "Baltimore", "zip": "21218", "rent": 1100, "beds": 1, "baths": 1, "title": "Quiet 1BR apartment", "source": "SampleFeed"},
     {"id": "HF-1003", "city": "Atlanta", "zip": "30303", "rent": 1700, "beds": 3, "baths": 2, "title": "Family 3BR townhome", "source": "SampleFeed"},
     {"id": "HF-1004", "city": "Atlanta", "zip": "30310", "rent": 1250, "beds": 2, "baths": 1, "title": "Renovated 2BR", "source": "SampleFeed"},
     {"id": "HF-1005", "city": "Atlanta", "zip": "30318", "rent": 950, "beds": 1, "baths": 1, "title": "Studio-style 1BR", "source": "SampleFeed"},
    ]
    if day == 1: return base
    if day == 2:   # one rent change, one listing gone, one new, one duplicate row in feed
        d = [dict(x) for x in base]; d[0]["rent"] = 1395; d = [x for x in d if x["id"] != "HF-1002"]
        d.append({"id": "HF-1006", "city": "Baltimore", "zip": "21230", "rent": 1325, "beds": 2, "baths": 1, "title": "New 2BR listing", "source": "SampleFeed"})
        d.append(dict(d[0])); return d
    if day == 3: raise ConnectionError("feed timeout (simulated)")
    if day == 4: return base[:1]            # suspicious: 1 of 5 rows
    return None

con = sqlite3.connect(DB)
con.execute("CREATE TABLE listings(id TEXT PRIMARY KEY, city TEXT, zip TEXT, rent INT, beds INT, baths INT, title TEXT, source TEXT, status TEXT)")
runs = []
for day in (1, 2, 3, 4):
    r = {"run": day, "added": 0, "updated": 0, "unavailable": 0, "dupes_skipped": 0, "result": "OK", "note": ""}
    try:
        data = feed(day)
    except Exception as e:
        r.update(result="ABORTED", note=f"{e}. Nothing changed, inventory kept."); runs.append(r); continue
    live = con.execute("SELECT COUNT(*) FROM listings WHERE status='live'").fetchone()[0]
    ids = {x["id"] for x in data}
    would_remove = con.execute("SELECT COUNT(*) FROM listings WHERE status='live'").fetchone()[0] - len(ids & {i for (i,) in con.execute("SELECT id FROM listings WHERE status='live'")})
    if not data or (live and would_remove / live > MAX_DROP):
        r.update(result="ABORTED", note=f"Safeguard: feed would remove {would_remove} of {live} live listings (>{int(MAX_DROP*100)}%). Nothing changed, alert sent.")
        runs.append(r); continue
    seen = set()
    for x in data:
        if x["id"] in seen: r["dupes_skipped"] += 1; continue
        seen.add(x["id"])
        row = con.execute("SELECT rent, status FROM listings WHERE id=?", (x["id"],)).fetchone()
        if row is None:
            con.execute("INSERT INTO listings VALUES(?,?,?,?,?,?,?,?,'live')", (x["id"], x["city"], x["zip"], x["rent"], x["beds"], x["baths"], x["title"], x["source"])); r["added"] += 1
        else:
            con.execute("UPDATE listings SET city=?,zip=?,rent=?,beds=?,baths=?,title=?,status='live' WHERE id=?", (x["city"], x["zip"], x["rent"], x["beds"], x["baths"], x["title"], x["id"])); r["updated"] += 1
    gone = con.execute("SELECT id FROM listings WHERE status='live' AND id NOT IN (%s)" % ",".join("?" * len(seen)), tuple(seen)).fetchall()
    for (i,) in gone: con.execute("UPDATE listings SET status='unavailable' WHERE id=?", (i,)); r["unavailable"] += 1
    runs.append(r)
con.commit()
rows = con.execute("SELECT * FROM listings ORDER BY city, id").fetchall()
(OUT / "runs.json").write_text(json.dumps(runs, indent=2))
total = len(rows); live_n = sum(1 for r in rows if r[8] == "live")
rt = "".join(f"<tr><td>Run {r['run']}</td><td class={'ok' if r['result']=='OK' else 'bad'}>{r['result']}</td><td>{r['added']}</td><td>{r['updated']}</td><td>{r['unavailable']}</td><td>{r['dupes_skipped']}</td><td>{html.escape(r['note']) or '-'}</td></tr>" for r in runs)
cards = "".join(f"<div class='l {'off' if r[8]!='live' else ''}'><b>{html.escape(r[6])}</b><div>{r[1]} {r[2]}</div><div>${r[3]}/mo | {r[4]} bd | {r[5]} ba</div><div class=id>{r[0]} {'' if r[8]=='live' else '(unavailable, hidden from search)'}</div><div class=btn>Get OFH Housing Help</div></div>" for r in rows)
(OUT / "report.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Listing feed sync (demo)</title>
<style>body{{font:15px system-ui;margin:32px;max-width:1050px;color:#1c2430;background:#f6f7f9}}h1{{font-size:22px;margin:0 0 4px}}h3{{margin:22px 0 8px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin:12px 0;font-size:13px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #dfe3e8}}th,td{{padding:8px 11px;border-bottom:1px solid #eceff2;text-align:left;font-size:13px;vertical-align:top}}th{{background:#eef1f5}}
.ok{{color:#14663a;font-weight:600}}.bad{{color:#a11f1f;font-weight:600}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.l{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:12px;font-size:13px}}.l.off{{opacity:.5}}.id{{color:#5b6573;font-size:12px;margin-top:4px}}
.btn{{margin-top:8px;background:#1f6feb;color:#fff;border-radius:5px;padding:5px 8px;display:inline-block;font-size:12px}}</style>
<h1>Housing listing feed sync</h1><div>Unique listing ID -> upsert -> mark missing as unavailable -> abort if the feed looks broken</div>
<div class=demo>Demo with a made-up feed and SQLite. Not connected to HousingFeed or WordPress. Shows the import logic a WP All Import or custom importer setup has to follow.</div>
<table><tr><th>Run</th><th>Result</th><th>Added</th><th>Updated</th><th>Marked unavailable</th><th>Duplicate rows skipped</th><th>Note</th></tr>{rt}</table>
<h3>Inventory after 4 runs ({live_n} live of {total}, no duplicates)</h3><div class=grid>{cards}</div>""")
for r in runs: print(r)
