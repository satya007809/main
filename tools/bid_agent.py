#!/usr/bin/env python3
"""Bharati Investigation Desk – command-line bridge for Claude Code (uses your Claude plan, no API key).

Environment:
  BID_SERVER_URL   e.g. https://api.your-domain.in
  BID_AGENT_TOKEN  token created in the iPhone app: Settings -> Claude Code access
                   (in a Claude Code cloud environment you can instead save it as a network secret for the
                   server host; the proxy then injects it and this variable can be any placeholder)

Commands:
  find <text>                                   search cases by claim no., vehicle, insured, insurer
  package <case_id> [--out DIR]                 download instructions + evidence into DIR (default ./work/<case_id>)
  page-image <document_id> <page_no> <out.jpg>  download a scanned page / photo to read
  read-page <document_id> <page_no> <reading.json>
                                                upload your transcription of that page
  submit-analysis <case_id> <analysis.json>     submit the analysis; prints validation result
  submit-report <case_id> <draft.json> [--run RUN_ID] [--pages N]
                                                submit report text; prints result or what to fix
  download-report <report_id> <out.docx>        download the generated Word report
Exit code 0 = accepted, 2 = rejected with fixable problems (details printed as JSON), 1 = other error.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _base() -> str:
    url = os.environ.get("BID_SERVER_URL", "").rstrip("/")
    if not url:
        sys.exit("Set BID_SERVER_URL (your Bharati server address)")
    return url + "/api/v1"


def _req(method: str, path: str, body=None, raw: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_base() + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + os.environ.get("BID_AGENT_TOKEN", "bid_at_placeholder"))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            payload = r.read()
            return payload if raw else json.loads(payload or b"{}")
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(text)
        except json.JSONDecodeError:
            detail = {"detail": text}
        if e.code == 422 or (e.code == 409 and "pending_pages" in text):
            print(json.dumps(detail, indent=1, ensure_ascii=False))
            sys.exit(2)
        sys.exit(f"HTTP {e.code}: {json.dumps(detail, ensure_ascii=False)[:2000]}")


def _flag(args: list[str], name: str, default=None):
    if name in args:
        i = args.index(name)
        val = args[i + 1]
        del args[i:i + 2]
        return val
    return default


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "find":
        q = urllib.parse.quote(" ".join(args))
        for c in _req("GET", f"/cases?q={q}"):
            print(f"{c['id']}  {c['claim_number']:<22} {c['vehicle_registration']:<14} {c['insured_name']:<28} "
                  f"{c['category']:<12} {c['status']}")
    elif cmd == "package":
        out = Path(_flag(args, "--out") or f"work/{args[0]}")
        out.mkdir(parents=True, exist_ok=True)
        pkg = _req("GET", f"/cases/{args[0]}/analysis-package")
        ins = pkg.pop("instructions")
        (out / "1_analysis_instructions.md").write_text(ins["analysis_system_prompt"], encoding="utf-8")
        (out / "analysis_schema.json").write_text(json.dumps(ins["analysis_schema"], indent=1), encoding="utf-8")
        (out / "page_reading_instructions.md").write_text(ins["page_reading_prompt"], encoding="utf-8")
        (out / "page_reading_schema.json").write_text(json.dumps(ins["page_reading_schema"], indent=1), encoding="utf-8")
        (out / "3_report_instructions.md").write_text(ins["report_draft_prompt"], encoding="utf-8")
        (out / "report_schema.json").write_text(json.dumps(ins["report_draft_schema"], indent=1), encoding="utf-8")
        docs = pkg.pop("documents")
        docdir = out / "documents"
        docdir.mkdir(exist_ok=True)
        for d in docs:
            body = "\n\n".join(f"[Page {p['page_no']}{' - ' + p['label'] if p['label'] else ''}]"
                               f"{' (NEEDS READING – see pending_pages)' if p['needs_reading'] else ''}\n{p['text']}"
                               for p in d["pages"])
            (docdir / f"{d['ref']}.txt").write_text(f"{d['ref']} | {d['filename']} | type: {d['type']}\n\n{body}",
                                                     encoding="utf-8")
        pkg["required_checklist"] = ins["required_checklist"]
        pkg["report_word_budget"] = ins["report_word_budget"]
        (out / "case.json").write_text(json.dumps(pkg, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Package written to {out}/")
        print(f"  case: {pkg['case']['claim_number']} – {pkg['case']['insured_name']} ({pkg['case']['category']})")
        print(f"  documents with text: {len(docs)} (documents/D###.txt); inventory entries: {len(pkg['inventory'])}")
        print(f"  investigator notes: {len(pkg['investigator_notes'])}; photos: {len(pkg['photos'])}")
        print(f"  pending pages to read: {len(pkg['pending_pages'])}")
        for p in pkg["pending_pages"]:
            print(f"    {p['ref']} page {p['page_no']}  document_id={p['document_id']}  ({p['filename']})")
    elif cmd == "page-image":
        Path(args[2]).write_bytes(_req("GET", f"/documents/{args[0]}/pages/{args[1]}/image", raw=True))
        print(args[2])
    elif cmd == "read-page":
        body = json.loads(Path(args[2]).read_text(encoding="utf-8"))
        print(json.dumps(_req("PUT", f"/documents/{args[0]}/pages/{args[1]}/reading", body), ensure_ascii=False))
    elif cmd == "submit-analysis":
        analysis = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        res = _req("POST", f"/cases/{args[0]}/analyses/import", {"analysis": analysis})
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0 if res.get("accepted") else 2
    elif cmd == "submit-report":
        run = _flag(args, "--run")
        pages = _flag(args, "--pages")
        draft = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        body = {"sections": draft["sections"] if isinstance(draft, dict) else draft}
        if run:
            body["analysis_run_id"] = run
        if pages:
            body["page_limit"] = int(pages)
        print(json.dumps(_req("POST", f"/cases/{args[0]}/reports/draft", body), indent=1, ensure_ascii=False))
    elif cmd == "download-report":
        Path(args[1]).write_bytes(_req("GET", f"/reports/{args[0]}/download?format=docx", raw=True))
        print(args[1])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
