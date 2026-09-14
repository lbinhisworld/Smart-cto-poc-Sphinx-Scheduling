from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    data: dict | list | None = None
    message: str = ""


class ScheduleBody(BaseModel):
    order_nos: list[str] = Field(default_factory=lambda: ["SO-001", "SO-002", "SO-003"])
    today: date
    reserved_ratio: float | None = 0.0


class OrderDuePatch(BaseModel):
    due_date: date
