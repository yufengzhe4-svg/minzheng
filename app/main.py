# -*- coding: utf-8 -*-
"""
FastAPI 应用入口。
启动：uvicorn app.main:app --reload --port 8000
自动文档：http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.api.routes import api_router

app = FastAPI(
    title="政务民生大数据统计与便民服务平台",
    description="后端统计接口 · 数据来源 minzheng MySQL 库",
    version="1.0.0",
)

# 前端页面跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
