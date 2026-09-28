"""
CodeMate AI IDE - 现代智能代码研发与审查工作台
架构与交互规范：
- 总体架构为形如现代 AI IDE (Cursor / VS Code + Copilot) 的双栏布局
- 右侧（占约 68% 宽幅）为主体代码工作区 (IDE Code Workspace)：
  - 文件切换与装载工具栏 (支持 .py 文件上传、Ctrl+V 快速粘贴、预置样例一键切换)
  - 核心 IDE 选项卡：当前代码编辑 (Editor)、修改前后对比 (Diff Viewer)、沙箱终端 (Terminal)、缺陷诊断 (Problems)
  - 具备一键“采纳 AI 修改 (Accept)”与“还原基准 (Revert)”
- 左侧（占约 32% 宽幅）为 AI Agent 伴生助手栏 (Copilot Panel)：
  - 顶部上下文文件指示器
  - 消息历史流、AI 思考与 LangChain 工具链调用折叠盒 (Thinking...)
  - 底部贴底对话框，支持 /review, /refactor, /test, /explain 斜杠快捷菜单与自然语言交互
"""

import sys
import os
import difflib
import html
from pathlib import Path
from typing import Dict, Any, List, Optional
import streamlit as st

# 导入核心后端与智能体引擎
from code_analyzer.core.config import Config
from code_analyzer.query.pipeline import CodePipeline
from code_analyzer.schemas.code_types import RiskSeverity


DEFAULT_REFACTORED_SHOPPING_CART = '''"""
重构优化版本：电商购物车与结算模块 (Refactored ShoppingCart)
已应用设计模式并消除所有已识别的缺陷与代码坏味道：
1. 策略模式 (Strategy Pattern) 解耦折扣计算，消除硬编码 if-elif
2. 上下文管理器 (Context Manager `with`) 确保日志文件句柄安全释放
3. 边界安全防御：判空保护，杜绝 ZeroDivisionError 与 ValueError
4. 异常精细化：剔除裸 except，精准捕获业务异常
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class DiscountStrategy(ABC):
    """折扣策略抽象基类 (Strategy Pattern)"""
    @abstractmethod
    def calculate_discount(self, total: float, items: List[Dict]) -> float:
        pass


class VIPCouponStrategy(DiscountStrategy):
    """VIP 会员九折策略"""
    def calculate_discount(self, total: float, items: List[Dict]) -> float:
        return total * 0.1


class MinusCouponStrategy(DiscountStrategy):
    """满减优惠券策略 (满减 50 元，防御超出总额)"""
    def calculate_discount(self, total: float, items: List[Dict]) -> float:
        discount = 50.0
        return min(discount, total)


class ShareCouponStrategy(DiscountStrategy):
    """分享裂变优惠券策略 (判空防御除零 ZeroDivisionError)"""
    def calculate_discount(self, total: float, items: List[Dict]) -> float:
        if not items:
            return 0.0
        avg_per_item = total / len(items)
        return avg_per_item * 0.5


COUPON_STRATEGIES: Dict[str, DiscountStrategy] = {
    "VIP90": VIPCouponStrategy(),
    "MINUS50": MinusCouponStrategy(),
    "SHARE_DISCOUNT": ShareCouponStrategy(),
}


class ShoppingCart:
    """购物车类：重构后具备完整的安全防御与向后兼容接口"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.items: List[Dict] = []

    def add_item(self, name: str, price: float, qty: int = 1) -> None:
        """添加商品：增加输入边界校验，禁止负数价格与数量"""
        if price < 0 or qty <= 0:
            raise ValueError("商品单价与数量必须为正数")
        self.items.append({"name": name, "price": float(price), "qty": int(qty)})

    def get_total_price(self) -> float:
        """计算总价：安全迭代累计"""
        return sum(item["price"] * item["qty"] for item in self.items)

    def apply_coupon(self, coupon_code: str) -> float:
        """
        计算优惠券折扣：
        1. 使用策略模式消除硬编码 if-elif
        2. 防御空列表除零异常
        3. 使用 with 语句确保日志句柄安全关闭
        """
        total = self.get_total_price()
        strategy = COUPON_STRATEGIES.get(coupon_code)
        discount = strategy.calculate_discount(total, self.items) if strategy else 0.0

        # 安全写入审计日志，使用上下文管理器确保释放
        try:
            with open("coupon_access_log.txt", "a", encoding="utf-8") as f:
                f.write(f"User {self.user_id} applied {coupon_code} at {time.time()}\\n")
        except IOError:
            pass

        final_price = max(0.0, total - discount)
        return round(final_price, 2)

    def get_most_expensive_item(self) -> Optional[Dict]:
        """获取单价最高商品：空购物车时防御性返回 None，杜绝 ValueError"""
        if not self.items:
            return None
        return max(self.items, key=lambda x: x["price"])


def batch_checkout_users(user_carts: Dict[str, ShoppingCart], discount_ratio: float) -> Dict[str, float]:
    """批量结算：增加折扣比例校验与精细化异常处理，消除裸 except"""
    if not (0.0 <= discount_ratio <= 1.0):
        raise ValueError("折扣比例必须在 0.0 至 1.0 之间")

    results = {}
    for uid, cart in user_carts.items():
        try:
            total = cart.get_total_price()
            res = total * (1.0 - discount_ratio)
            results[uid] = round(res, 2)
        except Exception:
            results[uid] = 0.0
    return results
'''


def extract_best_refactored_code(answer: str, original_code: str) -> Optional[str]:
    """从大模型回答中智能提取功能完整对齐的重构代码，杜绝截取局部片段"""
    if "```python" not in answer:
        return None
    parts = answer.split("```python")
    blocks = []
    for p in parts[1:]:
        snippet = p.split("```")[0].strip()
        if snippet:
            blocks.append(snippet)
    if not blocks:
        return None

    # 1. 优先提取明确标记了全量代码的代码块
    for b in reversed(blocks):
        if "# FULL_REFACTORED_CODE" in b or "# REFACTORED_FULL_CODE" in b:
            return b

    # 2. 寻找包含原主要类且行数最完整的全量代码块
    orig_classes = [
        line.split()[1].split("(")[0].split(":")[0]
        for line in original_code.splitlines()
        if line.strip().startswith("class ")
    ]
    scored = []
    for b in blocks:
        if "def test_" in b and "pytest" in b and not any(f"class {c}" in b for c in orig_classes):
            continue
        score = len(b.splitlines())
        for c in orig_classes:
            if f"class {c}" in b:
                score += 80
        scored.append((score, b))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        if len(best.splitlines()) >= 20:
            return best

    longest = max(blocks, key=lambda b: len(b.splitlines()))
    if len(longest.splitlines()) >= 25:
        return longest

    return None


