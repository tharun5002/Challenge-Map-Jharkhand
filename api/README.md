# ChallengeMap REST API

FastAPI service behind the product: citizen intake with duplicate interception,
challenge briefs generated from clustered complaints, explainable partner
matching, public analytics and an administrator console.

OpenAPI documentation is generated at `/docs` (and `/openapi.json`).

## Run it

```bash
python -m pip install -r requirements/api.txt
export JWT_SECRET="a-long-random-private-value"
export CHALLENGEMAP_BOOTSTRAP_ADMIN="admin:change-this-password"
export CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL="name@example.com"
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

On startup the app creates its tables, ensures the bootstrap administrator and
seeds the demo partner directory. **The demo organizations are fixtures, not real
partnerships.**

## Authentication and roles

`POST /api/v1/auth/login` returns a short-lived access token and a rotating
refresh token. Send the access token as `Authorization: Bearer <token>`.

Login requires an email address, password, and selected account role
(`citizen`, `partner`, or `admin`). The API looks up accounts by email only and
rejects a login if the selected role does not match the account's stored role.
Usernames are used for account management only; they cannot be used to sign in.
Citizen signup and administrator-created accounts require a unique email address.
Partner representatives can submit an organization name and job title for review;
their account remains disabled until an administrator approves it in the Accounts
tab. Approval creates or links the organization before enabling partner access.
Set `CHALLENGEMAP_BOOTSTRAP_ADMIN_EMAIL` for the bootstrap administrator.
Legacy HTTP Basic API requests also require the account email in the username
field; the stored account role still controls which endpoints are accessible.

| Role | Can do |
|---|---|
| `citizen` | submit complaints, read their own reports, attach them to any report in the same district, leave feedback |
| `partner` | respond to client reports in their organization's districts, read matched challenges, express interest |
| `admin` | the complaint queue, re-cluster job, challenge editing/publishing, match decisions, staff accounts, model metrics |

Missing credentials return **401**; a valid token with the wrong role returns
**403**. HTTP Basic is still accepted as a fallback so older clients and the
original citizen tests keep working; new clients should use Bearer tokens.

Refresh tokens are stored as SHA-256 digests and rotated on use, so a replayed
token is rejected.

## Endpoints

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | public | liveness plus a database check |
| POST | `/api/v1/auth/register` | public | citizen signup |
| POST | `/api/v1/auth/register/partner` | public | submit a partner account request for administrator approval |
| POST | `/api/v1/auth/login` | public | access + refresh tokens |
| POST | `/api/v1/auth/refresh` | public | rotate the refresh token |
| GET | `/api/v1/auth/me` | any | profile |
| GET | `/api/v1/me` | any | legacy profile alias (Basic compatible) |
| POST | `/api/v1/complaints` | citizen | submit; returns `duplicate_candidates` |
| GET | `/api/v1/complaints` | citizen | own reports, paginated |
| GET | `/api/v1/complaints/{report_id}` | owner/admin | one report |
| POST | `/api/v1/complaints/{report_id}/merge` | owner/admin | attach your report to an existing one in the same district |
| POST | `/api/v1/complaints/{report_id}/feedback` | owner/admin | resolution feedback |
| GET | `/api/v1/complaints/{report_id}/feedback` | owner/admin | feedback history |
| GET | `/api/v1/staff/issues` | partner/admin | active client reports in the staff member's organization districts |
| POST | `/api/v1/staff/issues/{report_id}/responses` | partner/admin | send an acknowledged, in-progress, resolved or unable-to-resolve update to the client |
| GET | `/api/v1/challenges` | public | published briefs, ordered by priority |
| GET | `/api/v1/challenges?status=draft` | admin | unpublished briefs |
| GET | `/api/v1/challenges/{slug}` | public | one brief with evidence, districts and monthly timeline |
| GET | `/api/v1/challenges/{slug}/matches` | public | matched partners with score breakdown |
| PATCH | `/api/v1/challenges/{id}` | admin | rename / re-tag |
| POST | `/api/v1/challenges/{id}/publish` | admin | draft → published |
| GET | `/api/v1/partners` | public | partner directory |
| GET | `/api/v1/partners/me/matches` | partner | matched challenges |
| POST | `/api/v1/matches/{id}/interest` | partner | express interest |
| GET | `/api/v1/analytics/districts` | public | counts and severity by district |
| GET | `/api/v1/analytics/trends` | public | monthly counts by domain |
| GET | `/api/v1/admin/complaints` | admin | queue with `status`/`district` filters |
| GET | `/api/v1/admin/stats` | admin | queue sizes and totals |
| POST | `/api/v1/admin/jobs/recluster` | admin | force a re-cluster of pending complaints (submissions cluster automatically) |
| GET | `/api/v1/admin/users` | admin | list accounts, optionally filtered by role |
| POST | `/api/v1/admin/users` | admin | create citizen, partner or admin accounts |
| PATCH | `/api/v1/admin/users/{id}` | admin | change role, active state, district or organisation |
| PATCH | `/api/v1/admin/matches/{id}` | admin | confirm or decline a match |
| GET | `/api/v1/models` | admin | latest measured model metrics |

## Duplicate interception

On submit, the report is compared with non-merged complaints in the same district
using the exact sparse TF-IDF cosine measured in `docs/RESULTS.md`. Candidates at
or above `DEDUP_THRESHOLD` (default `0.86`) are returned for the submitter to
attach or ignore. Nothing is merged automatically: the Phase 4 sweep put the best
F1 at 0.743, which is a review aid, not an oracle.

Merging requires owning the report being attached, but **not** the report it is
attached to: a citizen can attach their report to a neighbour's report in the
same district, which only marks their own row `merged`. The target is never
modified, a cross-district target is reported as missing, and an already-merged
target is rejected with **409** so chains cannot form.

## Automatic clustering

Each accepted submission queues `recluster` in a FastAPI `BackgroundTasks` run, so
the queue is grouped into drafts (with priority scores and partner matches)
without an administrator pressing a button. The POST above remains for a forced
re-run, for example after a merge. Background runs are serialised in-process and
coalesced: a report submitted during a run triggers one more pass.

## Challenge briefs

Challenge rows carry the cluster counts plus `district_count`, `district_names`,
`tags` (the capability tags), a derived `severity` label and
`first_reported_at`/`last_reported_at`. `GET /challenges/{slug}` adds the content
the public brief renders, all computed from the reports linked through
`challenge_complaints`:

- `districts` — report counts per district, largest first;
- `evidence` — up to five recent, non-merged report texts with district, date and language;
- `timeline` — monthly report counts.

Matches include `organization_type` and `organization_districts` so the brief can
name who it is recommending and where they already work. Nothing in this payload
is illustrative: an empty cluster produces empty evidence and an empty timeline.

## Re-clustering

`POST /api/v1/admin/jobs/recluster` requires at least two complaints that are
`pending` or `clustered`; it names each cluster with c-TF-IDF, scores it with the priority index,
creates **draft** challenges, links the member reports and proposes up to three
partner matches. Published challenges are never touched, and previous drafts are
replaced on each run.

## Implementation gaps (deliberate, documented)

| Gap | Why | Where it lands |
|---|---|---|
| SQLite instead of PostgreSQL + pgvector | no Postgres instance is configured on this machine | Phase 2, behind `api/store.py` |
| Rate-limit counters are per process (in memory) | correct for a single-worker demo; a shared backend (`limits` storage) is a deployment concern | Phase 8 hardening |
| No email verification or password reset | out of scope for the graded deliverable | post-submission |
| Dedup is district-blocked and O(n) per district | matches what the Phase 4 evaluation measured; pgvector HNSW replaces it | Phase 2 |

## Tests

`python -m unittest discover -s tests -t .` covers the API (auth, RBAC, dedup,
merge, staff issue responses, re-clustering, publishing, matching, analytics and
briefs) alongside the data, NLP and config suites. The `-t .` flag is required because
`tests/__init__.py` must run before any module imports the app.
