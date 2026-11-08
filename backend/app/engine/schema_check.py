"""Minimal JSON-Schema checker for the subset used in engine/schema.py (type, enum, properties, required,
additionalProperties=false, items). Used to check analyses submitted from Claude Code."""
from __future__ import annotations

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


def check(data, schema: dict, path: str = "$", errors: list[str] | None = None, limit: int = 50) -> list[str]:
    errors = [] if errors is None else errors
    if len(errors) >= limit:
        return errors
    t = schema.get("type")
    if t == "integer":
        ok = isinstance(data, int) and not isinstance(data, bool)
    elif t in _TYPES:
        ok = isinstance(data, _TYPES[t])
    else:
        ok = True
    if not ok:
        errors.append(f"{path}: expected {t}, got {type(data).__name__}")
        return errors
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: '{data}' not one of {schema['enum']}")
    if t == "object":
        props = schema.get("properties", {})
        for r in schema.get("required", []):
            if r not in data:
                errors.append(f"{path}: missing '{r}'")
        if schema.get("additionalProperties") is False:
            for k in data:
                if k not in props:
                    errors.append(f"{path}: unexpected field '{k}'")
        for k, sub in props.items():
            if k in data:
                check(data[k], sub, f"{path}.{k}", errors, limit)
    elif t == "array" and "items" in schema:
        for i, item in enumerate(data):
            check(item, schema["items"], f"{path}[{i}]", errors, limit)
    return errors
