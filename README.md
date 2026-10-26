# Credential Extractor – Starting Point

Baseline script for the MedTrainer AI Engineer technical challenge.

## Contents

- `docs/` – sample license and certification documents (PDF).
- `expected/` – expected output for each document (`<document>.json`).
- `expected/_reference.json` – reference date (`2026-11-01`) and the `expiring_soon` window (60 days, inclusive) used to compute `expiration_status` in the expected outputs. Use the same values in your eval.
- `extract.py` – baseline extractor. Sends the document to a vision model on OpenRouter and prints JSON. Expect around 60% field accuracy.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...   # the key we sent you

# One document
python extract.py docs/tx_01.pdf

# Every document in a folder, one JSON file per document
python extract.py docs/ --out-dir outputs/
```

Use `--model` or `OPENROUTER_MODEL` to try a different OpenRouter model.

The baseline is intentionally simple. Everything in it is fair game to change.
