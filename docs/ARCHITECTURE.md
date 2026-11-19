# Architecture (implemented)

**Last verified:** 12 November 2026. This page describes what runs today, not the
target stack in `docs/MASTER_PLAN.md` §3. Deviations are listed at the end.

## 1. Runtime

```
Browser
  │  React 19 / Next.js 15 App Router (TypeScript, Tailwind)
  │  fetch + Bearer JWT, localStorage session
  ▼
Next.js (dev :3000, production `next build`/`next start`)
  │  client components call the API directly
  │  server components read public briefs for /challenges/[slug]
  ▼
FastAPI (uvicorn :8000, /api/v1, OpenAPI at /docs)
  │  routers → services → api/store.py
  ▼
SQLite database (challenge_map.db by default, CHALLENGEMAP_DB_PATH to move it)
```

No container, message queue or background worker is required. The re-cluster job runs
synchronously inside the admin request; the interface waits for its result.

## 2. Frontend

| Path | Rendering | Data |
|---|---|---|
| `/` | Server | Seeded demo dataset (`frontend/lib/data.ts`) |
| `/challenges` | Client | `GET /challenges`, falls back to the demo set with a badge |
| `/challenges/[slug]` | Server, dynamic | `GET /challenges/{slug}` + `/matches`, falls back to demo |
| `/submit` | Client | `POST /complaints`, then `/complaints/{id}/merge` |
| `/reports` | Client | `GET /complaints`, `GET/POST /complaints/{id}/feedback` |
| `/partners` | Server | Seeded demo directory |
| `/partners/dashboard` | Client | `GET /partners/me/matches`, `POST /matches/{id}/interest` |
| `/admin` | Client | `/admin/stats`, `/admin/complaints`, `/challenges?status=all`, `/matches` + mutations |
| `/login`, `/register` | Client | `/auth/login`, `/auth/register` and `/auth/refresh` |

- `frontend/components/session-provider.tsx` holds the user, persists the token pair and
  exposes sign-in/up/out; a storage listener keeps tabs in sync.
- `frontend/lib/api.ts` is the only HTTP layer. It adds the Bearer header, rotates the
  refresh token once on a 401, and converts API payloads into typed models.
- `frontend/lib/challenge-view.ts` maps lexicon domains (`water`, `health`, …) and
  numeric breakdowns onto the display models used by the brief.
- Public reads fail soft (`null`/`[]`) so the demo dataset keeps the site usable when the
  API is offline; mutations surface the API error instead.
- Role-bound navigation is cosmetic: every authorisation decision happens in
  `api/deps.py`, and the API returns 401/403 independently of the UI.

## 3. API surface

Routers live in `api/routers/` and are mounted under `/api/v1` by `api/main.py`:
`auth`, `complaints`, `challenges`, `partners`, `analytics`, `admin`, plus `health` and
the legacy `/me` in `main.py`. Request/response models are in `api/schemas.py`;
row-to-response conversion is in `api/presenters.py`.

| Role | Capabilities |
|---|---|
| public | published challenge list/detail/matches, partner directory, analytics, health |
| `citizen` | submit complaints, list/read/merge own reports, feedback |
| `partner` | own organisation's matches, express interest |
| `admin` | everything above plus the queue, stats, re-cluster, publishing, renaming, match decisions, staff accounts, model metrics |

Authentication: access + refresh JWTs signed with `JWT_SECRET`; refresh tokens are
stored as SHA-256 digests and rotated on use. Passwords use Argon2id with a transparent
PBKDF2 upgrade on login. Rate limits use `slowapi` with in-process counters.

## 4. Core request flows

### Submit → duplicate check → attach

1. `POST /complaints` inserts a `pending` row owned by the caller, then calls
   `api/services/dedup.py`.
2. That function compares the text with up to 500 non-merged complaints **in the same
   district** using sparse TF-IDF cosine (word 1–2 grams), returning at most five
   candidates at or above `DEDUP_THRESHOLD` (default 0.86).
3. The client shows the candidates. `POST /complaints/{id}/merge` marks the caller's own
   report `merged` and sets `duplicate_of`; the target is never modified, must exist in
   the same district, and must not itself be merged (409).

Nothing merges automatically: measured F1 peaks at 0.743, so the panel is a review aid.

### Re-cluster → publish → match

1. `POST /admin/jobs/recluster` requires at least 8 pending/clustered reports.
2. `api/services/clustering.py` fits TF-IDF on the queue, runs K-Means
   (`clusters` or `n/8`, capped), names clusters with c-TF-IDF, scores them with
   `src/nlp/priority.py`, inserts **draft** challenges, links member reports through
   `challenge_complaints`, and proposes up to three partners per challenge with
   `src/nlp/matching.py`.
