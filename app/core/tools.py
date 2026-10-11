# -*- coding: utf-8 -*-
"""
LangChain 工具集：把 stats.py 的查询能力封装成 @tool。
LLM 通过 docstring 判断何时调用哪个工具。
每个工具返回简洁文本（不要返回大 dict，避免撑爆 context）。
"""
from langchain_core.tools import tool
from app.core import stats


@tool
def query_kpi() -> str:
    """查询平台整体运行指标：总工单量、办结率、平均办结时长、超时率、咨询解决率、投诉满意度。
    当用户问"总体情况""办了多少件""整体效率如何"等概览问题时调用。"""
    k = stats.get_kpi()
    return (f"近90天总工单 {k['total_orders']} 件；"
            f"办结率 {k['done_rate']}%；平均办结 {k['avg_duration_days']} 天；"
            f"超时率 {k['timeout_rate']}%；咨询解决率 {k['consult_resolved_rate']}%；"
            f"投诉满意度 {k['complaint_satisfaction']} 分。")


@tool
def query_dept_ranking() -> str:
    """查询各部门办件量排行。当用户问"哪个部门办得最多""哪些部门忙"时调用。"""
    rows = stats.get_dept_ranking()[:5]
    return "办件量前五：" + "；".join(
        f"{r['dept_short']} {r['total']}件（办结率{r['done_rate']}%）" for r in rows)


@tool
def query_dept_timeout() -> str:
    """查询各部门超时率排行，找出效率最低/最高的部门。
    当用户问"哪个部门慢""效率低""谁在拖延""哪个部门口碑差"时调用。"""
    rows = stats.get_dept_ranking()
    worst = sorted(rows, key=lambda r: -r["timeout_rate"])[:3]
    best = sorted(rows, key=lambda r: r["timeout_rate"])[:1]
    return (f"超时率最高：" + "；".join(f"{r['dept_short']} {r['timeout_rate']}%" for r in worst)
            + f"。效率最好：{best[0]['dept_short']} {best[0]['timeout_rate']}%。")


@tool
def query_channel() -> str:
    """查询办事渠道分布（线上网办/窗口/自助终端占比）。
    当用户问"线上办还是窗口办""怎么办最方便""渠道分布"时调用。"""
    rows = stats.get_channel_dist()
    name = {"online": "线上网办", "window": "窗口办理", "self": "自助终端"}
    return "渠道分布：" + "；".join(f"{name[r['channel']]} {r['pct']}%" for r in rows)


@tool
def query_consult() -> str:
    """查询咨询主题分布与各主题解决率，找出哪个主题咨询最多、哪个最难解决。
    当用户问"大家都在问什么""咨询多不多""什么问题最难答"时调用。"""
    r = stats.get_consult_analysis()
    topic = r["by_topic"]
    most = max(topic, key=lambda x: x["cnt"])
    hardest = min(topic, key=lambda x: x["resolved_rate"])
    name = {"progress": "进度查询", "process": "办理流程", "material": "材料清单", "policy": "政策咨询"}
    return (f"咨询最多：{name.get(most['topic'], most['topic'])} {most['cnt']}条；"
            f"最难解决：{name.get(hardest['topic'], hardest['topic'])} 解决率仅 {hardest['resolved_rate']}%。")


@tool
def query_complaint() -> str:
    """查询投诉分析：投诉量最多且满意度最低的部门。
    当用户问"投诉多不多""满意度怎么样""哪个部门被投诉最多"时调用。"""
    r = stats.get_complaint_analysis()
    by_dept = r["by_dept"]
    worst = sorted(by_dept, key=lambda x: x["sat"])[:2]
    return "满意度最低：" + "；".join(
        f"{d['dept_short']}（{d['sat']}分，投诉{d['cnt']}件）" for d in worst)


@tool
def query_trend() -> str:
    """查询近期办件趋势（最近一周日均量、月末高峰规律）。
    当用户问"最近忙不忙""趋势怎样""什么时候人少"时调用。"""
    rows = stats.get_daily_trend()
    recent = rows[-7:]
    avg = sum(r["orders"] for r in recent) / 7
    return f"最近一周日均受理 {avg:.0f} 件；月末（25日后）是办件高峰，建议错峰。"


@tool
def query_item_info(item_name: str) -> str:
    """根据事项名称关键词查询该事项的办理详情：承诺时限、需带材料数、超时率。
    当用户问"XX怎么办""办XX要多久""办XX要带什么材料"时调用。
    item_name 用事项关键词，如"社保""不动产""医保"。"""
    items = stats.get_item_topn(20)
    hits = [it for it in items if item_name in it["item_name"]]
    if not hits:
        return f"未找到包含「{item_name}」的高频事项，建议换个关键词。"
    return "；".join(
        f"{it['item_name']}：超时率{it['timeout_rate']}%，近90天办{it['total']}件"
        for it in hits[:3])


TOOLS = [query_kpi, query_dept_ranking, query_dept_timeout, query_channel,
         query_consult, query_complaint, query_trend, query_item_info]
