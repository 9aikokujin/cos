from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db


from app.schemas.proxy import (ProxyBulkCreateRequest,
                              ProxyBulkDeleteResponse,
                              ProxyCreate, ProxyRead, ProxyUpdate)
from app.services.proxy import ProxyService

router = APIRouter()


@router.get("/", response_model=list[ProxyRead])
async def get_all(db: AsyncSession = Depends(get_db)):
    service = ProxyService(db)
    try:
        return await service.get_all()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=ProxyRead)
async def create_proxy(
    proxy_create: ProxyCreate, db: AsyncSession = Depends(get_db)
):
    service = ProxyService(db)
    try:
        return await service.create_proxy(proxy_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk", response_model=list[ProxyRead])
async def bulk_create_proxies(
    payload: ProxyBulkCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    service = ProxyService(db)
    try:
        return await service.bulk_create_proxies(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{id}", response_model=ProxyRead)
async def update_proxy(
    id: int,
    proxy_update: ProxyUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = ProxyService(db)
    try:
        return await service.update_proxy(id, proxy_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}", response_model=ProxyRead)
async def delete_proxy(id: int, db: AsyncSession = Depends(get_db)):
    service = ProxyService(db)
    try:
        return await service.delete_proxy(id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/", response_model=ProxyBulkDeleteResponse)
async def delete_all_proxies(db: AsyncSession = Depends(get_db)):
    service = ProxyService(db)
    try:
        deleted = await service.delete_all_proxies()
        return ProxyBulkDeleteResponse(deleted=deleted)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
