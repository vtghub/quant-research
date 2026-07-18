from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_research_api.database import get_db
from quant_research_api.deps import get_current_user
from quant_research_api.models import SavedConfig, User
from quant_research_api.schemas import SavedConfigCreate, SavedConfigOut, SavedConfigUpdate

router = APIRouter(prefix="/configs", tags=["configs"])


def _get_owned_config(config_id: int, user: User, db: Session) -> SavedConfig:
    config = db.get(SavedConfig, config_id)
    if config is None or config.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="config not found")
    return config


@router.post("", response_model=SavedConfigOut, status_code=status.HTTP_201_CREATED)
def create_config(
    payload: SavedConfigCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SavedConfig:
    config = SavedConfig(owner_id=user.id, name=payload.name, config_json=payload.config_json)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("", response_model=list[SavedConfigOut])
def list_configs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SavedConfig]:
    stmt = select(SavedConfig).where(SavedConfig.owner_id == user.id).order_by(SavedConfig.created_at.desc())
    return list(db.scalars(stmt))


@router.get("/{config_id}", response_model=SavedConfigOut)
def get_config(config_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SavedConfig:
    return _get_owned_config(config_id, user, db)


@router.put("/{config_id}", response_model=SavedConfigOut)
def update_config(
    config_id: int,
    payload: SavedConfigUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedConfig:
    config = _get_owned_config(config_id, user, db)
    if payload.name is not None:
        config.name = payload.name
    if payload.config_json is not None:
        config.config_json = payload.config_json
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(config_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    config = _get_owned_config(config_id, user, db)
    db.delete(config)
    db.commit()
