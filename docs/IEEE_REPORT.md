# ChallengeMap: An Evidence-Grounded Pipeline for Turning Citizen Complaints into Ranked Challenge Briefs

**[Author Name]**

*[Department], [Institution]*

*[City, State, Country]*

*[email@example.com]*

---

## Abstract

Citizen grievances in Indian states arrive as dispersed, multilingual and heavily duplicated text, which makes them difficult for universities, non-governmental organisations and industry to act on. This paper reports the design, implementation and measured evaluation of **ChallengeMap**, an end-to-end system that ingests citizen complaints, intercepts near-duplicates, clusters related reports into draft challenges, ranks them with an explainable priority index, and matches them to partner organisations with a capability- and district-aware score. The prototype couples a FastAPI service (role-based access for citizens, partners and administrators; JWT authentication; SQLite persistence) with a Next.js 15 web client covering submission, briefs, partner and administrator workflows. Because no openly downloadable bulk corpus of Jharkhand complaints exists, evaluation uses a deterministic, seeded synthetic corpus of 15,000 complaints across all 24 districts, 12 domains, 71 sub-issues and three language registers, with 1,500 deliberately injected duplicates. On this corpus, character n-gram TF-IDF with agglomerative clustering reaches an adjusted Rand index of 0.253 (0.244 held-out) and normalised mutual information of 0.458; exact sparse TF-IDF cosine duplicate detection peaks at F1 = 0.743 at a 0.85 threshold; and a supervised TF-IDF + logistic-regression router separates the twelve synthetic domains at ceiling accuracy. We report these numbers together with the conditions that make them optimistic, and specify what remains unmeasured. No figure in this paper describes real Jharkhand complaint data.

**Index Terms**—Civic technology, complaint analytics, duplicate detection, topic discovery, multilingual NLP, explainable ranking, FastAPI, Next.js.

---

## I. Introduction

State grievance portals in India typically publish one complaint at a time, small comment threads, or aggregate counts. They rarely expose the raw text needed to ask systemic questions: which problems recur across districts, how severe they are, and which institution could address them. For Jharkhand, a state with 24 districts and substantial linguistic diversity across Hindi, English and Hinglish, this gap is practical rather than theoretical. A university department looking for field projects, an NGO choosing where to intervene, and an industry partner assessing a skilling programme all need the same artefact: a short, verifiable brief built from many citizen reports, with the evidence attached.

ChallengeMap was built to produce that artefact. The system accepts citizen submissions, compares each new report against existing reports in the same district, and offers near-duplicate candidates for the citizen to attach or ignore. Administrators cluster the pending queue into draft challenges, review and rename them, publish a brief, and confirm or decline proposed partner matches. Public pages render the published brief with evidence quotations, district distribution and a monthly report timeline.

The contribution of this work is fivefold:

1. **A canonical data contract** for complaints with strict validation, provenance fields, and a rule that synthetic rows can never be marked verified.
2. **A reproducible synthetic corpus** with injected near-duplicates and exact duplicates, ground-truth labels in sidecar files, and a deterministic seed, so deduplication and clustering can be measured rather than asserted.
3. **An evaluated NLP pipeline** comparing word and character TF-IDF encoders across K-Means, agglomerative clustering and HDBSCAN, with ARI, NMI, purity, silhouette and a threshold sweep for duplicate pairs.
4. **Explainable ranking**: a five-component priority index and a four-component partner-match score, each returning its component breakdown so that every published number can be interrogated.
5. **A working full-stack prototype** with authentication, role separation, an audit log, a re-clustering job, publishing controls and a responsive web interface.

The remainder of the paper describes related work (Section II), requirements (Section III), architecture (Section IV), data (Section V), methods (Section VI), implementation (Section VII), measured results (Section VIII), and the limits of those results (Section IX).

---

## II. Related Work

**Text representation.** Sparse term-weighting remains a strong baseline for short, domain-specific documents. TF-IDF with sublinear term frequency and cosine normalisation is well understood [5], [6], and the scikit-learn implementation used here is the standard reference [1]. Dense multilingual sentence encoders such as Sentence-BERT [2] cross script boundaries that lexical features cannot, but they require a PyTorch stack that was unavailable in the evaluation environment.

