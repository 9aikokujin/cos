from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db


from app.schemas.account import (AccountBulkCreateRequest, AccountCreate,
                                 AccountRead, AccountUpdate)
from app.services.account import AccountService

router = APIRouter()


@router.get("/", response_model=list[AccountRead])
async def get_all(db: AsyncSession = Depends(get_db)):
    service = AccountService(db)
    try:
        return await service.get_all()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=list[AccountRead])
async def search_accounts(
    query: str = Query(..., min_length=1, description="Частичное совпадение в account_str"),
    db: AsyncSession = Depends(get_db)
):
    service = AccountService(db)
    try:
        accounts = await service.search_accounts(query)
        return accounts
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=AccountRead)
async def create_account(
    account_create: AccountCreate, db: AsyncSession = Depends(get_db)
):
    service = AccountService(db)
    try:
        return await service.create_account(account_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk", response_model=list[AccountRead])
async def bulk_create_accounts(
    payload: AccountBulkCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    service = AccountService(db)
    try:
        return await service.bulk_create_accounts(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{id}", response_model=AccountRead)
async def update_account(
    id: int,
    account_update: AccountUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = AccountService(db)
    try:
        return await service.update_account(id, account_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{id}", response_model=AccountRead)
async def delete_account(id: int, db: AsyncSession = Depends(get_db)):
    service = AccountService(db)
    try:
        return await service.delete_account(id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
