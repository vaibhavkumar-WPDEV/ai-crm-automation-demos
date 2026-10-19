# AI & CRM automation demos

Small, runnable demos of automation patterns I use: **AI reads or drafts, a person approves before anything is posted or sent.**
All demos use made-up sample data and plain Python (no API keys). They are demos, not client work.

| Demo | What it shows |
|---|---|
| [invoice-approval-workflow](invoice-approval-workflow) | Invoices from email/WhatsApp -> extracted fields -> duplicate/missing checks -> approval -> ledger |
| [message-review-desk](message-review-desk) | Text intake -> guardrails (STOP, emergency, legal) -> human review queue |
| [ops-dashboard](ops-dashboard) | Task sheet -> status roll-up -> plain-English summary |
| [hubspot-followup-debugger](hubspot-followup-debugger) | Reproduce and fix "reschedules but still gets follow-up email" (illustrative simulation) |
| [crm-email-ai-triage](crm-email-ai-triage) | Email classification + extraction + grounded draft + approval + CRM update |
| [automation-audit](automation-audit) | Takeover audit of a workflow inventory + first 20 hours plan |
| [listing-feed-sync](listing-feed-sync) | Listing feed import by unique ID, no duplicates, safe removals, abort on bad feed |

## Run any demo
```
cd <demo-folder>
python3 run.py
```
Open the generated HTML in `output/`. Screenshots are in each demo's `screenshots/` folder.

Author: Vaibhav Kumar
