"""Email -> classify -> extract -> grounded draft -> human approval -> CRM update.

Rule-based so it runs with no API key; `call_llm()` marks where a model goes.
Covers wrong outputs (confidence gate), missing info (asks, never invents) and
failed steps (retry, then manual queue). CRM is a dict standing in for HubSpot.
"""
import html, json, pathlib, re
OUT = pathlib.Path(__file__).parent / "output"; OUT.mkdir(exist_ok=True)

CRM = {"anna@sampleco.test": {"name": "Anna Lee", "company": "SampleCo", "stage": "Discovery"},
       "raj@demo-retail.test": {"name": "Raj Mehta", "company": "Demo Retail", "stage": "Proposal"}}
APPROVED_SNIPPETS = {  # the only facts a draft may use
    "pricing": "Our plans start with a fixed-scope pilot. A team member will send a quote after a short call.",
    "support": "Thanks for flagging this. Our support team will review it and reply within one business day.",
    "meeting": "Happy to find a time. Could you share two slots that suit you?",
}
EMAILS = [
 {"id": "E1", "from": "anna@sampleco.test", "subject": "Pricing for the pilot", "body": "Hi, can you send pricing? We have around 25 users and want to start by 15 Nov."},
 {"id": "E2", "from": "raj@demo-retail.test", "subject": "Can't log in", "body": "Our team has been locked out since this morning, this is urgent."},
 {"id": "E3", "from": "new@unknown.test", "subject": "Quick call?", "body": "Would love to talk about your service sometime."},
 {"id": "E4", "from": "anna@sampleco.test", "subject": "Re: invoice", "body": "asdf ???"},
 {"id": "E5", "from": "raj@demo-retail.test", "subject": "Meeting next week", "body": "Can we meet Tuesday or Thursday? Budget is approved at $12k."},
]
FAIL_ONCE = {"E5"}  # simulate one transient failure to show retry
_seen = set()

def call_llm(email):
    """Plug point: classification + extraction by an LLM returning the same shape."""
    t = (email["subject"] + " " + email["body"]).lower()
    if any(w in t for w in ["pricing", "quote", "price"]): cat, conf = "pricing", 0.92
    elif any(w in t for w in ["log in", "locked", "error", "bug"]): cat, conf = "support", 0.95
    elif any(w in t for w in ["meet", "call", "talk"]): cat, conf = "meeting", 0.7 if "sometime" in t else 0.9
    else: cat, conf = "unclear", 0.3
    f = {}
    m = re.search(r"(\d+)\s*users", t); f["users"] = int(m.group(1)) if m else None
    m = re.search(r"\$(\d+)k", t); f["budget_usd"] = int(m.group(1)) * 1000 if m else None
    m = re.search(r"by (\d+ \w+)", t); f["start_by"] = m.group(1) if m else None
    f["urgent"] = "urgent" in t
    return {"category": cat, "confidence": conf, "fields": {k: v for k, v in f.items() if v}}

def with_retry(email, tries=2):
    for i in range(tries):
        if email["id"] in FAIL_ONCE and email["id"] not in _seen:
            _seen.add(email["id"]); log.append(f"{email['id']}: AI step failed (timeout), retry {i+1}"); continue
        return call_llm(email)
    return None

log, rows = [], []
APPROVED = {"E1", "E2", "E5"}   # reviewer decisions (the human step)
for e in EMAILS:
    r = with_retry(e)
    contact = CRM.get(e["from"])
    flags = []
    if r is None: flags.append("AI step failed twice, sent to manual queue")
    else:
        if r["confidence"] < 0.8: flags.append(f"Low confidence ({r['confidence']}), human decides")
        if r["category"] == "unclear": flags.append("Could not classify")
    if not contact: flags.append("Sender not in CRM, no record updated until a person matches/creates it")
    missing = []
    if r and r["category"] == "pricing":
        missing = [k for k in ("users", "start_by") if k not in r["fields"]]
        if missing: flags.append("Missing: " + ", ".join(missing))
    draft = APPROVED_SNIPPETS.get(r["category"]) if r else None
    needs_human = bool(flags)
    status = ("Needs human" if needs_human else ("Approved, CRM updated" if e["id"] in APPROVED else "Waiting approval"))
    if e["id"] in APPROVED and needs_human and r and contact and r["confidence"] >= 0.8 and not missing:
        status = "Approved, CRM updated"
    rows.append({"id": e["id"], "from": e["from"], "subject": e["subject"], "result": r, "draft": draft if r and r["category"] != "unclear" else None,
                 "contact": contact, "flags": flags, "status": status})
updates = [{"contact": r["from"], "note": f"AI summary: {r['subject']} ({r['result']['category']})", **r["result"]["fields"]}
           for r in rows if r["status"].startswith("Approved") and r["result"]]
(OUT / "crm_updates.json").write_text(json.dumps(updates, indent=2))
(OUT / "log.json").write_text(json.dumps({"rows": rows, "events": log}, indent=2))

cls = {"Approved, CRM updated": "ok", "Waiting approval": "wait", "Needs human": "stop"}
cards = ""
for r in rows:
    res = r["result"]
    fields = ", ".join(f"{k}: {v}" for k, v in (res["fields"].items() if res else [])) or "none"
    flags = "".join(f"<span class=flag>{html.escape(x)}</span>" for x in r["flags"])
    cards += f"""<div class=row><div><b>{r['id']}</b> {html.escape(r['from'])} <span class='b {cls[r['status']]}'>{r['status']}</span></div>
<div class=sub2>{html.escape(r['subject'])}</div>
<div class=meta>Category: {res['category'] if res else '-'} ({res['confidence'] if res else '-'}) | Extracted: {html.escape(fields)} | CRM: {html.escape(r['contact']['company']+' / '+r['contact']['stage']) if r['contact'] else 'not found'}</div>
<div class=draft>{('Draft from approved text: ' + html.escape(r['draft'])) if r['draft'] else 'No draft (not enough to answer safely)'}</div><div>{flags}</div></div>"""
(OUT / "triage.html").write_text(f"""<!doctype html><meta charset=utf-8><title>CRM email triage (demo)</title>
<style>body{{font:15px system-ui;margin:32px;max-width:940px;color:#1c2430;background:#f6f7f9}}h1{{font-size:22px;margin:0 0 4px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin:12px 0;font-size:13px}}
.row{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:12px 14px;margin-bottom:10px}}.sub2{{font-weight:600;margin:4px 0}}.meta{{color:#5b6573;font-size:13px}}
.draft{{background:#eef3fb;border-radius:6px;padding:6px 10px;margin:6px 0;font-size:14px}}.b{{padding:2px 9px;border-radius:12px;font-size:12px;margin-left:8px}}
.ok{{background:#d9f2e1;color:#14663a}}.wait{{background:#fff0c9;color:#7a5a00}}.stop{{background:#fbdada;color:#8a1f1f}}
.flag{{background:#fbdada;color:#8a1f1f;border-radius:4px;padding:2px 7px;font-size:12px;margin-right:8px;display:inline-block;margin-top:2px}}
.log{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:8px 14px;font-size:13px;color:#5b6573}}</style>
<h1>Email triage into the CRM</h1><div>Email in -> classify -> extract -> draft from approved text -> person approves -> CRM updated</div>
<div class=demo>Demo with made-up emails and a fake in-memory CRM. Classifier is rule based; no live HubSpot or AI provider connected.</div>
{cards}<div class=log><b>Step failures handled:</b> {html.escape('; '.join(log)) or 'none'}</div>""")
for r in rows: print(r["id"], "|", r["status"], "|", "; ".join(r["flags"]) or "ok")
