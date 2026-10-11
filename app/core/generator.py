# -*- coding: utf-8 -*-
"""
数据生成器：用 Faker 模拟政务办件数据（含质量问题埋点）。
产出 4 张原始表（DataFrame），落盘 data/raw/*.csv 留档，交给 cleaner 清洗。
"""
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker
import pymysql

from app.config import DB_CONFIG, GEN_CONFIG

RAW_DIR = os.path.join("data", "raw")


def load_dim():
    """从 MySQL 读字典表（部门 / 事项），保证生成口径与库一致"""
    conn = pymysql.connect(**DB_CONFIG)
    depts = pd.read_sql("SELECT * FROM dim_department", conn)
    items = pd.read_sql("SELECT * FROM dim_item", conn)
    conn.close()
    return depts, items


# ---------- 小工具 ----------
def _name_pool(fake, n=500):
    return [fake.name() for _ in range(n)]


def _masked_id(rnd):
    """脱敏证件号：6101 + 8 个* + 4 位数字"""
    return f"6101{'*'*8}{rnd.randint(1000, 9999)}"


def _day_weights(end_date, days):
    """给 90 天候选日期算权重：周末 ×0.3，每月 25 日后（月末）×1.5，
    法定节假日 ×0.1（几乎无人办事）。"""
    # 2026 年法定节假日（在 90 天窗口内的）：中秋、国庆
    HOLIDAYS = {
        "2026-09-25",  # 中秋节
        "2026-10-01", "2026-10-02", "2026-10-03",
        "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",  # 国庆
    }
    weights, dates = [], []
    for i in range(days - 1, -1, -1):
        d = end_date - timedelta(days=i)
        w = 1.0
        ds = d.strftime("%Y-%m-%d")
        if ds in HOLIDAYS:
            w *= 0.1                                  # 法定节假日
        elif d.weekday() >= 5:
            w *= 0.3                                  # 周六日
        if d.day >= 25:
            w *= 1.5                                  # 月末堆积
        dates.append(d)
        weights.append(w)
    return dates, np.array(weights) / sum(weights)


