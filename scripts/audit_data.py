# -*- coding: utf-8 -*-
"""
数据质量审计：从业务实际出发，逐项检查生成数据的一致性、合理性、口径正确性。
"""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import pymysql
from app.config import DB_CONFIG

conn = pymysql.connect(**DB_CONFIG)

def q(sql):
    return pd.read_sql(sql, conn)

issues = []   # 问题清单


def check(name, ok, detail):
    flag = "PASS" if ok else "!!"
    print(f"[{flag}] {name}: {detail}")
    if not ok:
        issues.append(f"{name}: {detail}")


print("=" * 60)
print("A. 主键与唯一性")
print("=" * 60)
for t, k in [("fact_order","order_id"), ("fact_approval","approval_id"),
             ("fact_consult","consult_id"), ("fact_complaint","complaint_id")]:
    df = q(f"SELECT {k} c FROM {t}")
    dup = df["c"].duplicated().sum()
    check(f"{t} 主键唯一", dup == 0, f"总数 {len(df)}, 重复 {dup}")

print("\n" + "=" * 60)
print("B. 时间逻辑")
print("=" * 60)
r = q("SELECT MIN(receive_time) mn, MAX(receive_time) mx FROM fact_order").iloc[0]
check("受理时间跨度", str(r["mn"])[:10] == "2026-07-13" and str(r["mx"])[:10] == "2026-10-10",
      f"{r['mn']} ~ {r['mx']}")

neg = q("SELECT COUNT(*) c FROM fact_order WHERE finish_time < receive_time").iloc[0]["c"]
check("时长无负数", neg == 0, f"finish<receive 的件数 {neg}")

doing_bad = q("SELECT COUNT(*) c FROM fact_order WHERE status='doing' AND finish_time IS NOT NULL").iloc[0]["c"]
check("在办件无办结时间", doing_bad == 0, f"doing 但有 finish_time 的件数 {doing_bad}")

abn = q("SELECT COUNT(*) c FROM fact_order WHERE status='abandoned'").iloc[0]["c"]
check("废弃件已剔除", abn == 0, f"fact_order 中 abandoned 件数 {abn}")

print("\n" + "=" * 60)
print("C. 超时口径复核（重算 vs 库标记）")
print("=" * 60)
df = q("""SELECT o.order_id, o.duration_days, o.is_timeout, d.sla_days
          FROM fact_order o JOIN dim_department d ON d.dept_code=o.dept_code
          WHERE o.status='done'""")
expect = (df["duration_days"] > df["sla_days"] * 1.4).astype(int)
mismatch = (expect != df["is_timeout"]).sum()
check("is_timeout 口径一致", mismatch == 0,
      f"done 件 {len(df)}, 重算不一致 {mismatch}")

print("\n" + "=" * 60)
print("D. 审批流水一致性")
print("=" * 60)
orphan = q("""SELECT COUNT(*) c FROM fact_approval a
             LEFT JOIN fact_order o ON o.order_id=a.order_id
             WHERE o.order_id IS NULL""").iloc[0]["c"]
check("审批外键完整", orphan == 0, f"无主审批行数 {orphan}")

# 审批时间应落在 [receive, finish] 内（容差 1 分钟）
df = q("""SELECT a.approve_time, o.receive_time, o.finish_time FROM fact_approval a
          JOIN fact_order o ON o.order_id=a.order_id""")
bad = ((df["approve_time"] < df["receive_time"] - pd.Timedelta(minutes=1)) |
       (df["approve_time"] > df["finish_time"] + pd.Timedelta(minutes=1))).sum()
check("审批时间在办件区间内", bad == 0, f"越界审批 {bad} / {len(df)}")

print("\n" + "=" * 60)
print("E. 业务分布合理性")
print("=" * 60)
df = q("SELECT DAYOFWEEK(receive_time) w, COUNT(*) c FROM fact_order GROUP BY w")
wk = {1:"周日",2:"周一",3:"周二",4:"周三",5:"周四",6:"周五",7:"周六"}
df["wd"] = df["w"].map(wk)
weekday_avg = df[df["w"].isin([2,3,4,5,6])]["c"].mean()
weekend_avg = df[df["w"].isin([1,7])]["c"].mean()
ratio = weekend_avg / weekday_avg
check("周末量明显低于工作日", 0.2 < ratio < 0.5,
      f"工作日均 {weekday_avg:.0f} 件, 周末均 {weekend_avg:.0f} 件, 比值 {ratio:.2f} (设计 0.3)")

df = q("SELECT DAY(receive_time) d, COUNT(*) c FROM fact_order GROUP BY d")
month_end = df[df["d"] >= 25]["c"].mean()
normal = df[df["d"] < 25]["c"].mean()
check("月末量高于平日", month_end > normal * 1.2,
      f"平日均 {normal:.0f}, 月末均 {month_end:.0f}, 比值 {month_end/normal:.2f}")

print("\n" + "=" * 60)
print("F. 值域检查")
print("=" * 60)
sat1 = q("SELECT COUNT(*) c FROM fact_consult WHERE satisfaction NOT BETWEEN 1 AND 5").iloc[0]["c"]
sat2 = q("SELECT COUNT(*) c FROM fact_complaint WHERE satisfaction NOT BETWEEN 1 AND 5").iloc[0]["c"]
check("满意度值域 1-5", sat1 + sat2 == 0, f"越界 {sat1+sat2}")
hd = q("SELECT COUNT(*) c FROM fact_complaint WHERE handle_days < 0").iloc[0]["c"]
check("处理天数非负", hd == 0, f"负数 {hd}")

print("\n" + "=" * 60)
print("G. 业务合理性总评")
print("=" * 60)
kpi = q("""SELECT COUNT(*) total,
                  AVG(status='done') done_rate,
                  AVG(is_timeout=1) timeout_rate,
                  SUM(dq_flag='abnormal_dur') abnormal
           FROM fact_order""").iloc[0]
days = 90
per_day = kpi["total"] / days
print(f"  日均工单: {per_day:.0f} 件/天")
print(f"  办结率: {kpi['done_rate']*100:.1f}%")
print(f"  超时率: {kpi['timeout_rate']*100:.1f}%")
print(f"  异常标记件: {kpi['abnormal']} 件, 占比 {kpi['abnormal']/kpi['total']*100:.1f}%")

conn.close()
print("\n" + "=" * 60)
if issues:
    print(f"发现 {len(issues)} 个问题：")
    for i in issues:
        print("  -", i)
else:
    print("全部检查通过，无逻辑问题")
