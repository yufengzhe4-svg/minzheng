# -*- coding: utf-8 -*-
"""
数据库初始化模块：建表 DDL + 部门/事项初始数据
这是项目正式代码的一部分，不是脚本。
"""
import pymysql
from app.config import DB_CONFIG

# ========== 建表 DDL ==========

DDL = [
    # 1. 部门字典
    """CREATE TABLE IF NOT EXISTS dim_department (
      dept_code         VARCHAR(8)    NOT NULL COMMENT '部门编码（主键）',
      dept_name         VARCHAR(32)   NOT NULL COMMENT '部门全称',
      dept_short        VARCHAR(16)   NOT NULL COMMENT '部门简称',
      sla_days          INT           NOT NULL DEFAULT 10 COMMENT '承诺办结时限（工作日）',
      workload_weight   DECIMAL(3,2)  NOT NULL DEFAULT 1.00 COMMENT '工单量生成权重',
      satisfaction_bias DECIMAL(3,2)  NOT NULL DEFAULT 0.00 COMMENT '满意度偏差（生成器用）',
      PRIMARY KEY (dept_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门字典'""",

    # 2. 事项字典
    """CREATE TABLE IF NOT EXISTS dim_item (
      item_code     VARCHAR(8)   NOT NULL COMMENT '事项编码（主键）',
      item_name     VARCHAR(48)  NOT NULL COMMENT '事项名称',
      dept_code     VARCHAR(8)   NOT NULL COMMENT '归属部门',
      avg_materials INT          NOT NULL DEFAULT 3 COMMENT '平均材料数',
      complexity    DECIMAL(3,2) NOT NULL DEFAULT 1.00 COMMENT '复杂度系数',
      PRIMARY KEY (item_code),
      KEY idx_item_dept (dept_code),
      CONSTRAINT fk_item_dept FOREIGN KEY (dept_code) REFERENCES dim_department (dept_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事项字典'""",

    # 3. 工单主表
    """CREATE TABLE IF NOT EXISTS fact_order (
      order_id        VARCHAR(20)   NOT NULL COMMENT '工单号',
      citizen_name    VARCHAR(20)   NOT NULL COMMENT '申请人姓名',
      citizen_masked  VARCHAR(20)   NOT NULL COMMENT '脱敏证件号',
      item_code       VARCHAR(8)    NOT NULL COMMENT '事项编码',
      dept_code       VARCHAR(8)    NOT NULL COMMENT '责任部门',
      channel         VARCHAR(8)    NOT NULL COMMENT 'online/window/self',
      receive_time    DATETIME      NOT NULL COMMENT '受理时间',
      finish_time     DATETIME      NULL     COMMENT '办结时间',
      status          VARCHAR(10)   NOT NULL COMMENT 'done/doing/timeout/abandoned/returned',
      is_appointment  TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否预约',
      materials_count INT           NULL     COMMENT '材料数',
      handler         VARCHAR(20)   NOT NULL COMMENT '经办人',
      duration_days   DECIMAL(6,2)  NULL     COMMENT '办结时长（自然日）',
      is_timeout      TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否超时件',
      dq_flag         VARCHAR(20)   NULL     COMMENT '数据质量标记',
      PRIMARY KEY (order_id),
      KEY idx_order_dept (dept_code),
      KEY idx_order_status (status),
      KEY idx_order_receive (receive_time),
      KEY idx_order_dept_status (dept_code, status),
      CONSTRAINT fk_order_item FOREIGN KEY (item_code) REFERENCES dim_item (item_code),
      CONSTRAINT fk_order_dept FOREIGN KEY (dept_code) REFERENCES dim_department (dept_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='办事工单（清洗后）'""",

    # 4. 审批记录
    """CREATE TABLE IF NOT EXISTS fact_approval (
      approval_id  VARCHAR(24)  NOT NULL COMMENT '审批单号',
      order_id     VARCHAR(20)  NOT NULL COMMENT '所属工单',
      approver     VARCHAR(20)  NOT NULL COMMENT '审批人',
      step         VARCHAR(12)  NOT NULL COMMENT 'accept/review1/review2/finish',
      result       VARCHAR(8)   NOT NULL COMMENT 'pass/return',
      approve_time DATETIME     NOT NULL COMMENT '审批时间',
      PRIMARY KEY (approval_id),
      KEY idx_appr_order (order_id),
      CONSTRAINT fk_appr_order FOREIGN KEY (order_id) REFERENCES fact_order (order_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审批记录'""",

    # 5. 咨询记录
    """CREATE TABLE IF NOT EXISTS fact_consult (
      consult_id   VARCHAR(20)  NOT NULL COMMENT '咨询单号',
      channel      VARCHAR(10)  NOT NULL COMMENT 'hotline/online/window',
      topic        VARCHAR(20)  NOT NULL COMMENT 'policy/process/material/progress',
      is_resolved  TINYINT(1)   NOT NULL DEFAULT 1,
      satisfaction TINYINT      NULL     COMMENT '1-5',
      consult_time DATETIME     NOT NULL COMMENT '咨询时间',
      PRIMARY KEY (consult_id),
      KEY idx_consult_time (consult_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='咨询记录'""",

    # 6. 投诉记录
    """CREATE TABLE IF NOT EXISTS fact_complaint (
      complaint_id   VARCHAR(20)   NOT NULL COMMENT '投诉单号',
      type           VARCHAR(12)   NOT NULL COMMENT 'efficiency/attitude/process/other',
      dept_code      VARCHAR(8)    NOT NULL COMMENT '被投诉部门',
      status         VARCHAR(10)   NOT NULL COMMENT 'done/doing',
      handle_days    DECIMAL(5,1)  NULL     COMMENT '处理天数',
      satisfaction   TINYINT       NULL     COMMENT '1-5',
      complaint_time DATETIME     NOT NULL COMMENT '投诉时间',
      PRIMARY KEY (complaint_id),
      KEY idx_comp_dept (dept_code),
      KEY idx_comp_time (complaint_time),
      CONSTRAINT fk_comp_dept FOREIGN KEY (dept_code) REFERENCES dim_department (dept_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='投诉记录'""",
]

