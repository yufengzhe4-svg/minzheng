# -*- coding: utf-8 -*-
"""
一键灌数入口：生成 → 清洗 → 写库
用法：python run_generate.py
"""
from app.core import generator, cleaner


def main():
    print("== 1. Faker 生成原始数据 ==")
    data = generator.generate_all()

    print("== 2. 清洗 ==")
    data = cleaner.clean_all(data)

    print("== 3. 写入 MySQL ==")
    cleaner.save_to_db(data)

    print("全部完成。")


if __name__ == "__main__":
    main()
