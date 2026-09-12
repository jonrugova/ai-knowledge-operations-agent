import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.middleware.sessions import SessionMiddleware

from agent import answer_question
from approval_store import list_approval_requests
from approval_workflow import decide_and_resume_approval
from protected_actions import get_execution_for_approval


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    session_secret: str
    admin_password: str
    employee_password: str
    frontend_origin: str | None


def load_settings(environment: Mapping[str, str] | None = None):
    values = os.environ if environment is None else environment
    app_env = values.get("APP_ENV", "development")
    if app_env not in {"development", "production"}:
        raise RuntimeError(
            'APP_ENV must be either "development" or "production".'
        )

    missing = [
        name
        for name in (
            "SESSION_SECRET",
            "ADMIN_PASSWORD",
            "EMPLOYEE_PASSWORD",
        )
        if not values.get(name)
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return AppSettings(
        app_env=app_env,
        session_secret=values["SESSION_SECRET"],
        admin_password=values["ADMIN_PASSWORD"],
        employee_password=values["EMPLOYEE_PASSWORD"],
        frontend_origin=values.get("FRONTEND_ORIGIN") or None,
    )


class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, message):
        trimmed_message = message.strip()
        if not trimmed_message:
            raise ValueError("message must not be empty")
        return trimmed_message


class LoginRequest(BaseModel):
    username: str
    password: str


class ApprovalDecisionRequest(BaseModel):
    decision: str
    decision_note: str

    model_config = {"extra": "forbid"}

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, decision):
        if decision not in {"approved", "rejected"}:
            raise ValueError('decision must be "approved" or "rejected"')
        return decision

    @field_validator("decision_note")
    @classmethod
    def validate_required_text(cls, value):
        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError("field must not be blank")
        return trimmed_value


APPROVAL_RESPONSE_FIELDS = {
    "approval_id",
    "approval_type",
    "reason",
    "user_request",
    "requested_by",
    "status",
    "created_at",
    "decided_at",
    "decided_by",
    "decision_note",
}

EXECUTION_RESPONSE_FIELDS = {
    "execution_id",
    "action_type",
    "status",
    "executed_at",
}


def _public_approval(approval):
    return {
        key: approval[key]
        for key in APPROVAL_RESPONSE_FIELDS
        if key in approval
    }


def _public_execution(execution):
    if execution is None:
        return None
    return {
        key: execution[key]
        for key in EXECUTION_RESPONSE_FIELDS
        if key in execution
    }


def _execution_status(approval, execution):
    if execution is not None:
        return "executed"
    if approval.get("status") == "pending":
        return "pending"
    if approval.get("status") == "approved":
        return "retry_required"
    return "not_executed"


def require_authenticated(request: Request):
    username = request.session.get("username")
    role = request.session.get("role")
    if (
        request.session.get("authenticated") is not True
        or not isinstance(username, str)
        or not username
        or role not in {"employee", "approver"}
    ):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    return {
        "user_id": username,
        "username": username,
        "role": role,
    }


def require_approver(request: Request):
    user = require_authenticated(request)
    if user["role"] != "approver":
        raise HTTPException(
            status_code=403,
            detail="Approver access required",
        )
    return user


api_router = APIRouter()


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.post("/auth/login")
def login(request_body: LoginRequest, request: Request):
    expected_passwords = {
        "employee": (
            "employee",
            request.app.state.employee_password,
        ),
        "manager": (
            "manager",
            request.app.state.admin_password,
        ),
    }
    identity = expected_passwords.get(request_body.username)
    if identity is None or not secrets.compare_digest(
        request_body.password.encode("utf-8"),
        identity[1].encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )
    request.session.clear()
    request.session["authenticated"] = True
    request.session["username"] = identity[0]
    request.session["role"] = (
        "employee" if identity[0] == "employee" else "approver"
    )
    return {
        "authenticated": True,
        "username": identity[0],
        "role": request.session["role"],
    }


@api_router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}


@api_router.get("/auth/me")
def auth_me(request: Request):
    if request.session.get("authenticated") is not True:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": request.session.get("username"),
        "role": request.session.get("role"),
    }


@api_router.post("/chat")
def chat(
    request: ChatRequest,
    user=Depends(require_authenticated),
):
    try:
        answer, tool_calls = answer_question(
            request.message,
            requester_id=user["username"],
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )

    return {
        "answer": answer,
        "tools_used": [call["name"] for call in tool_calls],
    }


@api_router.get("/approvals")
def approvals(_approver=Depends(require_approver)):
    try:
        records = list_approval_requests()
        response = []
        for record in records:
            execution = get_execution_for_approval(record["approval_id"])
            public_record = _public_approval(record)
            public_record["execution"] = _public_execution(execution)
            public_record["execution_status"] = _execution_status(
                record,
                execution,
            )
            response.append(public_record)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to load approval requests",
        )
    return response


@api_router.post("/approvals/{approval_id}/decision")
def approval_decision(
    approval_id: str,
    request: ApprovalDecisionRequest,
    approver=Depends(require_approver),
):
    try:
        result = decide_and_resume_approval(
            approval_id=approval_id,
            decision=request.decision,
            decided_by=approver["username"],
            decision_note=request.decision_note,
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="The requester cannot decide their own approval request",
        )
    except ValueError as error:
        message = str(error)
        if "not found" in message:
            raise HTTPException(
                status_code=404,
                detail="Approval request not found",
            )
        if "already" in message:
            raise HTTPException(
                status_code=409,
                detail="Approval request has already been decided",
            )
        raise HTTPException(status_code=400, detail="Invalid decision")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to update approval request",
        )

    return {
        "approval": _public_approval(result["approval"]),
        "execution": _public_execution(result["execution"]),
        "execution_status": result["execution_status"],
    }


API_PATH_PREFIXES = ("health", "auth", "chat", "approvals")


def create_app(
    settings: AppSettings | None = None,
    frontend_dist: Path | None = None,
):
    active_settings = settings or load_settings()
    dist_path = frontend_dist or Path("frontend/dist")

    application = FastAPI(title="AI Knowledge Agent", debug=False)
    application.state.admin_password = active_settings.admin_password
    application.state.employee_password = active_settings.employee_password

    application.add_middleware(
        SessionMiddleware,
        secret_key=active_settings.session_secret,
        session_cookie="knowledge_agent_session",
        same_site="lax",
        https_only=active_settings.app_env == "production",
    )

    if active_settings.app_env == "production":
        allowed_origins = (
            [active_settings.frontend_origin]
            if active_settings.frontend_origin
            else []
        )
    else:
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        return response

    application.include_router(api_router)

    assets_path = dist_path / "assets"
    if assets_path.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=assets_path),
            name="frontend-assets",
        )

    @application.get("/{browser_path:path}", include_in_schema=False)
    def serve_frontend(browser_path: str):
        first_segment = browser_path.split("/", 1)[0]
        if first_segment in API_PATH_PREFIXES:
            raise HTTPException(status_code=404, detail="Not Found")

        index_path = dist_path / "index.html"
        if not index_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Frontend build not found",
            )
        return FileResponse(index_path)

    return application


SETTINGS = load_settings()
app = create_app(SETTINGS)