**Topic discovery.** Classical partitioning (K-Means), hierarchical agglomerative clustering with cosine linkage, and density-based HDBSCAN [4] represent three different assumptions about cluster shape. Because the product needs a fixed, reviewable number of challenge briefs, K-Means is used in the live re-clustering job, while all three algorithms are compared offline. Cluster naming follows the class-based TF-IDF (c-TF-IDF) procedure popularised by BERTopic [3]: a term is scored by its frequency within a cluster relative to its frequency across clusters, which surfaces characteristic vocabulary even when it is rare corpus-wide.

**Grievance redress.** Government portals such as CPGRAMS [13] provide lodgement and tracking but not open bulk text. The literature on e-government grievance analytics commonly reports supervised routing accuracy on labelled complaint corpora; this project reports both unsupervised structure and a supervised routing baseline, because the two answer different product questions ("what topics exist?" versus "which desk should receive this report?").

**Evaluation.** Clustering agreement is measured with the adjusted Rand index [7] and normalised mutual information, with purity reported as a descriptive complement. Duplicate detection is treated as pairwise classification and scored with precision, recall and F1. All metrics are computed against generator labels, never against human annotations, which is the central validity limitation discussed in Section IX.

---

## III. Requirements and Design Goals

The design was constrained by five requirements derived from the civic use case:

- **R1 — Explainability.** A priority score or partner recommendation that cannot be decomposed into named components is not usable in a public brief. Every score stores its component values, weights and weighted contributions.
- **R2 — Human authority.** No duplicate is merged automatically and no brief is published automatically. Machine output is a ranked candidate list; an administrator or citizen makes the decision.
- **R3 — Provenance.** Every complaint carries a `source_type`, and a synthetic row is structurally forbidden from carrying `verification_status = verified`.
- **R4 — Role separation.** Citizens, partner representatives and administrators have distinct capabilities enforced server-side, independent of the user interface.
- **R5 — Reproducibility.** Corpus generation, evaluation and tests must run from a clean checkout with fixed seeds and documented commands.

A deliberate non-goal was raw-scale ingestion. The system must first demonstrate a defensible pipeline on a corpus whose properties are known; real-text ingestion is a later phase behind the same canonical schema.

---

## IV. System Architecture

The implemented system is a three-tier application with no container, message queue or background worker requirement (Fig. 1).

```
Browser
  │  React 19 / Next.js 15 App Router (TypeScript, Tailwind CSS)
  │  fetch + Bearer JWT, localStorage session
  ▼
Next.js  (development :3000, production next build / next start)
  │  client components call the API directly
  │  server components read public briefs
  ▼
FastAPI  (uvicorn :8000, prefix /api/v1, OpenAPI at /docs)
  │  routers → services → api/store.py
  ▼
SQLite   (challenge_map.db, configurable via CHALLENGEMAP_DB_PATH)
```

**Fig. 1.** Runtime architecture of the implemented prototype.

The **presentation tier** is a Next.js 15 App Router application. Public pages (`/`, `/challenges`, `/challenges/[slug]`, `/methodology`) render seeded demo content or published API data; authenticated pages (`/submit`, `/reports`, `/partners/dashboard`, `/admin`, `/login`, `/register`) call the API. A single HTTP module (`frontend/lib/api.ts`) attaches the Bearer token, rotates a refresh token once on a 401, and maps payloads to typed view models. Public reads fail soft so that the demo site remains usable when the API is offline; mutations surface API errors rather than hiding them.

The **application tier** is a FastAPI service mounted under `/api/v1`, with routers for authentication, complaints, challenges, partners, staff responses, analytics and administration. Request and response models live in `api/schemas.py`; row-to-response conversion lives in `api/presenters.py`; all SQL is confined to `api/store.py`, which is the single seam for a future PostgreSQL migration.

The **persistence tier** is SQLite. Nine tables cover users, refresh tokens, complaints, challenges, challenge–complaint membership, organisations, matches, feedback, staff responses and an audit log, with indexes on district, status/date, feedback, staff responses and organisation matches. There is no vector column: duplicate similarity is recomputed on demand for the district block.

---

