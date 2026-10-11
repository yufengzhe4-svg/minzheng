# -*- coding: utf-8 -*-
"""
大模型封装（LangChain 版）：智谱 GLM-4-Flash，通过 OpenAI 兼容接口接入。
API Key 从环境变量 ZHIPU_API_KEY 读取。
"""
import os
from langchain_openai import ChatOpenAI

MODEL = "glm-4-flash"
BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


def get_chat_model(temperature: float = 0.3):
    """返回 LangChain ChatModel 实例；未配置 key 返回 None。"""
    key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not key:
        return None
    return ChatOpenAI(
        model=MODEL,
        api_key=key,
        base_url=BASE_URL,
        temperature=temperature,
        max_tokens=300,
    )
