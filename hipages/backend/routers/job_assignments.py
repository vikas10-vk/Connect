"""
backend/routers/job_assignments.py

Job assignment endpoints — controls which worker gets dispatched to each job.

CORE RULES (from the PDF, non-negotiable):
  1. Workers CANNOT self-assign. Only the business owner or the system's
     auto-dispatch Celery task can create an assignment. Enforced here via
     JWT role inspection — a worker JWT is rejected at the endpoint level.
  2. Every assignment records assigned_by_id + assignment_type for liability.
     "Who sent this person?" is always answerable from the DB.
  3. SELECT FOR UPDATE on the job row during assignment prevents two workers
     from being simultaneously assigned (double-dispatch race condition).
  4. Assignment gate checks before creating the row:
       a. Job must be in 'hired' or 'in_progress' status
       b. Worker must be active AND can_accept_jobs = True
       c. Worker must have a verified, non-expired cert for the job's category
       d. The business must have valid public liability insurance
  5. User sees the worker's first name + business name only AFTER assignment.
     The full worker profile is never shown pre-assignment.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.insurance_policy import InsurancePolicy, InsuranceStatus, InsuranceType
from models.job import Job
from models.job_assignment import JobAssignment, AssignmentType
from models.job_event import JobEvent
from models.team_member import TeamMember, TeamMemberRole
from models.tradie_certification import TradieCertification, CertificationStatus
from models.tradie_profile import TradieProfile
from models.user import User
from services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/job-assignments", tags=["Job Assignments"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class AssignWorkerRequest(BaseModel):
    worker_id: str


class AssignmentResponse(BaseModel):
    id:                  str
    job_id:              str
    assigned_worker_id:  str
    worker_name:         str
    business_name:       str
    assignment_type:     str
    assigned_at:         datetime
    is_active:           bool


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_owner_member(user: User, db: AsyncSession) -> TeamMember:
    """
    Load the TeamMember row for the current user (must be role='owner').
    Workers are rejected here — they cannot access assignment endpoints.
    """
    res = await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == user.id,
            TeamMember.role == TeamMemberRole.OWNER,
            TeamMember.is_active == True,
        )
    )
    member = res.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=403,
            detail="Only business owners can assign jobs. Workers cannot self-assign.",
        )
    return member


async def _check_worker_cert_gate(worker_id: str, category_id: str, db: AsyncSession) -> None:
    """
    Verify the worker has a valid (verified + non-expired) certification for the
    job's trade category. Blocks assignment if the gate fails.
    """
    today = date.today()
    res = await db.execute(
        select(TradieCertification).where(
            TradieCertification.team_member_id == worker_id,
            TradieCertification.category_id == category_id,
            TradieCertification.status == CertificationStatus.VERIFIED,
            TradieCertification.expires_at > today,
        ).limit(1)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=(
                "This worker does not have a verified trade licence for this job's category. "
                "They must submit and have their licence verified before being assigned."
            ),
        )


async def _check_business_insurance_gate(business_id: str, db: AsyncSession) -> None:
    """
    Verify the business has valid public liability insurance.
    No worker from an uninsured business can be dispatched.
    """
    today = date.today()
    res = await db.execute(
        select(InsurancePolicy).where(
            InsurancePolicy.tradie_profile_id == business_id,
            InsurancePolicy.insurance_type == InsuranceType.PUBLIC_LIABILITY,
            InsurancePolicy.status == InsuranceStatus.VERIFIED,
            InsurancePolicy.expires_at > today,
        ).limit(1)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=(
                "Your business does not have a verified public liability insurance policy. "
                "Submit and verify your insurance before assigning workers to jobs."
            ),
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/{job_id}/assign", response_model=AssignmentResponse, status_code=201)
async def assign_worker(
    job_id:       str,
    body:         AssignWorkerRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Business owner assigns a worker to a job.

    Gate checks (all must pass):
      - Current user must be the business owner (workers rejected immediately)
      - Job must be in 'hired' status
      - No existing active assignment on this job
      - Worker must belong to this business
      - Worker must be active and can_accept_jobs = True
      - Worker must have a verified cert for the job's trade category
      - Business must have valid public liability insurance

    Race condition protection:
      SELECT FOR UPDATE on the job row during the check-and-write prevents
      two simultaneous assignment requests from both succeeding. Only one wins.
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can assign workers.")

    # Load and validate the requesting owner
    owner_member = await _get_owner_member(current_user, db)

    # ── SELECT FOR UPDATE on the job row ──────────────────────────────────────
    # This is the double-dispatch prevention lock. If two assignment requests
    # arrive simultaneously, only one will acquire the lock. The other will
    # wait, then find the job already assigned and fail cleanly.
    res = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .with_for_update()
    )
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status != "hired":
        raise HTTPException(
            status_code=400,
            detail=f"Job must be in 'hired' status to assign a worker. Current status: '{job.status}'.",
        )

    # ── Check for existing active assignment ──────────────────────────────────
    existing_res = await db.execute(
        select(JobAssignment).where(
            JobAssignment.job_id == job_id,
            JobAssignment.is_active == True,
        )
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="This job already has an active worker assignment. Reassign instead of creating a new one.",
        )

    # ── Load and validate the worker ──────────────────────────────────────────
    worker_res = await db.execute(
        select(TeamMember).where(
            TeamMember.id == body.worker_id,
            TeamMember.business_id == owner_member.business_id,
        )
    )
    worker = worker_res.scalar_one_or_none()
    if not worker:
        raise HTTPException(
            status_code=404,
            detail="Worker not found in your business.",
        )

    if not worker.is_active:
        raise HTTPException(status_code=400, detail="This worker is deactivated.")

    if not worker.can_accept_jobs:
        raise HTTPException(
            status_code=400,
            detail=(
                "This worker cannot accept jobs yet. "
                "Their trade licence must be verified first."
            ),
        )

    # ── Certification gate ────────────────────────────────────────────────────
    await _check_worker_cert_gate(worker.id, job.category_id, db)

    # ── Insurance gate ────────────────────────────────────────────────────────
    await _check_business_insurance_gate(owner_member.business_id, db)

    # ── Load business profile for response ───────────────────────────────────
    biz_res = await db.execute(
        select(TradieProfile).where(TradieProfile.id == owner_member.business_id)
    )
    business = biz_res.scalar_one_or_none()

    # ── Create the assignment ─────────────────────────────────────────────────
    assignment = JobAssignment(
        id=str(uuid.uuid4()),
        job_id=job_id,
        business_id=owner_member.business_id,
        assigned_worker_id=worker.id,
        assigned_by_id=owner_member.id,
        assignment_type=AssignmentType.MANUAL,
        is_active=True,
    )
    db.add(assignment)

    # ── Audit event ───────────────────────────────────────────────────────────
    event = JobEvent(
        job_id=job_id,
        actor_id=current_user.id,
        actor_role="tradie",
        action="worker_assigned",
        old_value=None,
        new_value={"worker_id": worker.id, "worker_name": worker.full_name},
        note=f"Owner assigned {worker.full_name} to the job.",
    )
    db.add(event)

    await db.commit()

    return AssignmentResponse(
        id=assignment.id,
        job_id=job_id,
        assigned_worker_id=worker.id,
        worker_name=worker.full_name,
        business_name=business.business_name if business else "",
        assignment_type=assignment.assignment_type,
        assigned_at=assignment.assigned_at,
        is_active=assignment.is_active,
    )


@router.patch("/{job_id}/reassign", response_model=AssignmentResponse)
async def reassign_worker(
    job_id:       str,
    body:         AssignWorkerRequest,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Reassign a job to a different worker. Deactivates the current assignment
    and creates a new one. All gate checks apply to the new worker.
    History of previous assignments is preserved (is_active=False rows remain).
    """
    if current_user.role != "tradie":
        raise HTTPException(status_code=403, detail="Only tradies can reassign workers.")

    owner_member = await _get_owner_member(current_user, db)

    # SELECT FOR UPDATE to prevent race with simultaneous reassign
    res = await db.execute(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status not in ("hired", "in_progress"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reassign a job in status '{job.status}'.",
        )

    # Deactivate existing active assignment
    await db.execute(
        update(JobAssignment)
        .where(JobAssignment.job_id == job_id, JobAssignment.is_active == True)
        .values(is_active=False)
    )

    # Validate and load new worker
    worker_res = await db.execute(
        select(TeamMember).where(
            TeamMember.id == body.worker_id,
            TeamMember.business_id == owner_member.business_id,
            TeamMember.is_active == True,
            TeamMember.can_accept_jobs == True,
        )
    )
    worker = worker_res.scalar_one_or_none()
    if not worker:
        raise HTTPException(
            status_code=400,
            detail="Worker not found, inactive, or cannot accept jobs.",
        )

    await _check_worker_cert_gate(worker.id, job.category_id, db)
    await _check_business_insurance_gate(owner_member.business_id, db)

    biz_res = await db.execute(
        select(TradieProfile).where(TradieProfile.id == owner_member.business_id)
    )
    business = biz_res.scalar_one_or_none()

    new_assignment = JobAssignment(
        id=str(uuid.uuid4()),
        job_id=job_id,
        business_id=owner_member.business_id,
        assigned_worker_id=worker.id,
        assigned_by_id=owner_member.id,
        assignment_type=AssignmentType.MANUAL,
        is_active=True,
    )
    db.add(new_assignment)

    event = JobEvent(
        job_id=job_id,
        actor_id=current_user.id,
        actor_role="tradie",
        action="worker_reassigned",
        old_value=None,
        new_value={"worker_id": worker.id, "worker_name": worker.full_name},
        note=f"Owner reassigned job to {worker.full_name}.",
    )
    db.add(event)

    await db.commit()

    return AssignmentResponse(
        id=new_assignment.id,
        job_id=job_id,
        assigned_worker_id=worker.id,
        worker_name=worker.full_name,
        business_name=business.business_name if business else "",
        assignment_type=new_assignment.assignment_type,
        assigned_at=new_assignment.assigned_at,
        is_active=new_assignment.is_active,
    )


@router.get("/{job_id}/assignment")
async def get_current_assignment(
    job_id:       str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    Returns the current active assignment for a job.
    Accessible by: the job's homeowner, the assigned business owner,
    and the assigned worker.
    Worker first name + business name are revealed — full profile is not.
    """
    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    assign_res = await db.execute(
        select(JobAssignment)
        .where(JobAssignment.job_id == job_id, JobAssignment.is_active == True)
    )
    assignment = assign_res.scalar_one_or_none()
    if not assignment:
        return {"assignment": None}

    # Load worker for name reveal
    worker_res = await db.execute(
        select(TeamMember).where(TeamMember.id == assignment.assigned_worker_id)
    )
    worker = worker_res.scalar_one_or_none()

    biz_res = await db.execute(
        select(TradieProfile).where(TradieProfile.id == assignment.business_id)
    )
    business = biz_res.scalar_one_or_none()

    return {
        "assignment": {
            "id":              assignment.id,
            "job_id":          job_id,
            "worker_id":       assignment.assigned_worker_id,
            "worker_name":     worker.full_name if worker else None,
            "business_name":   business.business_name if business else None,
            "assignment_type": assignment.assignment_type,
            "assigned_at":     assignment.assigned_at,
        }
    }