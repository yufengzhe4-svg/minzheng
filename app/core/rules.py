# -*- coding: utf-8 -*-
"""
规则引擎：识别政务问答意图，直接查 stats 生成自然语言回答。
命中即返回（确定性、零成本）；未命中交给 LLM 层。
"""
from app.core import stats


# 意图规则表：(关键词列表, 处理函数)
RULES = []


# ===== 问候/身份类规则（最高优先级，先于业务规则匹配）=====
GREETINGS = [
    (["你是谁", "你叫什么", "自我介绍", "介绍一下", "你是啥", "你能干嘛"],
     "我是政务便民服务平台的智能客服「小政」。我能帮你查办件量、各部门超时率、投诉满意度、"
     "咨询趋势这些平台运行数据，也能解答办事材料、流程类问题。您想了解什么？"),
    (["你好", "您好", "hi", "hello", "在吗", "在不在", "早上好", "下午好", "晚上好"],
     "您好，我是政务便民服务平台智能客服「小政」。"
     "可以问我办件量、哪个部门效率高、怎么办社保这类问题。"),
    (["谢谢", "感谢", "辛苦了", "thx", "thank"],
     "不客气，为您服务是应该的。还有别的问题随时问。"),
    (["再见", "拜拜", "走了", "bye"],
     "再见，祝您办事顺利！"),
    (["天气", "气温", "新闻", "股票", "八卦"],
     "抱歉，我是政务便民客服，不负责天气/新闻这类信息。"
     "您可以问我办件量、部门效率、办事流程这些。"),
    # 营业时间（正面回答）
    (["营业时间", "几点上班", "几点下班", "大厅时间", "工作时间"],
     "政务服务大厅工作时间：周一至周五 9:00-12:00、13:00-17:00；"
     "周六 9:00-12:00（仅值班）；法定节假日休息。线上网办渠道 24 小时可用。"),
    # 大厅地址
    (["地址", "在哪", "位置", "怎么走", "大厅在哪"],
     "政务服务大厅位于市民中心一层，地铁 2 号线「政务中心」站 B 口出即到。"
     "停车请至市民中心地下车库，凭办事取号小票可免费停车 2 小时。"),
    # 投诉行动指引（优先于"投诉满意度"数据分析）
    (["我要投诉", "怎么投诉", "如何投诉", "投诉渠道", "我想投诉", "维权", "举报"],
     "您可以通过三个渠道投诉：① 拨打 12345 政务服务热线；② 在本平台「在线投诉」入口提交，"
     "我们会在 3 个工作日内反馈；③ 到办事大厅窗口填写投诉单。"
     "投诉时请提供工单号或办事事项名称，便于快速核实。"),
]


def rule(*keywords):
    """装饰器：把意图函数注册到规则表"""
    def wrapper(fn):
        RULES.append((keywords, fn))
        return fn
    return wrapper


@rule("社保", "材料", "带什么", "带哪些", "怎么办", "怎么办社保")
def _social_security(msg):
    return ("办社保（参保登记/缴费证明）需携带：① 本人身份证原件；② 户口本（本地户籍）"
            "或居住证（外地户籍）；③ 近期 1 寸白底照片 2 张；④ 银行卡（用于代扣缴费）。"
            "线上可通过「陕事通」APP 或政务网办大厅提交，无需到现场。")


@rule("总", "概况", "整体", "概览", "多少件", "总体")
def _overview(msg):
    k = stats.get_kpi()
    return (f"近 90 天平台共受理工单 {k['total_orders']} 件，"
            f"办结率 {k['done_rate']}%，平均办结时长 {k['avg_duration_days']} 天，"
            f"超时率 {k['timeout_rate']}%。"
            f"咨询解决率 {k['consult_resolved_rate']}%，"
            f"投诉满意度 {k['complaint_satisfaction']} 分。")


@rule("超时", "超期", "慢", "效率低", "拖延")
def _timeout(msg):
    rows = stats.get_dept_ranking()
    worst = sorted(rows, key=lambda r: -r["timeout_rate"])[:3]
    top = sorted(rows, key=lambda r: r["timeout_rate"])[:1]
    parts = "、".join([f"{r['dept_short']}（超时率 {r['timeout_rate']}%）" for r in worst])
    return (f"超时率最高的三个部门：{parts}。"
            f"做得最好的是 {top[0]['dept_short']}（{top[0]['timeout_rate']}%）。"
            f"整体超时率 {stats.get_kpi()['timeout_rate']}%。")


@rule("投诉", "满意度", "评价", "差评")
def _complaint(msg):
    r = stats.get_complaint_analysis()
    by_dept = r["by_dept"]
    worst = sorted(by_dept, key=lambda x: x["sat"])[:2]
    best = sorted(by_dept, key=lambda x: -x["sat"])[:1]
    parts = "、".join([f"{d['dept_short']}（满意度 {d['sat']} 分）" for d in worst])
    return (f"投诉最多且满意度最低的是 {parts}。"
            f"口碑最好的是 {best[0]['dept_short']}（{best[0]['sat']} 分）。"
            f"全平台投诉满意度均值 {stats.get_kpi()['complaint_satisfaction']} 分。")


@rule("渠道", "线上", "窗口", "自助", "网办")
def _channel(msg):
    rows = stats.get_channel_dist()
    name_map = {"online": "线上网办", "window": "窗口办理", "self": "自助终端"}
    parts = "、".join([f"{name_map.get(r['channel'], r['channel'])} {r['pct']}%" for r in rows])
    return f"办事渠道分布：{parts}。线上网办已接近一半，是主要办理方式。"


@rule("咨询", "问答", "电话")
def _consult(msg):
    r = stats.get_consult_analysis()
    topic = r["by_topic"]
    most = max(topic, key=lambda x: x["cnt"])
    least = min(topic, key=lambda x: x["resolved_rate"])
    return (f"咨询量最高的主题是「{most['topic']}」（{most['cnt']} 条）。"
            f"解决率最低的是「{least['topic']}」（{least['resolved_rate']}%），"
            f"这部分是智能问答最该补强的方向。")


@rule("排行", "排名", "最多", "最高", "哪些部门")
def _ranking(msg):
    rows = stats.get_dept_ranking()[:3]
    parts = "、".join([f"{r['dept_short']}（{r['total']} 件）" for r in rows])
    return f"办件量前三的部门：{parts}。"


@rule("趋势", "增长", "变化", "最近")
def _trend(msg):
    rows = stats.get_daily_trend()
    recent = rows[-7:]
    avg = sum(r["orders"] for r in recent) / 7
    return f"最近一周日均受理 {avg:.0f} 件。月末（25 日后）受理量明显高于平日，是办件高峰。"


@rule("质量", "异常", "脏", "清洗")
def _quality(msg):
    k = stats.get_kpi()
    return (f"原始数据中异常件 {k['abnormal_orders']} 件（占 {k['abnormal_orders']*100/k['total_orders']:.1f}%），"
            f"已被 dq_flag 标记并从率值类统计中剔除；"
            f"有效工单 {k['valid_orders']} 件。")


def try_answer(msg: str):
    """先查问候/身份规则，再遍历业务规则表；命中返回自然语言答案；未命中返回 None"""
    for keywords, reply in GREETINGS:
        if any(k in msg.lower() for k in keywords):
            return reply
    for keywords, fn in RULES:
        if any(k in msg for k in keywords):
            return fn(msg)
    return None
