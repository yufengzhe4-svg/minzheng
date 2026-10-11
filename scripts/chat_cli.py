# -*- coding: utf-8 -*-
"""
命令行对话体验脚本：python chat_cli.py
直接调 agent.answer，不经过 HTTP，按 Ctrl+C 或输入 exit 退出。
"""
from app.core.agent import answer

SOURCE_TAG = {"rule": "规则", "llm": "大模型", "fallback": "兜底"}

print("=" * 50)
print("  政务便民服务平台 · 智能客服（命令行体验）")
print("  输入问题回车；输入 exit 退出；Ctrl+C 也可")
print("=" * 50)

while True:
    try:
        q = input("\n你：").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n再见。")
        break
    if not q:
        continue
    if q.lower() in ("exit", "quit", "退出"):
        print("再见。")
        break
    r = answer(q)
    print(f"客服 [{SOURCE_TAG.get(r['source'], r['source'])}]：{r['reply']}")
