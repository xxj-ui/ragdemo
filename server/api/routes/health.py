"""M7 系统状态路由：04 §4.8（恒返 200）"""
from __future__ import annotations

from fastapi import APIRouter

from server.api.deps import get_container
from server.api.schemas import Envelope, HealthData
from server.services import health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Envelope[HealthData], summary="健康检查")
async def health_check():
    result = health.probe(get_container())
    return Envelope(data=HealthData(**result))
