# -*- coding: utf-8 -*-
"""
运行脚本：调用 app.db.schema 建库建表，然后验证结果
用法：python scripts/init_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from app.config import DB_CONFIG
from app.db.schema import init_schema


def main():
    # 1. 建库建表（正式代码在 app/db/schema.py）
    init_schema()
    print("[1/2] 建库建表 + 写入部门事项 完成")

    # 2. 验证
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = sorted(r[0] for r in cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM dim_department")
    n_dept = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dim_item")
    n_item = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"[2/2] 验证：{len(tables)} 张表（{', '.join(tables)}），部门 {n_dept} 个，事项 {n_item} 个")
    print("OK")


if __name__ == "__main__":
    main()
