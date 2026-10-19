"""Run the installed TradingAgents skill through the Codex CLI."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

from strategy_config import format_strategy_prompt

DEPTHS = {"快速": "quick", "标准": "standard", "深度": "deep"}


def _error(message: str) -> str:
    return f"## AI分析未完成\n\n{message}\n\n> 未生成模拟结论。请检查运行环境和日志后重试。"


def run_codex_analysis(stock_code: str, depth: str = "标准", enable_debate: bool = True,
                       enable_risk: bool = True, save_history: bool = True,
                       strategy_name: str = "中线趋势") -> str:
    """Execute the native TradingAgents skill and return its Markdown report."""
    stock_code = str(stock_code).strip()
    if not re.fullmatch(r"\d{6}", stock_code):
        return _error("股票代码必须是6位数字。")
    project_root = Path(__file__).resolve().parent
    skill_path = project_root / ".agents" / "skills" / "run-tradingagents-native" / "SKILL.md"
    if not skill_path.is_file():
        return _error(f"未找到技能文件：`{skill_path}`。请先安装 run-tradingagents-native。")
    codex = shutil.which("codex")
    if not codex:
        return _error("当前运行环境没有找到 `codex` 命令。Streamlit Cloud 通常不提供 Codex CLI 及其登录凭据，因此无法直接执行该技能。请将本页面连接到已认证的后端，或在带有 Codex CLI 的运行环境中部署。")
    strategy_prompt = format_strategy_prompt(strategy_name)
    prompt = f"""请使用 run-tradingagents-native 技能，分析A股股票 {stock_code}，生成中文、结构化的投研报告。
分析深度：{depth}（{DEPTHS.get(depth, 'standard')}）。
启用牛熊辩论：{'是' if enable_debate else '否'}。
启用风险评估：{'是' if enable_risk else '否'}。
保存历史记录：{'是' if save_history else '否'}。
请严格参考以下策略模型，但不要把规则信号当作确定性预测：
{strategy_prompt}
报告必须标注数据来源、数据时间、关键不确定性，并明确说明不构成投资建议。"""
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
