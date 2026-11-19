# ChallengeMap

Turning scattered citizen complaints into ranked, verifiable challenge briefs that
universities, NGOs and industry can act on. Built for Jharkhand.

> **Status: interface build, measured ML pipeline, working API, wired web client.**
> The challenge library and briefs read the API (evidence, districts, monthly timeline)
> and fall back to the seeded synthetic dataset when it is empty or unreachable, while
> authentication, citizen submission with live duplicate interception, the partner
> portal, the admin console and a citizen reports/feedback page call the FastAPI
> service. [`docs/RESULTS.md`](docs/RESULTS.md) records the measured clustering,
> deduplication and routing results. Persistence is still SQLite: the PostgreSQL +
> pgvector schema is Phase 2 of [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md).
> **No number in this project is a real Jharkhand complaint statistic.**

## Run the whole stack

```bash
cp .env.example .env     # then set a strong JWT_SECRET and bootstrap admin credentials/email
python scripts/dev.py    # or: make dev
```

`scripts/dev.py` loads `.env`, starts the FastAPI service, waits for
`/api/v1/health`, then starts the Next.js app with `NEXT_PUBLIC_API_BASE` set.
Ctrl+C stops both process trees. The API reads the same `.env` itself, so neither
service needs exported variables and no Docker, Postgres or `make` is required.

## Run the web app

The launcher above is the normal path; the separate commands below remain for
working on one half of the stack.

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Node 20+ is required (developed on Node 26).

Production check:

```bash
cd frontend
npm run build
```

### Routes

| Route | What it is |
|---|---|
| `/` | Landing page with seeded demo counters, a 24-district intensity grid and featured demo challenges |
| `/challenges` | Challenge library; reads published API clusters, falls back to the seeded demo set with a visible badge |
| `/challenges/[slug]` | Brief from the API detail endpoint: evidence quotes, monthly trend, districts, priority breakdown, explainable partner matches |
| `/submit` | Complaint form that submits to the API and returns real duplicate candidates to attach or keep separate |
| `/reports` | Citizen reports: clustering status, merge target and resolution feedback |
| `/partners` | Seeded demo partner directory with capability tags (the API directory is at `/api/v1/partners`) |
| `/partners/dashboard` | Partner portal: API-matched challenges and interest decisions |
| `/admin` | Review console: stats, pending reports, re-clustering, publishing, renaming, match decisions and partner accounts |
| `/login`, `/register` | Auth screens wired to the JWT `/auth/*` endpoints |
| `/methodology` | Data provenance, pipeline, evaluation status, limitations, ethics |

The interface is responsive, keyboard navigable, and sets Hindi text in Noto Sans
Devanagari. Set `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`) to point the
client at a running API; without it, auth and the portals report that the service is
unreachable while the public pages keep their seeded demo content.

## Run the API

The service loads the project `.env` on startup (existing environment variables win),
so one file covers the launcher and a direct run:

```bash
python -m pip install -r requirements/api.txt
cp .env.example .env          # JWT_SECRET and bootstrap admin credentials/email
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000/docs>. Register a citizen at `/api/v1/auth/register`, log
in at `/api/v1/auth/login` for a Bearer token, then submit a complaint at
`/api/v1/complaints`; identical reports in the same district come back as
`duplicate_candidates`. Admin endpoints need the bootstrap account above. Roles are
`citizen`, `partner` and `admin`; `api/README.md` has the endpoint and role matrix plus
the known gaps (SQLite persistence, in-memory rate-limit counters). `api/README.md`
also documents challenge briefs and the merge ownership rule.

### Back up the local database

The API store is a single SQLite file until Phase 2. `scripts/backup_db.py` uses
SQLite's online backup API, so the copy is consistent while the service is running,
and it verifies `PRAGMA integrity_check` on both sides:

```bash
python scripts/backup_db.py                       # backups/challenge_map-<timestamp>.db
python scripts/backup_db.py --restore backups/challenge_map-<timestamp>.db --force
```

Restore refuses to replace an existing database without `--force`; stop the API first
so no connection holds the old file. `backups/` is gitignored.

## What exists in Python

```bash
py -3.13 -m venv .venv313
.venv313/Scripts/Activate.ps1   # Windows PowerShell; use bin/activate on POSIX
python -m pip install -r requirements/dev.txt
python -m unittest discover -s tests -t .
```

`-t .` is required: `tests/__init__.py` must run before any test module imports the
app, because it switches the rate limiter off. This machine runs 3.13; CI runs 3.12.

- `src/data/complaints.py` — canonical complaint schema, strict validation, district list
- `src/data/synthetic_generator.py`, `src/data/ingest.py` — seeded corpus and source adapters
- `src/nlp/text_preparation.py` — Unicode-preserving normalisation (Hindi/Hinglish safe)
- `src/nlp/embeddings.py` — multilingual Sentence-BERT path (optional dependency)
- `src/nlp/duplicate_detection.py` — semantic near-duplicate candidates
- `src/nlp/topic_discovery.py` — Sentence-BERT + K-Means topic discovery
- `src/nlp/evaluation.py` — ARI/NMI/purity, clustering baselines, duplicate threshold sweep
- `src/nlp/topic_naming.py` — c-TF-IDF cluster names
- `src/nlp/priority.py`, `src/nlp/matching.py` — weighted priority index and explainable partner matching
- `src/nlp/classification.py` — supervised domain routing baseline
- `api/` — FastAPI service with authentication, ownership, feedback and the re-cluster job
- `scripts/` — corpus generation, evaluation, ingestion and development CLIs

The SBERT path needs the ML extras, which are **not installed** in this environment.
Every number in `docs/RESULTS.md` therefore comes from the TF-IDF baselines:

```bash
python -m pip install -r requirements/ml.txt
python scripts/prepare_dataset.py --input data/synthetic/complaints_15k.csv --output data/processed/complaints_prepared.csv
python scripts/discover_topics.py --input data/processed/complaints_prepared.csv --clusters 5
```

`data/processed/` is generated and gitignored, so the preparation step is required
before the second command.

Requirements are split by need: `requirements/base.txt` (pandas, numpy, scipy,
scikit-learn), `requirements/api.txt` (FastAPI, JWT, Argon2id, slowapi),
`requirements/ml.txt` (torch + sentence-transformers) and `requirements/dev.txt`
(the API set plus the test client).

## Data

No openly downloadable bulk corpus of Jharkhand citizen complaints exists. The
official portals (PGMS, DFCA PGMS, Jharkhand MyGov, CPGRAMS/DARPG) publish single
complaint lodgement, small comment threads, or aggregate counts — not raw text.
That finding is documented in `docs/MASTER_PLAN.md` section 4 and `docs/DATA.md`.

The development corpus is seeded synthetic: all 24 districts, twelve issue domains,
71 sub-issues, Hindi/English/Hinglish phrasing, modelled seasonality and **1,500
injected duplicates (1,200 near-paraphrases, 300 exact; 8% and 2%)** so deduplication
quality can be measured rather than asserted. Every row carries a `source_type`, and a
synthetic row can never be marked verified.

The plan's CC0 Indian grievance dataset is a **planned** real-text benchmark. It has not
been downloaded into this repository, so `docs/RESULTS.md` reports synthetic-only
numbers and lists the missing benchmark, SBERT comparison and inter-annotator kappa
under "Not measured".

Regenerate it (deterministic for a given seed):

```bash
python scripts/generate_corpus.py --records 15000 --eval-records 2000 --seed 42
```

This writes `data/synthetic/complaints_15k.csv` (header plus exactly 15,000 validated
rows), a 2,000-row held-out set, `ground_truth_*.csv` label sidecars for ARI/NMI and
deduplication F1, and refreshes `data/source_manifest.csv`. Real extracts enter through
`src/data/ingest.py`, which maps source columns onto the canonical schema and strips
phone numbers, emails and ID numbers on that bulk path.

Measure it (rewrites `docs/RESULTS.md`, `models/eval_metrics.json`,
`models/dedup_threshold.json` and `models/embedding_config.json`):

```bash
python scripts/run_eval.py --sample 3000 --clusters 12 --seed 42
```

## Tests

```bash
python -m unittest discover -s tests -t .
```

The suite covers the canonical data contract, synthetic generator, text preparation,
evaluation helpers, clustering, priority and matching, the API (auth, RBAC, dedup,
merging, re-clustering, publishing, matches, analytics, briefs), the SQLite migration
the `.env` loader and two full lifecycle rehearsals: 127 tests at the time of writing, including the backup/restore drill. CI runs the same command on
Python 3.12 (`.github/workflows/ci.yml`) plus `npm run build` for the frontend.

## Documentation

| Document | Contents |
|---|---|
| [`docs/DATA.md`](docs/DATA.md) | Corpus inventory, measured composition, schema, PII policy, licences, regeneration |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Runtime architecture, request flows, data model, deviations from the target stack |
| [`docs/RESULTS.md`](docs/RESULTS.md) | Measured ARI/NMI/purity, dedup sweep, routing baseline, error analysis, what was not measured |
| [`docs/VIVA.md`](docs/VIVA.md) | Demo script, anticipated questions and honest answers |
| [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) | Plan of record: audit, target design, phase order and gates |

## Project layout

```text
frontend/      Next.js web application (current interface)
api/           FastAPI service, SQLite store behind api/store.py
src/data/      canonical schema, seeded generator, ingestion adapters
src/nlp/       text preparation, embeddings, deduplication, clustering, priority, matching
scripts/       corpus generation, evaluation, dataset preparation, dev launcher
data/          synthetic corpus and ground truth, geography, source manifest; raw/processed ignored
models/        JSON model configs and measured metrics; models/saved ignored
notebooks/     experiment workbooks (none written yet)
docs/          master plan, data, architecture, results and viva documents
tests/         data, NLP, clustering, API, migration and config tests
```

`docs/MASTER_PLAN.md` is the plan of record: verified audit of the old code, target
stack, database schema, API contract, ML evaluation protocol, cleanup ledger and the
ten-week phase order with acceptance gates. Where this README and the plan disagree
about future work, the plan wins.