# ========== 初始数据：10 个部门 ==========

DEPTS = [
    ("HR", "人力资源和社会保障局", "人社局",   10, 1.20,  0.10),
    ("SB", "社会保险基金管理中心",  "社保中心", 5,   2.50, -0.20),
    ("YL", "医疗保障局",           "医保局",   15,  1.80, -0.30),
    ("GA", "公安局政务窗口",        "公安窗口", 12,  1.50,  0.00),
    ("SC", "市场监督管理局",        "市场监管", 10,  1.00,  0.10),
    ("SW", "税务局",              "税务局",   7,   0.90,  0.20),
    ("JW", "住房和城乡建设局",      "住建局",   20,  0.50, -0.10),
    ("BD", "不动产登记中心",        "不动产",   15,  2.00, -0.50),
    ("GJ", "住房公积金管理中心",    "公积金",   8,   0.80,  0.00),
    ("WS", "卫生健康委员会",        "卫健委",   10,  0.40,  0.00),
]

# ========== 初始数据：20 个办事事项 ==========

ITEMS = [
    ("SB01", "社保参保登记",     "SB", 4, 1.00),
    ("SB02", "社保缴费证明",     "SB", 2, 0.40),
    ("SB03", "养老资格认证",     "SB", 1, 0.30),
    ("YL01", "医保报销",         "YL", 5, 1.30),
    ("YL02", "生育登记",         "YL", 3, 0.70),
    ("YL03", "异地就医备案",     "YL", 3, 0.90),
    ("HR01", "失业登记",         "HR", 2, 0.60),
    ("HR02", "工伤认定",         "HR", 6, 1.60),
    ("GA01", "户籍迁移",         "GA", 5, 1.20),
    ("GA02", "居住证办理",       "GA", 3, 0.80),
    ("SC01", "营业执照设立",     "SC", 4, 1.10),
    ("SC02", "变更登记",         "SC", 2, 0.60),
    ("SW01", "税务申报",         "SW", 2, 0.70),
    ("SW02", "发票代开",         "SW", 1, 0.30),
    ("JW01", "建设工程竣工验收", "JW", 8, 2.00),
    ("GJ01", "公积金提取",       "GJ", 3, 0.80),
    ("GJ02", "公积金贷款",       "GJ", 6, 1.80),
    ("BD01", "不动产登记",       "BD", 7, 1.90),
    ("BD02", "抵押注销",         "BD", 3, 0.90),
    ("WS01", "生育服务证",       "WS", 2, 0.50),
]


def init_schema():
    """建库 + 建表 + 写入初始维度数据（幂等，可重复跑）"""
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 建库
    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} "
        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    conn.select_db(DB_CONFIG["database"])

    # 建表
    for sql in DDL:
        cur.execute(sql)

    # 写入部门和事项
    cur.executemany(
        "INSERT IGNORE INTO dim_department "
        "(dept_code, dept_name, dept_short, sla_days, workload_weight, satisfaction_bias) "
        "VALUES (%s,%s,%s,%s,%s,%s)", DEPTS)
    cur.executemany(
        "INSERT IGNORE INTO dim_item "
        "(item_code, item_name, dept_code, avg_materials, complexity) "
        "VALUES (%s,%s,%s,%s,%s)", ITEMS)

    conn.commit()
    cur.close()
    conn.close()
