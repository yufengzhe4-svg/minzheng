# -*- coding: utf-8 -*-
"""
指标计算层：从 MySQL 读 fact_* 表，计算政务便民平台的全部统计指标。
所有返回值都是原生 dict / list，可直接 FastAPI jsonify。

统一口径：
- 率值（办结率 / 超时率 / 平均时长）默认排除 dq_flag='abnormal_dur' 的异常件；
- doing 件计入"未办结"，returned 件单独统计；
- 满意度分别来自 fact_complaint（投诉）与 fact_consult（咨询）。
"""
import warnings

import pymysql
import pandas as pd

from app.config import DB_CONFIG

warnings.filterwarnings("ignore", category=UserWarning)

# 统计口径过滤条件：默认只统计无质量异常标记的工单
OK = "dq_flag IS NULL"


def _q(sql, params=None):
    conn = pymysql.connect(**DB_CONFIG)
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


# ---------- 1. KPI 总览（首页卡片） ----------
def get_kpi():
    df = _q(f"""
      SELECT
        COUNT(*)                                            AS total,
        SUM(status = 'done')                                AS done_cnt,
        SUM(status = 'doing')                               AS doing_cnt,
        SUM(status = 'returned')                            AS returned_cnt,
        SUM(is_timeout = 1)                                 AS timeout_cnt,
        AVG(CASE WHEN {OK} THEN duration_days END)          AS avg_dur
      FROM fact_order""")
    row = df.iloc[0]

    c = _q("SELECT AVG(is_resolved) resolved_rate, AVG(satisfaction) satisfaction FROM fact_consult").iloc[0]
    m = _q("SELECT AVG(satisfaction) satisfaction, COUNT(*) cnt FROM fact_complaint WHERE satisfaction IS NOT NULL").iloc[0]
    q = _q("SELECT COUNT(*) abnormal FROM fact_order WHERE dq_flag = 'abnormal_dur'").iloc[0]

    total = int(row["total"])
    return {
        "total_orders": total,                                   # 全量工单
        "abnormal_orders": int(q["abnormal"]),                   # 异常标记件
        "valid_orders": total - int(q["abnormal"]),              # 参与统计的有效件
        "done_rate": round(float(row["done_cnt"]) / total * 100, 1),     # 办结率 %
        "doing_cnt": int(row["doing_cnt"]),
        "returned_cnt": int(row["returned_cnt"]),
        "avg_duration_days": round(float(row["avg_dur"]), 2),   # 平均办结时长（天）
        "timeout_rate": round(float(row["timeout_cnt"]) / max(1, float(row["done_cnt"])) * 100, 1),  # 超时率 %
        "consult_resolved_rate": round(float(c["resolved_rate"]) * 100, 1),   # 咨询解决率 %
        "consult_satisfaction": round(float(c["satisfaction"]), 2),           # 咨询满意度 1-5
        "complaint_satisfaction": round(float(m["satisfaction"]), 2),         # 投诉满意度 1-5
        "complaint_cnt": int(m["cnt"]),
    }


# ---------- 2. 部门排行 ----------
def get_dept_ranking():
    df = _q(f"""
      SELECT d.dept_short,
             COUNT(*)                                   AS total,
             AVG(o.status = 'done')                     AS done_rate,
             AVG(CASE WHEN o.dq_flag IS NULL THEN o.duration_days END) AS avg_dur,
             AVG(o.is_timeout = 1)                      AS timeout_rate
      FROM fact_order o
      JOIN dim_department d ON d.dept_code = o.dept_code
      WHERE o.{OK}
      GROUP BY d.dept_code, d.dept_short
      ORDER BY total DESC""")
    df["done_rate"] = (df["done_rate"] * 100).round(1)
    df["timeout_rate"] = (df["timeout_rate"] * 100).round(1)
    df["avg_dur"] = df["avg_dur"].round(2)
    return df.to_dict("records")


