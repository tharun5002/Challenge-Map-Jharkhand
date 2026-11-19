# ChallengeMap — Master Development Plan

**Project:** ChallengeMap — Societal-Challenge Discovery & Matching for Jharkhand
**Document status:** Approved plan of record
**Last revised:** 10 November 2026

---

## 0. How to use this document

Sections 1–2 record decisions and the verified audit. Sections 3–8 are the target design
(data, database, ML, API, frontend). Sections 9–11 cover cleanup, testing and CI.
Section 12 is the executable 10-week plan with acceptance criteria. Sections 13–15 are
risks, the definition of done, and the final repository layout.

Every phase in Section 12 has a **gate**: a concrete, checkable result. Do not start
Phase N+1 until the gate of Phase N passes. If time runs short, the plan degrades
gracefully at the Phase 6 cut line (Section 12.7) — that is the minimum defensible
submission.

### Build status (updated as phases land)

| Phase | State | Evidence on disk |
|---|---|---|
| 0 — Web UI replaces Streamlit | **Done** | `frontend/` builds 20 routes; `streamlit_app.py` and `.streamlit/` removed; 50 tests pass |
| 1 — Repo hygiene & tooling | **Partial** | git initialised but has no commits yet; `.env.example`, `Makefile`, CI workflow and the split requirements exist; LICENSE added and the stale `.venv-1` removed; development uses `.venv313` (3.13) while CI runs 3.12 |
| 2 — Database & canonical model | **Not started (unblocked)** | no Postgres endpoint is configured yet and SQLAlchemy/Alembic are not installed; Docker is **not** the blocker — a hosted free-tier instance via `DATABASE_URL` is the default route (§11). Schema design is in §5 and needs a real instance to verify |
| 3 — Corpus & ingestion | **Done** | generator v1.1.0: 15,000 train + 2,000 held-out rows validated, 1,500 injected duplicates (1,200 true paraphrases), 24 districts, 71 sub-issues, `src/data/ingest.py`, `data/source_manifest.csv` |
| 4 — ML pipeline & evaluation | **Partial** | 127 tests pass; `docs/RESULTS.md` has ARI/NMI/purity for 3 algorithms on 2 datasets, dedup F1 **0.743** at threshold 0.85, c-TF-IDF naming, priority index, matching engine, error analysis. SBERT and inter-annotator κ outstanding |
| 5 — Backend API | **Partial** | 124 tests pass; JWT access/refresh with rotation, RBAC (citizen/partner/admin), dedup-on-submit, re-cluster job producing drafts and matches, analytics, admin console, OpenAPI at `/docs`, slowapi rate limits and Argon2id hashing. Persistence is still SQLite (Phase 2 not started); rate-limit counters are per process |
| 6 — Frontend v1 | **Partial** | the full route set builds; login/register call the JWT endpoints, `/submit` shows the API's real duplicate candidates and merge flow, the challenge library and detail brief read the API (evidence, districts, monthly timeline, derived severity) with the seeded demo dataset as fallback, and `/reports` records citizen resolution feedback. Playwright + Lighthouse have not been run |
| 7 — Admin & partner portals | **Done in code, not browser-tested** | the UI covers the full lifecycle: submit → attach duplicate → re-cluster → publish → match decision → partner interest → citizen resolution feedback. Admins can rename challenges and issue partner accounts linked to a directory organisation |
| 8 — Hardening & deploy | **Partial** | `scripts/dev.py` (also `make dev`) loads `.env`, waits for `/api/v1/health`, starts API + web and stops both trees on exit; the API loads `.env` for every entry point; `.env` and `backups/` are git-ignored; `scripts/backup_db.py` takes an integrity-checked SQLite copy and restores it. No container stack or hosted deployment |
| 9 — Documentation & report pack | **Partial** | README audited command-by-command (test command fixed to `-t .`, false CC0 benchmark claim removed, Python/venv and SBERT statements corrected); `docs/DATA.md`, `docs/ARCHITECTURE.md` and `docs/VIVA.md` added; methodology page metrics, provenance and PII claims corrected. No screenshots, written report or slide deck |
| 10 — Buffer & polish | **Partial** | a scripted lifecycle rehearsal runs the citizen → duplicate → publish → match → partner → feedback path twice in fresh databases (`tests/test_lifecycle.py`); accessibility pass: `aria-current` on the active nav/tab, table captions and column scopes, input hints linked with `aria-describedby`, decorative menu icons hidden, and the reports feedback form fixed (it showed “Feedback saved.” before the API had answered). No browser demo runs, Lighthouse/axe audit, screenshots or report |

---

## 1. Decisions locked

