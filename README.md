# Credential Extractor

Extracts structured data from medical licenses and certifications, flags expiring credentials and rejects documents that are not credentials. The LLM only **reads** the document; a deterministic engine in code **decides** dates, status, cleanup and review warnings.

| | |
|---|---|
| **Live demo** | https://medtrainer-credential-extractor-seven.vercel.app (one-click tests with the 8 samples) |
| **Accuracy** | 56.2% → **96.9–98.4%** strict field accuracy across runs; the deployed configuration scores **96.9%** (6/8 documents perfect, both misses in `issuing_authority`) |
| **Cost** | ~$0.0002 per single-page document, ~$0.0005 for a 2-page PDF |
| **Model** | `deepseek/deepseek-v4.1-flash` on OpenRouter, reasoning off |
| **Total spend** | ~$0.03 of the $5 key, including every eval run and demo tests |

> **Ground truth.** The eval uses only the expected outputs in [`expected/`](expected/). The example JSON in the challenge PDF is outdated (it uses `is_license`, `license_type` and a `state` field); Marco confirmed the repository files are the source of truth.

## Quick path

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env                       # add OPENROUTER_API_KEY

pytest                                     # 106 tests, no API calls
python run.py docs/ --out-dir outputs/final  # extract the 8 samples (~$0.003)
python evaluate.py outputs/final/          # per-field accuracy vs expected/
uvicorn app:app --reload                   # web UI on http://localhost:8000
```

## Why a deterministic engine around the LLM

The baseline asked the model to do everything: read, format dates, compute the status and decide what is a credential. Its errors were not reading errors. Of its 28 misses, most were **decisions the model should never have been making**:

| Baseline failure | Count | Root cause |
|---|---|---|
| Dates as `08/31/2027`, `12/15/26` | 7 of 8 `expiration_date` | Formatting is not a vision task |
| Wrong `expiration_status` | 3 of 8 | The model does not know the reference date; it guessed against "today" |
| Renewal notice taken as a license | 6 fields of `al_03` | No definition of what a credential is |
| `MD-41872` instead of `MD.41872` | 2 | 100 DPI render |

So the work is split by what each part is good at:

| Responsibility | Owner | Why |
|---|---|---|
| Read the document, copy values as printed | **LLM** | The only step that needs vision and language |
| Parse dates into ISO 8601 | **Code** ([`dates.py`](extractor/dates.py)) | Deterministic, testable, handles `12/15/26`, `March 4th, 2027`, `04-MAR-2027`; an unreadable date becomes `null`, never a guess |
| `expiration_status` | **Code** ([`status.py`](extractor/status.py)) | Pure date arithmetic against a configurable reference date; reproducible across runs and days | 100% |
| Nulls when not a credential, whitespace, title case, leading "The" | **Code** ([`normalize.py`](extractor/normalize.py)) | Output contract enforced in one place, independent of model mood |
| Review warnings | **Code** ([`validate.py`](extractor/validate.py)) | Cross-checks that never change values, so a human reviews instead of trusting a wrong field |

What this buys, with evidence:

- **Accuracy:** `expiration_date` 12% → 100% and `expiration_status` 62% → 100% from iteration 1 on, on every run since. These two fields never failed again.
- **Reproducibility:** the status for a given document and reference date is always the same; the eval pins `2026-11-01` from [`_reference.json`](expected/_reference.json), the UI defaults to today.
- **Safety in credentialing:** if an expiration date is printed but unreadable, status is `null` plus a warning, not `"no_expiration"`. Marking an expiring license as never-expiring is the worst possible error in this domain.
- **Generalization:** rules are about formats and document semantics, not about these 8 files. Unseen documents with new date formats or layouts go through the same tested code.
- **Cost:** reasoning tokens were spent on work code does for free. Turning reasoning off cut cost ~50% and *raised* accuracy (89.1% → 98.4%, iteration 2).
- **Testability:** 106 unit tests cover dates, status boundaries, normalization, validation and the API without spending a cent.

### The warnings (deterministic, never change values)

| Check | Catches |
|---|---|
| Key field missing (`holder_name`, `license_number`) | Partial reads |
| Printed date that could not be parsed | Unknown formats, OCR noise |
| Year outside 1950–2100, issue date after expiration | Misread or swapped dates |
| License number without digits | Picked a label or a word |
| License number not found in the PDF text layer (≥80% similarity, tolerant to OCR noise) | Hallucinated numbers |

Measured on the samples: **0 false warnings** after tuning (an exact-match version flagged 2 of 7 correct numbers because the embedded OCR reads `MD.41872` as `~.41872`). Known limit: a single wrong digit still passes the similarity check.

### Decisions the brief left open

| Question | Decision |
|---|---|
| Is a license valid on its expiration day? | Yes. `expired` only when the date is before the reference date |
| Is day 60 `expiring_soon`? | Yes, the window is 0–60 days inclusive |
| `03/04/2027`: March or April? | Month first (US documents); day first only when month first is impossible |
| Multi-page PDFs | The first 3 pages go to the model (cover letter + credential + wallet card) |

## Iterations

Every run is saved in [`results/`](results/) (per-field scores and every mismatch) and [`results/costs/`](results/costs/) (tokens and real cost per document from OpenRouter).

| # | Change | Strict | Docs perfect | Cost / doc |
|---|---|---|---|---|
| 0 | Baseline script, unchanged | 56.2% | 0/8 | ~$0.0003 |
| 1 | JSON schema (strict), prompt with field rules, dates and status in code, 200 DPI | 89.1% | 2/8 | ~$0.00043 |
| 2 | Prompt: names exactly as printed, credential type rule; **reasoning off** | **98.4%** | **7/8** | **~$0.00023** |
| 3 | Deterministic warnings, drop leading article (code only, re-applied to iteration 2 outputs, $0) | 98.4% | 7/8 | +$0 |
| 3b | Repeat run of the same config, to measure noise | 96.9% | 6/8 | ~$0.0002 |
| 4 | Schema asks for the printed label before each value (`{label, value}`) | 93.8% | 4/8 | ~$0.00027 |
| 4b | Repeat run of iteration 4 | 93.8% | 4/8 | ~$0.00017 |
| 5 | Up to 3 pages per PDF (measured on the 3 two-page documents) | 24/24 fields | 3/3 | ~$0.0005 |
| **Final** | **Deployed configuration (2 + 3 + 5), all 8 documents** | **96.9%** | **6/8** | **~$0.00033 avg** |

Per-field accuracy:

| Field | Baseline | Iter 1 | Iter 2/3 | Final |
|---|---|---|---|---|
| `is_credential` | 100% | 100% | 100% | 100% |
| `holder_name` | 38% | 75% | 100% | 100% |
| `credential_type` | 50% | 62% | 100% | 100% |
| `license_number` | 62% | 100% | 100% | 100% |
| `issuing_authority` | 38% | 75% | 88% | 75% |
| `issue_date` | 88% | 100% | 100% | 100% |
| `expiration_date` | 12% | 100% | 100% | 100% |
| `expiration_status` | 62% | 100% | 100% |

**What failed at first and what changed it**

- **Iteration 1** fixed every date and status error by moving them to code, and fixed the renewal notice (`al_03`) with an explicit definition of a credential that still accepts expired, wall, wallet and "sample" documents (`tx_03` is watermarked *not a valid license* and is still a credential in the expected output).
- **Iteration 2** fixed names (the model title-cased `DEVIN KOFI ASANTE`) and credential types. The rule is general: use the profession when the document states it ("registered … as a PHYSICIAN"), otherwise the document title verbatim. No per-document rules.
- **Iteration 4 was discarded.** Asking for the printed label first made labels perfectly correct but consistently hurt neighboring fields (sub-office lines leaked into the authority, "License" dropped from the type). Same 93.8% on two runs, so it is a real regression, not noise. The label-based warnings stay in the code and switch on with `--labelled`.
- **Noise is real:** the same configuration scored 98.4% and 96.9% (±1 field). With 8 documents one field is 1.6 points, so differences under ~3 points are not conclusive.

**The remaining misses** are in `issuing_authority` for the two New York documents. In the final run the model kept the sub-office line ("… Office of Licensed Professions") despite the prompt; across runs this field scored 75–88%. For `ny_01` the document prints *"The State of New York Department of Professional Registration"* and the expected value is *"New York State Department of Professional Registration"*. That rewording is a labeling convention, not something printed. A rule to force it would only fit this sample, so it is left as a known miss rather than overfitted.

**Considered and rejected:** a deterministic rule that cuts a trailing *"Office of …"* from `issuing_authority`. It would fix `ny_02` (+1.6 points) and fits the "code decides" design, but it is derived from a single document family. On unseen documents it could just as easily truncate an authority whose real name contains "Office of" (e.g. *"Office of the Professions"*). The sample score is not worth a rule that cannot be justified beyond these 8 files. The prompt already asks to drop sub-office lines; the right fix is more labeled examples, not a special case.

## Model choice

`deepseek/deepseek-v4.1-flash` ($0.14 / M input, $0.42 / M output tokens), the baseline's model, kept on purpose:

- After iteration 1 the remaining errors were conventions and formatting, not reading ability. A bigger model would not fix them, and the deterministic engine already removes the hard parts.
- It supports image input and strict JSON schema on OpenRouter.
- With reasoning off it answers in ~90 output tokens, ~1.5 s per document.
- Every change was measured against the same model, so each gain is attributable to the change, not to a model swap.

Not done for budget and time: a side-by-side of other vision models on a larger labeled set. That is the first thing to run before production (see below).

## Cost per document

| Document | Input tokens | Output tokens | Cost |
|---|---|---|---|
| 1 page | ~1,750 | ~90 | ~$0.0002 |
| 2 pages | ~2,750 | ~90 | ~$0.0005–0.0006 |

At these prices $5 covers roughly 10,000–25,000 documents. Real per-call costs are in [`results/costs/`](results/costs/); the API also returns `cost_usd` with every extraction.

## Taking it to production with PHI

**Security**

- Run the model under a BAA with zero data retention (e.g. Azure OpenAI, AWS Bedrock or Vertex AI), or self-host. A public aggregator key like this demo's is not acceptable for PHI.
- Authenticated access (SSO, per-tenant roles) instead of a public URL; audit log of who uploaded and viewed what.
- Documents encrypted in transit and at rest, with a retention policy. This demo already processes files in memory and never stores them.
- Never log document content. The app already logs only the error type on failures, because error messages can echo PHI.
- Validate uploads by content, not extension (already done with magic bytes), and scan files before processing.

**Cost**

- Cascade: the cheap model first; escalate to a stronger model only when warnings fire or a key field is missing.
- Render extra pages at lower resolution, and cache by document hash so re-uploads cost nothing.
- Batch non-urgent backlogs through batch APIs.

**Monitoring and quality**

- A labeled golden set of hundreds of real (de-identified for the team) documents, run in CI on every prompt or model change; block releases on per-field regressions.
- Dashboards: per-field accuracy from human corrections, warning rate, `is_credential=false` rate, latency, cost per document, by issuing state and document type. Alert on drift, such as a spike in unparseable dates from a board that changed its format.
- Human review queue for every document with warnings, feeding corrections back into the golden set.

## Known limitations

- 8 documents is a tiny eval; ±1 field of run-to-run variance.
- `ny_01` authority wording (see above).
- Only the first 3 pages of a PDF are read.
- The rate limit (20 documents per IP per hour) lives in memory per serverless instance: a guard for a shared demo key, not a quota system.
- The optional LLM-as-judge summary field was not built.

## Project layout

```
extractor/
  llm.py        OpenRouter call: prompt, strict JSON schema, reasoning off
  pipeline.py   render pages (200 DPI, up to 3), call, normalize, validate
  dates.py      date text → ISO 8601
  status.py     expiration_status against a reference date
  normalize.py  output contract
  validate.py   review warnings
evaluate.py     per-field eval (strict and lenient)
run.py          batch extraction with real cost logging
reapply.py      re-run only the deterministic engine on saved outputs ($0)
app.py          FastAPI app + upload limits + rate limit
templates/      single-page UI with document preview
results/        eval reports and cost logs per iteration
CHALLENGE.md    the original brief
```
