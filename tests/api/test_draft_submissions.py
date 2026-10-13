from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from src.core.assets import STATIC_ASSET_PREFIX
from src.db.schema import Base, DraftSubmission, User, get_db
from src.routers import dashboard, success
from src.services import submission_tracking
from src.services.submission_workflow import SubmissionWorkflowResult


@pytest.fixture
def draft_app(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'drafts.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for user_id in (1, 2):
            db.add(
                User(
                    id=user_id,
                    name=f"User {user_id}",
                    email=f"user{user_id}@example.com",
                    personal_email="personal@example.com",
                    address="123 Main St",
                    team="Software",
                    password="test-password",
                    signature_data=b"\x89PNG\r\n\x1a\ntest",
                    void_cheque=b"%PDF-test",
                )
            )
        db.commit()
    monkeypatch.setattr(submission_tracking, "SessionLocal", sessions)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(dashboard.router)
    app.include_router(success.router)

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database

    @app.get("/test-login/{user_id}")
    def test_login(request: Request, user_id: int):
        with sessions() as db:
            user = db.get(User, user_id)
            assert user is not None
            request.session.update(authenticated=True, user_email=user.email)
        return {"ok": True}

    with TestClient(
        app, follow_redirects=False, raise_server_exceptions=False
    ) as client:
        yield client, sessions
    engine.dispose()


def tracked_data(draft_id):
    return {"draft_id": draft_id, "draft_owner_id": "1"}


def test_dashboard_uses_versioned_assets_instead_of_cached_legacy_urls(draft_app):
    client, _ = draft_app
    client.get("/test-login/1")
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert f'src="{STATIC_ASSET_PREFIX}/js/dashboard.js"' in page.text
    assert f'href="{STATIC_ASSET_PREFIX}/css/output.css"' in page.text
    assert 'src="/static/js/dashboard.js"' not in page.text


def test_status_requires_login_and_does_not_expose_other_accounts(draft_app):
    client, sessions = draft_app
    draft_id = str(uuid4())
    assert client.get(f"/draft-submissions/{draft_id}").status_code == 401
    client.get("/test-login/1")
    claim = submission_tracking.claim_submission("user1@example.com", draft_id, "1")
    submission_tracking.finish_submission(claim.user_id, draft_id, "succeeded")
    response = client.get(f"/draft-submissions/{draft_id}")
    assert response.json()["status"] == "succeeded"
    assert response.headers["cache-control"] == "no-store"
    client.get("/test-login/2")
    assert client.get(f"/draft-submissions/{draft_id}").json() == {
        "user_id": 2,
        "status": "not_submitted",
        "stale": False,
    }
    assert (
        client.get(f"/success?submission_id={draft_id}").headers["location"]
        == "/dashboard"
    )
    with sessions() as db:
        db.get(User, 1).email = "renamed@example.com"
        db.commit()
    client.get("/test-login/1")
    assert client.get(f"/draft-submissions/{draft_id}").json()["status"] == "succeeded"


def test_success_is_committed_and_duplicate_submission_does_not_run_again(
    draft_app, monkeypatch
):
    client, sessions = draft_app
    client.get("/test-login/1")
    draft_id = str(uuid4())
    calls = []

    async def submit(_form, _email):
        with sessions() as db:
            assert db.get(DraftSubmission, (1, draft_id)).status == "processing"
        calls.append(True)
        return SubmissionWorkflowResult("/success", submission_status="succeeded")

    monkeypatch.setattr(dashboard, "process_submission_workflow", submit)
    for _ in range(2):
        response = client.post("/submit-all-requests", data=tracked_data(draft_id))
        assert response.status_code == 303
        assert response.headers["location"] == f"/success?submission_id={draft_id}"
    assert len(calls) == 1
    assert client.get(f"/draft-submissions/{draft_id}").json()["status"] == "succeeded"
    page = client.get(f"/success?submission_id={draft_id}")
    assert f'data-id="{draft_id}"' in page.text
    assert 'data-owner="1"' in page.text
    assert 'id="submitted-draft"' not in client.get("/success").text


def test_validation_rejection_can_be_corrected_and_retried(draft_app, monkeypatch):
    client, _ = draft_app
    client.get("/test-login/1")
    draft_id = str(uuid4())
    outcomes = iter(
        [
            SubmissionWorkflowResult("/dashboard?error=below_minimum"),
            SubmissionWorkflowResult("/success", submission_status="succeeded"),
        ]
    )

    async def submit(_form, _email):
        return next(outcomes)

    monkeypatch.setattr(dashboard, "process_submission_workflow", submit)
    response = client.post("/submit-all-requests", data=tracked_data(draft_id))
    assert response.headers["location"] == "/dashboard?error=below_minimum"
    assert client.get(f"/draft-submissions/{draft_id}").json()["status"] == "rejected"
    client.post("/submit-all-requests", data=tracked_data(draft_id))
    assert client.get(f"/draft-submissions/{draft_id}").json()["status"] == "succeeded"


@pytest.mark.parametrize("raises", [False, True])
def test_partial_or_uncertain_submission_keeps_draft_and_blocks_retry(
    draft_app, monkeypatch, raises
):
    client, _ = draft_app
    client.get("/test-login/1")
    draft_id = str(uuid4())
    calls = []

    async def submit(_form, _email):
        calls.append(True)
        if raises:
            raise RuntimeError("connection interrupted after external write")
        return SubmissionWorkflowResult("/success", submission_status="needs_review")

    monkeypatch.setattr(dashboard, "process_submission_workflow", submit)
    response = client.post("/submit-all-requests", data=tracked_data(draft_id))
    assert response.status_code == (500 if raises else 303)
    assert (
        client.get(f"/draft-submissions/{draft_id}").json()["status"] == "needs_review"
    )
    response = client.post("/submit-all-requests", data=tracked_data(draft_id))
    assert response.headers["location"] == "/dashboard?error=submission_needs_review"
    assert len(calls) == 1


def test_stale_processing_record_is_not_retried(draft_app, monkeypatch):
    client, sessions = draft_app
    client.get("/test-login/1")
    draft_id = str(uuid4())
    submission_tracking.claim_submission("user1@example.com", draft_id, "1")
    assert client.get(f"/draft-submissions/{draft_id}").json()["stale"] is False
    with sessions() as db:
        db.get(DraftSubmission, (1, draft_id)).updated_at = datetime.now(
            UTC
        ) - timedelta(minutes=16)
        db.commit()
    status = client.get(f"/draft-submissions/{draft_id}").json()
    assert status["status"] == "processing"
    assert status["stale"] is True

    async def unexpected_submit(_form, _email):
        pytest.fail("A processing draft must not start a second submission")

    monkeypatch.setattr(dashboard, "process_submission_workflow", unexpected_submit)
    response = client.post("/submit-all-requests", data=tracked_data(draft_id))
    assert response.headers["location"] == "/dashboard?error=submission_processing"


def test_old_tab_cannot_submit_for_a_different_signed_in_user(draft_app):
    client, sessions = draft_app
    client.get("/test-login/2")
    draft_id = str(uuid4())
    assert (
        client.post("/submit-all-requests", data=tracked_data(draft_id)).status_code
        == 409
    )
    with sessions() as db:
        assert db.query(DraftSubmission).count() == 0


def test_concurrent_claims_allow_only_one_submission(draft_app):
    _, _sessions = draft_app
    draft_id = str(uuid4())

    def claim(_index):
        return submission_tracking.claim_submission("user1@example.com", draft_id, "1")

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, range(2)))
    assert sum(result.claimed for result in claims) == 1
    submission_tracking.finish_submission(1, draft_id, "rejected")
    with ThreadPoolExecutor(max_workers=2) as pool:
        retries = list(pool.map(claim, range(2)))
    assert sum(result.claimed for result in retries) == 1


@pytest.mark.parametrize(
    "failed_output", [None, "report", "expense", "drive", "sheets"]
)
def test_workflow_confirms_success_only_after_every_output(
    monkeypatch, tmp_path, failed_output
):
    import asyncio

    from src.services import submission_workflow as workflow

    async def outputs(_user_info, _forms, _session_folder):
        return workflow.SubmissionOutputResult(
            purchase_request_filename="report.xlsx"
            if failed_output != "report"
            else "",
            expense_report_success=failed_output != "expense",
            drive_upload_success=failed_output != "drive",
            sheets_log_success=failed_output != "sheets",
            drive_folder_id="test-folder",
        )

    monkeypatch.setattr(workflow, "_run_submission_outputs", outputs)
    user = User(
        name="Test",
        email="user@example.com",
        personal_email="personal@example.com",
        address="123 Main St",
        team="Software",
    )
    folder = tmp_path / "submission"
    folder.mkdir()
    result = asyncio.run(workflow._complete_submission(user, [], str(folder)))
    assert result.submission_status == (
        "succeeded" if failed_output is None else "needs_review"
    )
    assert folder.exists() == (failed_output is not None)
