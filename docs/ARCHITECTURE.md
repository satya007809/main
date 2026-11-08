# Bharati Investigation Desk – System Architecture

## 1. Overview

```
 iPhone (SwiftUI app)                     Backend (your server, HTTPS only)                       External
 ┌──────────────────────┐   JWT over TLS  ┌──────────────────────────────────────────┐
 │ Dashboard / Cases     │ ─────────────► │ FastAPI REST API  (/api/v1)               │
 │ New case + folder link│                │  ├─ auth (scrypt, JWT + rotating refresh) │
 │ Inventory / Findings  │ ◄───────────── │  ├─ cases, documents, notes, audit        │
 │ Notes & verification  │   JSON / DOCX  │  ├─ connectors (OAuth, PKCE)  ───────────────► Google Drive API
 │ Reports + share sheet │                │  ├─ analyses / reports / playbooks        │──► Microsoft Graph (OneDrive)
 │ Playbook admin        │                │  └─ durable job queue (DB-backed)         │
 │ Keychain tokens only  │                │ Workers                                    │
 │ Offline cache+outbox  │                │  ├─ scan: walk folder → download → ZIP    │
 └──────────────────────┘                │  │    expand → dedupe → extract → classify│
        │ ASWebAuthenticationSession      │  ├─ analyze: digests → synthesis →        │──► Claude API (server-side key)
        └──────── OAuth consent ─────────►│  │    validation → repair pass            │
                                          │  └─ report: draft → DOCX → page check→PDF │──► LibreOffice (page count, PDF)
                                          │ PostgreSQL  ·  Encrypted file store        │
                                          └──────────────────────────────────────────┘
```

* **No secrets on the phone.** The app only holds its own session tokens (Keychain, this-device-only).
  The Claude API key and Google/Microsoft OAuth tokens live on the server; provider tokens are
  Fernet-encrypted in the database.
* **Modular**: connectors (`app/connectors/*`), extractors (`app/extraction/*`), AI client
  (`app/llm/client.py`), playbooks (database, editable), report templates (`app/reports/templates/*.yaml`
  + optional reference DOCX) are independent. New providers implement `CloudConnector`; new AI models are a
  setting; new case categories are a playbook YAML + a template YAML.

## 2. Processing pipeline

| Stage | Module | Behaviour |
|---|---|---|
| Folder link | `connectors/registry.py` | Detect provider, parse folder id, verify the user's connected account can read it |
| Recursive scan | `ingestion/scanner.py` | Walk every sub-folder (shortcuts resolved, loop-safe), download, export Google Docs/Sheets to DOCX/XLSX |
| Storage | `storage.py` | Every original stored Fernet-encrypted (`cases/<id>/docs/…`) |
| ZIP expansion | `scanner._expand_zip` | Nested ZIPs up to depth 4, zip-bomb limits, encrypted members flagged, path kept as `a.zip!/inner.zip!/Folder` |
| Dedupe | SHA-256 | Identical content marked `duplicate` with a pointer to the original |
| Extraction | `extraction/extractors.py` | PDF text layer per page; scanned pages rendered at 200 dpi → OCR; DOCX paragraphs+tables; XLSX per sheet; images (EXIF date/GPS/device kept); TXT/EML; legacy DOC/XLS/PPTX via LibreOffice |
| OCR + translation | `extraction/ocr.py` | Claude vision returns original-script transcription + English translation + neutral visual description for photos (Telugu, Kannada, Hindi, Tamil, Marathi…). Tesseract optional |
| Classification | `extraction/classifier.py` | Deterministic rules on filename + text (30 document types), refined by the AI digest, correctable by the user |
| Problem reporting | statuses | `password_protected`, `corrupted`, `unsupported`, `unreadable`, `partial`, `error` – never silently skipped; shown in inventory and in the report annexure |

Resumability: each file is a `Document` row; a scan job skips files already in a final state, and stale
running jobs are re-queued by the worker (`jobs/queue.py: recover_stale`).

## 3. Investigation engine

1. **Playbook composition** – `global_rules` + the case category playbook + any additional aspects
   (hire & reward, close proximity, vehicle modification, policy breach, road accident). Versions used are
   recorded on every analysis run.
2. **Per-document digest** (cached by content hash + corrections) – faithful facts with page numbers.
3. **Synthesis** – one structured-output call with: case particulars, full inventory (including problem
   files), investigator notes/verification results/corrections, all digests, full text within budget, and up
   to 24 photographs as images (for damage-pattern examination with EXIF). Documents are fenced as
   evidence; embedded instructions are ignored and reported as anomalies.
