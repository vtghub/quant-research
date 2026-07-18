from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research_api.database import get_db
from quant_research_api.deps import get_current_user
from quant_research_api.models import Run, SavedConfig, User
from quant_research_api.schemas import RunCreate, RunOut
from quant_research_api.tasks import run_pipeline_task

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_owned_run(run_id: int, user: User, db: Session) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return run


@router.post("", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Run:
    config_id: int | None = None

    if payload.config_id is not None:
        saved = db.get(SavedConfig, payload.config_id)
        if saved is None or saved.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="config not found")
        snapshot = saved.config_json
        config_id = saved.id
    elif payload.config_json is not None:
        snapshot = payload.config_json
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="either config_id or config_json is required"
        )

    run = Run(owner_id=user.id, config_id=config_id, config_snapshot=snapshot, kind=payload.kind, status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    run_pipeline_task.delay(run.id)
    return run


@router.get("", response_model=list[RunOut])
def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Run]:
    stmt = select(Run).where(Run.owner_id == user.id).order_by(Run.created_at.desc())
    return list(db.scalars(stmt))


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Run:
    return _get_owned_run(run_id, user, db)


@router.get("/{run_id}/artifacts/{filename}")
def get_run_artifact(
    run_id: int, filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FileResponse:
    run = _get_owned_run(run_id, user, db)
    if not run.report_dir:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no artifacts for this run")

    safe_name = Path(filename).name  # strip any directory components -- no path traversal
    artifact_path = Path(run.report_dir) / safe_name
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    return FileResponse(artifact_path)
