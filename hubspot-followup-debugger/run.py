"""Reproduce and fix a classic CRM automation bug (illustrative simulation, not a HubSpot account).

Bug: contact books a discovery call -> enters follow-up workflow -> delay ->
contact reschedules or completes next step during the delay -> still gets the
"follow up" email. Cause: nothing re-checks state AFTER the delay.
Fix: unenrol/suppress on state change + re-check at send time + no duplicate enrolments.
"""
import html, json, pathlib
OUT = pathlib.Path(__file__).parent / "output"; OUT.mkdir(exist_ok=True)

# Each scenario: events that happen to the contact while the workflow sits in its delay.
SCENARIOS = [
    ("A", "Books call, nothing else happens", []),
    ("B", "Reschedules during the delay", ["rescheduled"]),
    ("C", "Completes the next step (call held) during the delay", ["call_completed"]),
    ("D", "Reschedules twice (re-enrols while first run still waiting)", ["rescheduled", "rescheduled"]),
    ("E", "Unsubscribes during the delay", ["unsubscribed"]),
]
# What the correct business outcome is for each scenario.
EXPECTED = {"A": 1, "B": 0, "C": 0, "D": 0, "E": 0}

def run(events, fixed):
    """Return list of emails sent. Models enrolment, delay, send."""
    state = {"status": "booked", "unsub": False}
    enrolments = [1]          # one enrolment from the original booking
    for e in events:
        if e == "rescheduled":
            state["status"] = "rescheduled"
            if not fixed:
                enrolments.append(1)      # re-enrolment allowed -> second run in parallel
            # fixed: re-enrolment off while active, old run is unenrolled by criteria
        elif e == "call_completed":
            state["status"] = "completed"
        elif e == "unsubscribed":
            state["unsub"] = True
    sent = []
    if fixed:
        # unenrolment criteria (status changed) + send-time re-check + suppression
        if state["status"] == "booked" and not state["unsub"]:
            sent.append("follow-up email")
    else:
        for _ in enrolments:
            sent.append("follow-up email")   # no re-check after delay
    return sent

rows, fails = [], {False: 0, True: 0}
for sid, desc, ev in SCENARIOS:
    b, f = run(ev, False), run(ev, True)
    okb, okf = len(b) == EXPECTED[sid], len(f) == EXPECTED[sid]
    fails[False] += not okb; fails[True] += not okf
    rows.append({"id": sid, "scenario": desc, "expected": EXPECTED[sid], "before": len(b), "after": len(f), "before_ok": okb, "after_ok": okf})
(OUT / "results.json").write_text(json.dumps(rows, indent=2))

INVESTIGATE = [
 "Open the contact's workflow history: which workflow sent it, which enrolment, timestamps.",
 "Check enrolment trigger and whether re-enrolment is ON (second run during first delay).",
 "Inspect the delay: does any branch or unenrolment criterion re-check meeting/deal/lifecycle status after it?",
 "Look for a second workflow with an overlapping trigger sending a similar email.",
 "Check the send action: marketing contact status, unsubscribe and suppression lists.",
 "Reproduce with a test contact for each path, then re-run after the fix and compare.",
]
body = "".join(f"<tr><td>{r['id']}</td><td>{html.escape(r['scenario'])}</td><td>{r['expected']}</td>"
  f"<td class={'ok' if r['before_ok'] else 'bad'}>{r['before']} email(s) {'PASS' if r['before_ok'] else 'FAIL'}</td>"
  f"<td class={'ok' if r['after_ok'] else 'bad'}>{r['after']} email(s) {'PASS' if r['after_ok'] else 'FAIL'}</td></tr>" for r in rows)
steps = "".join(f"<li>{html.escape(s)}</li>" for s in INVESTIGATE)
(OUT / "report.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Follow-up bug reproduction (demo)</title>
<style>body{{font:15px system-ui;margin:32px;max-width:980px;color:#1c2430;background:#f6f7f9}}h1{{font-size:22px;margin:0 0 4px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin:12px 0;font-size:13px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #dfe3e8}}th,td{{padding:9px 11px;border-bottom:1px solid #eceff2;text-align:left;font-size:13px}}th{{background:#eef1f5}}
.ok{{color:#14663a;font-weight:600}}.bad{{color:#a11f1f;font-weight:600}}.panel{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:6px 18px;margin-top:16px}}
.cards{{display:flex;gap:12px;margin:14px 0}}.card{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:10px 16px}}.card b{{display:block;font-size:22px}}</style>
<h1>Follow-up email sent after reschedule: reproduce, fix, test</h1>
<div>Discovery call booked -> 2 day delay -> follow-up email</div>
<div class=demo>Illustrative simulation in plain Python, not a real HubSpot account. Shows the investigation method and test matrix, not a delivered client project.</div>
<div class=cards><div class=card><b>{fails[False]}/{len(rows)}</b>scenarios wrong before fix</div><div class=card><b>{fails[True]}/{len(rows)}</b>scenarios wrong after fix</div></div>
<table><tr><th>#</th><th>What the contact does</th><th>Emails that should send</th><th>Before fix</th><th>After fix</th></tr>{body}</table>
<div class=panel><h3>Investigation order</h3><ol>{steps}</ol></div>
<div class=panel><h3>Fix applied in the model</h3><ul><li>Unenrolment criteria: meeting status no longer "booked", call completed, unsubscribed</li><li>Re-enrolment off while a run is active (no parallel runs)</li><li>If/then branch after the delay re-checks status before the send action</li></ul></div>""")
for r in rows: print(r["id"], "before:", r["before"], "after:", r["after"], "expected:", r["expected"])
