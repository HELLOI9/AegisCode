"""aegiscode/service/api.py — FastAPI REST layer over ApplicationService.

SECURITY NOTE: This API has NO authentication. It is intentionally designed
for localhost-only use as a local observation and approval panel (SPEC §13).
Do NOT expose this API on a public or shared network interface. Callers must
bind the server to 127.0.0.1 (or a loopback equivalent).

The /credentials/status endpoint returns ONLY a masked status dict. The
plaintext credential value is never included in any API response.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aegiscode.credentials.store import CredentialStore
from aegiscode.service.app_service import ApplicationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    workspace: str
    description: str


class DecisionRequest(BaseModel):
    approved: bool


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def build_app(
    service: ApplicationService,
    credential_store: Optional[CredentialStore] = None,
) -> FastAPI:
    """Build and return a FastAPI application wired to the given ApplicationService.

    Parameters
    ----------
    service:
        The ApplicationService instance to delegate all task/approval/audit
        operations to.
    credential_store:
        Optional CredentialStore for the /credentials/status endpoint. When
        None, a no-op store (always unconfigured) is used so the endpoint
        remains functional without leaking secrets.
    """
    app = FastAPI(
        title="AegisCode Local Panel",
        description=(
            "Unauthenticated REST API for local observation and approval. "
            "Bind to localhost only — not for public exposure."
        ),
        version="1.0.0",
    )

    # -----------------------------------------------------------------------
    # Global exception handler
    # -----------------------------------------------------------------------
    # Any non-HTTPException that escapes a service call (sqlite3.OperationalError,
    # ValueError, etc.) is caught here and turned into a generic 500. This
    # prevents a real running server from leaking the full Python traceback —
    # which could expose db/file paths or config — in the response body.
    # HTTPExceptions (e.g. 404) are handled by FastAPI's own handlers and are
    # NOT swallowed here.
    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    # Fall back to an always-unconfigured store if none provided.
    if credential_store is None:
        class _NullBackend:
            def get_password(self, service, user):
                return None
            def set_password(self, service, user, value):
                pass
            def delete_password(self, service, user):
                pass

        _cred_store: CredentialStore = CredentialStore(backend=_NullBackend())
    else:
        _cred_store = credential_store

    # -----------------------------------------------------------------------
    # Endpoint: POST /tasks
    # -----------------------------------------------------------------------

    @app.post("/tasks")
    def create_task(body: CreateTaskRequest) -> dict:
        """Create a task and start execution. Returns the task_id."""
        task_id = service.create_task(
            workspace=body.workspace,
            description=body.description,
        )
        return {"task_id": task_id}

    # -----------------------------------------------------------------------
    # Endpoint: GET /tasks/{id}
    # -----------------------------------------------------------------------

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        """Return the task row. 404 if not found."""
        try:
            return service.get_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # -----------------------------------------------------------------------
    # Endpoint: GET /tasks/{id}/events?since=N
    # -----------------------------------------------------------------------

    @app.get("/tasks/{task_id}/events")
    def get_events(task_id: str, since: int = 0) -> list:
        """Return audit events for the task with event_id > since."""
        # Validate task exists first (raises 404 if not)
        try:
            service.get_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return service.get_events(task_id, since)

    # -----------------------------------------------------------------------
    # Endpoint: GET /tasks/{id}/approvals
    # -----------------------------------------------------------------------

    @app.get("/tasks/{task_id}/approvals")
    def list_approvals(task_id: str) -> list:
        """Return all approval requests for the task."""
        try:
            service.get_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return service.list_approvals(task_id)

    # -----------------------------------------------------------------------
    # Endpoint: POST /approvals/{id}/decision
    # -----------------------------------------------------------------------

    @app.post("/approvals/{approval_id}/decision")
    def decide(approval_id: str, body: DecisionRequest) -> dict:
        """Approve or reject a pending approval request."""
        service.decide(approval_id=approval_id, approved=body.approved)
        return {"status": "ok"}

    # -----------------------------------------------------------------------
    # Endpoint: POST /tasks/{id}/cancel
    # -----------------------------------------------------------------------

    @app.post("/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict:
        """Request cooperative cancellation of a task. Always 200."""
        service.cancel(task_id)
        return {"status": "ok"}

    # -----------------------------------------------------------------------
    # Endpoint: GET /tasks/{id}/audit
    # -----------------------------------------------------------------------

    @app.get("/tasks/{task_id}/audit")
    def get_audit(task_id: str) -> dict:
        """Return audit events + chain_valid for the task. 404 if not found."""
        try:
            service.get_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return service.get_audit(task_id)

    # -----------------------------------------------------------------------
    # Endpoint: GET /credentials/status
    # -----------------------------------------------------------------------

    @app.get("/credentials/status")
    def credentials_status() -> dict:
        """Return CredentialStore masked status only — never the plaintext key."""
        return _cred_store.status()

    return app
