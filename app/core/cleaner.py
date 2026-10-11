# -*- coding: utf-8 -*-
"""
清洗器：读 generator 产出的原始 DataFrame，按设计口径清洗，
写入 MySQL fact_* 表（先清表再批量插入，幂等可重跑）。
"""
import numpy as np
import pandas as pd
import pymysql

from app.config import DB_CONFIG


def clean_orders(df):
    """工单清洗，返回 (干净 DataFrame, 清洗报告 dict)"""
    report = {}
    report["raw"] = len(df)

    # ① 受理时间缺失 → 剔除
    df = df[df["receive_time"].notna()].copy()
    report["drop_missing_receive"] = report["raw"] - len(df)

    # ② 废弃件 → 剔除（留档在 raw CSV）
    abandoned = df[df["status"] == "abandoned"]
    df = df[df["status"] != "abandoned"].copy()
    report["drop_abandoned"] = len(abandoned)

    # ③ 重复件：同申请人 + 同事项 + 同自然日 → 保留最早一条，其余剔除
    df = df.sort_values("receive_time").reset_index(drop=True)
    df["_date"] = pd.to_datetime(df["receive_time"]).dt.date
    dup = df.duplicated(subset=["citizen_masked", "item_code", "_date"], keep="first")
    report["drop_duplicate"] = int(dup.sum())
    df = df[~dup].copy()
    df.drop(columns=["_date"], inplace=True)

    # ④ 计算 duration_days（办结时长，自然日）
    done_mask = df["status"] == "done"
    df.loc[done_mask, "duration_days"] = (
        (pd.to_datetime(df.loc[done_mask, "finish_time"]) -
         pd.to_datetime(df.loc[done_mask, "receive_time"])).dt.total_seconds() / 86400
    )

    # 加载部门承诺时限（异常判定与超时判定共用）
    conn = pymysql.connect(**DB_CONFIG)
    sla = pd.read_sql("SELECT dept_code, sla_days FROM dim_department", conn)
    conn.close()
    df["sla_days"] = df["dept_code"].map(dict(zip(sla["dept_code"], sla["sla_days"])))

    # ⑤ 异常时长：<0.05 天（秒办结）或 > 承诺时限 × 3（相对阈值，
    # 避免把建设工程这类本就该办 30+ 天的事项误判为异常）→ 打 dq_flag，保留入库
    abn = (df["duration_days"].notna() &
           ((df["duration_days"] < 0.05) | (df["duration_days"] > df["sla_days"] * 3)))
    df.loc[abn, "dq_flag"] = "abnormal_dur"
    report["flag_abnormal"] = int(abn.sum())

    # ⑥ 超时判定：duration_days > 部门 sla_days × 1.4
    df["sla_limit"] = df["sla_days"] * 1.4
    df["is_timeout"] = ((df["duration_days"].notna()) &
                        (df["duration_days"] > df["sla_limit"])).astype(int)
    df.drop(columns=["sla_days", "sla_limit"], inplace=True)

    report["clean"] = len(df)
    report["timeout_orders"] = int(df["is_timeout"].sum())
    report["missing_materials"] = int(df["materials_count"].isna().sum())
    return df, report


# ---------- 写库 ----------
def _batch_insert(cur, table, cols, rows, batch=2000):
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))})"
    for i in range(0, len(rows), batch):
        cur.executemany(sql, rows[i:i+batch])


def save_to_db(data):
    orders = data["orders"]
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 幂等：先清事实表；被外键引用的表不能 TRUNCATE，临时关掉外键检查
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in ["fact_approval", "fact_consult", "fact_complaint", "fact_order"]:
        cur.execute(f"TRUNCATE TABLE {t}")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")

    # fact_order
    o = orders.copy()
    o["receive_time"] = pd.to_datetime(o["receive_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    o["finish_time"] = pd.to_datetime(o["finish_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["order_id", "citizen_name", "citizen_masked", "item_code", "dept_code",
            "channel", "receive_time", "finish_time", "status", "is_appointment",
            "materials_count", "handler", "duration_days", "is_timeout", "dq_flag"]
    rows = [(r["order_id"], r["citizen_name"], r["citizen_masked"], r["item_code"],
             r["dept_code"], r["channel"], r["receive_time"],
             None if pd.isna(r["finish_time"]) else r["finish_time"],
             r["status"], int(r["is_appointment"]),
             None if pd.isna(r["materials_count"]) else int(r["materials_count"]),
             r["handler"],
             None if pd.isna(r["duration_days"]) else float(r["duration_days"]),
             int(r["is_timeout"]),
             None if pd.isna(r["dq_flag"]) else r["dq_flag"])
            for _, r in o.iterrows()]
    _batch_insert(cur, "fact_order", cols, rows)
    print(f"  fact_order 写入 {len(rows)} 行")

    # fact_approval：审批在清洗前生成，需按清洗后剩余的工单号过滤，否则触发外键
    a = data["approvals"]
    valid_ids = set(orders["order_id"])
    a = a[a["order_id"].isin(valid_ids)].copy()
    a["approve_time"] = pd.to_datetime(a["approve_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    rows = [(r["approval_id"], r["order_id"], r["approver"], r["step"],
             r["result"], r["approve_time"]) for _, r in a.iterrows()]
    _batch_insert(cur, "fact_approval",
                  ["approval_id", "order_id", "approver", "step", "result", "approve_time"], rows)
    print(f"  fact_approval 写入 {len(rows)} 行")

    # fact_consult
    c = data["consults"]
    c["consult_time"] = pd.to_datetime(c["consult_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    rows = [(r["consult_id"], r["channel"], r["topic"], int(r["is_resolved"]),
             None if pd.isna(r["satisfaction"]) else int(r["satisfaction"]), r["consult_time"])
            for _, r in c.iterrows()]
    _batch_insert(cur, "fact_consult",
                  ["consult_id", "channel", "topic", "is_resolved", "satisfaction", "consult_time"], rows)
    print(f"  fact_consult 写入 {len(rows)} 行")

    # fact_complaint
    m = data["complaints"]
    m["complaint_time"] = pd.to_datetime(m["complaint_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    rows = [(r["complaint_id"], r["type"], r["dept_code"], r["status"],
             None if pd.isna(r["handle_days"]) else float(r["handle_days"]),
             None if pd.isna(r["satisfaction"]) else int(r["satisfaction"]),
             r["complaint_time"]) for _, r in m.iterrows()]
    _batch_insert(cur, "fact_complaint",
                  ["complaint_id", "type", "dept_code", "status", "handle_days",
                   "satisfaction", "complaint_time"], rows)
    print(f"  fact_complaint 写入 {len(rows)} 行")

    conn.commit()
    cur.close()
    conn.close()


def clean_all(data):
    orders, report = clean_orders(data["orders"])
    data["orders"] = orders
    print("清洗报告：")
    for k, v in report.items():
        print(f"  {k}: {v}")
    return data