3. Previous drafts are deleted on each run; published challenges are never touched.
4. `POST /challenges/{id}/publish` makes a brief public. `GET /challenges/{slug}` reads
   evidence, district counts and the monthly timeline from linked reports.
5. `PATCH /admin/matches/{id}` confirms or declines; `POST /matches/{id}/interest` lets
   the matched partner express interest (published challenges only).

The admin UI exposes all of these steps; the endpoints also work through `/docs`.

## 5. Data model (SQLite)

Created by `api/store.py` on startup; `tests/test_store_migration.py` covers rebuilding
the legacy `users` table whose CHECK lacked the `partner` role.

| Table | Purpose |
|---|---|
| `users` | username, Argon2id digest, role, district, organisation, active flag |
| `refresh_tokens` | SHA-256 token digests with expiry; rotated on use |
| `complaints` | report id, owner, district, place, raw text, language, severity, affected population, status, duplicate target, provenance |
| `challenges` | slug, title, summary, domain, capability tags, counts, severity/priority scores, JSON breakdown, status |
| `challenge_complaints` | challenge ↔ report membership with similarity |
| `organizations` | demo partner directory with capability tags, districts, capacity |
| `matches` | challenge ↔ organisation score, JSON breakdown, status |
| `feedback` | per-report resolution status and comment |
| `audit_log` | actor, action, entity, JSON payload |

Indexes cover district, status/date, feedback by report and matches by organisation.
There is no vector column: dedup is recomputed on demand, which is O(n) per district.

## 6. ML layer

`src/nlp/` is the importable core used by both the evaluation scripts and the API:
text normalisation, TF-IDF/SVD vectorizers, clustering, c-TF-IDF naming, priority and
matching. The Sentence-BERT path is implemented but optional; it is not installed here,
so measured results come from TF-IDF baselines (`docs/RESULTS.md`). Model configuration
and metrics are JSON files in `models/`.

## 7. Configuration

`.env` is read by `api/main.py` (real environment variables win). Keys:

- `JWT_SECRET`, `JWT_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`
- `CHALLENGEMAP_BOOTSTRAP_ADMIN` (`user:password`, promoted to admin on startup)
- `CHALLENGEMAP_DB_PATH`, `ENV`, `ALLOWED_ORIGINS`
- `DEDUP_THRESHOLD`, `RATE_LIMIT_ENABLED`
- `NEXT_PUBLIC_API_BASE` (frontend)

`scripts/dev.py` sources the same file and starts both services.

## 8. Verification

- `python -m unittest discover -s tests -t .` — 127 tests: data contract, generator,
  text prep, evaluation helpers, clustering, priority/matching, API auth/RBAC/dedup/
  merge/recluster/publish/matches/analytics/briefs, store migration, env loader and
  backup/restore.
- `scripts/backup_db.py` copies the SQLite store with the online backup API, verifies
  `PRAGMA integrity_check`, and restores it only with `--force`.
- `cd frontend && npm run typecheck && npm run build`.
- The launcher was smoke-tested: API health 200, web home 200, both ports released on exit.

## 9. Deviations from the target stack, and why

| Plan | Implemented | Reason / next step |
|---|---|---|
| PostgreSQL + pgvector, SQLAlchemy, Alembic | SQLite behind `api/store.py` | no Postgres endpoint configured; Phase 2 gate needs a reachable `DATABASE_URL` |
| HDBSCAN primary clustering | K-Means in the API job; all three measured offline | HDBSCAN was not the best measured option on this corpus |
| SBERT embeddings for dedup | exact sparse TF-IDF cosine | SBERT not installed in this environment; path exists |
| Celery/nightly worker | synchronous admin endpoint | a single-node demo; no queue infrastructure |
| Shared rate-limit storage | in-process `slowapi` counters | documented gap; needs Redis or similar |
| Recharts + Leaflet choropleth | SVG bars and a schematic district grid | no verified 24-district GeoJSON bundled |
| Playwright/Vitest/Lighthouse | none | not run; UI verified by build, types and API tests |

## 10. Where to change what

- Persistence or schema: `api/store.py` (all SQL lives here).
- Endpoint behaviour or roles: `api/routers/*` and `api/deps.py`.
- Dedup, clustering, priority, matching: `api/services/*` and `src/nlp/*`.
- Response shape: `api/schemas.py` and `api/presenters.py`.
- Browser data access: `frontend/lib/api.ts`; display mapping: `frontend/lib/challenge-view.ts`.
