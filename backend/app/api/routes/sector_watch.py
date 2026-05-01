"""Sector Watch API routes.

Customers use these endpoints to manage watch profiles (which industry sectors
and US states to monitor) and retrieve matching regulatory filings.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.crud import (
    create_sector_watch,
    delete_sector_watch,
    get_sector_watch,
    get_sector_watches_by_owner,
    update_sector_watch,
)
from app.models import (
    SectorWatchCreate,
    SectorWatchesPublic,
    SectorWatchPublic,
    SectorWatchUpdate,
)

router = APIRouter()


@router.get("/", response_model=SectorWatchesPublic)
def list_sector_watches(
    current_user: CurrentUser,
    session: SessionDep,
) -> SectorWatchesPublic:
    """List the authenticated user's sector watch profiles."""
    watches = get_sector_watches_by_owner(session=session, owner_id=current_user.id)
    return SectorWatchesPublic(
        data=[SectorWatchPublic.model_validate(w) for w in watches],
        count=len(watches),
    )


@router.post("/", response_model=SectorWatchPublic)
def create_watch(
    watch_in: SectorWatchCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> SectorWatchPublic:
    """Create a new sector watch profile."""
    db_obj = create_sector_watch(
        session=session, watch_in=watch_in, owner_id=current_user.id
    )
    return SectorWatchPublic.model_validate(db_obj)


@router.put("/{watch_id}", response_model=SectorWatchPublic)
def update_watch(
    watch_id: UUID,
    update_in: SectorWatchUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> SectorWatchPublic:
    """Update sectors or state codes for an existing watch profile."""
    db_obj = get_sector_watch(
        session=session, watch_id=watch_id, owner_id=current_user.id
    )
    if not db_obj:
        raise HTTPException(status_code=404, detail="Watch profile not found")
    updated = update_sector_watch(session=session, db_obj=db_obj, update_in=update_in)
    return SectorWatchPublic.model_validate(updated)


@router.delete("/{watch_id}")
def delete_watch(
    watch_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    """Delete a sector watch profile."""
    db_obj = get_sector_watch(
        session=session, watch_id=watch_id, owner_id=current_user.id
    )
    if not db_obj:
        raise HTTPException(status_code=404, detail="Watch profile not found")
    delete_sector_watch(session=session, db_obj=db_obj)
    return {"message": "Watch profile deleted"}


@router.get("/{watch_id}/filings")
def get_watch_filings(
    watch_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    since_days: int = 7,
) -> dict[str, Any]:
    """Fetch live regulatory filings matching a watch profile's sectors and states.

    Results are grouped: ``{ state_code: { sector: [filings] } }``.
    Federal filings matching the sectors are also included under ``"federal"``.
    """
    from app.naturalsentinel.fetchers.base import fetch_filings
    from app.naturalsentinel.models import IndustrySector, StateCode

    db_obj = get_sector_watch(
        session=session, watch_id=watch_id, owner_id=current_user.id
    )
    if not db_obj:
        raise HTTPException(status_code=404, detail="Watch profile not found")

    sectors: list[IndustrySector] = []
    for s in db_obj.industry_sectors or []:
        try:
            sectors.append(IndustrySector(s))
        except ValueError:
            pass

    state_codes: list[StateCode] = []
    for sc in db_obj.state_codes or []:
        try:
            state_codes.append(StateCode(sc))
        except ValueError:
            pass

    filings = fetch_filings(
        sectors=sectors or None,
        state_codes=state_codes or None,
        since_days=since_days,
        live=True,
        fetch_full_text=False,
    )

    # Group: { jurisdiction/state_code: { sector: [filing_dicts] } }
    grouped: dict[str, dict[str, list[dict]]] = {}
    for f in filings:
        key = f.state_code.value if f.state_code else f.jurisdiction.value
        sector_list = f.industry_sectors or [f.domain.value]
        for sector in sector_list:
            grouped.setdefault(key, {}).setdefault(sector, []).append(
                {
                    "id": f.id,
                    "title": f.title,
                    "domain": f.domain.value,
                    "source_url": f.source_url,
                    "published_date": f.published_date,
                    "change_type": f.change_type.value,
                    "jurisdiction": f.jurisdiction.value,
                    "state_code": f.state_code.value if f.state_code else None,
                    "industry_sectors": f.industry_sectors,
                }
            )

    return {
        "watch_id": str(watch_id),
        "since_days": since_days,
        "total": len(filings),
        "grouped": grouped,
    }