| Area | Decision | Rationale |
|---|---|---|
| Dashboard | **Remove Streamlit entirely**; build a Next.js web app | User requirement; enables real UI, auth, public/partner/admin roles |
| Backend | **Keep and extend FastAPI** (`api/main.py` already has auth + feedback) | Working code, standard for ML serving, good for viva |
| Database | **PostgreSQL + pgvector** addressed by `DATABASE_URL` (managed Neon free tier is the default; local Docker or a native install are alternatives) | Replaces divergent SQLite; stores vectors for dedup; Docker optional (§11) |
| ORM / migrations | **SQLAlchemy 2.x + Alembic** | Single schema of record; no more schema drift |
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** | Fast, responsive, professional; Node 26 available |
| Auth | **Self-hosted JWT in FastAPI** (upgrade PBKDF2 → Argon2id) | No third-party service, no cost, defensible academically |
| ML core | **Keep `src/nlp/*`**, add HDBSCAN + supervised classifier + matching | Already tested; SBERT path is the novelty |
| Python | **3.12 for the ML environment** | PyTorch wheels are unreliable on 3.14 (current interpreter) |
| Data | Synthetic-first corpus (documented) + one real licensed benchmark | See Section 4 — no bulk official Jharkhand data is public |
| Repo | Initialize Git, one branch per phase, PR-style merges | Currently **not** a git repository |

---

## 2. Current state audit (verified 10 Nov 2026)

Measured, not assumed:

- `python -m unittest discover -s tests -t .` → **28 tests at the time, all passing,
  5.7 s** (the `-t .` flag is now required; the current suite is 124 tests).
- `sentence_transformers` and `torch` → **not installed**. Both README-advertised
  commands (`scripts/discover_topics.py`, `scripts/find_duplicates.py`) cannot run.
- Interpreter is **Python 3.14.6**; `streamlit 1.66.1`, `pandas 3.1.1`, `sklearn 1.9.1`,
  `fastapi 0.162.0`, `httpx 0.28.1` are present.
- `data/raw/` is **243 MB of leftover Chicago/NYC 311 data**, and
  `data/raw/nyc_311_prepared.csv` is the **first** entry of `DEFAULT_DATA_PATHS` in
  `streamlit_app.py` → the live app renders Brooklyn/Manhattan/Queens, not Jharkhand.
  Its `report_text` column is the 311 *category name*, not citizen prose.
- `challenge_map.db` contains `users`, `complaint_feedback` and `challenge_reports`
  **with** `owner_id`, created by the API. A Streamlit-only run creates
  `challenge_reports` **without** `owner_id` → two incompatible schemas.
- `README.md` documents accounts, admin review, a feedback tab and `.streamlit/secrets.toml`
  that **do not exist** in the Streamlit app. This is the highest-credibility-risk item in
  a graded submission.
- `requirements.txt` does not list `streamlit`; `requirements-api.txt` requires the
  non-existent package `httpx2`.
- Sidebar district picker hardcodes **10** districts; the codebase defines **24**.
- Total Python: **2,880 lines** across 25 modules.
- `dashboard/`, `database/`, `notebooks/`, `models/` contain **only placeholder READMEs**.
- Git: **not initialized** (no `.git`).

**Verdict:** the code is honest and well-tested at the module level, but the *product* is a
Streamlit clustering demo running on American municipal data, and the documentation
describes software that does not exist. The rewrite fixes both.

---

## 3. Target architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Next.js 15+ (App Router, TypeScript, Tailwind, shadcn/ui)        │
│  Public site · Citizen portal · Partner portal · Admin console    │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTPS / JSON (Bearer JWT)
┌───────────────────────────▼──────────────────────────────────────┐
│  FastAPI (Python 3.12)                                            │
│  routers: auth · complaints · challenges · partners · matches     │
│           feedback · analytics · admin · health                   │
│  services: dedup-on-submit · priority scoring · matching engine   │
│  jobs: nightly re-cluster · model metrics refresh                 │
└──────────┬────────────────────────────────────┬──────────────────┘
           │ SQLAlchemy + Alembic               │ sentence-transformers
