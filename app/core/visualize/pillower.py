# -*- coding: utf-8 -*-
"""
pillower.py —— 基于 stats.py 的指标数据，用 Matplotlib 出 8 张政务统计图表。
产出 PNG 到 output/charts/，供 Web 页面嵌入与课设报告插图使用。

配色（政务藏青 + 红金强调）：
  NAVY  #0d2038 主色 / BLUE #1f5fa8 次色
  RED   #b02a2a 超时/告警 / GOLD #b08d2e 强调
  GRAY  #9fb2c8 辅助
"""
import os
import warnings

import matplotlib
matplotlib.use("Agg")                      # 无窗口后端，服务器/脚本直接出图
import matplotlib.pyplot as plt

from app.core import stats

warnings.filterwarnings("ignore")

# 中文字体与负号
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

NAVY, BLUE, RED, GOLD, GRAY = "#0d2038", "#1f5fa8", "#b02a2a", "#b08d2e", "#9fb2c8"
OUT = os.path.join("output", "charts")
os.makedirs(OUT, exist_ok=True)


def _save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [ok] {name}")
    return path


# 1. 部门工单量排行（横向条形）
def chart_dept_volume():
    rows = stats.get_dept_ranking()
    rows = sorted(rows, key=lambda r: r["total"])          # 升序，横向条最大在最上
    fig, ax = plt.subplots(figsize=(9, 5.2))
    bars = ax.barh([r["dept_short"] for r in rows],
                   [r["total"] for r in rows],
                   color=NAVY, height=0.62)
    bars[-1].set_color(RED)                                # 第一名标红
    for b, r in zip(bars, rows):
        ax.text(b.get_width() + 60, b.get_y() + b.get_height()/2,
                f'{r["total"]}', va="center", fontsize=9, color="#333")
    ax.set_title("各部门工单办理量排行", fontsize=14, fontweight="bold", color=NAVY, pad=12)
    ax.set_xlabel("工单数（件）")
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, "chart01_dept_volume.png")


# 2. 部门超时率对比（横向条形，按超时率着色）
def chart_dept_timeout():
    rows = sorted(stats.get_dept_ranking(), key=lambda r: r["timeout_rate"])
    colors = [RED if r["timeout_rate"] >= 35 else GOLD if r["timeout_rate"] >= 25 else BLUE
              for r in rows]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    bars = ax.barh([r["dept_short"] for r in rows],
                   [r["timeout_rate"] for r in rows],
                   color=colors, height=0.62)
    for b, r in zip(bars, rows):
        ax.text(b.get_width() + 0.5, b.get_y() + b.get_height()/2,
                f'{r["timeout_rate"]}%', va="center", fontsize=9)
    ax.set_title("各部门超时办结率（红≥35% / 金25-35% / 蓝<25%）",
                 fontsize=13, fontweight="bold", color=NAVY, pad=12)
    ax.set_xlabel("超时率（%）")
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, "chart02_dept_timeout.png")


# 3. 90 天日工单量趋势（面积折线 + 7 日均线）
def chart_daily_trend():
    rows = stats.get_daily_trend()
    dates = [r["dt"][5:] for r in rows]                  # MM-DD
    orders = [r["orders"] for r in rows]
    ma7 = [sum(orders[max(0, i-6):i+1]) / min(i+1, 7) for i in range(len(orders))]
    # 区分工作日与周末：工作日深蓝线，周末灰点，让"低谷=周末"成为可读规律而非锯齿
    import datetime
    weekend = [datetime.datetime.strptime("2026-" + d, "%Y-%m-%d").weekday() >= 5
               for d in dates]
    workday_x = [i for i, w in enumerate(weekend) if not w]
    weekend_x = [i for i, w in enumerate(weekend) if w]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.fill_between(workday_x, [orders[i] for i in workday_x], color=BLUE, alpha=0.15)
    ax.plot(workday_x, [orders[i] for i in workday_x], color=BLUE, lw=1.4, label="工作日工单量")
    ax.scatter(weekend_x, [orders[i] for i in weekend_x], color=GRAY, s=22,
               zorder=5, label="周末（低谷）")
    ax.plot(range(len(ma7)), ma7, color=RED, lw=2, label="7 日均线")
    ax.set_title("近 90 天每日工单受理量趋势", fontsize=14, fontweight="bold", color=NAVY, pad=12)
    ax.set_ylabel("工单数（件）")
    ticks = list(range(0, len(dates), 7))
    ax.set_xticks(ticks)
    ax.set_xticklabels([dates[i] for i in ticks], rotation=45, fontsize=8)
    ax.legend(loc="upper right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, "chart03_daily_trend.png")


# 4. 办事渠道分布（环形图）
def chart_channel_pie():
    rows = stats.get_channel_dist()
    labels = {"online": "线上网办", "window": "窗口办理", "self": "自助终端"}
    fig, ax = plt.subplots(figsize=(6.5, 5))
    wedges, texts, autotexts = ax.pie(
        [r["cnt"] for r in rows],
        labels=[labels.get(r["channel"], r["channel"]) for r in rows],
        autopct="%1.1f%%", pctdistance=0.79, startangle=90, counterclock=False,
        colors=[NAVY, BLUE, GOLD],
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
        textprops=dict(fontsize=11))
    for at in autotexts:
        at.set_color("white"); at.set_fontweight("bold")
    ax.set_title("办事渠道分布", fontsize=14, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "chart04_channel_pie.png")


# 5. TOP10 事项办理量
def chart_item_top10():
    rows = sorted(stats.get_item_topn(10), key=lambda r: r["total"])
    fig, ax = plt.subplots(figsize=(9, 5.6))
    bars = ax.barh([r["item_name"] for r in rows],
                   [r["total"] for r in rows], color=GRAY, height=0.6)
    for b, r in zip(bars, rows):
        ax.text(b.get_width() + 30, b.get_y() + b.get_height()/2,
                f'{r["total"]}（超时 {r["timeout_rate"]}%）',
                va="center", fontsize=8.5, color="#444")
    ax.set_title("TOP 10 高频事项（附超时率）", fontsize=14, fontweight="bold", color=NAVY, pad=12)
    ax.set_xlabel("工单数（件）")
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, "chart05_item_top10.png")


