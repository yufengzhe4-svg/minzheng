# -*- coding: utf-8 -*-
"""灌库后抽查验证"""
import pymysql
from app.config import DB_CONFIG

conn = pymysql.connect(**DB_CONFIG)
cur = conn.cursor()

print("== 各表行数 ==")
for t in ["dim_department", "dim_item", "fact_order", "fact_approval", "fact_consult", "fact_complaint"]:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t}: {cur.fetchone()[0]}")

print("\n== 工单状态分布 ==")
cur.execute("SELECT status, COUNT(*) FROM fact_order GROUP BY status")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

print("\n== 各部门工单量 Top5（含超时率） ==")
cur.execute("""
  SELECT d.dept_short, COUNT(*), SUM(o.is_timeout),
         ROUND(AVG(o.duration_days),1)
  FROM fact_order o JOIN dim_department d ON d.dept_code=o.dept_code
  GROUP BY o.dept_code ORDER BY COUNT(*) DESC LIMIT 5""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}件, 超时{r[2]}件, 均时长{r[3]}天")

print("\n== 数据质量标记分布 ==")
cur.execute("""SELECT COALESCE(dq_flag,'正常'), COUNT(*) FROM fact_order GROUP BY dq_flag""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

print("\n== 时间范围 ==")
cur.execute("SELECT MIN(receive_time), MAX(receive_time) FROM fact_order")
r = cur.fetchone()
print(f"  {r[0]}  ~  {r[1]}")

print("\n== 样本 3 条工单 ==")
cur.execute("""SELECT order_id, citizen_name, item_code, dept_code, channel,
                      status, duration_days, is_timeout, dq_flag
               FROM fact_order LIMIT 3""")
for r in cur.fetchall():
    print(" ", r)

cur.close(); conn.close()