┌──────────▼───────────────────┐   ┌────────────▼──────────────────┐
│  PostgreSQL 16 + pgvector     │   │  ML sidecar / in-process       │
│  complaints · challenges      │   │  src/nlp/*  (embeddings,       │
│  matches · users · audit      │   │  dedup, clustering, matching)  │
└───────────────────────────────┘   └────────────────────────────────┘
```

Deployment target for the demo: **api + web, with Postgres reached through `DATABASE_URL`**.
A single Docker Compose stack (api + web + postgres/pgvector) is the optional convenience for
running it offline; a hosted Postgres (Neon) plus any process runner is equally supported and is
the default development route. No phase gate may depend on a container — see §11.

**Service note:** for the hosted database, **Neon** (serverless Postgres, free plan,
`DATABASE_URL`, supports `pgvector`) was the top-rated option when compared; Aiven and
Crunchy Bridge are standard-Postgres alternatives. Final hosting choice is deferred to
Phase 7 and must be validated then, not assumed.

---

## 4. Data strategy

### 4.1 What actually exists for Jharkhand (researched)

| Source | What it offers | Bulk text? | Usable how |
|---|---|---|---|
| Jharkhand PGMS — `pgms.dmajharkhand.in` (Urban Dev. & Housing) | citizen complaint lodgement + single-complaint tracking | **No** public list/export API | Reference for real categories and phrasing; no scraping without written permission |
| DFCA PGMS — `pgms.dfcajharkhand.in` | PDS/food grievance lodgement, Hindi+English UI | **No** export | Same |
| `jharkhand.mygov.in` — Public Grievances group | public comment thread | Only **24** comments | Illustrative examples for the report, not a corpus |
| CPGRAMS / DARPG reports (`darpg.gov.in`, PIB) | state- and district-wise **counts**, disposal rates, Grievance Redressal Index | **No** raw text | Real statistics for the impact/motivation section (e.g. Jharkhand: 18,078 grievances, 43.89% index score, H1 2024) |
| DARPG Hackathon 2024 restricted CPGRAMS datasets | anonymised grievance records | **Yes, but gated** | Register if still open; best path to genuinely real text |
| Kaggle `citizen-grievance-dataset` (**CC0**) | ~3,000 Hindi / Hinglish / English grievances, 14 CPGRAMS-aligned categories, plus a holdout set | **Yes, downloadable** | Planned benchmark for model validation — **not downloaded** |

**Conclusion (recorded decision):** there is **no openly downloadable bulk corpus of
Jharkhand citizen complaints**. Claiming otherwise in the report would be false. Therefore:

1. **Primary development corpus:** a purpose-built **synthetic** corpus of **15,000**
   complaints, generated by a committed, seeded, documented generator
   (`src/data/synthetic_generator.py`, `--seed 42`, version-tagged).
2. **Real benchmark (planned):** the CC0 Kaggle citizen-grievance dataset (~3,000
   real-form Hindi/Hinglish/English grievances, 14 categories) is the intended check
   that the model is not an artifact of synthetic templates. It has **not been
   downloaded** into this repository; if it is added, report both numbers, always labelled.
3. **Official outreach (do in parallel, report the outcome honestly):**
   - Written request to NIC Jharkhand / UD&H Dept. for an anonymised PGMS extract.
   - Register/apply for the DARPG CPGRAMS dataset route.
   - If granted, ingest through the adapter in 4.4 — no code change required.
4. **Never** present synthetic rows as verified real complaints. The `source` column
   (`public_dataset` | `consent_survey` | `synthetic` | `other`) and a
   `is_synthetic` flag travel with every row into the UI ("Source: synthetic demo data").

### 4.2 Synthetic corpus specification

Generate **15,000** records (plus **2,000** held out as an unseen evaluation set).

| Dimension | Specification |
|---|---|
| Districts | all **24** Jharkhand districts, sampled ∝ population, with realistic per-district skew (Ranchi, Dhanbad, East Singhbhum over-represented) |
| Domains | 12: water supply, sanitation & waste, roads & connectivity, electricity, healthcare, education, food & PDS, land & revenue, pensions & welfare, employment, law & order, agriculture & irrigation |
| Sub-issues | ≥ 70 (e.g. `handpump_defunct`, `school_no_toilet`, `phc_no_doctor`, `ration_dealer_shortweight`) |
| Languages | 45% Hindi (Devanagari), 35% English, 20% Hinglish/Hinglish-romanised; language column recorded |
| Realism | template families × slot filling × paraphrase bank; lengths 8–140 words; inject typos, abbreviation, code-mixing, missing punctuation |
| Severity | weighted `low/medium/high/critical` per sub-issue, correlated with domain |
| Affected population | log-normal per sub-issue, district-scaled |
| Dates | 18 months, **seasonality** (monsoon → water/road/sanitation spikes), weekday bias |
| **Injected duplicates** | **8% near-duplicates** (paraphrase + noise) and **2% exact duplicates**, each tagged with a `duplicate_group_id` |
| Ground truth | `true_domain`, `true_sub_issue`, `duplicate_group_id`, `severity` — enables ARI/NMI/purity and dedup F1 |
| Provenance | `generator_version`, `seed`, `generated_at` written into the CSV and `data/source_manifest.csv` |

Deliverables (all but the notebook are in the repository): `src/data/synthetic_generator.py`
`v1.1.0`, `scripts/generate_corpus.py`, `data/synthetic/complaints_15k.csv` (exactly 15,000
rows), `data/synthetic/complaints_2k_eval.csv`, the matching `ground_truth_*.csv` sidecars,
and `data/source_manifest.csv`. `notebooks/01_corpus_eda.ipynb` is still to be written for
the report figures.

**v1.1.0 corrections (11 Nov 2026), both found by measurement, not review:**

1. *Near-duplicates were not paraphrases.* v1.0.0 rendered a near-duplicate from a
   randomly chosen template, so it shared only the 2–3 word issue phrase with its
   source (median cosine 0.29) and was indistinguishable from an independent
   complaint about the same sub-issue. Injected near-duplicates are now the same
   template with the same slots, reworded through a paraphrase bank (median cosine
   0.91), which is what the 8% injection rate always claimed to be.
2. *Topic signal was drowned by boilerplate.* Every complaint was one of twelve
   sentences per language, so the template — not the topic — was the strongest
   lexical signal, and any clustering scored ARI ≈ 0 against the labels. v1.1.0
   adds a per-domain detail clause (e.g. water: "the supply line pressure has
   dropped and the tank stays dry") that fires on 75% of rows, which is both more
   realistic and makes the domain label expressible in the text.

````bash
python scripts/generate_corpus.py --records 15000 --eval-records 2000 --seed 42
````

### 4.3 Canonical schema (unchanged contract)

Every dataset — synthetic, benchmark, or future official extract — must validate against
`src/data/complaints.py`. The canonical columns are exactly:

```
complaint_id, complaint_text, district, block, complaint_date, language,
severity, affected_population, source_type, verification_status
```

`complaint_date` is ISO `YYYY-MM-DD`, `severity` is one of
`unknown|low|medium|high|critical`, `source_type` is one of
`public_dataset|consent_survey|synthetic|other`, and a row whose source is `synthetic`
can never carry `verification_status=verified`. Validation **rejects** unknown districts,
invented severities, missing text and duplicate ids rather than coercing them.

Ground truth never lives in the canonical file. It is written to a sidecar keyed by
`complaint_id` (`domain`, `sub_issue`, `true_severity`, `duplicate_group_id`,
`is_duplicate`, `duplicate_kind`, `duplicate_of`) so that evaluation code can read labels
while production code only ever sees canonical complaints. This is what makes ARI/NMI and
deduplication F1 measurable without leaking labels into the pipeline.

### 4.4 Ingestion adapter (real data later)

`src/data/ingest.py` with one function per source shape:
`ingest_canonical_csv`, `ingest_cpgrams_extract`, `ingest_pgms_export`.
Each maps to the canonical schema, records provenance, and refuses rows lacking a
`source`. This is what makes the "swap in real data" story credible instead of aspirational.

### 4.5 Licensing & ethics record

`docs/DATA.md` must contain: source, licence, retrieval date, row count, anonymisation
steps, PII handling policy (strip names/phone/ID numbers on ingest), and an explicit
statement that synthetic data is synthetic. This single page answers most examiner
questions about data integrity.

---

## 5. Database schema (PostgreSQL + pgvector)

Manage with Alembic. All tables get `created_at`, `updated_at`. Soft-delete via `deleted_at`
on user-generated content.

```sql
-- identity
users(id, email UNIQUE, password_hash, full_name, role, phone, district,
      is_active, created_at, updated_at)
-- role: citizen | partner | admin
organizations(id, name, type, website, description, district, contact_email)
-- type: university_dept | research_lab | ngo | industry | government
partner_capabilities(organization_id, tag_id)         -- M:N

-- taxonomy
domains(id, slug, name_en, name_hi, description)
sub_issues(id, domain_id, slug, name_en, name_hi)
capability_tags(id, slug, name_en, name_hi, partner_types[])  -- who can solve what

-- core content
complaints(id, report_id UNIQUE, submitted_by, district, raw_text, language,
           severity, affected_population, reported_on, lat, lon,
           source, is_synthetic, status, duplicate_of, embedding vector(384))
-- status: pending | clustered | merged | rejected
complaint_duplicates(complaint_id, candidate_id, similarity, decision)
-- decision: auto_merged | suggested | rejected

challenges(id, slug, title, summary, domain_id, sub_issue_id,
           district_count, complaint_count, affected_total,
           severity_score, priority_score, priority_breakdown JSONB,
           status, created_by, approved_by, published_at)
-- status: draft | under_review | published | archived
challenge_complaints(challenge_id, complaint_id, similarity)

challenge_matches(id, challenge_id, organization_id, score,
                  breakdown JSONB, status, reviewed_by)
-- status: suggested | confirmed | declined | expressed_interest

feedback(id, target_type, target_id, user_id, rating, comment, created_at)
model_runs(id, model_name, version, params JSONB, metrics JSONB,
           trained_at, artifact_path, is_active)
audit_log(id, actor_id, action, entity_type, entity_id, payload JSONB, created_at)
districts(id, name, division, population, geojson_feature_id)
```

Indexes: `embedding` → HNSW (`vector_cosine_ops`); `complaints(district)`,
`complaints(reported_on)`, `complaints(severity)`, `challenges(status, priority_score)`,
full-text GIN on `raw_text`.

**Migration of existing data:** export the 3 rows from `challenge_map.db` to
`migrations/legacy_export.json`, import them with `is_synthetic=false` only if their
provenance is known — otherwise import as `synthetic`. Then **delete `challenge_map.db`**.

---

## 6. ML / AI pipeline

### 6.1 Stages

1. **Normalise** — `src/nlp/text_preparation.py` (keep): Unicode NFC, Devanagari
   preservation, Hinglish token handling, digits/emoji stripping, script detection.
2. **Embed** — `sentence-transformers` multilingual model, CPU-friendly:
   `paraphrase-multilingual-MiniLM-L12-v2` (384-d) as default;
   benchmark `intfloat/multilingual-e5-small` in the comparison table.
   Cache embeddings in `complaints.embedding`; batch 64.
3. **Deduplicate** — cosine similarity + threshold calibrated on the injected duplicate
   groups (sweep 0.70–0.95, pick max-F1 threshold). Run **at submission time** (top-5
   nearest via pgvector) and nightly (full sweep).
4. **Cluster** — **HDBSCAN** primary (no fixed k, handles noise, variable density) with
   **K-Means** and **Agglomerative** as baselines; `k` swept 4→15.
5. **Name topics** — c-TF-IDF top terms + dominant sub-issue; admin can rename.
6. **Score priority** — transparent weighted index, stored with its breakdown:
   `0.30·severity + 0.25·log(affected_population) + 0.20·complaint_volume
    + 0.15·district_spread + 0.10·recurrence`. Weights live in config, not in code,
   and the report includes a sensitivity table (±10% on each weight).
7. **Match partners** — for each challenge: candidate partners whose capability tags
   intersect the challenge's tags; score
   `0.40·tag_overlap + 0.25·district_proximity + 0.20·severity + 0.15·capacity`.
   Persist the **breakdown**, not just the score, so the UI can explain every match.
8. **Persist** — cluster → `challenges`, membership → `challenge_complaints`,
   matches → `challenge_matches`, metrics → `model_runs`.

### 6.2 Training & evaluation protocol

| Evaluation | Metric | Why |
|---|---|---|
| Dedup (on injected ground truth) | precision, recall, F1, threshold curve | proves the duplicate claim |
| Clustering vs generator labels | **ARI, NMI, purity** | the numbers students usually lack |
| Clustering vs human labels | ARI, NMI on a 300-complaint hand-labelled sample, 2 annotators, **Cohen's κ** | proves it generalises past the generator |
| Clustering vs real benchmark | ARI, NMI, purity on the CC0 Kaggle set (14 categories) | proves it is not synthetic-only |
| Intrinsic | silhouette, Davies–Bouldin | supporting only, never the headline |
| Baseline comparison | TF-IDF+KMeans **vs** SBERT+HDBSCAN, same data, same metrics | justifies the deep model |
| Error analysis | 10 misassigned examples + cause notes | the slide examiners remember |
| Matching (manual) | precision@5 on 50 challenges reviewed by hand | shows the matching layer works |

**Rules:** every metric goes into `model_runs.metrics` and into
`docs/RESULTS.md` with the seed and dataset version. No metric is quoted without its
dataset and baseline. Targets are for Phase 5 to *measure*, never to assume.

### 6.3 Model artifacts

`models/` holds `embedding_config.json`, `dedup_threshold.json`,
`hdbscan_params.json`, `priority_weights.json`, `matching_weights.json`.
Each file carries `version`, `seed`, `trained_on`, `metrics`. `models/saved/*` stays gitignored
except the JSON configs.

---

## 7. Backend API (FastAPI)

Keep `api/main.py` as the seed; split into `api/routers/*` and `api/services/*`.

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | citizen signup (email, password ≥10, district) |
| POST | `/auth/login` | public | JWT access + refresh |
| GET | `/auth/me` | any | profile |
| POST | `/complaints` | citizen | submit; returns `{complaint_id, duplicate_candidates[]}` |
| POST | `/complaints/{id}/merge` | citizen/admin | attach to an existing challenge instead |
| GET | `/complaints` | admin | paginated queue, filters |
| GET | `/challenges` | public | published, filter by district/domain/priority, sort |
| GET | `/challenges/{slug}` | public | brief, evidence, timeline, matches |
| PATCH | `/challenges/{id}` | admin | rename, set domain, approve, archive |
| POST | `/challenges/{id}/publish` | admin | draft → published |
| GET | `/partners` | public | directory |
| GET | `/partners/me/matches` | partner | matched challenges |
| POST | `/matches/{id}/interest` | partner | express interest |
| PATCH | `/matches/{id}` | admin | confirm / decline |
| POST | `/feedback` | citizen | rate resolution |
| GET | `/analytics/districts` | public | counts + severity by district (choropleth) |
| GET | `/analytics/trends` | public | monthly series by domain |
| GET | `/admin/stats` | admin | queue sizes, resolution %, model health |
| POST | `/admin/jobs/recluster` | admin | trigger re-clustering |
| GET | `/models` | admin | latest metrics per model version |
| GET | `/health` | public | liveness + DB check |

Cross-cutting: Pydantic v2 validation; `HTTPBearer` + role dependency; `slowapi`
rate limiting on `/auth/*` and `/complaints`; `select` with pagination;
`request_id` middleware; structured logging; OpenAPI docs at `/docs` (use it in the report).
Replace deprecated `@app.on_event("startup")` with `lifespan`.

Env: `DATABASE_URL`, `JWT_SECRET`, `JWT_TTL_MINUTES`, `ALLOWED_ORIGINS`,
`EMBEDDING_MODEL`, `DEDUP_THRESHOLD`, `ENV`.

---

## 8. Frontend (Next.js)

### 8.1 Design language

Warm, civic, trustworthy — not a generic dashboard. Palette: ink `#0B1F2A`, sand
`#F7F4EF`, primary teal `#0F766E`, accent amber `#D97706`, danger `#B91C1C`.
Type: **Inter** + **Noto Sans Devanagari** (Hindi must never render as tofu).
8-pt spacing scale, 12-col grid, soft shadows, 2px focus rings, **WCAG AA** contrast,
full dark mode, skeleton loaders, empty states with actions, mobile-first down to 360px.

Motion: 150–250 ms ease-out transitions only; no parallax, no scroll-jacking.
Charts: Recharts. Map: react-leaflet + bundled Jharkhand district GeoJSON
(`data/geography/`, add the 24-district file — the current single state outline is not
enough for a choropleth).

### 8.2 Routes

```
/                        Landing: problem, live impact counters, district choropleth, featured challenges
/submit                  Complaint form (Hindi/English toggle) → live "3 similar reports found" panel → attach or create
/challenges              Browse: filter chips (domain, district, severity, priority), map/list toggle, sort
/challenges/[slug]       Challenge brief: summary, affected districts, evidence quotes, timeline chart,
                         priority breakdown, matched partners with score explanations, "I can help"
/partners                Partner directory
/partners/dashboard      Matched challenges, expressed interest, portfolio
/admin                   Overview: queue counts, model metrics, recent activity
/admin/review            Duplicate-suggestion queue (merge / keep separate)
/admin/challenges        Rename, re-tag, approve, publish
/admin/matches           Confirm or decline matches
/login, /register        Auth
/methodology             Data sources, corpus provenance, metrics, limitations, ethics  ← examiners read this
```

### 8.3 Key UX moments (the ones worth demoing)

1. **Duplicate interception** — typing a Ranchi water complaint and seeing
   "4 similar reports in Ranchi since July — attach to *Handpump failure, 12 wards*?"
   This is the product thesis in one screen.
2. **Challenge brief** — one page that a university department could act on.
3. **Explainable match** — "Civil Engineering, BIT Mesra — 0.82 (water-infrastructure ×3,
   2 districts within 60 km, 14,000 affected)".
4. **District choropleth** — real geography, real counts, honest "synthetic data" badge.

Accessibility and i18n are requirements, not polish: every string through a dictionary,
`lang` toggles EN/HI, all inputs labelled, keyboard-navigable admin tables.

---

## 9. Cleanup & removal ledger

**Removed in this commit** (see git history for the exact diff):

| Removed | Why |
|---|---|
| `data/raw/chicago_311_sample.csv` (253 MB) | unrelated US template data, bulk clutter |
| `data/raw/nyc_311_sample.csv` | unrelated US template data |
| `data/raw/nyc_311_prepared.csv` | made the app show Brooklyn/Manhattan as "Jharkhand districts" |
| `data/raw/dataset_research.md` | documents a superseded decision |
| `dashboard/` (placeholder README) | superseded by `frontend/` |
| `database/` (placeholder README) | superseded by Alembic migrations |
| `notebooks/README.md`, `models/README.md` | empty placeholders; dirs kept for real artifacts |
| all `__pycache__/` | build junk |

**Scheduled removals (phase-gated, do not do early):**

| Item | Phase | Gate |
|---|---|---|
| `streamlit_app.py`, `.streamlit/` | 6 | only after the Next.js app reaches feature parity |
| `requirements.txt` (split into `requirements/base|api|ml|dev`) | 1 | CI installs from the new files |
| `challenge_map.db` | 2 | after Postgres import is verified |
| `sample_reports.csv` (40 rows) | **Done** | removed 12 Nov 2026; the default fallback in `prepare_dataset.py` was removed first |
| `.venv-1` (duplicate env) | **Done** | removed 12 Nov 2026; `.venv313` runs the full suite |

**Kept deliberately:** `src/nlp/*` (validated, becomes the ML core),
`src/data/complaints.py` (canonical contract), `tests/*` (extend, never delete),
`data/geography/jharkhand_state.geojson` (extend to 24 districts),
`data/source_manifest.template.csv` (becomes `source_manifest.csv`).

---

## 10. Testing strategy

| Layer | Tool | Coverage target |
|---|---|---|
| Unit (text prep, dedup, clustering, priority, matching) | pytest | keep existing 28, extend to ≥ 60 |
| API (auth, RBAC, complaints, challenges, matches) | pytest + `TestClient` on a throwaway Postgres schema | all endpoints, 401/403/404/409/422 paths |
| Database | migration up/down test | Alembic head is clean |
| Frontend components | Vitest + Testing Library | form validation, duplicate panel, filter logic |
| E2E | Playwright | submit→duplicate→attach; admin publish; partner interest |
| Data contract | pytest | generator output validates against canonical schema |
| ML regression | pytest | metrics stored in `model_runs` must not drop below recorded baseline |

CI (GitHub Actions): `ruff`, `mypy` (soft), `pytest`, `npm run lint`, `npm run build`,
`playwright test` on the main flows. Badge in the README.

---

## 11. DevOps

The database is an **external dependency addressed by `DATABASE_URL`**, not a container this
project ships. **Docker is optional at every phase.** Any of these satisfies the database
requirement; the code path is identical for all three:

| Route to Postgres 16 + pgvector | Requires Docker | Notes |
|---|---|---|
| Hosted free tier (Neon; provider re-validated in Phase 7) | **No** | Default for development and the hosted demo — only `DATABASE_URL` is needed |
| Local Docker (`postgres:16` + pgvector image) | Yes | Offline / CI-identical option, for whoever has it installed |
| Native Postgres install | No | Must provide the `vector` extension; no official Windows binary, so the compile cost is real |

- `.env.example` with every variable, no secrets committed. `DATABASE_URL` is the only
database switch — no code path reads a Docker-specific value or a container hostname.
- `docker-compose.yml` (**optional convenience only**): `db` (postgres:16 + pgvector), `api`,
  `web`. Absent or unused, `make migrate` / `make seed` / `make test` behave identically
  against a hosted `DATABASE_URL`.
- `Makefile`: `make migrate`, `make seed`, `make test`, `make eval` — all database-target
  agnostic; `make dev` starts api + web; `make db-up` exists only for the compose route and
  is skipped (or a no-op) when a hosted database is configured.
- `scripts/seed_db.py` — generates + loads the synthetic corpus into whatever `DATABASE_URL`
  points at.
- `scripts/run_eval.py` — produces `docs/RESULTS.md` (markdown table + charts).
- Structured logs; `/health` probes the configured database, so it works with or without
  compose.

**Rule for every phase:** a gate is written against a **reachable `DATABASE_URL`** plus a query
that proves the schema, never against "a container is running". This keeps the plan executable
on a machine with no Docker, no `psql`, and no local Postgres.

---

## 12. Execution plan (10 weeks)

### Phase 1 — Repo hygiene & tooling (2 days)
Init git, `.gitignore` rewrite, `frontend/` + `api/` layout, split requirements, pin
Python 3.12 venv, install torch + sentence-transformers, CI skeleton, LICENSE, `docs/`.
**Gate:** `pip install -r requirements/ml.txt` succeeds on 3.12; CI green on an empty app.

### Phase 2 — Database & canonical model (3 days)
Provision Postgres 16 + pgvector — a **hosted free-tier instance via `DATABASE_URL` is the
default route and needs no Docker**; a local compose stack or a native install are acceptable
alternatives (§11). Then SQLAlchemy models, Alembic initial migration, legacy import, delete
`challenge_map.db`.
**Gate:** `alembic upgrade head` + `downgrade base` + `upgrade head` succeeds against a
reachable `DATABASE_URL`; `SELECT extname FROM pg_extension WHERE extname = 'vector';` returns
`vector`; 3 legacy rows queryable. **A reachable database is the gate — not a container.**
Docker, a compose file and a local server install are all explicitly not required to pass it.

### Phase 3 — Synthetic corpus + ingestion (4 days)
Generator, 15k + 2k files, manifest, EDA notebook, `ingest.py`, validator tests,
CC0 benchmark loader.
**Gate:** 15k rows validate; all 24 districts present; duplicate groups correctly injected
(dedup ground truth recall = 1.0 by construction); manifest complete.

### Phase 4 — ML pipeline & evaluation (6 days)
SBERT embeddings, dedup threshold sweep, HDBSCAN + baselines, c-TF-IDF naming,
priority index, matching engine, `run_eval.py`, `docs/RESULTS.md`.
**Gate:** RESULTS.md has ARI/NMI/purity for ≥2 algorithms on ≥2 datasets, dedup F1,
TF-IDF vs SBERT table, κ from the 300-sample annotation, error-analysis section.

**Gate status (11 Nov 2026).** Met: ARI/NMI/purity for three algorithms on the 3,000-row
sample and the untouched 2,000-row held-out set; dedup F1 0.743 at threshold 0.85;
c-TF-IDF naming; error analysis. Not met, and not faked: the TF-IDF vs SBERT table
(the working 3.13 environment does not have `sentence-transformers` installed; adding
torch is a multi-GB step that was not taken, as recorded in `models/embedding_config.json`)
and Cohen's κ (needs two
human annotators; an evaluator script cannot produce it). Both stay in RESULTS.md
under "Not measured".

### Phase 5 — Backend API (6 days)
Routers, auth/JWT, RBAC, dedup-on-submit, background re-cluster, analytics endpoints,
OpenAPI polish, pytest suite.
**Gate:** OpenAPI complete; ≥ 60 tests pass; authenticated flows return correct 401/403.

**Gate status (11 Nov 2026).** Met: the router/service split exists behind `/api/v1`, JWT
access + refresh (rotated, digests stored), three roles, dedup-on-submit, re-cluster job,
challenges, matches, analytics, admin console, `GET /models`, and 127 passing tests
(24 new API tests covering 401 vs 403, ownership 404s, duplicate suggestion,
merge conflicts, clustering, publishing and match decisions, plus 2 tests for the
legacy-database rebuild). Not met, deliberately:
persistence is still the SQLite store because Phase 2 has no Postgres instance, and
the rate-limit counters are per process. Both are recorded in
`api/README.md` under "Implementation gaps" rather than left implicit. The client-facing
paths also differ slightly from the table in §7: match decisions are
`PATCH /admin/matches/{id}`, and `GET /complaints` is the citizen's own list while the
queue lives at `GET /admin/complaints`.

### Phase 6 — Frontend v1 (10 days)
Design tokens, layout, auth pages, submit + duplicate panel, browse, challenge detail
with map and charts, methodology page, i18n EN/HI, dark mode.
**Gate:** Playwright happy paths pass; Lighthouse ≥ 90 accessibility/performance on
`/` and `/challenges`; **then and only then delete Streamlit.**

### Phase 7 — Admin & partner portals (5 days)
Review queue, approve/publish, rename, match confirmation, partner dashboard, feedback.
**Gate:** full lifecycle demo — citizen submits → duplicate suggested → admin publishes
challenge → match suggested → partner expresses interest → citizen sees resolution.

### Phase 8 — Hardening & deploy (4 days)
Docker Compose one-command run, hosted demo (Neon + a PaaS for api/web — validate at
this point), seed-on-boot, error states, rate limits, backup/restore drill.
**Gate:** a fresh clone runs with `make dev` and no manual steps beyond `.env`.

**Gate status (12 Nov 2026).** Partially met: `scripts/dev.py` implements the gate
without requiring `make` (which is not installed on this machine), loads `.env`,
waits for a healthy API, starts both services and terminates both process trees;
the API also reads `.env` directly. Met locally: `scripts/backup_db.py` takes an online SQLite copy, verifies
`PRAGMA integrity_check`, and restores it (covered by tests). Not met: Docker Compose, a
hosted deployment and a Postgres backup drill — the local copy does not test `pg_dump`
or a managed snapshot.

### Phase 9 — Documentation & report pack (4 days)
Rewrite `README.md` to match reality exactly, `docs/DATA.md`, `docs/ARCHITECTURE.md`,
`docs/RESULTS.md`, `docs/VIVA.md`, screenshots, 8–10 page report, slide deck.
**Gate:** every claim in the README is reproducible by a command in the README.

**Gate status (12 Nov 2026).** Audited command-by-command. Fixed: the documented test
command failed without `-t .` (26 failures) and is now correct; the documented
`discover_topics` input did not exist, so a `prepare_dataset.py` step was added and run;
the CC0 benchmark was described as “used” when RESULTS already said it was never
downloaded; the documented 3.12 venv does not exist here, so the working 3.13 venv is
documented (CI still runs 3.12); the methodology page claimed SBERT, Phase-4-pending
statuses, `official_extract` sources and PII scrubbing on API submissions that do not
match the code. Added `docs/DATA.md`, `docs/ARCHITECTURE.md` and `docs/VIVA.md`. Not
produced: screenshots, the written report and the slide deck.

### Phase 10 — Buffer & polish (3 days)
Bug fixes, a11y audit, empty-state copy, demo script rehearsal, final metric refresh.
**Gate:** two consecutive clean end-to-end demo runs.

**Gate status (12 Nov 2026).** Partially met in scripted form: `tests/test_lifecycle.py`
exercises the entire lifecycle twice, each run on a fresh temporary database, through
the same endpoints the UI calls, and the suite is green. Accessibility: the active nav
link and admin tab expose `aria-current`, and both admin tables now carry captions and
column scopes. Not done: two browser-driven demo runs, an axe/Lighthouse audit,
screenshots, the written report and the slide deck. The ML metrics were not refreshed
because no ML code changed after the 11 Nov evaluation.

### 12.7 Minimum viable submission (cut line)

If the deadline lands mid-plan, ship **Phases 1–6** only, with admin actions performed
via `curl`/`/docs` and documented as such. That still satisfies: real web UI, real
database, real ML pipeline, honest evaluation, honest docs. Anything less than Phase 5
is not defensible.

---

## 13. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| PyTorch/SBERT install pain on the student's machine | High | Standardise on Python 3.12; CPU wheels; Docker fallback; cache model in `models/` |
| Scope: frontend + ML + admin in 10 weeks | High | Hard cut line (12.7); admin UI is the first thing to drop to API-only |
| Synthetic data criticised as "fake" | High | Real CC0 benchmark + human-labelled 300 + explicit provenance UI + outreach evidence |
| No official Jharkhand data granted | Medium | Document the request and the refusal; use CPGRAMS published statistics for context |
| Metrics disappoint (low ARI) | Medium | Report honestly with baseline comparison and error analysis — that *is* good science |
| District GeoJSON unavailable/incorrect | Low | OpenStreetMap-derived district shapes (ODbL 1.0); validate 24 feature names against `DISTRICTS` |
| Team time collision with exams | Medium | Phases 1–6 ordered by defensibility, not by novelty |

---

## 14. Definition of done

A reviewer can, unaided:

1. `git clone && cp .env.example .env && python scripts/dev.py` → working site at `localhost:3000` (`make dev` does the same where `make` is installed).
2. Submit a Hindi complaint and watch a duplicate be suggested.
3. Open a published challenge and read why each partner was matched.
4. Open `/methodology` and see data provenance, corpus size, metrics and limitations.
5. Open `/docs` (OpenAPI) and hit any endpoint.
6. Read `docs/RESULTS.md` and find ARI/NMI/purity, dedup F1, and the TF-IDF vs SBERT table.
7. Find **zero** claims in the README that fail when executed.

---

## 15. Final repository layout

```
challengemap/
├── api/                     # FastAPI app
│   ├── main.py  deps.py  routers/  services/  schemas/
├── src/                     # importable core
│   ├── data/                # complaints.py, synthetic_generator.py, ingest.py
│   └── nlp/                 # text_preparation, embeddings, duplicate_detection,
│                            # topic_discovery, priority, matching
├── frontend/                # Next.js app
│   ├── app/  components/  lib/  messages/{en,hi}.json  public/
├── alembic/                 # migrations
├── scripts/                 # seed_db, run_eval, migrate_legacy
├── tests/                   # pytest (api, nlp, data)
├── frontend/tests/          # vitest + playwright
├── data/
│   ├── synthetic/           # complaints_15k.csv, complaints_2k_eval.csv
│   ├── geography/           # jharkhand_districts.geojson
│   └── source_manifest.csv
├── models/                  # JSON configs + metrics
├── notebooks/               # 01_corpus_eda, 02_model_comparison
├── docs/                    # MASTER_PLAN.md, DATA.md, ARCHITECTURE.md, RESULTS.md, VIVA.md
├── docker-compose.yml  Makefile  .env.example  README.md
```

---

*This plan supersedes the placeholder migration notes previously in `dashboard/`,
`database/`, `notebooks/` and `models/` README files, and the feature claims in the
old `README.md`.*