# 6. 咨询主题分布（柱状 + 解决率折线）
def chart_consult_topic():
    rows = stats.get_consult_analysis()["by_topic"]
    zh = {"policy": "政策咨询", "process": "办理流程", "material": "材料清单", "progress": "进度查询"}
    labels = [zh.get(r["topic"], r["topic"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(labels, [r["cnt"] for r in rows], color=NAVY, width=0.55)
    for b, r in zip(bars, rows):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+60,
                str(r["cnt"]), ha="center", fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(labels, [r["resolved_rate"] for r in rows], color=RED,
             marker="o", lw=2, label="解决率%")
    for i, r in enumerate(rows):
        ax2.text(i, r["resolved_rate"]+1.5, f'{r["resolved_rate"]}%',
                 ha="center", fontsize=9, color=RED)
    ax2.set_ylim(0, 105); ax2.set_ylabel("解决率（%）", color=RED)
    ax.set_title("咨询主题分布与解决率", fontsize=14, fontweight="bold", color=NAVY, pad=12)
    ax.set_ylabel("咨询量（条）")
    ax.spines[["top"]].set_visible(False); ax2.spines[["top"]].set_visible(False)
    return _save(fig, "chart06_consult_topic.png")


# 7. 投诉类型分布（环形图）
def chart_complaint_type():
    rows = stats.get_complaint_analysis()["by_type"]
    zh = {"efficiency": "效率慢", "attitude": "服务态度", "process": "流程繁琐", "other": "其他"}
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.pie([r["cnt"] for r in rows],
           labels=[zh.get(r["type"], r["type"]) for r in rows],
           autopct="%1.1f%%", startangle=90, counterclock=False,
           colors=[RED, GOLD, BLUE, GRAY],
           wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
           textprops=dict(fontsize=10))
    ax.set_title("投诉类型分布", fontsize=14, fontweight="bold", color=NAVY, pad=10)
    return _save(fig, "chart07_complaint_type.png")


# 8. 部门满意度气泡图（投诉量 × 满意度，气泡=处理天数）
def chart_dept_satisfaction():
    rows = stats.get_complaint_analysis()["by_dept"]
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    xs = [r["cnt"] for r in rows]
    ys = [r["sat"] for r in rows]
    sizes = [(r["handle_days"] or 3) * 40 for r in rows]
    ax.scatter(xs, ys, s=sizes, c=BLUE, alpha=0.55, edgecolors=NAVY, linewidths=1.2)
    for r in rows:
        off = {"住建局": (6, 10), "卫健委": (16, -14), "税务局": (-50, -12)}.get(
            r["dept_short"], (8, 4))
        ax.annotate(r["dept_short"], (r["cnt"], r["sat"]),
                    textcoords="offset points", xytext=off, fontsize=9.5)
    ax.axhline(3.0, color=RED, ls="--", lw=1, alpha=0.6)
    ax.text(max(xs)*0.98, 3.05, "满意度警戒线 3.0", color=RED, fontsize=8.5, ha="right")
    ax.set_title("各部门投诉量 × 满意度（气泡大小=平均处理天数）",
                 fontsize=13, fontweight="bold", color=NAVY, pad=12)
    ax.set_xlabel("投诉量（件）")
    ax.set_ylabel("投诉满意度（1-5）")
    # 坐标范围按数据自适应，避免最差/最优部门被裁出画面
    ax.set_ylim(min(ys) - 0.15, max(ys) + 0.15)
    ax.set_xlim(min(xs) - 30, max(xs) + 40)
    ax.spines[["top", "right"]].set_visible(False)
    return _save(fig, "chart08_dept_satisfaction.png")


def generate_all():
    print("生成 8 张统计图表 ...")
    paths = [
        chart_dept_volume(),
        chart_dept_timeout(),
        chart_daily_trend(),
        chart_channel_pie(),
        chart_item_top10(),
        chart_consult_topic(),
        chart_complaint_type(),
        chart_dept_satisfaction(),
    ]
    print(f"完成，共 {len(paths)} 张，输出目录：{OUT}/")
    return paths


if __name__ == "__main__":
    generate_all()