def extract_pasted_code(text: str) -> Optional[str]:
    """智能检测并提取用户在对话框或输入流中粘贴的 Python 源码"""
    if not text:
        return None
    cleaned = text.strip()
    # 1. 优先提取被 ```python ... ``` 或 ``` ... ``` 包裹的代码块
    code_match = re.search(r"```(?:python)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if code_match:
        extracted = code_match.group(1).strip()
        if len(extracted) > 10:
            return extracted

    # 2. 判断输入文本本身是否为多行 Python 源代码 (具有典型的函数/类/导包/控制流特征)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) >= 3:
        code_keywords = [
            "def ", "class ", "import ", "from ", "return ", "if ",
            "for ", "while ", "try:", "except", "with open", "print("
        ]
        match_count = sum(
            1 for kw in code_keywords
            if any(line.startswith(kw) or (" " + kw in line) for line in lines)
        )
        if match_count >= 2:
            return cleaned

    return None



def render_code_with_risk_highlights(
    code_text: str,
    issues: List[Any],
    highlight_fixed_lines: Optional[set] = None,
    title: str = "源代码全景透视 (带风险行警示标记)",
) -> str:
    """生成带有精准行号与多级风险高亮的专业代码检视视图"""
    if not code_text:
        return "<div style='color: #64748b; padding: 20px;'>暂无代码内容。</div>"

    lines = code_text.splitlines()
    risk_map = {}
    for iss in issues:
        l = getattr(iss, "line", None)
        if l and 1 <= l <= len(lines):
            sev = getattr(iss.severity, "value", str(getattr(iss, "severity", "MEDIUM")))
            cat = getattr(iss, "category", "潜在风险")
            desc = getattr(iss, "description", "")
            sugg = getattr(iss, "suggestion", "")
            risk_map[l] = (sev, cat, desc, sugg)

    html_rows = []
    for i, line in enumerate(lines, 1):
        escaped_line = html.escape(line)
        if not escaped_line:
            escaped_line = "&nbsp;"

        row_cls = ""
        chip_html = ""
        tooltip = ""

        if highlight_fixed_lines and i in highlight_fixed_lines:
            row_cls = "fixed-row-highlight"
            chip_html = f'<span class="code-risk-chip fixed">✔ 已应用防御修复</span>'
        elif i in risk_map:
            sev, cat, desc, sugg = risk_map[i]
            sev_lower = sev.lower()
            row_cls = f"risk-row-{sev_lower}"
            chip_icon = "🔴" if sev == "CRITICAL" else ("🟠" if sev == "HIGH" else "🔵")
            chip_text = f"{chip_icon} {cat.split()[0]}"
            tip_text = f"【第{i}行 {sev}】{cat}\n问题分析: {desc}\n修复建议: {sugg}"
            chip_html = f'<span class="code-risk-chip {sev_lower}" title="{html.escape(tip_text)}">{chip_text}</span>'
            tooltip = f' title="{html.escape(tip_text)}"'

        html_rows.append(
            f'<div class="code-line-row {row_cls}"{tooltip}>'
            f'<span class="code-line-num">{i}</span>'
            f'<span class="code-line-code">{escaped_line}</span>'
            f'{chip_html}'
            f'</div>'
        )

    risk_count = len(risk_map)
    return f"""
<div class="source-viewer-card">
    <div class="source-viewer-header">
        <span>📄 <strong>{title}</strong> ({len(lines)} 行 · 命中 <strong>{risk_count}</strong> 处风险行高亮标记)</span>
        <span style="font-size: 0.74rem; font-family: monospace;">🔴 Critical 致命崩溃 | 🟠 High 资源/安全 | 🔵 Medium 坏味道</span>
    </div>
    <div class="source-viewer-body">
        {''.join(html_rows)}
    </div>
</div>
"""


st.set_page_config(
    page_title="CodeReviewerAgent | 智能代码审查与质量分析工作台",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 注入现代 AI IDE 样式
st.markdown("""
<style>
    /* 彻底隐藏 Streamlit 原生顶部悬浮白条 */
    header[data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    #MainMenu {
        visibility: hidden !important;
    }
    footer {
        visibility: hidden !important;
    }

    /* 页面主体容器 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
    }

    /* IDE 顶部导航状态栏 */
    .ide-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #0f172a;
        color: #f8fafc;
        padding: 10px 18px;
        border-radius: 8px;
        margin-bottom: 14px;
        border: 1px solid #1e293b;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .ide-title-box {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .ide-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    .ide-badge {
        background: #2563eb;
        color: #ffffff;
        font-size: 0.72rem;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
    .ide-meta-box {
        display: flex;
        align-items: center;
        gap: 16px;
        font-size: 0.82rem;
        color: #94a3b8;
    }
    .ide-meta-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* IDE 编辑器容器卡片 */
    .editor-card {
        background: #090d16;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
    }

    /* 仿 Terminal 黑色控制台 */
    .terminal-window {
        background: #000000;
        border: 1px solid #1e293b;
        border-radius: 6px;
        padding: 12px 16px;
        font-family: 'Consolas', 'Courier New', monospace;
        color: #4ade80;
        font-size: 0.85rem;
        line-height: 1.5;
        max-height: 480px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* 上下文药丸徽章 */
    .context-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #1e293b;
        border: 1px solid #334155;
        color: #38bdf8;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-family: monospace;
    }

    /* 智能代码审计看板与风险卡片样式 (对标工业级 ReviewResults 面板) */
    .audit-metrics-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-bottom: 14px;
    }
    .audit-stat-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .audit-stat-title {
        font-size: 0.76rem;
        color: #94a3b8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .audit-stat-value {
        font-size: 1.45rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.2;
    }
    .audit-stat-sub {
        font-size: 0.72rem;
        color: #64748b;
        margin-top: 4px;
    }

    /* 现代结构化缺陷诊断卡片 */
    .issue-card {
        background: #0b1120;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        transition: all 0.2s ease;
    }
    .issue-card:hover {
        border-color: #334155;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
    }
    .issue-card.critical {
        border-left: 4px solid #ef4444;
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.08) 0%, #0b1120 100%);
    }
    .issue-card.high {
        border-left: 4px solid #f97316;
        background: linear-gradient(90deg, rgba(249, 115, 22, 0.08) 0%, #0b1120 100%);
    }
    .issue-card.medium {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(90deg, rgba(59, 130, 246, 0.08) 0%, #0b1120 100%);
    }
    .issue-card.low {
        border-left: 4px solid #10b981;
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.08) 0%, #0b1120 100%);
    }

    .issue-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }
    .issue-title-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .issue-id {
        font-family: monospace;
        font-size: 0.78rem;
        color: #94a3b8;
        font-weight: 600;
    }
    .issue-pill {
        font-size: 0.72rem;
        padding: 2px 8px;
        border-radius: 9999px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .issue-pill.critical {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .issue-pill.high {
        background: rgba(249, 115, 22, 0.2);
        color: #fdba74;
        border: 1px solid rgba(249, 115, 22, 0.4);
    }
    .issue-pill.medium {
        background: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }
    .issue-pill.low {
        background: rgba(16, 185, 129, 0.2);
        color: #86efac;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }

    .issue-category-name {
        font-size: 0.92rem;
        font-weight: 600;
        color: #f1f5f9;
    }
    .issue-loc {
        font-size: 0.78rem;
        color: #64748b;
        font-family: monospace;
        background: #1e293b;
        padding: 2px 8px;
        border-radius: 4px;
    }

    .issue-snippet-box {
        background: #020617;
        border: 1px solid #1e293b;
        border-radius: 4px;
        padding: 6px 12px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.8rem;
        color: #f87171;
        margin: 6px 0 10px 0;
        white-space: pre-wrap;
    }
    .issue-desc {
        font-size: 0.84rem;
        color: #cbd5e1;
        line-height: 1.5;
        margin-bottom: 6px;
    }
    .issue-suggestion-box {
        background: rgba(30, 41, 59, 0.5);
        border-left: 3px solid #38bdf8;
        padding: 6px 10px;
        border-radius: 0 4px 4px 0;
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 6px;
    }

    /* 左侧对话助手列弹性与置底吸附 */
    [data-testid="column"]:first-child {
        display: flex !important;
        flex-direction: column !important;
        min-height: calc(100vh - 120px) !important;
    }
    [data-testid="column"]:first-child [data-testid="stChatInput"] {
        margin-top: auto !important;
        position: sticky !important;
        bottom: 8px !important;
        z-index: 99 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
    }

    /* Claude AI 风格快捷指令药丸按钮 (Quick Action Chips) */
    [data-testid="column"]:first-child div[data-testid="stHorizontalBlock"] {
        gap: 6px !important;
        margin-top: 6px !important;
        margin-bottom: 6px !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] button {
        height: 36px !important;
        min-height: 36px !important;
        max-height: 36px !important;
        border-radius: 9999px !important; /* Claude 经典的 Pill 药丸胶囊圆角 */
        background: rgba(30, 41, 59, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        color: #f1f5f9 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        padding: 0 4px !important;
        width: 100% !important;
        white-space: nowrap !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        cursor: pointer !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] button p {
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        white-space: nowrap !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
        display: inline-block !important;
        color: inherit !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] button:hover {
        background: rgba(217, 119, 6, 0.16) !important; /* Claude 标志性陶土/暖金微光 */
        border-color: rgba(245, 158, 11, 0.7) !important;
        color: #fbbf24 !important;
        transform: translateY(-1.5px) !important;
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.25) !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] button:hover p {
        color: #fbbf24 !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] button:active {
        transform: scale(0.96) !important;
        background: rgba(217, 119, 6, 0.25) !important;
    }
    [data-testid="column"]:first-child div[data-testid="stButton"] button:focus:not(:active) {
        border-color: rgba(245, 158, 11, 0.5) !important;
        color: #fbbf24 !important;
    }

    /* 三列布局头部与空状态 (Empty State) 现代卡片样式 */
    .col-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .col-header-title {
        font-size: 1.02rem;
        font-weight: 600;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .empty-state-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        background: rgba(15, 23, 42, 0.45);
        border: 1.5px dashed rgba(148, 163, 184, 0.25);
        border-radius: 12px;
        padding: 44px 24px;
        margin: 10px 0;
        min-height: 480px;
    }
    .empty-state-icon {
        font-size: 2.8rem;
        margin-bottom: 14px;
        opacity: 0.9;
    }
    .empty-state-title {
        font-size: 1.12rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-bottom: 8px;
    }
    .empty-state-desc {
        font-size: 0.85rem;
        color: #94a3b8;
        max-width: 360px;
        line-height: 1.6;
        margin-bottom: 18px;
    }

    /* 源代码检视器与风险行高亮 (Source Code Risk Highlighter) */
    .source-viewer-card {
        background: #090d16;
        border: 1px solid #1e293b;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 12px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
    }
    .source-viewer-header {
        background: #0f172a;
        padding: 8px 14px;
        border-bottom: 1px solid #1e293b;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.8rem;
        color: #94a3b8;
    }
    .source-viewer-body {
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.84rem;
        line-height: 1.6;
        max-height: 600px;
        overflow-y: auto;
        overflow-x: auto;
        padding: 8px 0;
        background: #090d16;
    }
    .code-line-row {
        display: flex;
        align-items: center;
        padding: 1px 12px;
        min-height: 24px;
        transition: background-color 0.15s ease;
    }
    .code-line-row:hover {
        background: rgba(255, 255, 255, 0.04);
    }
    .code-line-num {
        width: 44px;
        min-width: 44px;
        text-align: right;
        padding-right: 14px;
        color: #475569;
        user-select: none;
        font-size: 0.76rem;
    }
    .code-line-code {
        flex: 1;
        white-space: pre;
        color: #e2e8f0;
    }
    /* 风险行多级高亮标记 */
    .code-line-row.risk-row-critical {
        background: rgba(239, 68, 68, 0.22) !important;
        border-left: 4px solid #ef4444;
    }
    .code-line-row.risk-row-critical .code-line-num {
        color: #fca5a5;
        font-weight: 700;
    }
    .code-line-row.risk-row-high {
        background: rgba(249, 115, 22, 0.2) !important;
        border-left: 4px solid #f97316;
    }
    .code-line-row.risk-row-high .code-line-num {
        color: #fdba74;
        font-weight: 700;
    }
    .code-line-row.risk-row-medium {
        background: rgba(59, 130, 246, 0.16) !important;
        border-left: 4px solid #3b82f6;
    }
    .code-line-row.risk-row-medium .code-line-num {
        color: #93c5fd;
        font-weight: 700;
    }
    .code-line-row.fixed-row-highlight {
        background: rgba(16, 185, 129, 0.2) !important;
        border-left: 4px solid #10b981;
    }
    .code-line-row.fixed-row-highlight .code-line-num {
        color: #86efac;
        font-weight: 700;
    }
    .code-risk-chip {
        font-size: 0.7rem;
        padding: 1px 7px;
        border-radius: 4px;
        margin-left: 12px;
        font-weight: 600;
        white-space: nowrap;
        user-select: none;
    }
    .code-risk-chip.critical {
        background: #ef4444;
        color: #ffffff;
    }
    .code-risk-chip.high {
        background: #f97316;
        color: #ffffff;
    }
    .code-risk-chip.medium {
        background: #2563eb;
        color: #ffffff;
    }
    .code-risk-chip.fixed {
        background: #059669;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)


# ================= 全局状态与会话初始化 =================
if "config" not in st.session_state:
    st.session_state.config = Config.from_env()

if "pipeline" not in st.session_state:
    st.session_state.pipeline = CodePipeline(config=st.session_state.config)

if "active_code" not in st.session_state:
    st.session_state.active_code = ""
    st.session_state.active_file_name = "未加载代码"

if "baseline_code" not in st.session_state:
    st.session_state.baseline_code = ""

if "reviewed" not in st.session_state:
    st.session_state.reviewed = False

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "refactored_code" not in st.session_state:
    st.session_state.refactored_code = None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": (
                "👋 **你好！我是基于主流框架 LangChain 驱动的专业代码审查智能体 (CodeReviewerAgent)**。\n\n"
                "🎯 **核心使命**：深入分析代码质量、排查隐蔽运行时崩溃风险与漏洞、输出高质量整改建议。\n\n"
                "🔄 **Agent 执行闭环 (ReAct 循环)**：\n"
                "- 📥 **输入 (Input)**：接收目标源码与审查指令；\n"
                "- 🧠 **推理 (Reasoning)**：制定审计计划，分析潜在风险点；\n"
                "- ⚡ **工具调用 (Tools)**：自主调度 `read_file`、`lint_code` (AST代码解析) 与 `execute_python_code` (沙箱运行)；\n"
                "- 💡 **成果输出 (Output)**：生成结构化缺陷诊断大屏与一键可采纳的修复建议！\n\n"
                "👉 *点击下方快捷胶囊按钮或直接输入自然语言指令，即刻启动全量安全审查！*"
            )
        }
    ]

if "thought_steps" not in st.session_state:
    st.session_state.thought_steps = []

if "test_sandbox_output" not in st.session_state:
    st.session_state.test_sandbox_output = ""

if "pending_task" not in st.session_state:
    st.session_state.pending_task = None


# ================= IDE 顶部状态栏 =================
active_lines = len(st.session_state.active_code.splitlines())
st.markdown(f"""
<div class="ide-header">
    <div class="ide-title-box">
        <span class="ide-title">🛡️ CodeReviewerAgent 工作台</span>
        <span class="ide-badge">LangChain Core 驱动</span>
        <span class="ide-badge" style="background: #059669;">ReAct 闭环循环</span>
    </div>
    <div class="ide-meta-box">
        <div class="ide-meta-item">
            <span>当前聚焦:</span>
            <span class="context-pill">📄 {st.session_state.get('active_file_name', 'untitled.py')} ({active_lines} 行)</span>
        </div>
        <div class="ide-meta-item">
            <span>推理模型:</span>
            <strong style="color: #38bdf8;">{st.session_state.config.model_name}</strong>
        </div>
        <div class="ide-meta-item">
            <span>循环链路:</span>
            <span style="color: #fbbf24; font-family: monospace;">输入 ➔ 推理 ➔ 工具 ➔ 输出</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ================= 侧边栏：环境与底层监控 =================
with st.sidebar:
    st.title("⚙️ IDE 设置中心")
    st.caption("基于主流 Agent 框架 LangChain 驱动")

    st.subheader("🔑 凭据与模型")
    api_key_val = st.text_input(
        "DeepSeek API Key",
        value=st.session_state.config.api_key,
        type="password",
        help="系统默认读取根目录 .env 配置",
    )
    if api_key_val and api_key_val != st.session_state.config.api_key:
        st.session_state.config.api_key = api_key_val
        st.session_state.pipeline = CodePipeline(config=st.session_state.config)
        st.toast("已更新 API Key", icon="🔑")

    models = ["deepseek-flash", "deepseek-v4-pro", "deepseek-chat", "gpt-4o-mini"]
    selected_m = st.selectbox("核心驱动模型", models, index=0)
    if selected_m != st.session_state.config.model_name:
        st.session_state.config.model_name = selected_m
        st.session_state.pipeline = CodePipeline(config=st.session_state.config)
        st.toast(f"已切换模型至: {selected_m}", icon="🤖")

    st.markdown("---")
    st.subheader("🛠️ LangChain 工具链")
    with st.expander("已挂载的标准 StructuredTool (6个)", expanded=False):
        for tool_schema in st.session_state.pipeline.reviewer_agent.tool_registry.get_tools_schema():
            fn = tool_schema["function"]
            st.markdown(f"**`{fn['name']}`**")
            st.caption(fn["description"])

    if st.button("🗑️ 重置 IDE 状态与记忆", use_container_width=True):
        st.session_state.analysis_result = None
        st.session_state.thought_steps = []
        st.session_state.test_sandbox_output = ""
        st.session_state.active_code = st.session_state.baseline_code
        if "shopping_cart" in st.session_state.get("active_file_name", ""):
            st.session_state.refactored_code = DEFAULT_REFACTORED_SHOPPING_CART
        else:
            st.session_state.refactored_code = None
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "IDE 工作台与上下文记忆已重置。"}
        ]
        st.rerun()


# ================= 核心 AI IDE 三列布局：左助手 (28%) + 中源代码 (44%) + 右风险点 (28%) =================
col_left, col_center, col_right = st.columns([2.8, 4.4, 2.8], gap="small")


# -------------------------------------------------------------
# 【左侧栏】：🤖 AI Copilot 助手 (占比 28%)
# 沉浸式对话、思考流、Claude Pill 快捷指令、智能提取粘贴代码的置底输入框
# -------------------------------------------------------------
with col_left:
    st.markdown('<div class="col-header"><span class="col-header-title">🤖 AI Copilot 助手</span><span style="font-size: 0.72rem; color: #94a3b8; font-family: monospace;">LangChain ReAct</span></div>', unsafe_allow_html=True)

    # 辅助函数：格式化思考步骤 (严格契合 Agent 循环：输入 → 推理 → 工具调用 → 输出)
    def format_step_badge(step: Dict[str, Any]) -> str:
        s_type = step.get("type")
        if s_type == "pipeline_start":
            return f"📥 **[Agent 循环 1/4 · 输入 Input]**: 接收目标源码 ({step.get('lines', 0)} 行)"
        elif s_type == "phase1_complete":
            issues_cnt = step.get("initial_issues_count", 0)
            return f"🔍 **[代码解析 · 静态 AST 扫描]**: 初筛锁定 **{issues_cnt}** 处潜在风险线索 (函数 {len(step.get('functions', []))} 个)"
        elif s_type == "phase2_dispatch":
            return f"🤖 **[专家智能体调度]**: 任务委派给 `{step.get('agent', 'CodeReviewerAgent')}`"
        elif s_type == "agent_start":
            return f"🧠 **[Agent 循环 2/4 · 推理 Reasoning]**: {step.get('agent_name', 'CodeReviewerAgent')} 深入分析代码质量与潜在Bug"
        elif s_type == "call":
            return f"⚡ **[Agent 循环 3/4 · 工具调用 Tool Call]**: 第 {step.get('iteration', 1)} 轮自主调度 LangChain 工具 `{step.get('tool')}`"
        elif s_type == "result":
            status_text = "✅ 沙箱执行成功" if step.get("success") else "❌ 执行报错/异常"
            return f"📋 **[Agent 循环 3/4 · 环境观察 Observation]**: {status_text} (工具 `{step.get('tool')}`)"
        elif s_type == "agent_finish":
            return f"💡 **[Agent 循环 4/4 · 推理收敛]**: 历经 {step.get('iterations', 1)} 轮 ReAct 思考，整改建议生成完毕"
        elif s_type == "pipeline_finish":
            return f"✔ **[成果输出 Output]**: 代码质量评估与缺陷看板聚合就绪"
        return f"● {step.get('title', '处理中')}"

    # 对话流容器 (高度 560px，极致清爽的沉浸式对话)
    chat_box = st.container(height=560)
    with chat_box:
        # 1. 历史消息渲染
        for msg in st.session_state.chat_messages:
            role = msg.get("role", "assistant")
            with st.chat_message(role, avatar="🧑‍💻" if role == "user" else "🤖"):
                steps = msg.get("steps", [])
                if steps:
                    with st.expander(f"🧠 思考与 LangChain 工具轨迹 ({len(steps)} 步)", expanded=False):
                        for s in steps:
                            st.markdown(format_step_badge(s))
                            if s.get("type") == "call" and s.get("arguments"):
                                st.caption(f"入参: `{s.get('arguments')}`")
                            elif s.get("type") == "result":
                                out_text = str(s.get("output", "")).strip()
                                if out_text:
                                    st.code(out_text[:500] + ("\n... [完整日志见中间沙箱终端]" if len(out_text) > 500 else ""), language="text")
                            st.markdown("<hr style='margin: 3px 0; border: none; border-top: 1px dashed #334155;'/>", unsafe_allow_html=True)
                st.markdown(msg.get("content", ""))

        # 2. 待处理任务实时执行
        if st.session_state.get("pending_task"):
            cur_task = st.session_state.pending_task
            st.session_state.pending_task = None
            prompt_text = cur_task.get("prompt", "")
            task_type = cur_task.get("task_type", "review")

            with st.chat_message("user", avatar="🧑‍💻"):
                st.markdown(prompt_text)
            st.session_state.chat_messages.append({"role": "user", "content": prompt_text})

            current_steps: List[Dict[str, Any]] = []
            with st.chat_message("assistant", avatar="🤖"):
                status_box = st.status(f"🤖 正在调度 LangChain Pipeline [{task_type}]...", expanded=True)

                def step_cb(evt: str, data: Dict[str, Any]):
                    if evt == "pipeline_start":
                        current_steps.append({
                            "type": "pipeline_start",
                            "lines": data.get("lines", 0),
                        })
                        status_box.write(f"🚀 流水线启动，分析代码规模: {data.get('lines', 0)} 行")
                    elif evt == "phase1_complete":
                        current_steps.append({
                            "type": "phase1_complete",
                            "initial_issues_count": data.get("initial_issues_count", 0),
                            "functions": data.get("functions", []),
                            "classes": data.get("classes", []),
                        })
                        status_box.write(f"🔍 Phase 1 静态初筛完成，识别到 {data.get('initial_issues_count', 0)} 处坏味道")
                    elif evt == "phase2_dispatch":
                        current_steps.append({
                            "type": "phase2_dispatch",
                            "agent": data.get("agent", ""),
                        })
                        status_box.write(f"🤖 任务分发至专家智能体: `{data.get('agent')}`")
                    elif evt == "start":
                        current_steps.append({
                            "type": "agent_start",
                            "agent_name": data.get("agent_name", ""),
                        })
                        status_box.write(f"🧠 模型推理启动: `{data.get('agent_name', '')}` 正在规划方案")
                    elif evt == "call_tool":
                        current_steps.append({
                            "type": "call",
                            "tool": data.get("tool"),
                            "arguments": data.get("arguments"),
                            "iteration": data.get("iteration"),
                        })
                        status_box.write(f"⚡ [第 {data.get('iteration', 1)} 轮] 调用 LangChain 工具: `{data.get('tool')}`")
                    elif evt == "tool_result":
                        current_steps.append({
                            "type": "result",
                            "tool": data.get("tool"),
                            "success": bool(data.get("success", False)),
                            "output": str(data.get("output", "")),
                        })
                        status_box.write(f"{'✅' if data.get('success') else '❌'} 工具 `{data.get('tool')}` 沙箱运行完毕")
                    elif evt == "finish":
                        current_steps.append({
                            "type": "agent_finish",
                            "iterations": data.get("iterations", 1),
                            "agent_name": data.get("agent_name", ""),
                        })
                        status_box.write(f"💡 专家智能体思考推理结束 (共 {data.get('iterations', 1)} 轮)")
                    elif evt == "pipeline_finish":
                        current_steps.append({"type": "pipeline_finish"})
                        status_box.write("✔ 聚合校验完成")

                pipeline_res = st.session_state.pipeline.run_pipeline(
                    target=st.session_state.active_code,
                    task_type=task_type,
                    on_step=step_cb,
                )
                status_box.update(label="✔ 思考与分析完成 (已折叠)", state="complete", expanded=False)

                answer = pipeline_res.get("phase2", {}).get("report", "")
                if not answer and not pipeline_res.get("success"):
                    answer = f"⚠️ 流水线执行异常: {pipeline_res.get('error', '未知错误')}"

                st.markdown(answer)

                st.session_state.reviewed = True
                st.session_state.analysis_result = pipeline_res
                st.session_state.thought_steps = current_steps
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": answer,
                    "steps": current_steps,
                })

                # 智能提取重构代码更新 Diff
                extracted_code = extract_best_refactored_code(answer, st.session_state.baseline_code)
                if extracted_code:
                    st.session_state.refactored_code = extracted_code
                    st.toast("已在中间视图生成修改前后对比 Diff！", icon="🔀")

                sandbox_logs = [
                    str(s.get("output", ""))
                    for s in current_steps
                    if s.get("type") == "result" and s.get("tool") in ("execute_python_code", "run_pytest") and s.get("output")
                ]
                if sandbox_logs:
                    st.session_state.test_sandbox_output = "\n\n".join(sandbox_logs)

            st.rerun()

    # 4 个漂浮在输入框上方的快捷指令按钮 (Claude AI Pill 风格)
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4, gap="small")
    with btn_col1:
        if st.button("⚡ 全面审查", use_container_width=True, help="/review: 全维度排查除零、未关文件、越界与安全缺陷"):
            if not st.session_state.active_code:
                p = Path("samples/demo_shopping_cart.py")
                if p.exists():
                    txt = p.read_text(encoding="utf-8")
                    st.session_state.active_code = txt
                    st.session_state.baseline_code = txt
                    st.session_state.active_file_name = "samples/demo_shopping_cart.py"
                    st.toast("已自动装载电商购物车样例并启动审查！", icon="🚀")
            st.session_state.pending_task = {
                "prompt": "/review: 请对中间源代码进行全维度的深度安全与漏洞审查",
                "task_type": "review"
            }
            st.rerun()
    with btn_col2:
        if st.button("➗ 崩溃排查", use_container_width=True, help="/review: 重点排查除以零、空序列max/min、下标越界等崩溃点"):
            if not st.session_state.active_code:
                p = Path("samples/demo_shopping_cart.py")
                if p.exists():
                    txt = p.read_text(encoding="utf-8")
                    st.session_state.active_code = txt
                    st.session_state.baseline_code = txt
                    st.session_state.active_file_name = "samples/demo_shopping_cart.py"
                    st.toast("已自动装载样例并启动排查！", icon="🚀")
            st.session_state.pending_task = {
                "prompt": "/review: 专项排查代码中的除零、空序列、下标越界等运行时致命崩溃隐患",
                "task_type": "review"
            }
            st.rerun()
    with btn_col3:
        if st.button("📂 资源审计", use_container_width=True, help="/review: 重点排查裸open未关闭、文件句柄泄漏与资源释放"):
            if not st.session_state.active_code:
                p = Path("samples/demo_shopping_cart.py")
                if p.exists():
                    txt = p.read_text(encoding="utf-8")
                    st.session_state.active_code = txt
                    st.session_state.baseline_code = txt
                    st.session_state.active_file_name = "samples/demo_shopping_cart.py"
                    st.toast("已自动装载样例并启动审计！", icon="🚀")
            st.session_state.pending_task = {
                "prompt": "/review: 专项审计代码中裸open文件未关闭、句柄泄漏及外部资源释放安全",
                "task_type": "review"
            }
            st.rerun()
    with btn_col4:
        if st.button("🛡️ 异常防御", use_container_width=True, help="/review: 重点排查裸except异常吞噬、静默pass与边界防御"):
            if not st.session_state.active_code:
                p = Path("samples/demo_shopping_cart.py")
                if p.exists():
                    txt = p.read_text(encoding="utf-8")
                    st.session_state.active_code = txt
                    st.session_state.baseline_code = txt
                    st.session_state.active_file_name = "samples/demo_shopping_cart.py"
                    st.toast("已自动装载样例并启动排查！", icon="🚀")
            st.session_state.pending_task = {
                "prompt": "/review: 专项排查代码中的裸except异常吞噬、静默忽略与输入边界防御缺失",
                "task_type": "review"
            }
            st.rerun()

    # 置底输入框：支持自然语言、指令，以及复制代码直接粘贴
    input_text = st.chat_input("输入修改需求，或直接在此粘贴 Python 代码...")
    if input_text:
        cleaned = input_text.strip()
        pasted = extract_pasted_code(cleaned)
        if pasted:
            # 智能提取到代码，自动装入中间源代码区，并自动触发审查
            st.session_state.active_code = pasted
            st.session_state.baseline_code = pasted
            st.session_state.active_file_name = "clipboard_code.py"
            st.session_state.reviewed = False
            st.session_state.analysis_result = None
            st.session_state.refactored_code = None
            st.session_state.pending_task = {
                "prompt": "/review: 请对我复制粘贴的 Python 源代码进行全面安全与漏洞审查，排查潜在运行时Bug与安全漏洞",
                "task_type": "review"
            }
            st.toast("已将您粘贴的代码自动载入中间源代码区，并启动审查！", icon="📋")
            st.rerun()
        else:
            task_type = "review"
            if cleaned.startswith("/review"):
                task_type = "review"
            elif cleaned.startswith("/refactor"):
                task_type = "refactor"
            elif cleaned.startswith("/test"):
                task_type = "test"
            elif cleaned.startswith("/explain"):
                task_type = "explain"
            elif cleaned == "/":
                task_type = "review"
                cleaned = "/review: 请审查当前代码"

            if not st.session_state.active_code:
                p = Path("samples/demo_shopping_cart.py")
                if p.exists():
                    txt = p.read_text(encoding="utf-8")
                    st.session_state.active_code = txt
                    st.session_state.baseline_code = txt
                    st.session_state.active_file_name = "samples/demo_shopping_cart.py"
                    st.toast("已自动为您装载电商购物车样例代码！", icon="🚀")

            st.session_state.pending_task = {
                "prompt": cleaned if cleaned.startswith("/") else f"针对当前中间源码，我的具体修改需求是：{cleaned}",
                "task_type": task_type
            }
            st.rerun()


