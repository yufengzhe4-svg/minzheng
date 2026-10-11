# 政务民生大数据统计与便民服务平台

数据科学与大数据技术专业 · 团队实训项目

## 技术栈

- **数据生成**：Faker + NumPy（模拟政务大厅 90 天办件数据）
- **数据清洗**：Pandas（缺失/废弃/重复/异常四步清洗）
- **数据库**：MySQL 8（6 表星型模型）
- **后端**：FastAPI + Uvicorn（11 个 REST 接口）
- **AI 智能客服**：规则引擎 → LangChain + 智谱 GLM-4-Flash → 兜底（三层降级）
- **前端**：原生 HTML + ECharts（单页驾驶舱）

## 项目结构

```
minzheng-service-platform/
├── app/                    # 后端主程序
│   ├── config.py           # 数据库连接 + 生成规模配置
│   ├── main.py             # FastAPI 入口
│   ├── api/routes.py        # 11 个 REST 接口
│   └── core/
│       ├── generator.py    # Faker 造数（含节假日权重）
│       ├── cleaner.py       # 四步清洗 + 写库
│       ├── stats.py         # 9 个统计指标函数
│       ├── rules.py         # 规则引擎（8 业务 + 5 问候）
│       ├── llm.py           # LangChain ChatOpenAI（指向智谱）
│       ├── tools.py         # 8 个 @tool 工具
│       ├── agent.py         # 三层降级编排 + 多轮记忆
│       └── visualize/pillower.py  # Matplotlib 8 张图表
├── data/
│   ├── raw/                 # 原始脏数据（CSV）
│   └── clean/               # 清洗后数据（CSV）
├── docs/
│   ├── er_diagram.html      # ER 图
│   └── 数据库设计.md         # 建表 SQL + 字段说明
├── output/charts/           # Matplotlib 产出的 PNG 图表
├── scripts/                 # 工具脚本（建库/审计/测试等）
├── web/index.html           # 前端单页驾驶舱
├── run_generate.py          # 一键：造数 → 清洗 → 灌库
├── run_clean.py             # 单独跑清洗（不重新造数）
└── requirements.txt
```

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 设智谱 API key（Windows）
setx ZHIPU_API_KEY "你的key"

# 3. 建库灌数据
python scripts/init_db.py
python run_generate.py

# 4. 启动后端
python -m uvicorn app.main:app --port 8000

# 5. 打开前端
# 浏览器直接打开 web/index.html
```

## 核心数据规模

- 近 90 天工单：27,312 件（原始 30,808 → 清洗后 27,312）
- 办结率 93.7% · 超时率 13.8% · 平均满意度 2.64 分
- 10 个部门 / 20 个事项 / 4 类投诉 / 4 类咨询主题

## AI 智能客服

三层降级策略：
1. **规则引擎**（秒回）：办社保、投诉流程、营业时间、部门排行等高频问题
2. **LangChain Agent**（带工具调用）：自动查询数据库回答数据分析类问题
3. **兜底**：友好提示换问法

支持多轮对话上下文（最近 3 轮）。
