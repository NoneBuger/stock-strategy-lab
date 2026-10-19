"""Run the installed TradingAgents skill through the Codex CLI."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_config import format_strategy_prompt

DEPTHS = {"快速": "quick", "标准": "standard", "深度": "deep"}


def _error(message: str) -> str:
    return f"## AI分析未完成\n\n{message}\n\n> 未生成模拟结论。请检查运行环境和日志后重试。"


def fetch_recent_data_markdown(stock_code: str, rows: int = 50) -> str:
    """Fetch recent AkShare daily bars and serialize them as a Markdown table."""
    try:
        import akshare as ak

        end_date = date.today()
        data = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=(end_date - timedelta(days=180)).strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="",
        )
    except Exception as exc:
        raise RuntimeError(f"AkShare 获取近50日日线失败：{exc}") from exc
    if data.empty:
        raise RuntimeError(f"AkShare 未返回股票 {stock_code} 的日线数据")

    columns = [
        column for column in ["日期", "开盘", "最高", "最低", "收盘", "成交量", "涨跌幅"]
        if column in data.columns
    ]
    data = data[columns].tail(rows).copy()
    data["日期"] = data["日期"].astype(str)
    for column in columns:
        if column != "日期":
            data[column] = pd.to_numeric(data[column], errors="coerce").round(4)
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join("" if pd.isna(value) else str(value) for value in row) + " |"
        for row in data.itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider, *body])


def run_codex_analysis(stock_code: str, depth: str = "标准", enable_debate: bool = True,
                       enable_risk: bool = True, save_history: bool = True,
                       strategy_name: str = "中线趋势",
                       strategy_overrides: dict[str, Any] | None = None) -> str:
    """Execute the native TradingAgents skill and return its Markdown report."""
    stock_code = str(stock_code).strip()
    if not re.fullmatch(r"\d{6}", stock_code):
        return _error("股票代码必须是6位数字。")
    project_root = Path(__file__).resolve().parent
    skill_path = project_root / ".agents" / "skills" / "run-tradingagents-native" / "SKILL.md"
    if not skill_path.is_file():
        return _error(f"未找到技能文件：`{skill_path}`。请先安装 run-tradingagents-native。")
    try:
        recent_data_markdown = fetch_recent_data_markdown(stock_code)
    except RuntimeError as exc:
        return _error(str(exc))
    codex = shutil.which("codex")
    if not codex:
        return _error("当前运行环境没有找到 `codex` 命令。Streamlit Cloud 通常不提供 Codex CLI 及其登录凭据，因此无法直接执行该技能。请将本页面连接到已认证的后端，或在带有 Codex CLI 的运行环境中部署。")
    strategy_prompt = format_strategy_prompt(strategy_name, strategy_overrides)
    prompt = f"""请使用 run-tradingagents-native 技能，分析A股股票 {stock_code}，生成中文、结构化的投研报告。
分析深度：{depth}（{DEPTHS.get(depth, 'standard')}）。
启用牛熊辩论：{'是' if enable_debate else '否'}。
启用风险评估：{'是' if enable_risk else '否'}。
保存历史记录：{'是' if save_history else '否'}。
请严格参考以下策略模型，但不要把规则信号当作确定性预测：
{strategy_prompt}
报告必须标注数据来源、数据时间、关键不确定性，并明确说明不构成投资建议。"""
    prompt += f"""

以下是 AkShare 获取的 {stock_code} 最近50个交易日日线数据。你必须逐项对照策略规则，明确写出每条规则“满足/不满足/数据不足”，并给出明确结论：买入候选、持有观察、观望或卖出/规避。禁止只写“再等等”“视情况而定”等无条件、无依据的含糊结论。

### AkShare 最近50日日线数据
{recent_data_markdown}
"""
    try:
        result = subprocess.run([codex, "exec", "-C", str(project_root),
                                 f"先完整读取并遵循技能文件 {skill_path}，然后执行以下请求：\n{prompt}"],
                                cwd=project_root, env=os.environ.copy(), capture_output=True,
                                text=True, timeout=600, check=False)
    except subprocess.TimeoutExpired:
        return _error("Codex 分析超过10分钟仍未完成，已安全终止。")
    except OSError as exc:
        return _error(f"启动 Codex CLI 失败：`{exc}`")
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        return _error(f"Codex CLI 返回错误（退出码 {result.returncode}）：\n\n```text\n{output}\n```")
    return output or _error("Codex CLI 未返回报告内容。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TradingAgents stock analysis")
    parser.add_argument("stock_code")
    parser.add_argument("depth", nargs="?", default="标准", choices=tuple(DEPTHS))
    parser.add_argument("--no-debate", action="store_true")
    parser.add_argument("--no-risk", action="store_true")
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()
    print(run_codex_analysis(args.stock_code, args.depth, not args.no_debate, not args.no_risk, not args.no_history))