## V. Data

### A. Corpus composition

No openly downloadable bulk corpus of Jharkhand citizen complaints exists; the official portals publish single lodgements, small threads or aggregate counts. The development corpus is therefore synthetic and seeded:

| Property | Value |
|---|---|
| Training rows | 15,000 |
| Held-out rows | 2,000 (separate seed, never used for tuning) |
| Districts | 24 (all Jharkhand districts) |
| Domains | 12 |
| Sub-issues | 71 |
| Languages | Hindi, English, Hinglish |
| Injected duplicates | 1,500 (1,200 near-paraphrases, 300 exact) |
| Modelled period | 18 months with monsoon and month-end seasonality |

**TABLE I.** Composition of the synthetic development corpus.

Templates are filled with district, place, duration and affected-population slots, producing phrasing variation within a domain. Near-duplicates are true paraphrases of a source report (same template and slots, reworded), not merely a different template on the same sub-issue. Every injected row carries `is_duplicate`, `duplicate_kind`, `duplicate_of` and a `duplicate_group_id`. Ground-truth domain, sub-issue and severity labels live in sidecar CSV files keyed by `complaint_id`, so production code never reads labels.

### B. Canonical schema and validation

Every dataset must validate against a ten-column schema:

```
complaint_id, complaint_text, district, block, complaint_date, language,
severity, affected_population, source_type, verification_status
```

Validation rejects unknown districts, invented severity values, empty text and duplicate identifiers instead of repairing them silently. `severity` is restricted to `unknown | low | medium | high | critical`; `source_type` to `public_dataset | consent_survey | synthetic | other`. The combination of `source_type = synthetic` with `verification_status = verified` is rejected, which makes provenance a structural property rather than a convention.

### C. Privacy and licensing

The synthetic corpus contains no personal data by construction. The bulk ingestion path strips phone numbers, e-mail addresses and identifier patterns before writing canonical rows. The API submission path is different: it stores text as written, and the form warns citizens not to include names, phone numbers or identifiers, but no automatic scrubber runs on submissions. This is a documented gap, not a claim of anonymisation. Public evidence quotations never display account usernames. Code, corpus and metrics are original work; the bundled state outline is derived from OpenStreetMap under ODbL 1.0.

---

## VI. Methodology

### A. Text normalisation

Hindi and Hinglish text is normalised with Unicode NFKC, HTML unescaping, control-character replacement and whitespace collapse. Punctuation is removed for TF-IDF while retaining every character whose Unicode category begins with `L` (letter), `M` (combining mark) or `N` (number). Retaining marks is essential: every Devanagari vowel sign is category `Mn` or `Mc`, so a naive `\w` filter would split words such as "उपलब्धता" into fragments. Case folding is applied without transliteration, so the three language registers remain distinguishable — a property the error analysis later shows matters.

### B. Vectorisation

Two encoder families share one interface:

- **Word TF-IDF**, 1–2 grams, sublinear term frequency, `min_df = 2`, maximum document frequency initially 3%, reduced vocabulary to 60,000 terms, truncated SVD to 128 components.
- **Character TF-IDF**, `char_wb` 3–5 grams, the same frequency bounds, SVD to 160 components.

Both L2-normalise the reduced vectors. A boilerplate filter drops terms appearing in more than `max_df` of documents, because shared template sentences outvote topic vocabulary. The filter is loosened iteratively when it would empty a document, settling at 4.5% for both encoders on the 3,000-row sample; this is recorded in the model configuration rather than hidden. Duplicate detection bypasses the SVD entirely and uses the exact sparse cosine, because the reduced space inflates similarity between unrelated documents and can round an identical pair just below a 1.00 threshold.

### C. Duplicate detection

For a new report, the system retrieves up to 500 non-merged complaints in the same district, fits TF-IDF on that block, and scores the new report against each candidate with exact sparse cosine similarity. Candidates at or above `DEDUP_THRESHOLD` (default 0.86) are returned, at most five, ranked by similarity. Nothing is merged automatically.

Merging has a deliberate ownership rule: a citizen must own the report being attached, but need not own the target. This lets a citizen attach their report to a neighbour's report in the same district without granting edit rights over the neighbour's row. A cross-district target is reported as missing, and an already-merged target is rejected with HTTP 409 so that merge chains cannot form.

