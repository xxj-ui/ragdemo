"""M7 系统状态路由：04 §4.8（恒返 200）"""
from __future__ import annotations

from fastapi import APIRouter

from server.deps import get_container
from server.schemas import Envelope, HealthData
from server.service import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Envelope[HealthData], summary="健康检查")
async def health():
    result = health_service.probe(get_container())
    return Envelope(data=HealthData(**result))
