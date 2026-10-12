"""Atomically claim submissions so a recovered draft cannot be submitted twice."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.schema import DraftSubmission, SessionLocal
from src.models.user_service import get_user_by_email


@dataclass(frozen=True)
class SubmissionClaim:
    user_id: int
    status: str
    claimed: bool


def submission_status(db: Session, user_id: int, draft_id: str) -> dict:
    receipt = db.get(DraftSubmission, (user_id, draft_id))
    if receipt is None:
        return {"user_id": user_id, "status": "not_submitted", "stale": False}
    updated_at = receipt.updated_at.replace(tzinfo=UTC)
    return {
        "user_id": user_id,
        "status": receipt.status,
        "updated_at": updated_at.isoformat(),
        "stale": receipt.status == "processing"
        and datetime.now(UTC) - updated_at >= timedelta(minutes=15),
    }


def claim_submission(email: str, draft_id: str, owner_id: str) -> SubmissionClaim:
    with SessionLocal() as db:
        user = get_user_by_email(db, email)
        if user is None:
            raise HTTPException(status_code=401, detail="Please log in again")
        if owner_id != str(user.id):
            raise HTTPException(status_code=409, detail="The signed-in account changed")
        user_id = user.id
        now = datetime.now(UTC)
        db.add(
            DraftSubmission(
                user_id=user_id,
                draft_id=draft_id,
                status="processing",
                created_at=now,
                updated_at=now,
            )
        )
        try:
            db.commit()
            return SubmissionClaim(user_id, "processing", True)
        except IntegrityError:
            db.rollback()

        # Only a pre-processing validation rejection is safe to retry. The
        # conditional UPDATE also prevents two tabs from claiming that retry.
        result = db.execute(
            update(DraftSubmission)
            .where(
                DraftSubmission.user_id == user_id,
                DraftSubmission.draft_id == draft_id,
                DraftSubmission.status == "rejected",
            )
            .values(status="processing", updated_at=now)
            .returning(DraftSubmission.draft_id)
        )
        claimed_id = result.scalar_one_or_none()
        db.commit()
        if claimed_id is not None:
            return SubmissionClaim(user_id, "processing", True)
        receipt = db.get(DraftSubmission, (user_id, draft_id))
        if receipt is None:
            raise RuntimeError("Submission receipt disappeared during claim")
        return SubmissionClaim(user_id, receipt.status, False)


def finish_submission(user_id: int, draft_id: str, status: str) -> None:
    with SessionLocal() as db:
        db.execute(
            update(DraftSubmission)
            .where(
                DraftSubmission.user_id == user_id,
                DraftSubmission.draft_id == draft_id,
                DraftSubmission.status == "processing",
            )
            .values(status=status, updated_at=datetime.now(UTC))
        )
        db.commit()
