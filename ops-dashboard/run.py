"""Ops dashboard demo: approval log + task tracker + weekly numbers.

Reads a CSV that stands in for a Google Sheet and renders a dashboard.
`summary_text()` is where a Gemini/OpenAI call would write the plain-English
summary; here it is computed from the data so the demo needs no API key.
"""
import csv
import html
import pathlib
from collections import Counter

BASE = pathlib.Path(__file__).parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# Made-up sample rows (stand-in for a Google Sheet export).
SAMPLE = """task,owner,area,status,due,hours_saved
Reconcile rent payments,Bookkeeper,Accounting,Done,2026-10-12,3.0
Code vendor bills to property,VA 1,Accounting,Done,2026-10-13,2.5
Chase missing receipts,VA 2,Accounting,In progress,2026-10-20,1.5
Approve invoice batch,Bookkeeper,Accounting,Waiting approval,2026-10-21,2.0
Tenant maintenance requests triage,VA 1,Operations,Done,2026-10-14,2.0
Weekly owner report,Manager,Reporting,In progress,2026-10-22,1.0
Late rent reminder drafts,VA 2,Operations,Waiting approval,2026-10-21,1.5
Update dashboard sheet,Manager,Reporting,Overdue,2026-10-15,0.5
"""
(BASE / "sample_tasks.csv").write_text(SAMPLE)


def load():
    with open(BASE / "sample_tasks.csv") as fh:
        return list(csv.DictReader(fh))


def summary_text(rows):
    c = Counter(r["status"] for r in rows)
    saved = sum(float(r["hours_saved"]) for r in rows if r["status"] == "Done")
    return (f"{c['Done']} of {len(rows)} tasks are done, saving about {saved:.1f} hours this week. "
            f"{c['Waiting approval']} items are waiting on a person's approval and {c['Overdue']} is overdue.")


def render(rows):
    c = Counter(r["status"] for r in rows)
    colors = {"Done": "#2e9e5b", "In progress": "#3b7dd8", "Waiting approval": "#d9a400", "Overdue": "#c93a3a"}
    bars = "".join(
        f"<div class=bar><span>{s}</span><i style='width:{n*40}px;background:{colors[s]}'></i><em>{n}</em></div>"
        for s, n in c.items())
    body = "".join(
        f"<tr><td>{html.escape(r['task'])}</td><td>{r['owner']}</td><td>{r['area']}</td>"
        f"<td><b style='color:{colors[r['status']]}'>{r['status']}</b></td><td>{r['due']}</td></tr>"
        for r in rows)
    saved = sum(float(r["hours_saved"]) for r in rows if r["status"] == "Done")
    page = f"""<!doctype html><meta charset=utf-8><title>Ops dashboard (demo)</title>
<style>
body{{font:15px system-ui;margin:32px;color:#1c2430;background:#f6f7f9;max-width:960px}}
h1{{margin:0 0 4px;font-size:22px}}.sub{{color:#5b6573;margin-bottom:14px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin-bottom:16px;font-size:13px}}
.cards{{display:flex;gap:12px;margin-bottom:16px}}.card{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:10px 16px}}.card b{{display:block;font-size:22px}}
.ai{{background:#eef3fb;border-left:4px solid #3b7dd8;padding:10px 14px;border-radius:4px;margin-bottom:16px}}
.panel{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:12px 16px;margin-bottom:16px}}
.bar{{display:flex;align-items:center;gap:10px;margin:6px 0}}.bar span{{width:130px}}.bar i{{height:14px;border-radius:3px;display:inline-block}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #dfe3e8}}
th,td{{padding:8px 11px;border-bottom:1px solid #eceff2;text-align:left;font-size:13px}}th{{background:#eef1f5}}
</style>
<h1>Operations dashboard</h1>
<div class=sub>Task sheet -> status roll-up -> plain-English summary</div>
<div class=demo>Demo with made-up sample data. Not a client's records.</div>
<div class=cards><div class=card><b>{len(rows)}</b>tasks</div><div class=card><b>{saved:.1f}h</b>saved (done)</div>
<div class=card><b>{c['Waiting approval']}</b>waiting approval</div><div class=card><b>{c['Overdue']}</b>overdue</div></div>
<div class=ai><b>Summary:</b> {summary_text(rows)}</div>
<div class=panel><b>Tasks by status</b>{bars}</div>
<table><tr><th>Task</th><th>Owner</th><th>Area</th><th>Status</th><th>Due</th></tr>{body}</table>"""
    (OUT / "dashboard.html").write_text(page)


if __name__ == "__main__":
    rows = load()
    render(rows)
    print(summary_text(rows))
