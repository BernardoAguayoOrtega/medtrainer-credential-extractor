"""Reads the model's answer whether a field is flat ("PA20733") or labelled
({"label": "License #", "value": "PA20733"} / {"label": "Expires", "text": "..."})."""


def raw_value(raw: dict, field: str):
    value = raw.get(field)
    if isinstance(value, dict):
        return value.get("value", value.get("text"))
    return value


def raw_label(raw: dict, field: str) -> str | None:
    value = raw.get(field)
    label = value.get("label") if isinstance(value, dict) else None
    return label.strip() if isinstance(label, str) and label.strip() else None
