"""ChallengeMap API (Phase 5).

Persistence is the existing SQLite store, not the Postgres + pgvector schema the
plan targets: Phase 2 is blocked on the absence of a Postgres instance here, and
faking that migration would be worse than declaring it. Everything a future swap
needs is behind ``api/store.py``.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.config import PROJECT_ROOT, get_settings, load_env_file
from api.deps import AdminUser, CurrentUser
from api.rate_limit import limiter
from api.routers import admin, analytics, auth, challenges, complaints, partners, staff
from api.schemas import HealthResponse, UserResponse
from api.store import connection, ensure_bootstrap_admin, init_db, seed_organizations

API_PREFIX = "/api/v1"
VERSION = "2.0.0"

# Load the project .env before anything reads settings. uvicorn imports this
# module, so a direct `uvicorn api.main:app` needs no exported variables either.
# Explicit environment variables still win, so tests and deployments are safe.
load_env_file()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.database_path)
    ensure_bootstrap_admin(
        settings.bootstrap_admin, settings.bootstrap_admin_email
    )
    seed_organizations()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="ChallengeMap API",
        description=(
            "Citizen complaint intake with duplicate interception, challenge "
            "generation, partner matching, analytics and an administrator console. "
            "Roles: citizen, partner, admin."
        ),
        version=VERSION,
        lifespan=lifespan,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins) or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    for router in (
        auth.router,
        complaints.router,
        challenges.router,
        partners.router,
        staff.router,
        analytics.router,
        admin.router,
    ):
        application.include_router(router, prefix=API_PREFIX)

    @application.get(
        f"{API_PREFIX}/health", response_model=HealthResponse, tags=["health"]
    )
    def health() -> HealthResponse:
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return HealthResponse(status="ok", database="ok", version=VERSION)

    @application.get(f"{API_PREFIX}/models", tags=["admin"])
    def model_metrics(current: AdminUser) -> dict:
        """Latest measured model metrics (plan section 7: GET /models)."""
        metrics_path = PROJECT_ROOT / "models" / "eval_metrics.json"
        if not metrics_path.exists():
            raise HTTPException(
                status_code=404,
                detail="No evaluation metrics have been recorded yet.",
            )
        return json.loads(metrics_path.read_text(encoding="utf-8"))

    @application.get(f"{API_PREFIX}/me", response_model=UserResponse, tags=["auth"])
    def legacy_me(current: CurrentUser) -> UserResponse:
        """Citizen profile endpoint kept for the pre-JWT clients."""
        return UserResponse(
            id=current.id,
            username=current.username,
            role=current.role,
            district=current.district,
            organization_id=current.organization_id,
        )

    return application


app = create_app()
