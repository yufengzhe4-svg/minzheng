# -*- coding: utf-8 -*-
"""
单独跑数据清洗：从 data/raw/*.csv 读原始脏数据 → 清洗 → 写入 MySQL。
不重新生成数据，适合你想重跑清洗流程时用。
运行：python run_clean.py
"""
import os
import pandas as pd
from app.core.cleaner import clean_all, save_to_db

RAW_DIR = os.path.join("data", "raw")

print("== 1. 读取原始脏数据 ==")
orders = pd.read_csv(os.path.join(RAW_DIR, "orders.csv"), parse_dates=["receive_time", "finish_time"])
approvals = pd.read_csv(os.path.join(RAW_DIR, "approvals.csv"), parse_dates=["approve_time"])
consults = pd.read_csv(os.path.join(RAW_DIR, "consults.csv"), parse_dates=["consult_time"])
complaints = pd.read_csv(os.path.join(RAW_DIR, "complaints.csv"), parse_dates=["complaint_time"])
print(f"  工单 {len(orders)} 条 / 审批 {len(approvals)} 条 / 咨询 {len(consults)} 条 / 投诉 {len(complaints)} 条")

data = dict(orders=orders, approvals=approvals, consults=consults, complaints=complaints)

print("\n== 2. 数据清洗 ==")
data = clean_all(data)

print("\n== 3. 清洗后数据落盘 data/clean/ ==")
CLEAN_DIR = os.path.join("data", "clean")
os.makedirs(CLEAN_DIR, exist_ok=True)

# 审批表要按清洗后剩余的工单号过滤，和写库口径一致
valid_ids = set(data["orders"]["order_id"])
approvals_clean = data["approvals"][data["approvals"]["order_id"].isin(valid_ids)]

for name, df in [("orders", data["orders"]),
                 ("approvals", approvals_clean),
                 ("consults", data["consults"]),
                 ("complaints", data["complaints"])]:
    path = os.path.join(CLEAN_DIR, f"{name}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  {path}  ({len(df)} 行)")

print("\n== 4. 写入 MySQL ==")
save_to_db(data)

print("\n全部完成。")