# -------------------------------------------------------------
# 【中间栏】：💻 源代码检视与编辑 (占比 44%)
# 最初为空状态卡片；载入代码后显示源码透视、红橙风险高亮与在线编辑器
# -------------------------------------------------------------
with col_center:
    code_lines = len(st.session_state.active_code.splitlines()) if st.session_state.active_code else 0
    cur_fname = Path(st.session_state.get('active_file_name', 'untitled.py')).name

    st.markdown(f"""
<div class="col-header">
    <span class="col-header-title">💻 源代码检视与编辑</span>
    <span style="font-size: 0.76rem; color: #94a3b8; font-family: monospace;">
        {f'📄 {cur_fname} ({code_lines} 行)' if st.session_state.active_code else '📁 暂无代码'}
    </span>
</div>
""", unsafe_allow_html=True)

    if not st.session_state.active_code:
        # 最初没有任何代码时的空状态卡片
        st.markdown("""
<div class="empty-state-box">
    <div class="empty-state-icon">📁</div>
    <div class="empty-state-title">暂无代码内容</div>
    <div class="empty-state-desc">
        请在下方上传本地 <code>.py</code> 源代码文件，或者直接在左侧 AI 助手对话框中<strong>粘贴代码</strong>，中间区域将立即呈现源码。
    </div>
</div>
""", unsafe_allow_html=True)

        emp_c1, emp_c2 = st.columns([1.2, 1], gap="small")
        with emp_c1:
            up_initial = st.file_uploader("上传 Python 源代码", type=["py"], key="initial_source_upload", label_visibility="collapsed")
            if up_initial is not None:
                content = up_initial.read().decode("utf-8", errors="replace")
                st.session_state.active_code = content
                st.session_state.baseline_code = content
                st.session_state.active_file_name = up_initial.name
                st.session_state.reviewed = False
                st.session_state.analysis_result = None
                st.session_state.refactored_code = None
                st.toast(f"已装载代码: {up_initial.name}", icon="📤")
                st.rerun()
        with emp_c2:
            if st.button("🚀 载入电商购物车样例", use_container_width=True, help="一键载入含除零、句柄未关缺陷的电商购物车代码"):
                p = Path("samples/demo_shopping_cart.py")
                if p.exists():
                    txt = p.read_text(encoding="utf-8")
                    st.session_state.active_code = txt
                    st.session_state.baseline_code = txt
                    st.session_state.active_file_name = "samples/demo_shopping_cart.py"
                    st.session_state.reviewed = False
                    st.session_state.analysis_result = None
                    st.session_state.refactored_code = None
                    st.toast("已载入电商购物车样例代码！", icon="🚀")
                    st.rerun()

    else:
        # 已有代码：顶部单行工具栏 (模式切换、启动审查按钮、上传、样例、清空)
        tb_c1, tb_c2, tb_c3, tb_c4, tb_c5 = st.columns([2.0, 1.8, 1.0, 1.0, 0.8], gap="small")
        with tb_c1:
            code_view_mode = st.radio(
                "视图模式",
                ["🌟 源码透视", "✏️ 在线编辑"],
                horizontal=True,
                label_visibility="collapsed",
                key="center_code_mode"
            )
        with tb_c2:
            if st.button("⚡ 启动代码审查", type="primary", use_container_width=True, help="立即启动 CodeReviewerAgent 审查当前代码"):
                st.session_state.pending_task = {
                    "prompt": "/review: 请对当前代码进行全面安全与漏洞审查，排查潜在运行时Bug与安全漏洞，并给出修复后的对比代码",
                    "task_type": "review"
                }
                st.rerun()
        with tb_c3:
            with st.popover("📤 上传", use_container_width=True):
                up_replace = st.file_uploader("上传新 .py 源码", type=["py"], key="replace_source_upload")
                if up_replace is not None:
                    c = up_replace.read().decode("utf-8", errors="replace")
                    if c != st.session_state.active_code:
                        st.session_state.active_code = c
                        st.session_state.baseline_code = c
                        st.session_state.active_file_name = up_replace.name
                        st.session_state.reviewed = False
                        st.session_state.analysis_result = None
                        st.session_state.refactored_code = None
                        st.toast(f"已更新源码: {up_replace.name}", icon="📤")
                        st.rerun()
        with tb_c4:
            with st.popover("📚 样例", use_container_width=True):
                sample_files = {
                    "电商购物车 (含除零/泄漏)": "samples/demo_shopping_cart.py",
                    "典型坏味道代码": "samples/buggy_code.py",
                    "算法函数集": "samples/math_utils.py",
                }
                sel_sample = st.selectbox("选择样例文件", list(sample_files.keys()))
                if st.button("确认切换样例", use_container_width=True):
                    sp = Path(sample_files[sel_sample])
                    if sp.exists():
                        st.session_state.active_code = sp.read_text(encoding="utf-8")
                        st.session_state.baseline_code = st.session_state.active_code
                        st.session_state.active_file_name = sample_files[sel_sample]
                        st.session_state.reviewed = False
                        st.session_state.analysis_result = None
                        st.session_state.refactored_code = None
                        st.rerun()
        with tb_c5:
            if st.button("🗑️", help="清空当前代码，恢复初始空状态", use_container_width=True):
                st.session_state.active_code = ""
                st.session_state.baseline_code = ""
                st.session_state.active_file_name = "未加载代码"
                st.session_state.reviewed = False
                st.session_state.analysis_result = None
                st.session_state.refactored_code = None
                st.rerun()

        # 源码展示区
        if "源码透视" in code_view_mode:
            highlight_issues = []
            if st.session_state.reviewed:
                rule_res = st.session_state.pipeline.rule_engine.analyze_source(st.session_state.active_code)
                highlight_issues = rule_res.get("issues", [])

            rendered_html = render_code_with_risk_highlights(
                code_text=st.session_state.active_code,
                issues=highlight_issues,
                title=f"源码视图 · {cur_fname}"
            )
            st.markdown(rendered_html, unsafe_allow_html=True)
            if st.session_state.reviewed and highlight_issues:
                st.caption(f"💡 审查已完成：命中 **{len(highlight_issues)}** 处风险行标记，悬停红色/橙色高亮行可查看机理成因。")
            elif not st.session_state.reviewed:
                st.caption("💡 提示：点击上方【⚡ 启动代码审查】后，将在此自动标注红橙风险高亮与悬停诊断！")
        else:
            edited_code = st.text_area(
                "编辑代码",
                value=st.session_state.active_code,
                height=560,
                key="center_source_editor",
                label_visibility="collapsed"
            )
            if edited_code != st.session_state.active_code:
                st.session_state.active_code = edited_code
                st.session_state.baseline_code = edited_code

        # 底部折叠抽屉：修改对比 Diff
        refactored = st.session_state.get("refactored_code")
        if not refactored and "shopping_cart" in st.session_state.get("active_file_name", ""):
            refactored = DEFAULT_REFACTORED_SHOPPING_CART
            st.session_state.refactored_code = refactored

        with st.expander("🔀 修改前后对比 Diff (重构建议视图)", expanded=False):
            if refactored:
                diff_c1, diff_c2 = st.columns([1, 1])
                with diff_c1:
                    if st.button("✅ 采纳此重构代码", type="primary", use_container_width=True):
                        st.session_state.active_code = refactored
                        st.toast("已采纳修复代码！", icon="🎉")
                        st.rerun()
                with diff_c2:
                    if st.button("↩️ 还原基线", use_container_width=True):
                        st.session_state.active_code = st.session_state.baseline_code
                        st.toast("已还原至初始基准代码！", icon="↩️")
                        st.rerun()

                diff_lines = list(difflib.unified_diff(
                    st.session_state.baseline_code.splitlines(keepends=True),
                    refactored.splitlines(keepends=True),
                    fromfile="a/original.py",
                    tofile="b/refactored.py",
                    n=3,
                ))
                patch_text = "".join(diff_lines)
                if patch_text:
                    st.code(patch_text, language="diff")
                else:
                    st.info("当前基线代码与重构代码完全一致，无增量差异。")
            else:
                st.info("💡 尚未生成修复代码。点击上方【⚡ 启动代码审查】即可生成！")

        # 底部折叠抽屉：沙箱终端
        with st.expander("🧪 终端沙箱输出 (Terminal)", expanded=False):
            t_output = st.session_state.get("test_sandbox_output", "")
            if t_output:
                st.markdown(f'<div class="terminal-window">>_ 沙箱执行输出：\n\n{t_output}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="terminal-window">>_ 终端就绪 (等待代码审查与沙箱运行验证任务...)</div>', unsafe_allow_html=True)


