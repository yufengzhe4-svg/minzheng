# -*- coding: utf-8 -*-
"""全局配置：数据库连接 + 数据生成规模"""
import os

DB_CONFIG = dict(
    host="localhost",
    port=3306,
    user="root",
    password=os.getenv("MYSQL_PASSWORD", "123456"),
    database="minzheng",
    charset="utf8mb4",
)

# 数据生成规模（可按需调小调试）
GEN_CONFIG = dict(
    days=90,            # 生成近 90 天数据（约 3 个月）
    n_orders=30000,     # 工单总量
    n_consult=15000,    # 咨询记录
    n_complaint=2000,   # 投诉记录
    seed=42,            # 随机种子，可复现
)
