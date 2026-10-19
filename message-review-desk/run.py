"""Message intake + guardrails + human review desk demo.

Flow: inbound text -> structured fields saved -> draft reply -> guardrail check
-> review queue (approve / edit / reject / escalate). Nothing is sent until a
person approves. Consent and STOP are honoured before anything else.

Drafting is template based so the demo runs with no API key. `draft_with_llm()`
marks where an LLM call goes; guardrails and the review gate stay the same.
"""
import html
import json
import pathlib
import re

BASE = pathlib.Path(__file__).parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# Made-up test conversations. No real people.
MESSAGES = [
    {"id": "M1", "from": "+1 555 0101", "text": "Hi, I'm looking for a quote on a 3 bedroom renovation in Austin. Budget around 40k."},
    {"id": "M2", "from": "+1 555 0102", "text": "STOP"},
    {"id": "M3", "from": "+1 555 0103", "text": "Was it my fault? Should I sue them? Tell me what to do legally."},
    {"id": "M4", "from": "+1 555 0104", "text": "I need help right now, I am hurt and scared"},
    {"id": "M5", "from": "+1 555 0105", "text": "Do you do bathroom remodels? I can start next month."},
    {"id": "M6", "from": "+1 555 0106", "text": "wrong number"},
]
# Reviewer actions (the human step). Missing id = still waiting in queue.
REVIEW = {"M1": ("approved", "unchanged"), "M5": ("approved", "edited: added booking link")}

OPT_OUT = {"stop", "unsubscribe", "cancel", "quit"}
EMERGENCY = ["hurt", "scared", "emergency", "help right now", "danger"]
LEGAL = ["fault", "sue", "legally", "legal advice", "lawsuit"]
FORBIDDEN_OUT = ["it was not your fault", "you will win", "guaranteed", "you should sue"]


def fields(text):
    t = text.lower()
    out = {}
    m = re.search(r"(\d+)\s*(?:bed|bedroom)", t)
    if m:
        out["bedrooms"] = int(m.group(1))
    m = re.search(r"(\d+)\s*k\b", t)
    if m:
        out["budget_usd"] = int(m.group(1)) * 1000
    for city in ["austin", "dallas", "houston"]:
        if city in t:
            out["city"] = city.title()
    if "bathroom" in t:
        out["service"] = "bathroom remodel"
    elif "renovation" in t:
        out["service"] = "renovation"
    if "next month" in t:
        out["timing"] = "next month"
    return out


def draft_with_llm(text, state):
    """Plug point for an LLM. Return reply text."""
    raise NotImplementedError


def draft(text, f):
    if f.get("service"):
        known = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in f.items())
        return (f"Thanks for the details ({known}). To prepare an estimate, "
                "could you share your postcode and a good time for a short call? "
                "This is an automated assistant; a team member reviews every reply.")
    return "Thanks for your message. Could you tell us a bit more about what you need?"


def route(m):
    t = m["text"].strip().lower()
    if t in OPT_OUT:
        return {"lane": "Opt-out", "draft": "", "flags": ["STOP honoured, no reply drafted"], "f": {}}
    f = fields(m["text"])
    if any(w in t for w in EMERGENCY):
        return {"lane": "Escalate", "draft": "", "flags": ["Possible emergency, alert a person now"], "f": f}
    if any(w in t for w in LEGAL):
        return {"lane": "Needs human", "draft": "I can't give legal advice, but a member of our team will contact you shortly.",
                "flags": ["Legal-advice request, guardrail blocked drafted advice"], "f": f}
    if t in {"wrong number", "wrong num"}:
        return {"lane": "Close", "draft": "", "flags": ["Wrong number, close thread"], "f": {}}
    d = draft(m["text"], f)
    flags = [g for g in FORBIDDEN_OUT if g in d.lower()]
    return {"lane": "Review", "draft": d, "flags": [f"Blocked phrase: {x}" for x in flags], "f": f}


