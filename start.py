# -*- coding: utf-8 -*-
"""一键启动：开后端 + 自动打开浏览器"""
import subprocess, webbrowser, time, os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("[1/2] 启动后端 FastAPI (端口 8000)...")
# 用和系统一致的 python 解释器
python = sys.executable
subprocess.Popen([python, "-m", "uvicorn", "app.main:app", "--port", "8000"])

print("[2/2] 等待 4 秒后打开前端...")
time.sleep(4)
webbrowser.open(os.path.abspath("web/index.html"))

print("完成！后端在后台运行，关闭此窗口不会停后端。")
print("要停止后端：关掉那个新弹出的 uvicorn 黑窗口，或任务管理器结束 python 进程。")
input("按回车键退出此启动器...")
