"""Experts CRUD endpoints.

GET    /experts             — list experts for the current user
POST   /experts             — create a new expert
GET    /experts/{id}        — get a specific expert
PUT    /experts/{id}        — update an expert
DELETE /experts/{id}        — delete an expert
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from surogate_agent.auth.database import get_db
from surogate_agent.auth.jwt import get_current_user
from surogate_agent.auth.models import User
from surogate_agent.auth.schemas import ExpertCreate, ExpertResponse, ExpertUpdate
from surogate_agent.auth.service import (
    create_expert,
    delete_expert,
    get_expert,
    get_expert_by_name,
    list_experts,
    update_expert,
)
from surogate_agent.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/experts", tags=["experts"])


@router.get("", response_model=list[ExpertResponse])
def get_experts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Return all experts owned by the current user."""
    return list_experts(db, current_user.id)


@router.post("", response_model=ExpertResponse, status_code=status.HTTP_201_CREATED)
def create_new_expert(
    req: ExpertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new expert for the current user."""
    if get_expert_by_name(db, current_user.id, req.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Expert '{req.name}' already exists.",
        )
    expert = create_expert(db, current_user.id, req)
    log.info("expert created: name=%r user_id=%d", expert.name, current_user.id)
    return expert


@router.get("/{expert_id}", response_model=ExpertResponse)
def get_expert_by_id(
    expert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a single expert by ID."""
    expert = get_expert(db, current_user.id, expert_id)
    if not expert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert not found.")
    return expert


@router.put("/{expert_id}", response_model=ExpertResponse)
def update_expert_by_id(
    expert_id: int,
    req: ExpertUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing expert."""
    expert = get_expert(db, current_user.id, expert_id)
    if not expert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert not found.")
    # Check name uniqueness if renaming
    if req.name is not None and req.name.strip() != expert.name:
        if get_expert_by_name(db, current_user.id, req.name.strip()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Expert '{req.name}' already exists.",
            )
    updated = update_expert(db, expert, req)
    log.info("expert updated: id=%d name=%r user_id=%d", updated.id, updated.name, current_user.id)
    return updated


@router.delete("/{expert_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_expert_by_id(
    expert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an expert."""
    expert = get_expert(db, current_user.id, expert_id)
    if not expert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert not found.")
    delete_expert(db, expert)
    log.info("expert deleted: id=%d user_id=%d", expert_id, current_user.id)