# ---------- 主生成 ----------
def gen_orders(depts, items, rnd, names):
    """生成工单 DataFrame（含脏数据埋点）"""
    n = GEN_CONFIG["n_orders"]
    end_date = datetime(2026, 10, 10, 17, 30)
    day_list, day_probs = _day_weights(end_date, GEN_CONFIG["days"])

    # 部门按权重展开成可选池
    dept_pool = []
    for _, d in depts.iterrows():
        dept_pool += [d["dept_code"]] * int(d["workload_weight"] * 10)
    items_by_dept = {dc: g for dc, g in items.groupby("dept_code")}
    sla_map = dict(zip(depts["dept_code"], depts["sla_days"]))

    rows = []
    seq_by_day = {}
    channel_pool = ["online"] * 46 + ["window"] * 38 + ["self"] * 16

    for _ in range(n):
        dept = rnd.choice(dept_pool)
        item = items_by_dept[dept].sample(1, random_state=rnd.randint(0, 10**9)).iloc[0]

        # 受理时间：按日期权重选日 + 工作时段随机
        day = np.random.choice(day_list, p=day_probs)
        receive = day.replace(hour=rnd.randint(8, 17), minute=rnd.randint(0, 59), second=0)

        # 状态：4% 废弃 / 1% 退件 / 5% 在办 / 其余已办结
        r = rnd.random()
        if r < 0.04:
            status, finish = "abandoned", None
        elif r < 0.05:
            status, finish = "returned", None
        elif r < 0.10:
            status, finish = "doing", None
        else:
            status = "done"
            # 办结时长：基础 = 承诺时限 × 0.85，复杂度温和加成（避免双乘法把
            # 高复杂度事项均值推到判定线之上导致超时率畸高）
            mean_dur = max(0.5, sla_map[dept] * (0.85 + item["complexity"] * 0.15))
            dur = max(0.5, rnd.gauss(mean_dur, mean_dur * 0.35))
            finish = receive + timedelta(days=dur)

        # 当日工单序号 → 工单号
        day_key = receive.strftime("%Y%m%d")
        seq_by_day[day_key] = seq_by_day.get(day_key, 0) + 1
        order_id = f"GW{day_key}{seq_by_day[day_key]:04d}"

        rows.append({
            "order_id": order_id,
            "citizen_name": rnd.choice(names),
            "citizen_masked": _masked_id(rnd),
            "item_code": item["item_code"],
            "dept_code": dept,
            "channel": rnd.choice(channel_pool),
            "receive_time": receive,
            "finish_time": finish,
            "status": status,
            "is_appointment": 1 if (rnd.random() < 0.4) else 0,
            "materials_count": int(item["avg_materials"] + rnd.randint(-1, 2)),
            "handler": rnd.choice(names),
        })

    df = pd.DataFrame(rows)

    # ===== 质量问题埋点 =====
    # ① 5% 受理时间缺失（清洗时剔除）
    miss_idx = df.sample(frac=0.05, random_state=42).index
    df.loc[miss_idx, "receive_time"] = pd.NaT

    # ② 3% 重复件：复制已生成工单，同申请人同日同事项（清洗时去重）
    dup_src = df[df["status"] == "done"].sample(frac=0.03, random_state=7)
    dup_rows = []
    for _, o in dup_src.iterrows():
        new_id = o["order_id"] + "C"          # 重复件 ID 带 C 后缀，便于识别
        new_recv = o["receive_time"] + timedelta(hours=rnd.randint(1, 5))
        dup_rows.append({**o.to_dict(), "order_id": new_id, "receive_time": new_recv})
    df = pd.concat([df, pd.DataFrame(dup_rows)], ignore_index=True)

    # ③ 2% 异常时长：秒级办结 或 超 30 天（清洗时打 dq_flag）
    abn = df[df["status"] == "done"].sample(frac=0.02, random_state=11).index
    for i in abn:
        if rnd.random() < 0.5:
            df.at[i, "finish_time"] = df.at[i, "receive_time"] + timedelta(minutes=3)
        else:
            df.at[i, "finish_time"] = df.at[i, "receive_time"] + timedelta(days=35)

    return df


def gen_approvals(orders, rnd, names):
    """每个 done/timeout 工单生成 1-4 个审批环节"""
    items = pd.read_sql("SELECT * FROM dim_item", pymysql.connect(**DB_CONFIG))
    comp_map = dict(zip(items["item_code"], items["complexity"]))
    rows = []
    for _, o in orders[orders["status"].isin(["done", "timeout"])].iterrows():
        c = comp_map.get(o["item_code"], 1.0)
        steps = ["accept"]
        if c > 0.6:
            steps.append("review1")
        if c > 1.3:
            steps.append("review2")
        steps.append("finish")

        t0, t1 = o["receive_time"], o["finish_time"]
        if pd.isna(t1):
            continue
        for k, step in enumerate(steps, start=1):
            approve_t = t0 + (t1 - t0) * (k / len(steps))
            code = {"accept": "A", "review1": "R1", "review2": "R2", "finish": "F"}[step]
            rows.append({
                "approval_id": f"AP{o['order_id'][-8:]}{code}",
                "order_id": o["order_id"],
                "approver": rnd.choice(names),
                "step": step,
                "result": "pass" if rnd.random() < 0.95 else "return",
                "approve_time": approve_t,
            })
    return pd.DataFrame(rows)


