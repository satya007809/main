# Test plan

## Automated (backend) – `cd backend && python -m pytest`

The synthetic Own Damage folder (`tests/synthetic_case.py`, all names fictitious) contains: policy schedule PDF
in a sub-folder, claim form DOCX, driver statement DOCX with a conflicting accident time, RC PDF, a **scanned**
DL PDF (image only → OCR path), photographs with EXIF date/GPS (one dated before policy inception), an exact
duplicate photo, a job-card XLSX, `additional_documents.zip` → `inner_docs.zip` → towing bill + a
Telugu FIR image, a password-flagged ZIP member, a password-protected PDF, a corrupted PDF, an MP4, and a text
file containing a prompt-injection attempt.

| Test | Verifies |
|---|---|
| `test_full_od_workflow` | create case → recursive scan → statuses for duplicate / password / corrupted / unsupported / container; nested ZIP paths; EXIF kept; Telugu original + English translation; idempotent rescan; offline-note idempotency; analysis with OD playbook (+ repair of an invalid citation); hospital verification only via note; injection text only inside fenced evidence; DOCX opens, TNR 13 / 1.5 spacing, headings, verdict sentence, discrepancy table, invoice totals with GST; unsupported "verified FASTag" sentence removed by redraft; page limit; report versioning; audit trail; dashboard and search |
| `test_upload_additional_evidence` | iPhone upload path, client-UUID de-duplication, background extraction, document-type and page-text corrections |
| `test_report_blocked_without_invoice_details` | invoice amounts are never invented – generation fails listing missing fields |
| `test_units.py` | citation/page validation, verified-fact rules, external-check rules, opinion rules, unsupported-verification detection, all default playbooks valid, playbook validation errors, Drive/OneDrive link parsing, path-traversal protection, file sniffing, classifier |
| `test_security_and_resilience.py` | auth required, case isolation between users, admin-only playbook edits, refresh-token rotation, wrong password, files encrypted on disk, purge copies, confirmed deletion, interrupted scan resumes without re-downloading, stale jobs re-queued, playbook versioning/activation/rejection |

The tests use a deterministic stand-in for Claude (`tests/fake_llm.py`) so they are free and repeatable; it
lives only in `tests/`. No sample case results are hard-coded in the application.

## Live-AI acceptance (run before relying on reports)

1. `python scripts/demo_vertical_slice.py out --real` with `ANTHROPIC_API_KEY` set; open the DOCX in Word on
   iPhone and desktop.
2. Run 3–5 of your **closed** real cases (where you know the right outcome) per category. For each check:
   every citation opens the right page; no unverified external check is described as verified; discrepancies
   you know about are listed; the opinion matches yours or the difference is explainable; page count within
   limit; formatting matches your reference report.
3. Multilingual: include scanned Telugu/Kannada/Hindi FIRs, PM reports, statements; compare translations of
   names, dates and registration numbers against the originals.
4. Tune playbooks (Admin) and rerun; keep a log of playbook versions vs. results.

## Manual iPhone checklist

* Sign in, Face ID lock on/off, sign out wipes cached data.
* Connect Google Drive (ASWebAuthenticationSession), paste a folder link, scan; close the app mid-scan and
  reopen – progress resumes.
* Airplane mode: open cached cases, add a field note and photos → "waiting to sync" → reconnect → synced once.
* Inventory filters, document detail (original vs English), correct a page, change document type.
* Findings tabs; tap a source chip → correct document page opens.
* Generate report; Preview; Share → Open in Word; Save to Files; Upload to case folder (appears in Drive).
* Regenerate with page limit 10 → version 2 kept alongside version 1.
* Admin: edit a playbook, save, rerun analysis, confirm the new version appears in Run details.

## Security checks before go-live

* HTTPS only; `/docs` disabled in production; `BID_ALLOW_REGISTRATION=false`.
* Verify a second account cannot read your cases (covered by tests; repeat on the deployed server).
* Disconnect Google Drive in the app → confirm the app disappears from https://myaccount.google.com/permissions.
* Restore test of database + storage + encryption key backups.
