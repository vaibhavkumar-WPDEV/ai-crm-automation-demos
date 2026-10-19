"""Invoice approval workflow demo.

Flow: incoming invoice text -> extract fields -> flag problems -> approval queue
-> ledger. NOTHING reaches the ledger until a person approves it.

The extractor here is rule-based so the demo runs with no API key. The place
where an LLM call would go is `extract_with_llm()`; the checks and the approval
gate around it stay the same.
"""
import csv
import html
import json
import pathlib
import re

BASE = pathlib.Path(__file__).parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# Fake sample data. No real vendors, people or amounts.
INVOICES = [
    {"id": "INV-A", "source": "email",
     "text": "From: Sample Plumbing Co\nInvoice #: 4471\nDate: 2026-10-02\nProperty: Maple Court Unit 4\nDescription: Replace kitchen tap, labour and parts\nTotal: $186.50"},
    {"id": "INV-B", "source": "whatsapp",
     "text": "From: Demo Electric Ltd\nInvoice #: 1029\nDate: 2026-10-05\nProperty: Harbour View 12B\nDescription: Smoke alarm battery check\nTotal: $95.00"},
    {"id": "INV-C", "source": "email",
     "text": "From: Sample Plumbing Co\nInvoice #: 4471\nDate: 2026-10-02\nProperty: Maple Court Unit 4\nDescription: Replace kitchen tap, labour and parts\nTotal: $186.50"},
    {"id": "INV-D", "source": "email",
     "text": "From: Example Cleaning Services\nDate: 2026-10-07\nDescription: End of tenancy clean\nTotal: $240.00"},
]
# Decisions made by the bookkeeper (the human step). Anything not listed stays pending.
DECISIONS = {"INV-A": "approved"}

CATEGORIES = {
    "Repairs": ["tap", "pipe", "repair", "replace", "leak"],
    "Electrical": ["smoke alarm", "electric", "wiring"],
    "Cleaning": ["clean"],
}
REQUIRED = ["vendor", "invoice_no", "date", "property", "total"]


def extract_with_llm(text):
    """Plug point for an LLM. Same output shape as extract_rules()."""
    raise NotImplementedError("Demo runs without an API key; see extract_rules().")


def extract_rules(text):
    def grab(label):
        m = re.search(rf"^{label}:\s*(.+)$", text, re.M | re.I)
        return m.group(1).strip() if m else None

    total = grab("Total")
    return {
        "vendor": grab("From"),
        "invoice_no": grab(r"Invoice #"),
        "date": grab("Date"),
        "property": grab("Property"),
        "description": grab("Description"),
        "total": float(total.replace("$", "").replace(",", "")) if total else None,
    }


def categorise(desc):
    d = (desc or "").lower()
    for cat, words in CATEGORIES.items():
        if any(w in d for w in words):
            return cat
    return "Uncategorised"


def process():
    rows, seen = [], {}
    for inv in INVOICES:
        f = extract_rules(inv["text"])
        missing = [k for k in REQUIRED if not f.get(k)]
        key = (f.get("vendor"), f.get("invoice_no"))
        notes = []
        if missing:
            notes.append("Missing: " + ", ".join(missing))
        if f.get("invoice_no") and key in seen:
            notes.append(f"Possible duplicate of {seen[key]}")
        elif f.get("invoice_no"):
            seen[key] = inv["id"]
        if notes:
            state = "Needs human review"
        else:
            state = "Ready for approval"
        decision = DECISIONS.get(inv["id"])
        if decision == "approved" and state == "Ready for approval":
            state = "Approved, posted to ledger"
        rows.append({"id": inv["id"], "source": inv["source"], **f,
                     "category": categorise(f.get("description")),
                     "state": state, "notes": "; ".join(notes)})
    return rows


def write_outputs(rows):
    (OUT / "queue.json").write_text(json.dumps(rows, indent=2))
    with open(OUT / "ledger.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "vendor", "invoice_no", "date", "property", "category", "total"])
        for r in rows:
            if r["state"].startswith("Approved"):
                w.writerow([r[k] for k in ["id", "vendor", "invoice_no", "date", "property", "category", "total"]])

    badge = {"Approved, posted to ledger": "ok", "Ready for approval": "wait", "Needs human review": "stop"}
    body = ""
    for r in rows:
        total = f"${r['total']:.2f}" if r["total"] is not None else "-"
        body += (
            "<tr>"
            f"<td>{r['id']}</td><td>{html.escape(r['source'])}</td>"
            f"<td>{html.escape(r['vendor'] or '-')}</td><td>{html.escape(r['invoice_no'] or '-')}</td>"
            f"<td>{html.escape(r['property'] or '-')}</td><td>{r['category']}</td><td>{total}</td>"
            f"<td><span class='b {badge[r['state']]}'>{r['state']}</span></td>"
            f"<td>{html.escape(r['notes']) or '-'}</td></tr>"
        )
    posted = sum(1 for r in rows if r["state"].startswith("Approved"))
    page = f"""<!doctype html><meta charset=utf-8><title>Invoice approval queue (demo)</title>
<style>
body{{font:15px system-ui;margin:32px;color:#1c2430;background:#f6f7f9}}
h1{{margin:0 0 4px;font-size:22px}} .sub{{color:#5b6573;margin-bottom:18px}}
.demo{{background:#fff7e0;border:1px solid #ecd28a;padding:8px 12px;border-radius:6px;margin-bottom:18px;font-size:13px}}
.cards{{display:flex;gap:12px;margin-bottom:18px}}
.card{{background:#fff;border:1px solid #dfe3e8;border-radius:8px;padding:12px 18px}}
.card b{{display:block;font-size:24px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #dfe3e8}}
th,td{{padding:9px 11px;border-bottom:1px solid #eceff2;text-align:left;font-size:13px;vertical-align:top}}
th{{background:#eef1f5}} .b{{padding:3px 9px;border-radius:12px;font-size:12px;white-space:nowrap}}
.ok{{background:#d9f2e1;color:#14663a}} .wait{{background:#fff0c9;color:#7a5a00}} .stop{{background:#fbdada;color:#8a1f1f}}
</style>
<h1>Invoice approval queue</h1>
<div class=sub>Email and WhatsApp invoices -> extracted fields -> checks -> person approves -> ledger</div>
<div class=demo>Demo with made-up sample data. Not a client's records.</div>
<div class=cards>
<div class=card><b>{len(rows)}</b>invoices in</div>
<div class=card><b>{posted}</b>posted after approval</div>
<div class=card><b>{sum(1 for r in rows if r['state']=='Needs human review')}</b>need a person to look</div>
</div>
<table><tr><th>ID</th><th>Source</th><th>Vendor</th><th>Invoice #</th><th>Property</th><th>Category</th><th>Total</th><th>Status</th><th>Notes</th></tr>{body}</table>"""
    (OUT / "dashboard.html").write_text(page)


if __name__ == "__main__":
    rows = process()
    write_outputs(rows)
    for r in rows:
        print(r["id"], "|", r["state"], "|", r["notes"] or "ok")