def gen_consults(depts, rnd, names):
    n = GEN_CONFIG["n_consult"]
    end_date = datetime(2026, 10, 10, 17, 30)
    day_list, day_probs = _day_weights(end_date, GEN_CONFIG["days"])
    # 主题按真实咨询热度加权：进度查询最多（大家都在等办件）、政策咨询最少
    topic_pool = ["progress"] * 35 + ["process"] * 28 + ["material"] * 22 + ["policy"] * 15
    # 各主题解决率分层：进度查询一句话搞定最高；政策复杂难当场解答最低
    resolve_rate = {"progress": 0.92, "process": 0.85, "material": 0.88, "policy": 0.70}
    sat_mean = {"progress": 3.8, "process": 3.5, "material": 3.6, "policy": 2.9}
    rows = []
    for i in range(n):
        day = np.random.choice(day_list, p=day_probs)
        ct = day.replace(hour=rnd.randint(8, 19), minute=rnd.randint(0, 59))
        topic = rnd.choice(topic_pool)
        sat = min(5.0, max(1.0, rnd.gauss(sat_mean[topic], 0.8)))
        rows.append({
            "consult_id": f"CS{ct.strftime('%Y%m%d')}{i:05d}",
            "channel": rnd.choice(["hotline", "online", "window"]),
            "topic": topic,
            "is_resolved": 1 if rnd.random() < resolve_rate[topic] else 0,
            "satisfaction": round(sat) if rnd.random() > 0.1 else np.nan,
            "consult_time": ct,
        })
    return pd.DataFrame(rows)


def gen_complaints(depts, rnd, names):
    n = GEN_CONFIG["n_complaint"]
    end_date = datetime(2026, 10, 10, 17, 30)
    day_list, day_probs = _day_weights(end_date, GEN_CONFIG["days"])
    depts = depts.copy()
    # 投诉权重 = 工单量权重 × 投诉倾向（满意度越差投诉越多），
    # 使投诉量与部门工单规模正相关，而不是 2000 条被 10 个部门均分
    depts["w"] = depts["workload_weight"] * (1.0 + (-depts["satisfaction_bias"]) * 1.5)
    w = depts["w"].values / depts["w"].sum()
    # 部门分层：投诉满意度均值 = 3.0 + bias×2（效率差部门真的低）；
    # 投诉处理天数均值 = 3 + (-bias)×6（效率差部门处理也慢）
    sat_mean = dict(zip(depts["dept_code"], 3.0 + depts["satisfaction_bias"] * 2.0))
    hd_mean = dict(zip(depts["dept_code"], 3.0 + (-depts["satisfaction_bias"]) * 6.0))

    rows = []
    for i in range(n):
        day = np.random.choice(day_list, p=day_probs)
        ct = day.replace(hour=rnd.randint(8, 18), minute=rnd.randint(0, 59))
        dept = np.random.choice(depts["dept_code"], p=w)
        is_doing = rnd.random() < 0.1
        sat = min(5.0, max(1.0, rnd.gauss(sat_mean[dept], 0.9)))
        hd = min(15.0, max(0.5, rnd.gauss(hd_mean[dept], 2.0)))
        rows.append({
            "complaint_id": f"TS{ct.strftime('%Y%m%d')}{i:05d}",
            "type": rnd.choice(["efficiency", "attitude", "process", "other"]),
            "dept_code": dept,
            "status": "doing" if is_doing else "done",
            "handle_days": np.nan if is_doing else round(hd, 1),
            "satisfaction": round(sat),
            "complaint_time": ct,
        })
    return pd.DataFrame(rows)


def generate_all():
    rnd = random.Random(GEN_CONFIG["seed"])
    fake = Faker("zh_CN")
    names = _name_pool(fake)

    depts, items = load_dim()
    print("[1/4] 生成工单 ...")
    orders = gen_orders(depts, items, rnd, names)
    print(f"      原始工单 {len(orders)} 条")
    print("[2/4] 生成审批 ...")
    approvals = gen_approvals(orders, rnd, names)
    print(f"      审批记录 {len(approvals)} 条")
    print("[3/4] 生成咨询 ...")
    consults = gen_consults(depts, rnd, names)
    print(f"      咨询记录 {len(consults)} 条")
    print("[4/4] 生成投诉 ...")
    complaints = gen_complaints(depts, rnd, names)
    print(f"      投诉记录 {len(complaints)} 条")

    os.makedirs(RAW_DIR, exist_ok=True)
    for name, df in [("orders", orders), ("approvals", approvals),
                     ("consults", consults), ("complaints", complaints)]:
        df.to_csv(os.path.join(RAW_DIR, f"{name}.csv"), index=False, encoding="utf-8-sig")
    print("原始 CSV 已落盘 data/raw/")
    return dict(orders=orders, approvals=approvals, consults=consults, complaints=complaints)


if __name__ == "__main__":
    generate_all()