# ---------- 3. 日趋势（近 90 天） ----------
def get_daily_trend():
    df = _q(f"""
      SELECT DATE(receive_time)                        AS dt,
             COUNT(*)                                  AS orders,
             AVG(status = 'done')                      AS done_rate,
             AVG(is_timeout = 1)                       AS timeout_rate
      FROM fact_order
      WHERE {OK}
      GROUP BY DATE(receive_time)
      ORDER BY dt""")
    df["dt"] = df["dt"].astype(str)
    df["done_rate"] = (df["done_rate"] * 100).round(1)
    df["timeout_rate"] = (df["timeout_rate"] * 100).round(1)
    df["orders"] = df["orders"].astype(int)
    return df.to_dict("records")


# ---------- 4. 渠道分布 ----------
def get_channel_dist():
    df = _q(f"""
      SELECT channel, COUNT(*) AS cnt
      FROM fact_order WHERE {OK}
      GROUP BY channel ORDER BY cnt DESC""")
    total = int(df["cnt"].sum())
    return [{"channel": r["channel"], "cnt": int(r["cnt"]),
             "pct": float(round(float(r["cnt"]) / total * 100, 1))}
            for _, r in df.iterrows()]


# ---------- 5. 事项 TOP N ----------
def get_item_topn(n=10):
    df = _q(f"""
      SELECT i.item_name, i.dept_code,
             COUNT(*)                              AS total,
             AVG(o.is_timeout = 1)                 AS timeout_rate
      FROM fact_order o
      JOIN dim_item i ON i.item_code = o.item_code
      WHERE o.{OK}
      GROUP BY i.item_code, i.item_name
      ORDER BY total DESC LIMIT {int(n)}""")
    df["timeout_rate"] = (df["timeout_rate"] * 100).round(1)
    df["total"] = df["total"].astype(int)
    return df.to_dict("records")


# ---------- 6. 咨询分析 ----------
def get_consult_analysis():
    topic = _q("""
      SELECT topic, COUNT(*) cnt, AVG(is_resolved) resolved_rate, AVG(satisfaction) sat
      FROM fact_consult GROUP BY topic ORDER BY cnt DESC""")
    topic["resolved_rate"] = (topic["resolved_rate"] * 100).round(1)
    topic["sat"] = topic["sat"].round(2)
    ch = _q("SELECT channel, COUNT(*) cnt FROM fact_consult GROUP BY channel ORDER BY cnt DESC")
    return {
        "by_topic": topic.to_dict("records"),
        "by_channel": ch.to_dict("records"),
    }


# ---------- 7. 投诉分析 ----------
def get_complaint_analysis():
    tp = _q("SELECT type, COUNT(*) cnt FROM fact_complaint GROUP BY type ORDER BY cnt DESC")
    dept = _q("""
      SELECT d.dept_short, COUNT(*) cnt,
             AVG(handle_days) handle_days, AVG(satisfaction) sat
      FROM fact_complaint c JOIN dim_department d ON d.dept_code = c.dept_code
      GROUP BY d.dept_code ORDER BY cnt DESC""")
    dept["handle_days"] = dept["handle_days"].round(1)
    dept["sat"] = dept["sat"].round(2)
    return {
        "by_type": tp.to_dict("records"),
        "by_dept": dept.to_dict("records"),
    }


# ---------- 8. 数据质量概览 ----------
def get_quality_overview():
    df = _q("SELECT COALESCE(dq_flag, '正常') flag, COUNT(*) cnt FROM fact_order GROUP BY dq_flag")
    return {r["flag"]: int(r["cnt"]) for _, r in df.iterrows()}


# ---------- 9. 一键取首页全部指标 ----------
def get_dashboard():
    return {
        "kpi": get_kpi(),
        "dept_ranking": get_dept_ranking(),
        "daily_trend": get_daily_trend(),
        "channel_dist": get_channel_dist(),
        "item_top10": get_item_topn(10),
        "consult": get_consult_analysis(),
        "complaint": get_complaint_analysis(),
        "quality": get_quality_overview(),
    }


if __name__ == "__main__":
    import json
    d = get_dashboard()
    print(json.dumps(d["kpi"], ensure_ascii=False, indent=2))
    print("\n部门排行 Top3：")
    for r in d["dept_ranking"][:3]:
        print(" ", r)
    print("\n日趋势条数：", len(d["daily_trend"]))
    print("渠道分布：", d["channel_dist"])
    print("数据质量：", d["quality"])
