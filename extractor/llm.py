"""OpenRouter call with a strict JSON schema. The model only reads; code decides dates and status."""

import json
import os

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"


class ExtractionError(Exception):
    pass


SYSTEM_PROMPT = """You read scanned or digital documents for a healthcare credentialing team.
Decide whether the document is a professional credential and extract its fields.

A credential is a document that itself grants or certifies the right to practice:
a license, a registration certificate, a permit, or a certification card (for
example BLS or ACLS). It is a credential even if it is expired, a wall
certificate, a wallet card, or marked as a sample/test document.

It is NOT a credential when the document is about a credential but does not
grant it: renewal notices, payment requests, invoices, receipts, applications,
verification letters, CE transcripts, or any document that says it is not a
license or may not be used as proof. If it is not a credential, set
is_credential to false and every other field to null.

Field rules:
- Copy values from the document. Never infer, complete or guess. Use null when
  a field is not printed.
- holder_name: the person's name exactly as printed: same capitalization (if
  it is printed in ALL CAPS, return it in ALL CAPS) and same word order. Drop
  professional degrees or titles after the name (MD, DO, RN, PA-C, PhD). Keep
  generational suffixes (Jr., Sr., III).
- credential_type: if the document explicitly states the profession the holder
  is licensed or registered as (e.g. "registered to practice ... as a(n)
  PHYSICIAN ASSISTANT"), use that profession. Otherwise use the document's
  title wording verbatim (e.g. "License to Practice Medicine", "Physician
  License", "BLS Provider"); do not paraphrase it. Write it in title case even
  when printed in capitals.
- license_number: the license or registration number exactly as printed,
  including letters, dots and dashes. Not a certificate, receipt, notice or
  board action number.
- issuing_authority: the name of the board, commission, department or
  organization that issued it, in title case. Leave out leading articles,
  addresses and sub-office lines.
{label_rule}- issue_date, expiration_date: copy the date text exactly as printed. "Valid
  through", "expires" and "registered through" dates are expiration dates. Use
  null for expiration_date when the document has none.
- The document may be rotated or skewed; read it in its natural orientation."""

LABEL_RULE = """- For license_number, issue_date and expiration_date, first copy the label
  printed next to the value (e.g. "License #", "Date Issued", "Expires",
  "registered ... through"), then the value. Use null for both when absent.
"""


def _labelled(key: str, description: str) -> dict:
    """The printed label comes first so the model locates the field before copying it."""
    return {
        "type": "object",
        "properties": {
            "label": {
                "type": ["string", "null"],
                "description": "The label printed next to it, e.g. 'License #'",
            },
            key: {"type": ["string", "null"], "description": description},
        },
        "required": ["label", key],
        "additionalProperties": False,
    }


NULLABLE_STRING = {"type": ["string", "null"]}


def fields_schema(labelled: bool = False) -> dict:
    """labelled=True asks for the printed label before each value (iteration 4: measured worse, off by default)."""
    number = (
        _labelled("value", "the license or registration number, as printed")
        if labelled
        else NULLABLE_STRING
    )
    issued = (
        _labelled("text", "the issue date text, exactly as printed")
        if labelled
        else NULLABLE_STRING
    )
    expires = (
        _labelled("text", "the expiration date text, exactly as printed")
        if labelled
        else NULLABLE_STRING
    )
    return {
        "type": "object",
        "properties": {
            "document_kind": {
                "type": "string",
                "description": "One short phrase: what this document is.",
            },
            "is_credential": {"type": "boolean"},
            "holder_name": {"type": ["string", "null"]},
            "credential_type": {"type": ["string", "null"]},
            "license_number": number,
            "issuing_authority": {"type": ["string", "null"]},
            "issue_date": issued,
            "expiration_date": expires,
        },
        "required": [
            "document_kind",
            "is_credential",
            "holder_name",
            "credential_type",
            "license_number",
            "issuing_authority",
            "issue_date",
            "expiration_date",
        ],
        "additionalProperties": False,
    }


def build_payload(
    mime: str,
    image_b64: str,
    model: str,
    reasoning: bool = False,
    labelled: bool = False,
) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "reasoning": {"enabled": reasoning},
        "usage": {"include": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "credential",
                "strict": True,
                "schema": fields_schema(labelled),
            },
        },
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.replace(
                    "{label_rule}", LABEL_RULE if labelled else ""
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract the credential fields from this document.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            },
        ],
    }


def parse_response(body: dict) -> tuple[dict, dict]:
    text = body["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        fields = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"invalid JSON from model: {text[:200]}") from exc
    usage = body.get("usage", {})
    return fields, {
        "generation_id": body.get("id"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cost": usage.get("cost"),
    }


def call_openrouter(
    mime: str, image_b64: str, model: str, labelled: bool = False
) -> tuple[dict, dict]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ExtractionError("OPENROUTER_API_KEY is not set")
    response = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json=build_payload(mime, image_b64, model, labelled=labelled),
        timeout=120,
    )
    if response.status_code >= 400:
        raise ExtractionError(
            f"OpenRouter {response.status_code}: {response.text[:200]}"
        )
    return parse_response(response.json())