Offline, candidate pairs are each complaint's top-5 neighbours within its district block, mirroring product behaviour. Ground truth is the set of injected duplicate families.

### D. Clustering and naming

The administrative re-clustering job fits word TF-IDF on all `pending` or `clustered` reports, runs K-Means with `k` supplied by the administrator (or `n/8`, capped by queue size), and names each cluster with c-TF-IDF [3]. Naming is a post-hoc stage and never feeds back into the partition, so it cannot inflate agreement metrics. The job deletes previous **drafts** but never touches published challenges, links member reports through a membership table, and proposes up to three partner matches per challenge. The entire job runs synchronously inside the administrator's request.

### E. Priority index

Each challenge receives a score in the range 0–100:

```
priority = 100 × (0.30·severity + 0.25·affected + 0.20·volume
                  + 0.15·district_spread + 0.10·recurrence)
```

Severity is the mean mapped severity of member reports (`low` 0.25, `medium` 0.5, `high` 0.75, `critical` 1.0). Affected population and volume are min–max scaled after `log1p` transformation, so a 100,000-person outage is not treated as a thousand times worse than a 100-person one. District spread is the share of the state's 24 districts touched, capped at 1. Recurrence is the share of a group's reports whose normalised text was already reported in that group — "the same problem reported again", not recency. The component values, weights and weighted contributions are stored as JSON beside the score.

### F. Partner matching

A partner is scored against a challenge as:

```
match = 0.40·tag_overlap + 0.25·district_proximity
        + 0.20·severity + 0.15·capacity
```

Tag overlap is the share of the challenge's capability tags held by the partner. District proximity is 1.0 when the partner already works in a district the challenge touches; when an explicit distance is supplied, exponential decay with a 150 km scale is used instead. Severity is inherited from the challenge and capacity is the partner's declared capacity. The breakdown is returned with every match and rendered in the brief, so a recommendation reads as a sentence with named components rather than an opaque number.

### G. Supervised routing baseline

To separate "can the text be separated at all?" from "can it be separated without labels?", the same TF-IDF features are used with logistic regression trained on all 15,000 training rows and scored on the 2,000 held-out rows. This answers the routing question the product must eventually answer for a new complaint.

### H. Evaluation protocol

Clustering is evaluated on a 3,000-row stratified sample (k = 12, matching the 12 domains) and on the full 2,000-row held-out set; encoders are fitted on the training sample and only transformed on held-out rows. ARI [7], NMI, purity, silhouette and noise fraction are reported. Duplicate detection is evaluated as a threshold sweep from 0.30 to 1.00 using the injected pairs. The protocol deliberately reports the English-only slice alongside the mixed-language result, because a low mixed-language ARI can reflect script separation rather than absence of topic structure.

---

## VII. Implementation

### A. API and security

The service exposes more than thirty endpoints under `/api/v1`, documented automatically at `/docs`. Authentication uses short-lived JWT access tokens [8] and rotating refresh tokens whose SHA-256 digests are stored; a replayed refresh token is rejected. Passwords use Argon2id [9] with a transparent PBKDF2 upgrade on login for legacy accounts. HTTP Basic remains accepted as a fallback for older clients while the web application uses Bearer tokens. Missing credentials return 401; an authenticated but unauthorised request returns 403. A per-request identifier is attached to every response, and an audit log records administrative actions such as re-clustering decisions.

| Role | Capabilities |
|---|---|
| Public | published briefs, partner directory, district and trend analytics, health |
| Citizen | submit reports, list/read/merge own reports, feedback |
| Partner | matched challenges for its organisation, express interest, respond to clients |
| Administrator | queue, statistics, re-clustering, publishing, renaming, matches, accounts, model metrics |

**TABLE II.** Role capability matrix enforced in `api/deps.py`.

Rate limiting is applied to authentication and submission endpoints with in-process counters. This is correct for a single-worker demonstration and is explicitly listed as a deployment gap, because counters do not survive multiple workers.

### B. Web client