4. **Validation** (`engine/validation.py`, deterministic):
   * every citation must exist and the page must exist;
   * verified facts need a document or a verification note; field verifications must cite a note;
   * external sources (Timeline, FASTag, hospital, police, RTO, weather…) can only be "verified" if a record or
     note is cited;
   * definite opinions need sourced decisive evidence; repudiation needs established facts or a clause;
   * warnings for "genuine" with unresolved material discrepancies, missing required documents, missing wording.
5. **Repair pass** – if validation fails, the model gets the errors once and must re-source or drop claims.
   Remaining errors block report generation.

Output (see `engine/schema.py`): findings categorised as verified fact / documentary evidence / claimant
statement / third-party statement / technical observation / field verification / AI inference; chronology;
discrepancies (both versions sourced); playbook checklist; question answers; photo observations; external
checks; pending verifications; policy clauses (quoted, sourced); anomalies; opinion
(`genuine_admissible | not_genuine_or_breach_established | insufficient_evidence`).

## 4. Report generation

`reports/generator.py`: drafting call (word budget = page limit × 300 words minus tables) → unsupported
verification-claim scan (redraft if found) → DOCX via python-docx (Times New Roman 13, 1.5 spacing, A4) →
LibreOffice PDF to count pages → condense and rebuild if above the limit (max 10). Chronology, discrepancy,
pending-verification and documents-examined tables are rendered from the validated analysis, not from model
prose. The opinion heading prints the fixed verdict sentence from the global rules so the report cannot
contradict the analysis. Signature/invoice data come only from the investigator profile and the case invoice
fields; generation fails with a list of missing invoice fields rather than inventing them. If a reference
DOCX (e.g. `OD_report.docx`) is uploaded for the category, its header/footer/letterhead/styles/margins are
used as the base document.

## 5. Database schema (PostgreSQL; migration `alembic/versions/0001_initial_schema.py`)

| Table | Purpose / key columns |
|---|---|
| `users` | email, scrypt hash, is_admin, `investigator_profile` (JSON: name, firm, licence, GSTIN, bank…) |
| `refresh_sessions` | hashed single-use refresh tokens, expiry, revoked |
| `connector_accounts` | provider, account email, encrypted refresh/access token, scopes |
| `oauth_states` | PKCE verifier + state (15-minute life) |
| `cases` | particulars, category, `additional_aspects`, source provider/link/folder id, status, page limit, invoice JSON, retention days |
| `documents` | `ref` (D001…), parent (ZIP), origin, source id/path/filename, sha256, storage key, status + detail, duplicate_of, doc type (+confidence, corrected flag), languages, pages, metadata (EXIF/PDF info) |
| `document_pages` | page no/label, method (text_layer / ocr_vision / native), original text, English text, visual description, legible, user correction |
| `document_digests` | cached AI digest per document + cache key |
| `case_notes` | `ref` (N001…), kind (field observation, hospital/police/RTO/FASTag/GPS verification, correction, instruction), verified by/on, `client_uuid` (offline idempotency) |
| `playbooks` / `playbook_versions` | key, kind, active version / immutable YAML versions with change notes |
| `reference_templates` | uploaded reference DOCX per category |
| `analysis_runs` | run no, playbooks used (key+version), document/note refs, result JSON, validation, model, usage |
| `report_versions` | version, analysis run, DOCX/PDF keys, page count/limit, draft text, warnings, drive file id |
| `jobs` | kind, status, progress, message, attempts, heartbeat |
| `audit_logs` | who/when/what (case, action, detail, IP) |

## 6. Security & privacy

* TLS everywhere (HSTS header; deploy behind HTTPS proxy). JWT access tokens (30 min) + rotating single-use
  refresh tokens (30 days), hashed at rest.
* Cases are private to their owner; every endpoint checks ownership (admins get no implicit access).
* Files and OAuth tokens encrypted at rest (Fernet; replaceable with KMS-backed object storage).
* Least-privilege Google scopes: `drive.readonly` + `drive.file`; folders are never re-shared or made public.
  Disconnect revokes the Google token and deletes stored tokens.
* Case documents are sent only to the Claude API for analysis; no other third party receives case content.
  Under Anthropic's commercial API terms, inputs are not used for model training by default – confirm the
  current terms and data-retention options for your account before going live.
* Controlled deletion (`DELETE /cases/{id}?confirm=<claim no.>`), "delete stored copies" while keeping
  findings, per-case retention with `python -m app.cli purge-expired` (schedule daily).
* Audit trail for logins, scans, downloads, corrections, analyses (with playbook versions), reports.
* iOS: Keychain `WhenUnlockedThisDeviceOnly`, files written with `.completeFileProtection`, no URL cache,
  optional Face ID lock, sign-out wipes cached cases.
* Prompt-injection defence: documents fenced as evidence, explicit guard in every prompt, anomalies surfaced,
  and deterministic validation independent of the model.
