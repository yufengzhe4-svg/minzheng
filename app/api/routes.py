# -*- coding: utf-8 -*-
"""
API 路由层：把 stats.py 的指标计算结果暴露成 REST 接口。
前端页面直接 fetch 这些接口拿 JSON。
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.core import stats, agent

api_router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list = []


@api_router.get("/health", summary="健康检查")
def health():
    return {"status": "ok", "service": "minzheng-platform"}


@api_router.get("/kpi", summary="KPI 总览（首页卡片）")
def kpi():
    return stats.get_kpi()


@api_router.get("/dashboard", summary="一键取首页全部指标")
def dashboard():
    return stats.get_dashboard()


@api_router.get("/dept/ranking", summary="部门排行")
def dept_ranking():
    return {"data": stats.get_dept_ranking()}


@api_router.get("/trend/daily", summary="近 90 天日趋势")
def daily_trend():
    return {"data": stats.get_daily_trend()}


@api_router.get("/channel", summary="渠道分布")
def channel():
    return {"data": stats.get_channel_dist()}


@api_router.get("/items/top", summary="高频事项 TOP N")
def items_top(n: int = Query(10, ge=1, le=20)):
    return {"data": stats.get_item_topn(n)}


@api_router.get("/consult", summary="咨询分析（主题/渠道）")
def consult():
    return stats.get_consult_analysis()


@api_router.get("/complaint", summary="投诉分析（类型/部门）")
def complaint():
    return stats.get_complaint_analysis()


@api_router.get("/quality", summary="数据质量概览")
def quality():
    return stats.get_quality_overview()


@api_router.post("/chat", summary="AI 智能问答（规则+大模型）")
def chat(req: ChatRequest):
    return agent.answer(req.message, req.history)