The client implements twelve routes, including a landing page with a 24-district intensity grid, a challenge library with a visible "demo data" badge when the API is unavailable, a brief page with evidence quotations and a monthly trend, a submission form that displays real duplicate candidates, a citizen reports and feedback page, a partner portal, and an administrator console. Typography supports Devanagari through Noto Sans Devanagari. Accessibility measures include keyboard navigation and visible focus states. Authorisation is never enforced in the browser: every decision is made by the API, and role-bound navigation is cosmetic.

### C. Development workflow and verification

A single launcher loads `.env`, starts the API, waits for `/api/v1/health`, then starts the web application and shuts both process trees down on interrupt. Dependencies are split by need — base data/ML, API, optional ML (PyTorch and Sentence-BERT), and development — so that a contributor installing the API does not download the deep-learning stack. CI runs the Python suite on 3.12 and a production frontend build on Node 22.

---

## VIII. Results

All numbers below were produced by running the code in this repository on the synthetic corpus with seed 42. They describe the pipeline, not Jharkhand.

### A. Clustering agreement

**TABLE III.** Clustering agreement with generator domain labels (k = 12).

| Split | Encoder | Algorithm | ARI | NMI | Purity | Silhouette |
|---|---|---|---|---|---|---|
| Train (3,000) | TF-IDF word | K-Means | 0.000 | 0.009 | 0.110 | 0.163 |
| Train (3,000) | TF-IDF word | Agglomerative | 0.098 | 0.227 | 0.312 | 0.068 |
| Train (3,000) | TF-IDF word | HDBSCAN | 0.009 | 0.244 | 0.297 | 0.142 |
| Train (3,000) | TF-IDF char | K-Means | 0.048 | 0.116 | 0.187 | 0.109 |
| Train (3,000) | TF-IDF char | Agglomerative | **0.253** | **0.458** | 0.442 | 0.088 |
| Train (3,000) | TF-IDF char | HDBSCAN | −0.000 | 0.002 | 0.090 | 0.026 |
| Held-out (2,000) | TF-IDF word | K-Means | −0.000 | 0.014 | 0.119 | 0.174 |
| Held-out (2,000) | TF-IDF word | Agglomerative | 0.066 | 0.172 | 0.271 | 0.081 |
| Held-out (2,000) | TF-IDF word | HDBSCAN | −0.000 | 0.001 | 0.103 | 0.048 |
| Held-out (2,000) | TF-IDF char | K-Means | 0.096 | 0.215 | 0.269 | 0.116 |
| Held-out (2,000) | TF-IDF char | Agglomerative | **0.244** | **0.431** | 0.458 | 0.090 |
| Held-out (2,000) | TF-IDF char | HDBSCAN | −0.000 | 0.002 | 0.103 | 0.023 |

Character n-grams with agglomerative clustering are the strongest partition on both splits, and the train-to-held-out gap is small (ARI 0.253 → 0.244), which suggests the result is not an artefact of fitting. K-Means on word features performs at chance against the domain labels, despite a higher silhouette than the best partition — an instructive case where an intrinsic metric prefers a partition that is semantically wrong.

The **English-only slice** of the same primary partition reaches ARI 0.442, NMI 0.546 and purity 0.636. The difference between 0.253 and 0.442 localises the failure: on mixed-language text the encoder separates scripts before it separates topics. This is precisely the boundary a multilingual sentence encoder is intended to cross.

Scoring the primary mixed-language partition against other metadata gives ARI 0.175 for language, −0.001 for district and 0.003 for severity. District and severity are not encoded in the text in a recoverable way, which is expected and useful to state: the cluster is a topic grouping, not a geographic or urgency estimate.

### B. Duplicate detection

**TABLE IV.** Duplicate-pair sweep (excerpt; 1,500 true pairs, top-5 district-blocked candidates).

| Threshold | Predicted | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| 0.600 | 7,500 | 1,447 | 6,053 | 53 | 0.193 | 0.965 | 0.322 |
| 0.700 | 3,632 | 1,395 | 2,237 | 105 | 0.384 | 0.930 | 0.544 |
| 0.750 | 2,676 | 1,346 | 1,330 | 154 | 0.503 | 0.897 | 0.645 |
| 0.800 | 1,961 | 1,277 | 684 | 223 | 0.651 | 0.851 | 0.738 |
| **0.850** | **1,502** | **1,115** | **387** | **385** | **0.742** | **0.743** | **0.743** |
| 0.900 | 1,079 | 857 | 222 | 643 | 0.794 | 0.571 | 0.665 |
| 1.000 | 359 | 327 | 32 | 1,173 | 0.911 | 0.218 | 0.352 |