# -------------------------------------------------------------
# 【右侧栏】：⚠️ 风险点与缺陷诊断 (占比 28%)
# 最初为空状态卡片；审查完毕后呈现健康评分、致命/高危风险点、成因建议与一键修复
# -------------------------------------------------------------
with col_right:
    st.markdown('<div class="col-header"><span class="col-header-title">⚠️ 风险点与缺陷诊断</span></div>', unsafe_allow_html=True)

    if not st.session_state.active_code or not st.session_state.reviewed:
        # 最初没有审查时的优雅空状态卡片
        st.markdown("""
<div class="empty-state-box">
    <div class="empty-state-icon">🛡️</div>
    <div class="empty-state-title">暂无风险内容</div>
    <div class="empty-state-desc">
        当前尚未执行代码审查。<br/>
        请在中间区域载入源代码，并点击<strong>【⚡ 启动代码审查】</strong>。<br/><br/>
        审查完成后，CodeReviewerAgent 将在此展示深度安全健康评分、致命崩溃与高危风险点、以及逐行整改建议。
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        # 审查完毕后，呈现丰富的风险内容！
        rule_res = st.session_state.pipeline.rule_engine.analyze_source(st.session_state.active_code)
        issues = rule_res.get("issues", [])

        crit_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "CRITICAL")
        high_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "HIGH")
        med_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "MEDIUM")

        health_score = max(0, 100 - crit_cnt * 25 - high_cnt * 15 - med_cnt * 5)
        if health_score >= 90:
            grade_text, grade_color = "A (优秀)", "#4ade80"
        elif health_score >= 75:
            grade_text, grade_color = "B (良好)", "#60a5fa"
        elif health_score >= 60:
            grade_text, grade_color = "C (需整改)", "#fbbf24"
        else:
            grade_text, grade_color = "D (高危风险)", "#f87171"

        # 顶部 2x2 统计卡片 (完美适配 28% 宽度)
        st.markdown(f"""
<div class="audit-metrics-row" style="grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 8px;">
    <div class="audit-stat-card" style="padding: 8px 10px;">
        <div class="audit-stat-title" style="font-size: 0.72rem;">🛡️ 健康评分</div>
        <div class="audit-stat-value" style="color: {grade_color}; font-size: 1.2rem;">{health_score} <span style="font-size: 0.75rem;">/ 100</span></div>
        <div class="audit-stat-sub" style="font-size: 0.68rem;">评级: <strong>{grade_text}</strong></div>
    </div>
    <div class="audit-stat-card" style="padding: 8px 10px;">
        <div class="audit-stat-title" style="font-size: 0.72rem;">🔴 致命崩溃 (P0)</div>
        <div class="audit-stat-value" style="color: #f87171; font-size: 1.2rem;">{crit_cnt} <span style="font-size: 0.75rem; color: #94a3b8;">处</span></div>
        <div class="audit-stat-sub" style="font-size: 0.68rem;">除零、越界</div>
    </div>
    <div class="audit-stat-card" style="padding: 8px 10px;">
        <div class="audit-stat-title" style="font-size: 0.72rem;">🟠 高危泄漏 (P1)</div>
        <div class="audit-stat-value" style="color: #fb923c; font-size: 1.2rem;">{high_cnt} <span style="font-size: 0.75rem; color: #94a3b8;">处</span></div>
        <div class="audit-stat-sub" style="font-size: 0.68rem;">句柄未关、吞异常</div>
    </div>
    <div class="audit-stat-card" style="padding: 8px 10px;">
        <div class="audit-stat-title" style="font-size: 0.72rem;">🔵 中危异味 (P2)</div>
        <div class="audit-stat-value" style="color: #60a5fa; font-size: 1.2rem;">{med_cnt} <span style="font-size: 0.75rem; color: #94a3b8;">处</span></div>
        <div class="audit-stat-sub" style="font-size: 0.68rem;">参数过多</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # 筛选与导出报告
        rf_c1, rf_c2 = st.columns([1.6, 1.2], gap="small")
        with rf_c1:
            severity_filter = st.selectbox(
                "严重级别筛选",
                ["全部严重度", "🔴 仅致命 (P0)", "🟠 仅高危 (P1)", "🔵 仅中危 (P2)"],
                index=0,
                label_visibility="collapsed",
                key="right_sev_filter"
            )
        with rf_c2:
            with st.popover("📥 导出报告", use_container_width=True):
                rep_lines = [
                    f"# Python 源代码安全与缺陷审计报告",
                    f"- **审计目标**: `{Path(st.session_state.get('active_file_name', 'source.py')).name}`",
                    f"- **安全评分**: **{health_score} / 100** ({grade_text})",
                    f"- **缺陷总计**: {len(issues)} 处 (致命 {crit_cnt} | 高危 {high_cnt} | 中危 {med_cnt})",
                    f"\n## 一、缺陷清单与深度整改方案",
                ]
                for idx, iss in enumerate(issues, 1):
                    sev_str = getattr(iss.severity, 'value', str(iss.severity))
                    line_no = getattr(iss, 'line', 1)
                    cat_name = getattr(iss, 'category', '未知分类')
                    desc = getattr(iss, 'description', '')
                    sugg = getattr(iss, 'suggestion', '')
                    snip = getattr(iss, 'snippet', '')
                    rep_lines.append(f"### [R-{idx:02d}] [{sev_str}] 第 {line_no} 行: {cat_name}")
                    if snip:
                        rep_lines.append(f"```python\n# 缺陷代码行\n{snip}\n```")
                    rep_lines.append(f"- **机理剖析**: {desc}")
                    rep_lines.append(f"- **修复建议**: {sugg}\n")

                if st.session_state.get("analysis_result"):
                    p2_rep = st.session_state.analysis_result.get("phase2", {}).get("report", "")
                    if p2_rep:
                        rep_lines.append(f"\n## 二、专家智能体综合审计报告\n{p2_rep}")

                full_report_md = "\n".join(rep_lines)
                st.download_button(
                    label="💾 下载 Markdown 报告",
                    data=full_report_md,
                    file_name=f"audit_report_{Path(st.session_state.get('active_file_name', 'code')).stem}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

        # 过滤缺陷
        filtered_issues = []
        for iss in issues:
            sev_val = getattr(iss.severity, 'value', str(iss.severity))
            if "致命" in severity_filter and sev_val != "CRITICAL":
                continue
            if "高危" in severity_filter and sev_val != "HIGH":
                continue
            if "中危" in severity_filter and sev_val != "MEDIUM":
                continue
            filtered_issues.append(iss)

        # 风险卡片纵向滚动列表 (高度 540px)
        risk_box = st.container(height=540)
        with risk_box:
            if filtered_issues:
                for idx, iss in enumerate(filtered_issues, 1):
                    sev_val = getattr(iss.severity, 'value', str(iss.severity))
                    sev_cls = "critical" if sev_val == "CRITICAL" else ("high" if sev_val == "HIGH" else "medium")
                    line_no = getattr(iss, "line", 1)
                    cat_name = getattr(iss, "category", "潜在缺陷")
                    desc = getattr(iss, "description", "")
                    sugg = getattr(iss, "suggestion", "")
                    snippet = getattr(iss, "snippet", "")

                    snippet_html = f'<div class="issue-snippet-box">▶ {snippet}</div>' if snippet else ''
                    fix_html = f'<div class="issue-suggestion-box">💡 <strong>修复建议：</strong><br/>{sugg}</div>'

                    st.markdown(f"""
<div class="issue-card {sev_cls}" style="margin-bottom: 8px;">
    <div class="issue-header">
        <div class="issue-title-group">
            <span class="issue-id">[R-{idx:02d}]</span>
            <span class="issue-pill {sev_cls}">{sev_val}</span>
            <span class="issue-category-name">{cat_name}</span>
        </div>
        <span class="issue-loc">第 {line_no} 行</span>
    </div>
    {snippet_html}
    <div class="issue-desc">{desc}</div>
    {fix_html}
</div>
""", unsafe_allow_html=True)

                    # 卡片专属操作
                    act_c1, act_c2 = st.columns([1, 1], gap="small")
                    with act_c1:
                        if st.button(f"🛠️ 一键修复", key=f"btn_fix_{idx}", use_container_width=True):
                            st.session_state.pending_task = {
                                "prompt": f"/refactor: 请针对第 {line_no} 行的【{cat_name}】漏洞进行彻底修复并输出完整重构代码，杜绝运行时异常",
                                "task_type": "refactor"
                            }
                            st.toast(f"已向专家发起针对 [R-{idx:02d}] 的修复！", icon="🛠️")
                            st.rerun()
                    with act_c2:
                        if st.button(f"💬 深度追问", key=f"btn_ask_{idx}", use_container_width=True):
                            st.session_state.pending_task = {
                                "prompt": f"/review: 请向我深入解释第 {line_no} 行出现的【{cat_name}】漏洞：在何种特定业务输入或边界条件下会触发？它的底层运行机制是什么？如何彻底杜绝？",
                                "task_type": "review"
                            }
                            st.toast(f"已向 Copilot 发起深度追问！", icon="💬")
                            st.rerun()
            else:
                st.success("✅ 当前筛选条件下无缺陷，代码符合规范！")

            # 专家 Agent 深度综合审计报告折叠盒
            if st.session_state.get("analysis_result"):
                p2 = st.session_state.analysis_result.get("phase2", {})
                if p2.get("report"):
                    with st.expander("📄 查看专家 Agent 深度综合审计长篇报告", expanded=False):
                        st.markdown(p2["report"])

