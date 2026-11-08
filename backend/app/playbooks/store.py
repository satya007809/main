"""Version-controlled, editable investigation playbooks.

Defaults ship as YAML in playbooks/defaults and are seeded into the database on first start. Every edit made
from the Admin screen creates a new immutable version; analysis runs record exactly which versions they used.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from ..models import Playbook, PlaybookVersion

DEFAULTS_DIR = Path(__file__).parent / "defaults"
LIST_FIELDS = ["document_checklist", "investigation_questions", "evidence_verification", "chronology_checks",
               "policy_verification", "red_flags_to_examine", "report_instructions", "related_aspects"]


class PlaybookValidationError(ValueError):
    pass


def parse_and_validate(text: str, expected_key: str | None = None) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PlaybookValidationError(f"Invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise PlaybookValidationError("Playbook must be a YAML mapping")
    for f in ("key", "name", "kind"):
        if not data.get(f):
            raise PlaybookValidationError(f"Missing required field '{f}'")
    if expected_key and data["key"] != expected_key:
        raise PlaybookValidationError(f"key must remain '{expected_key}'")
    if data["kind"] not in ("global", "category", "aspect"):
        raise PlaybookValidationError("kind must be global, category or aspect")
    if data["kind"] == "global":
        if not isinstance(data.get("rules"), list) or not data["rules"]:
            raise PlaybookValidationError("Global rules need a non-empty 'rules' list")
    else:
        if not data.get("objective"):
            raise PlaybookValidationError("Missing 'objective'")
        for f in LIST_FIELDS:
            if f in data and not isinstance(data[f], list):
                raise PlaybookValidationError(f"'{f}' must be a list")
        for item in data.get("document_checklist", []):
            if not isinstance(item, dict) or not {"id", "label"} <= item.keys():
                raise PlaybookValidationError("document_checklist items need 'id' and 'label'")
    return data


def seed_defaults(db: Session) -> None:
    for path in sorted(DEFAULTS_DIR.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        data = parse_and_validate(text)
        if db.query(Playbook).filter_by(key=data["key"]).one_or_none():
            continue
        pb = Playbook(key=data["key"], name=data["name"], kind=data["kind"], active_version=1)
        pb.versions.append(PlaybookVersion(version=1, content_yaml=text, change_note="Initial default"))
        db.add(pb)
    db.commit()


def add_version(db: Session, key: str, text: str, note: str, user_id: str, activate: bool = True) -> PlaybookVersion:
    pb = db.query(Playbook).filter_by(key=key).one_or_none()
    if pb is None:
        data = parse_and_validate(text)
        pb = Playbook(key=data["key"], name=data["name"], kind=data["kind"], active_version=0)
        db.add(pb)
        db.flush()
    data = parse_and_validate(text, expected_key=key)
    n = max((v.version for v in pb.versions), default=0) + 1
    ver = PlaybookVersion(playbook_id=pb.id, version=n, content_yaml=text, change_note=note, created_by=user_id)
    db.add(ver)
    pb.name = data["name"]
    if activate:
        pb.active_version = n
    db.commit()
    return ver


def load_active(db: Session, key: str) -> tuple[dict, int]:
    pb = db.query(Playbook).filter_by(key=key).one_or_none()
    if pb is None:
        raise KeyError(f"Playbook '{key}' not found")
    ver = next(v for v in pb.versions if v.version == pb.active_version)
    return parse_and_validate(ver.content_yaml), ver.version


def compose_for_case(db: Session, category: str, aspects: list[str]) -> tuple[dict, list[dict], list[dict]]:
    """Return (global_rules, [playbooks], [{key, version}]) for the case's category plus selected aspects."""
    glob, gv = load_active(db, "global_rules")
    used = [{"key": "global_rules", "version": gv}]
    books = []
    for key in [category, *[a for a in aspects if a != category]]:
        pb, v = load_active(db, key)
        books.append(pb)
        used.append({"key": key, "version": v})
    return glob, books, used


def available_aspects(db: Session) -> list[dict]:
    return [{"key": p.key, "name": p.name, "kind": p.kind}
            for p in db.query(Playbook).order_by(Playbook.kind, Playbook.name) if p.kind != "global"]
