# Bharati Investigation Desk

AI-assisted insurance claim investigation for iPhone. Link a case folder (Google Drive, OneDrive designed
in), pick the case type, and the system reads every document – including nested ZIPs, scanned and
regional-language papers and photographs – applies the matching investigation playbook, separates verified
facts from statements and inferences, and prepares a concise, editable Word report in your format.

```
backend/   Python FastAPI API, workers, investigation engine, playbooks, DOCX reports, tests
ios/       Native SwiftUI iPhone app (XcodeGen project)
docs/      Architecture, setup & deployment, iOS/TestFlight, playbooks, test plan, OpenAPI spec
```

## Workflow

Dashboard → New Investigation → case details → paste folder link → case type → scan → review inventory →
add field notes / verification results → run investigation → review findings (sources, chronology,
discrepancies, pending verifications, policy clauses, opinion) → generate Word report → preview / open in
Word / save to Files / upload back to the case folder. Rerun and regenerate at any time; every analysis and
report version is kept.

## Status by phase

| Phase | Scope | Status |
|---|---|---|
| 1 – Working application | iPhone app, Google Drive connection, recursive reading incl. ZIPs, extraction/OCR, Own Damage playbook, validated analysis, editable DOCX | **Built and tested** (backend: automated tests with a stand-in AI; iOS: code complete, compile on a Mac) |
| 2 – Investigation intelligence | PA Death, PA Injury, Theft, Fire, Road Accident and special-aspect playbooks, policy-clause analysis, multilingual OCR, evidence comparison | **Playbooks and engine features included**; need tuning against your real closed cases |
| 3 – Production system | OneDrive, reference-format templates, invoices, history/audit, offline drafts, security hardening, TestFlight | **Implemented**; OneDrive connector not yet tested against a live account; deployment and TestFlight steps documented |

## Two ways to run the AI

* **Claude-plan mode** (`BID_AI_MODE=claude_code`, recommended if you already have Claude Max): no API
  charges. You run the investigation in Claude Code with the bundled `investigate-case` skill, and the
  server validates the results and builds the report. See `docs/CLAUDE_CODE_MODE.md`.
* **API mode** (`BID_AI_MODE=api`): one tap in the app, billed per use through the Claude API.

## Quick start

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest
```

```bash
python scripts/demo_vertical_slice.py ./demo_output
```

Then see `docs/SETUP_AND_DEPLOYMENT.md` (server, Google OAuth, Claude API key) and
`docs/IOS_BUILD_AND_TESTFLIGHT.md` (Xcode, signing, TestFlight).

## Design principles

* **Evidence first** – every finding carries document + page citations; a deterministic validator rejects
  unknown citations, unverified external checks and unsupported opinions before a report can be generated.
* **No fabrication** – investigator details, invoice amounts and verification results come only from what you
  enter. External sources stay "pending" until a record or your verification note exists.
* **Your logic, editable** – investigation playbooks are versioned YAML edited from the app's Admin section.
* **Private by design** – no secrets on the phone, encrypted storage and tokens, per-user case isolation,
  audit trail, retention controls, documents treated as untrusted evidence.
