# -*- coding: utf-8 -*-
"""
Agent 编排：规则引擎（快路径）→ LangChain Agent（工具调用）→ 兜底。
LangChain 1.x 新 API：create_agent。
"""
from langchain.agents import create_agent

from app.core import rules, llm as llm_module, tools as tool_module

_agent = None  # 懒加载


def _get_agent():
    global _agent
    if _agent is not None:
        return _agent
    chat = llm_module.get_chat_model()
    if chat is None:
        return None
    _agent = create_agent(
        model=chat,
        tools=tool_module.TOOLS,
        system_prompt=(
            "你是政务便民服务平台的智能客服助手。"
            "用户提问时，优先判断是否需要调用工具查询真实数据；"
            "拿到工具返回的数字后，用简洁口语（不超过 100 字）组织回答，"
            "不要编造数字，不要罗列工具名。"
        ),
    )
    return _agent


def answer(user_msg: str, history: list = None):
    msg = (user_msg or "").strip()
    if not msg:
        return {"reply": "请输入您的问题。", "source": "fallback"}

    # 第一层：规则引擎（高频确定性问题，零成本秒回）
    rule_reply = rules.try_answer(msg)
    if rule_reply:
        return {"reply": rule_reply, "source": "rule"}

    # 第二层：LangChain Agent（自主决定调哪个工具，带历史消息）
    try:
        agent = _get_agent()
        if agent is not None:
            # 组装消息：历史 + 当前
            messages = []
            for h in (history or [])[-6:]:
                role = h.get("role", "user")
                content = h.get("content", "")
                if content:
                    messages.append((role, content))
            messages.append(("user", msg))
            result = agent.invoke({"messages": messages})
            reply = result["messages"][-1].content
            return {"reply": reply, "source": "llm"}
    except Exception as e:
        print(f"[agent] 调用失败：{e}")

    # 第三层：兜底
    return {"reply": "抱歉，这个问题我暂时答不上来。您可以换个问法，"
                     "比如「哪个部门超时最多」「投诉满意度怎么样」「总办件量多少」。",
            "source": "fallback"}
