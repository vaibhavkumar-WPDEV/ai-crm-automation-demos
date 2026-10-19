"""Takeover audit: scan an exported workflow inventory for the problems a new owner must find first.

Input is a made-up inventory (stand-in for a HubSpot workflows export). Output is a
prioritised findings report plus a first-20-hours plan.
"""
import html, json, pathlib
BASE = pathlib.Path(__file__).parent; OUT = BASE / "output"; OUT.mkdir(exist_ok=True)

WORKFLOWS = [
 {"name": "Discovery call follow-up", "active": True, "object": "contact", "trigger": "meeting_booked", "delay_days": 2, "sends_email": True, "reenroll": True, "unenroll_criteria": [], "errors_30d": 0, "owner": "Ops", "documented": False},
 {"name": "Meeting booked: nurture", "active": True, "object": "contact", "trigger": "meeting_booked", "delay_days": 1, "sends_email": True, "reenroll": False, "unenroll_criteria": ["call_completed"], "errors_30d": 0, "owner": "Marketing", "documented": True},
 {"name": "Lead assignment", "active": True, "object": "contact", "trigger": "form_submitted", "delay_days": 0, "sends_email": False, "reenroll": False, "unenroll_criteria": [], "errors_30d": 14, "owner": "Ops", "documented": False},
 {"name": "Deal stage -> Slack alert", "active": True, "object": "deal", "trigger": "stage_changed", "delay_days": 0, "sends_email": False, "reenroll": True, "unenroll_criteria": [], "errors_30d": 3, "owner": None, "documented": False},
 {"name": "Old webinar sequence", "active": True, "object": "contact", "trigger": "webinar_2024", "delay_days": 7, "sends_email": True, "reenroll": False, "unenroll_criteria": [], "errors_30d": 0, "owner": None, "documented": False},
 {"name": "Welcome email", "active": False, "object": "contact", "trigger": "form_submitted", "delay_days": 0, "sends_email": True, "reenroll": False, "unenroll_criteria": [], "errors_30d": 0, "owner": "Marketing", "documented": True},
]
findings = []
def add(sev, wf, issue, why, fix): findings.append({"severity": sev, "workflow": wf, "issue": issue, "why": why, "fix": fix})
act = [w for w in WORKFLOWS if w["active"]]
by_trigger = {}
for w in act: by_trigger.setdefault((w["object"], w["trigger"]), []).append(w)
for (o, t), ws in by_trigger.items():
    mailers = [w["name"] for w in ws if w["sends_email"]]
    if len(mailers) > 1:
        add("High", " + ".join(mailers), f"{len(mailers)} active workflows send email on the same trigger ({t})", "Contact can get overlapping or contradictory messages", "Merge into one workflow or add mutual suppression")
for w in act:
    if w["sends_email"] and w["delay_days"] > 0 and not w["unenroll_criteria"]:
        add("High", w["name"], "Delay before email with no unenrolment criteria", "State can change during the delay and the email still goes out", "Add unenrolment criteria and a re-check branch before the send")
    if w["sends_email"] and w["reenroll"]:
        add("Medium", w["name"], "Re-enrolment ON with an email action", "Repeat triggers can create parallel runs and duplicate sends", "Turn re-enrolment off or dedupe with a property check")
    if w["errors_30d"] >= 5:
        add("High", w["name"], f"{w['errors_30d']} action errors in 30 days", "Silent failures: leads may not be assigned", "Read the error log, fix the failing action, add an alert")
    elif w["errors_30d"] > 0:
        add("Medium", w["name"], f"{w['errors_30d']} action errors in 30 days", "Intermittent failures", "Check the failing action and add monitoring")
    if not w["owner"]: add("Low", w["name"], "No owner", "Nobody is accountable when it breaks", "Assign an owner")
    if not w["documented"]: add("Low", w["name"], "Not documented", "Hard to change safely", "Write one paragraph: purpose, trigger, side effects")
    if w["trigger"].endswith("2024"): add("Medium", w["name"], "Looks like an expired campaign still active", "Enrols people for a finished event", "Confirm with owner, then turn off")
order = {"High": 0, "Medium": 1, "Low": 2}
findings.sort(key=lambda f: order[f["severity"]])
(OUT / "findings.json").write_text(json.dumps(findings, indent=2))
PLAN = [("Hours 1-4", "Inventory every workflow, owner, trigger, object and what it changes. Read only, change nothing."),
        ("Hours 5-8", "Reproduce the top issues on a test contact. Rank by customer impact."),
        ("Hours 9-14", "Fix the highest-priority one (duplicate or inappropriate email). Test each path, write the result down."),
        ("Hours 15-18", "Add error alerts and a weekly workflow health check. Check n8n backups, updates and restore steps."),
        ("Hours 19-20", "Handover note: what changed, what is still risky, proposal for the first supervised AI pilot.")]
cnt = {s: sum(1 for f in findings if f["severity"] == s) for s in order}
color = {"High": "#c93a3a", "Medium": "#d9a400", "Low": "#6b7685"}
rows = "".join(f"<tr><td style='color:{color[f['severity']]};font-weight:600'>{f['severity']}</td><td>{html.escape(f['workflow'])}</td><td>{html.escape(f['issue'])}</td><td>{html.escape(f['why'])}</td><td>{html.escape(f['fix'])}</td></tr>" for f in findings)
plan = "".join(f"<tr><td><b>{a}</b></td><td>{html.escape(b)}</td></tr>" for a, b in PLAN)
(OUT / "audit.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Automation takeover audit (demo)</title>
<style>body{{font:15px system-ui;margin:32px;max-width:1100px;color:#1c2430;background:#f6f7f9}}h1{{font-size:22px;margin:0 0 4px}}h3{{margin:22px 0 8px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin:12px 0;font-size:13px}}
.cards{{display:flex;gap:12px;margin:14px 0}}.card{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:10px 16px}}.card b{{display:block;font-size:22px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #dfe3e8}}th,td{{padding:8px 11px;border-bottom:1px solid #eceff2;text-align:left;font-size:13px;vertical-align:top}}th{{background:#eef1f5}}</style>
<h1>Taking over an automation setup: audit and first 20 hours</h1><div>{len(WORKFLOWS)} workflows scanned ({len(act)} active)</div>
<div class=demo>Demo using a made-up workflow inventory. Shows the method, not a real client account.</div>
<div class=cards><div class=card><b>{cnt['High']}</b>high</div><div class=card><b>{cnt['Medium']}</b>medium</div><div class=card><b>{cnt['Low']}</b>low</div></div>
<table><tr><th>Severity</th><th>Workflow</th><th>Finding</th><th>Why it matters</th><th>Suggested fix</th></tr>{rows}</table>
<h3>First 20 hours</h3><table>{plan}</table>""")
print(cnt)