The best F1 is **0.743 at threshold 0.85**, with balanced precision and recall. At 0.95 precision rises to 0.819 but recall collapses to 0.265, which would hide most duplicates from a reviewer. The deployed default is 0.86, and the interface treats the result as a review aid rather than an oracle. This is the single most important design consequence of the measurement: because the classifier is imperfect, automatic merging would corrupt the evidence base.

### C. Supervised routing

The TF-IDF + logistic-regression router achieves accuracy 1.000, macro F1 1.000 and weighted F1 1.000 on the 2,000 held-out rows. This is a **synthetic ceiling, not a transfer result**: every domain has its own vocabulary by construction (a pipeline versus a culvert versus a ration card), so a linear model has little to confuse. The result demonstrates that the feature pipeline can separate the domains the corpus defines; it says nothing about real citizen language.

### D. Error analysis

The ten largest-cluster misassignments are dominated by two mechanisms. First, **script boundaries**: Hinglish and Hindi reports land in clusters dominated by another script, because lexical features cannot align "पानी" with "water". Second, **shared boilerplate**: reports from Land & Revenue or Agriculture contain template phrases ("needs urgent repair", "since the last monsoon") that resemble the water-supply cluster's vocabulary. A third, smaller mechanism is genuine vocabulary overlap between domains, such as land demarcation and irrigation. These causes were assigned by rule rather than by hand, so they are hypotheses to verify, not findings.

### E. Verification status

The Python suite currently contains **18 test modules and 145 test cases**; the full run completed in 61 seconds on Python 3.13 with all tests passing. Coverage includes the canonical data contract, the generator, text preparation, evaluation helpers, clustering, priority and matching, API authentication and role-based access, deduplication, merging, re-clustering, publishing, matches, analytics, briefs, the SQLite schema migration, `.env` loading and a backup/restore drill. The frontend is verified by type-check and production build. There is no automated browser or accessibility test suite; this is a stated gap rather than an implied pass.

---

## IX. Discussion

### A. What the results support

Three conclusions are supported by the measurements. First, character n-gram features are a better lexical representation than word n-grams for this code-mixed corpus, and agglomerative clustering with cosine linkage is a better partition than K-Means or HDBSCAN at the target granularity. Second, duplicate detection at a high threshold is useful as a human-facing candidate list but is not accurate enough to merge autonomously. Third, a simple linear router separates the corpus's domains almost perfectly, which means the hard problem is representation and language, not classifier capacity.

### B. What the results do not support

The corpus is synthetic. Template-generated phrasing is more regular than field language, the labels come from the generator rather than human annotators, and the 71 sub-issues are a project taxonomy rather than an official classification. Consequently:

- No claim about the accuracy of this pipeline on real Jharkhand complaints follows from these tables.
- The routing ceiling is an artefact of constructed vocabulary separation.
- No inter-annotator agreement (Cohen's kappa) is reported; the protocol requires two annotators on a 300-complaint sample, which a single evaluator cannot produce.
- No real-text benchmark is included, because the planned CC0 grievance dataset has not been downloaded into the repository.
- Sentence-BERT was not measured: the encoder path is implemented, but no PyTorch wheel was available for the working interpreter. The TF-IDF-versus-SBERT comparison is absent rather than estimated.

Two further limitations are architectural. Duplicate candidate generation is restricted to a district block, so the same real-world problem filed in two districts is never compared; the sweep measures what the product does, not an unconstrained oracle. And persistence is SQLite with recomputed similarity, which is appropriate for a demonstration but not for state-scale volume.

### C. Threats to validity

*Construct validity:* agreement with generator labels measures recovery of the generator's structure, not usefulness to a programme officer. *Internal validity:* the corpus, features and thresholds were developed on the same synthetic distribution, although the held-out set and separate seed reduce optimistic bias. *External validity:* the language mix, district distribution and severity model are assumptions. *Conclusion validity:* single-seed runs are reported; variance across generator seeds is not characterised.

### D. Ethical and operational considerations

Citizen submissions may contain personal information, and the API path does not scrub it. The interface warns against including names, phone numbers and identifiers, and public evidence quotes omit account identities, but the honest position is that anonymisation is a bulk-ingestion property, not a platform guarantee. Partner organisations in the directory are fixtures, not real partnerships. The system is designed so that a human publishes every brief and confirms every match, which keeps accountability with an identifiable administrator and is recorded in the audit log.

---

## X. Conclusion and Future Work

ChallengeMap demonstrates that a civic complaint pipeline can be built end to end and evaluated honestly at prototype scale: complaints are validated and stored, duplicates are surfaced for human review, clusters become named and ranked drafts, partners receive explainable matches, and the public reads evidence-backed briefs. The measured results identify character-level lexical features as the strongest available representation for this code-mixed corpus, duplicate detection as a review aid rather than an oracle, and multilingual embeddings as the missing capability.

Future work follows the documented phase plan:

1. **Real-text evaluation** on a licensed or CC0 grievance corpus, with inter-annotator agreement and a frozen evaluation protocol.
2. **Multilingual sentence embeddings** (Sentence-BERT or a comparable encoder) to cross the script boundary that dominates the current error analysis.
3. **PostgreSQL with pgvector**, replacing SQLite and on-demand similarity with an indexed vector store and a versioned schema migration.
4. **Asynchronous processing** for re-clustering and ingestion, with shared rate-limit storage.
5. **Field validation** with district administrators and partner organisations, measuring whether published briefs change decisions rather than only whether clusters match labels.

Until the first item is complete, every quantitative claim in this paper should be read as a statement about a controlled synthetic corpus and about the engineering of the pipeline, not about the state of Jharkhand.

---

## References

[1] F. Pedregosa *et al.*, "Scikit-learn: Machine learning in Python," *J. Mach. Learn. Res.*, vol. 12, pp. 2825–2830, Oct. 2011.

[2] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in *Proc. Conf. Empirical Methods Natural Lang. Process. (EMNLP-IJCNLP)*, Hong Kong, 2019, pp. 3982–3992.

[3] M. Grootendorst, "BERTopic: Neural topic modeling with a class-based TF-IDF procedure," *arXiv:2203.05794*, Mar. 2022.

[4] R. J. G. B. Campello, D. Moulavi, and J. Sander, "Density-based clustering based on hierarchical density estimates," in *Proc. Pacific-Asia Conf. Knowl. Discovery Data Mining (PAKDD)*, Gold Coast, QLD, Australia, 2013, pp. 160–172.

[5] G. Salton and C. Buckley, "Term-weighting approaches in automatic text retrieval," *Inf. Process. Manag.*, vol. 24, no. 5, pp. 513–523, 1988.

[6] K. Sparck Jones, "A statistical interpretation of term specificity and its application in retrieval," *J. Document.*, vol. 28, no. 1, pp. 11–21, 1972.

[7] L. Hubert and P. Arabie, "Comparing partitions," *J. Classification*, vol. 2, no. 1, pp. 193–218, Dec. 1985.

[8] M. Jones, J. Bradley, and N. Sakimura, "JSON Web Token (JWT)," RFC 7519, May 2015.

[9] A. Biryukov, D. Dinu, D. Khovratovich, and S. Josefsson, "Argon2 memory-hard function for password hashing and proof-of-work applications," RFC 9106, Sep. 2021.

[10] S. Ramírez, "FastAPI," 2018. [Online]. Available: https://fastapi.tiangolo.com

[11] Vercel, "Next.js," 2016. [Online]. Available: https://nextjs.org

[12] A. K. Jain, M. N. Murty, and P. J. Flynn, "Data clustering: A review," *ACM Comput. Surv.*, vol. 31, no. 3, pp. 264–323, Sep. 1999.

[13] Government of India, "Centralized Public Grievance Redress and Monitoring System (CPGRAMS)." [Online]. Available: https://pgportal.gov.in
