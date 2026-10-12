import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import get_db
from app.services import delivery

router = APIRouter(prefix="/api")

Category = Literal["tobacco", "ambient_drink", "chilled", "ready_meal"]
Unit = Literal["개", "박스", "판", "봉지"]


class CompleteIn(BaseModel):
    receiver: str | None = None


class ZoneCheckIn(BaseModel):
    checked: bool


class IssueIn(BaseModel):
    type: Literal["파손", "수량부족", "오배송", "온도이상"]
    product_id: int | None = None
    qty: int | None = Field(default=None, gt=0)
    unit: Unit | None = None
    source: Literal["voice", "touch"] = "touch"


def _found(value, what: str):
    if value is None:
        raise HTTPException(status_code=404, detail=f"{what}을(를) 찾을 수 없습니다.")
    return value


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/driver")
def get_driver(conn: sqlite3.Connection = Depends(get_db)):
    return _found(delivery.get_driver(conn), "기사 정보")


@router.get("/routes/today")
def get_today_route(conn: sqlite3.Connection = Depends(get_db)):
    return _found(delivery.get_today_route(conn), "오늘 운행")


@router.get("/stops/{stop_id}")
def get_stop(stop_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _found(delivery.get_stop(conn, stop_id), "배송지")


@router.post("/stops/{stop_id}/complete")
def complete_stop(stop_id: int, body: CompleteIn | None = None, conn: sqlite3.Connection = Depends(get_db)):
    receiver = body.receiver if body else None
    return _found(delivery.complete_stop(conn, stop_id, receiver), "배송지")


@router.delete("/stops/{stop_id}/complete")
def cancel_complete(stop_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _found(delivery.cancel_complete(conn, stop_id), "배송지")


@router.patch("/stops/{stop_id}/zones/{category}")
def set_zone_checked(
    stop_id: int, category: Category, body: ZoneCheckIn, conn: sqlite3.Connection = Depends(get_db)
):
    return _found(delivery.set_zone_checked(conn, stop_id, category, body.checked), "배송지 구역")


@router.post("/stops/{stop_id}/issues", status_code=201)
def create_issue(stop_id: int, body: IssueIn, conn: sqlite3.Connection = Depends(get_db)):
    if body.product_id is not None and not delivery.product_exists(conn, body.product_id):
        raise HTTPException(status_code=404, detail="품목을(를) 찾을 수 없습니다.")
    issue = delivery.create_issue(
        conn, stop_id, body.type, product_id=body.product_id, qty=body.qty, unit=body.unit, source=body.source
    )
    return _found(issue, "배송지")


@router.get("/products/barcode/{barcode}")
def find_product_by_barcode(barcode: str, conn: sqlite3.Connection = Depends(get_db)):
    return _found(delivery.find_product_by_barcode(conn, barcode), "품목")