def build():
    rows = []
    for m in MESSAGES:
        r = route(m)
        action = REVIEW.get(m["id"])
        if r["lane"] == "Review" and action:
            status = "Sent after approval"
            note = action[1]
        elif r["lane"] == "Review":
            status, note = "Waiting for reviewer", ""
        elif r["lane"] == "Opt-out":
            status, note = "Opted out", "no further texts"
        elif r["lane"] == "Escalate":
            status, note = "Escalated, alert sent", "email + Teams alert (simulated)"
        elif r["lane"] == "Close":
            status, note = "Closed", ""
        else:
            status, note = "Waiting for reviewer", "legal flag"
        rows.append({**m, **r, "status": status, "note": note})
    return rows


def render(rows):
    (OUT / "log.json").write_text(json.dumps(rows, indent=2))
    cls = {"Sent after approval": "ok", "Waiting for reviewer": "wait", "Opted out": "gray",
           "Escalated, alert sent": "stop", "Closed": "gray"}
    cards = ""
    for r in rows:
        flags = "".join(f"<span class='flag'>{html.escape(x)}</span>" for x in r["flags"])
        fl = ", ".join(f"{k}: {v}" for k, v in r["f"].items()) or "none"
        cards += f"""<div class=row>
<div class=head><b>{r['id']}</b> {html.escape(r['from'])} <span class='b {cls.get(r['status'],'wait')}'>{r['status']}</span></div>
<div class=msg>"{html.escape(r['text'])}"</div>
<div class=meta>Saved fields: {html.escape(fl)}</div>
<div class=draft>{('Draft: ' + html.escape(r['draft'])) if r['draft'] else 'No reply drafted'}</div>
<div>{flags}<span class=note>{html.escape(r['note'])}</span></div></div>"""
    sent = sum(1 for r in rows if r["status"] == "Sent after approval")
    unchanged = sum(1 for r in rows if r["note"] == "unchanged")
    page = f"""<!doctype html><meta charset=utf-8><title>Review desk (demo)</title>
<style>
body{{font:15px system-ui;margin:32px;color:#1c2430;background:#f6f7f9;max-width:900px}}
h1{{margin:0 0 4px;font-size:22px}}.sub{{color:#5b6573;margin-bottom:14px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin-bottom:16px;font-size:13px}}
.cards{{display:flex;gap:12px;margin-bottom:16px}}.card{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:10px 16px}}.card b{{display:block;font-size:22px}}
.row{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:12px 14px;margin-bottom:10px}}
.head{{margin-bottom:6px}}.msg{{font-style:italic;margin-bottom:4px}}.meta{{color:#5b6573;font-size:13px}}
.draft{{background:#eef3fb;border-radius:6px;padding:6px 10px;margin:6px 0;font-size:14px}}
.b{{padding:2px 9px;border-radius:12px;font-size:12px;margin-left:8px}}
.ok{{background:#d9f2e1;color:#14663a}}.wait{{background:#fff0c9;color:#7a5a00}}.stop{{background:#fbdada;color:#8a1f1f}}.gray{{background:#e6e9ee;color:#444}}
.flag{{background:#fbdada;color:#8a1f1f;border-radius:4px;padding:2px 7px;font-size:12px;margin-right:8px}}.note{{color:#5b6573;font-size:12px}}
</style>
<h1>Message review desk</h1>
<div class=sub>Inbound text -> fields saved -> draft -> guardrails -> person approves, edits, rejects or escalates</div>
<div class=demo>Demo with made-up test messages. Drafts are template based, no live SMS or AI provider is connected.</div>
<div class=cards><div class=card><b>{len(rows)}</b>messages</div><div class=card><b>{sent}</b>sent after approval</div>
<div class=card><b>{unchanged}/{sent}</b>drafts sent unchanged</div>
<div class=card><b>{sum(1 for r in rows if r['status'].startswith('Escalated'))}</b>escalated</div></div>
{cards}"""
    (OUT / "review_desk.html").write_text(page)


if __name__ == "__main__":
    rows = build()
    render(rows)
    for r in rows:
        print(r["id"], "|", r["status"], "|", "; ".join(r["flags"]) or "ok")
