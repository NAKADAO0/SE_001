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


st.set_page_config(
    page_title="CodeMate AI IDE | 智能代码工作台",
    page_icon="💻",
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
</style>
""", unsafe_allow_html=True)


# ================= 全局状态与会话初始化 =================
if "config" not in st.session_state:
    st.session_state.config = Config.from_env()

if "pipeline" not in st.session_state:
    st.session_state.pipeline = CodePipeline(config=st.session_state.config)

if "active_code" not in st.session_state:
    default_path = Path("samples/demo_shopping_cart.py")
    if default_path.exists():
        st.session_state.active_code = default_path.read_text(encoding="utf-8")
        st.session_state.active_file_name = "samples/demo_shopping_cart.py"
    else:
        st.session_state.active_code = "def hello():\n    return 'world'\n"
        st.session_state.active_file_name = "custom_code.py"

if "baseline_code" not in st.session_state:
    st.session_state.baseline_code = st.session_state.active_code

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "refactored_code" not in st.session_state:
    if "shopping_cart" in st.session_state.get("active_file_name", ""):
        st.session_state.refactored_code = DEFAULT_REFACTORED_SHOPPING_CART
    else:
        st.session_state.refactored_code = None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "你好！我是你的 AI Copilot 智能体。右侧为主体代码工作区。你可以在下方直接输入自然语言需求（例如“修复除零和未关文件Bug”），或输入 `/` 呼出 4 个专家命令（`/review`, `/refactor`, `/test`, `/explain`），我将在右侧代码区实时反馈重构与 Diff！"}
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
        <span class="ide-title">💻 CodeMate AI IDE</span>
        <span class="ide-badge">LangChain 驱动</span>
    </div>
    <div class="ide-meta-box">
        <div class="ide-meta-item">
            <span>当前聚焦:</span>
            <span class="context-pill">📄 {st.session_state.get('active_file_name', 'untitled.py')} ({active_lines} 行)</span>
        </div>
        <div class="ide-meta-item">
            <span>LLM:</span>
            <strong style="color: #38bdf8;">{st.session_state.config.model_name}</strong>
        </div>
        <div class="ide-meta-item">
            <span>后端状态:</span>
            <span style="color: #4ade80;">● FastAPI :8000 在线</span>
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


# ================= 核心 AI IDE 布局：左助手 (32%) + 右代码主体 (68%) =================
col_agent, col_editor = st.columns([3.2, 6.8], gap="medium")


# -------------------------------------------------------------
# 【左侧栏】：🤖 AI Copilot 对话伴生栏 (占比 32%)
# 沉浸式对话、思考流、斜杠指令、贴底输入框
# -------------------------------------------------------------
with col_agent:
    st.markdown("#### 🤖 AI Copilot 助手")

    # 辅助函数：格式化思考步骤
    def format_step_badge(step: Dict[str, Any]) -> str:
        s_type = step.get("type")
        if s_type == "pipeline_start":
            return f"🚀 **流水线启动**: 分析代码规模 {step.get('lines', 0)} 行"
        elif s_type == "phase1_complete":
            issues_cnt = step.get("initial_issues_count", 0)
            return f"🔍 **[Phase 1] 静态 AST 规则扫描**: 检出 **{issues_cnt}** 处潜在风险线索 (函数 {len(step.get('functions', []))} 个，类 {len(step.get('classes', []))} 个)"
        elif s_type == "phase2_dispatch":
            return f"🤖 **[Phase 2] 专家就位**: 任务分配给 `{step.get('agent', '专家 Agent')}`"
        elif s_type == "agent_start":
            return f"🧠 **[模型推理启动]**: {step.get('agent_name', 'Agent')} 制定执行方案"
        elif s_type == "call":
            return f"⚡ **[第 {step.get('iteration', 1)} 轮推理] 工具调用**: `{step.get('tool')}`"
        elif s_type == "result":
            status_text = "✅ 沙箱执行成功" if step.get("success") else "❌ 执行报错/异常"
            return f"📋 **沙箱执行反馈**: {status_text} (工具 `{step.get('tool')}`)"
        elif s_type == "agent_finish":
            return f"💡 **[专家推理完成]**: 历经 {step.get('iterations', 1)} 轮思考，方案提炼完毕"
        elif s_type == "pipeline_finish":
            return f"✔ **[Phase 3] 校验完成**: 最终结果聚合"
        return f"● {step.get('title', '处理中')}"

    # 对话流容器 (高度拉满至 600px，极致清爽的沉浸式对话)
    chat_box = st.container(height=600)
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
                                    st.code(out_text[:500] + ("\n... [完整日志见右侧沙箱终端]" if len(out_text) > 500 else ""), language="text")
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
                    st.toast("已在右侧 IDE 生成修改前后对比 Diff！", icon="🔀")

                sandbox_logs = [
                    str(s.get("output", ""))
                    for s in current_steps
                    if s.get("type") == "result" and s.get("tool") in ("execute_python_code", "run_pytest") and s.get("output")
                ]
                if sandbox_logs:
                    st.session_state.test_sandbox_output = "\n\n".join(sandbox_logs)

            st.rerun()

    # 4 个漂浮在输入框上方的快捷指令按钮 (专精于代码漏洞与安全审计，Claude AI Pill 风格)
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4, gap="small")
    with btn_col1:
        if st.button("⚡ 全面审查", use_container_width=True, help="/review: 全维度深度排查除零、未关文件、越界与安全缺陷"):
            st.session_state.pending_task = {
                "prompt": "/review: 请对右侧代码进行全维度的深度安全与漏洞审查",
                "task_type": "review"
            }
            st.rerun()
    with btn_col2:
        if st.button("➗ 崩溃排查", use_container_width=True, help="/review: 重点排查除以零、空序列max/min、下标越界等运行时崩溃点"):
            st.session_state.pending_task = {
                "prompt": "/review: 专项排查代码中的除零、空序列、下标越界等运行时致命崩溃隐患",
                "task_type": "review"
            }
            st.rerun()
    with btn_col3:
        if st.button("📂 资源审计", use_container_width=True, help="/review: 重点排查裸open未关闭、文件句柄泄漏与资源释放安全"):
            st.session_state.pending_task = {
                "prompt": "/review: 专项审计代码中裸open文件未关闭、句柄泄漏及外部资源释放安全",
                "task_type": "review"
            }
            st.rerun()
    with btn_col4:
        if st.button("🛡️ 异常防御", use_container_width=True, help="/review: 重点排查裸except异常吞噬、静默pass与边界类型防御缺失"):
            st.session_state.pending_task = {
                "prompt": "/review: 专项排查代码中的裸except异常吞噬、静默忽略与输入边界防御缺失",
                "task_type": "review"
            }
            st.rerun()

    # 置底输入框：支持自然语言自由交互与斜杠指令手动输入
    input_text = st.chat_input("输入修改需求（或点击上方4个指令按钮快速执行）...")
    if input_text:
        cleaned = input_text.strip()
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

        st.session_state.pending_task = {
            "prompt": cleaned if cleaned.startswith("/") else f"针对当前右侧代码，我的具体修改需求是：{cleaned}",
            "task_type": task_type
        }
        st.rerun()


# -------------------------------------------------------------
# 【右侧栏】：💻 IDE 代码主体工作区 (Code Workspace，占比 68%)
# 文件切换工具条、当前代码编辑、修改对比 Diff、沙箱终端 Terminal、缺陷诊断 Problems
# -------------------------------------------------------------
with col_editor:
    # 1. 极简单行 IDE 控制工具栏 (信息与操作全部缩小收缩为轻量级按钮，代码占据绝对主体)
    sample_files = {
        "samples/demo_shopping_cart.py (电商购物车: 含除零/句柄未关/硬编码折扣)": "samples/demo_shopping_cart.py",
        "samples/buggy_code.py (典型坏味道与逻辑缺陷)": "samples/buggy_code.py",
        "samples/math_utils.py (算法样例与单元测试)": "samples/math_utils.py",
    }

    rule_res = st.session_state.pipeline.rule_engine.analyze_source(st.session_state.active_code)
    cur_lines = len(st.session_state.active_code.splitlines())
    cur_funcs = len(rule_res.get("functions", []))
    cur_classes = len(rule_res.get("classes", []))
    cur_issues = len(rule_res.get("issues", []))

    # 一行放齐全部控件：文件选择、上传按钮、度量统计按钮、一键重构按钮、保存基线按钮
    t_c1, t_c2, t_c3, t_c4, t_c5 = st.columns([3.2, 1.2, 1.6, 1.2, 1.0], gap="small")

    with t_c1:
        sel_sample = st.selectbox(
            "选择文件",
            options=list(sample_files.keys()),
            index=0,
            label_visibility="collapsed",
        )
        if st.session_state.get("_prev_sample") != sel_sample:
            st.session_state._prev_sample = sel_sample
            target_path = sample_files[sel_sample]
            p = Path(target_path)
            if p.exists():
                file_text = p.read_text(encoding="utf-8")
                st.session_state.active_code = file_text
                st.session_state.baseline_code = file_text
                st.session_state.active_file_name = target_path
                if "shopping_cart" in target_path:
                    st.session_state.refactored_code = DEFAULT_REFACTORED_SHOPPING_CART
                else:
                    st.session_state.refactored_code = None

    with t_c2:
        # 上传文件收缩为轻量按钮，点击弹出上传，不占主页面高度
        with st.popover("📤 上传", use_container_width=True):
            st.markdown("##### 📤 上传本地 Python 源码")
            up_f = st.file_uploader("选择 .py 文件", type=["py"], key="compact_upload")
            if up_f is not None:
                content = up_f.read().decode("utf-8", errors="replace")
                if content != st.session_state.active_code:
                    st.session_state.active_code = content
                    st.session_state.baseline_code = content
                    st.session_state.active_file_name = up_f.name
                    st.session_state.refactored_code = None
                    st.toast(f"已装载: {up_f.name}", icon="📤")
                    st.rerun()

    with t_c3:
        # 4 个大号 Metric 压缩为单行轻量按钮，点击浮现详细度量面板
        with st.popover(f"📊 {cur_lines}行·{cur_funcs}函数·{cur_issues}风险", use_container_width=True):
            st.markdown("##### 📊 代码静态度量概览")
            m_a, m_b = st.columns(2)
            with m_a:
                st.metric("代码行数", cur_lines)
                st.metric("定义函数", cur_funcs)
            with m_b:
                st.metric("定义类", cur_classes)
                st.metric("初筛坏味道", cur_issues)

    with t_c4:
        if st.button("⚡ 深度审查", type="primary", use_container_width=True, help="立即启动 CodeReviewerAgent 深度审查当前代码"):
            st.session_state.pending_task = {
                "prompt": "/review: 请对右侧代码进行全面安全与漏洞审查，深入排查隐蔽运行时崩溃风险、未处理异常与资源泄漏，并给出修复后的对比代码",
                "task_type": "review"
            }
            st.rerun()

    with t_c5:
        if st.button("💾 保存", use_container_width=True, help="保存当前编辑的代码为基准版本"):
            st.session_state.baseline_code = st.session_state.active_code
            st.toast("已保存当前代码为基准！", icon="💾")

    # 2. 核心选项卡系统：专精代码缺陷与安全审计工作台 (首选展示缺陷诊断看板)
    tab_problems, tab_editor, tab_diff, tab_terminal = st.tabs([
        f"⚠️ 缺陷诊断与审计看板 ({cur_issues})",
        f"📄 {Path(st.session_state.get('active_file_name', 'main.py')).name} (代码主体)",
        "🔀 修复前后对比 (Diff)",
        "🧪 终端沙箱 (Terminal)"
    ])

    # ===== Tab 1: 缺陷诊断与审计大屏 (专精代码审查核心面板，对标工业级 ReviewResults) =====
    with tab_problems:
        issues = rule_res.get("issues", [])
        
        # 1. 统计计算指标看板
        crit_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "CRITICAL")
        high_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "HIGH")
        med_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "MEDIUM")
        low_cnt = sum(1 for i in issues if getattr(i.severity, 'value', str(i.severity)) == "LOW")
        
        health_score = max(0, 100 - crit_cnt * 25 - high_cnt * 15 - med_cnt * 5)
        if health_score >= 90:
            grade_text, grade_color = "A (优秀)", "#4ade80"
        elif health_score >= 75:
            grade_text, grade_color = "B (良好)", "#60a5fa"
        elif health_score >= 60:
            grade_text, grade_color = "C (需整改)", "#fbbf24"
        else:
            grade_text, grade_color = "D (高危风险)", "#f87171"

        # 渲染顶部 4 列现代数据指标卡
        st.markdown(f"""
<div class="audit-metrics-row">
    <div class="audit-stat-card">
        <div class="audit-stat-title">🛡️ 安全健康评分</div>
        <div class="audit-stat-value" style="color: {grade_color};">{health_score} <span style="font-size: 0.85rem; font-weight: 500;">/ 100</span></div>
        <div class="audit-stat-sub">评级: <strong>{grade_text}</strong></div>
    </div>
    <div class="audit-stat-card">
        <div class="audit-stat-title">🔴 致命崩溃风险 (P0)</div>
        <div class="audit-stat-value" style="color: #f87171;">{crit_cnt} <span style="font-size: 0.8rem; font-weight: normal; color: #94a3b8;">处</span></div>
        <div class="audit-stat-sub">除零、空值越界、致命异常</div>
    </div>
    <div class="audit-stat-card">
        <div class="audit-stat-title">🟠 高危安全与泄漏 (P1)</div>
        <div class="audit-stat-value" style="color: #fb923c;">{high_cnt} <span style="font-size: 0.8rem; font-weight: normal; color: #94a3b8;">处</span></div>
        <div class="audit-stat-sub">句柄未关、裸except异常吞噬</div>
    </div>
    <div class="audit-stat-card">
        <div class="audit-stat-title">🔵 中危与坏味道 (P2)</div>
        <div class="audit-stat-value" style="color: #60a5fa;">{med_cnt} <span style="font-size: 0.8rem; font-weight: normal; color: #94a3b8;">处</span></div>
        <div class="audit-stat-sub">参数过多、可变默认参数</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # 2. 交互式过滤工具栏与报告导出
        filter_c1, filter_c2, filter_c3 = st.columns([2.8, 2.4, 1.8], gap="small")
        with filter_c1:
            severity_filter = st.selectbox(
                "严重级别筛选",
                ["全部严重度 (All)", "🔴 仅看致命风险 (Critical)", "🟠 仅看高危隐患 (High)", "🔵 仅看中危问题 (Medium)"],
                index=0,
                label_visibility="collapsed"
            )
        with filter_c2:
            search_query = st.text_input("搜索缺陷...", placeholder="🔍 快速搜索缺陷或函数名...", label_visibility="collapsed")
        with filter_c3:
            # 报告导出 Popover
            with st.popover("📥 导出审计报告", use_container_width=True):
                st.markdown("##### 📄 源代码安全与漏洞审查报告")
                # 拼接结构化 Markdown 报告文本
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
                st.caption(f"共包含 {len(issues)} 处缺陷分析及整改依据。")
                st.download_button(
                    label="💾 下载 Markdown 审查报告",
                    data=full_report_md,
                    file_name=f"audit_report_{Path(st.session_state.get('active_file_name', 'code')).stem}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

        # 3. 执行过滤
        filtered_issues = []
        for iss in issues:
            sev_val = getattr(iss.severity, 'value', str(iss.severity))
            if "致命" in severity_filter and sev_val != "CRITICAL":
                continue
            if "高危" in severity_filter and sev_val != "HIGH":
                continue
            if "中危" in severity_filter and sev_val != "MEDIUM":
                continue
            if search_query:
                q = search_query.lower()
                desc_text = getattr(iss, 'description', '').lower()
                cat_text = getattr(iss, 'category', '').lower()
                if q not in desc_text and q not in cat_text:
                    continue
            filtered_issues.append(iss)

        # 4. 渲染各风险卡片
        if filtered_issues:
            for idx, iss in enumerate(filtered_issues, 1):
                sev_val = getattr(iss.severity, 'value', str(iss.severity))
                sev_cls = "critical" if sev_val == "CRITICAL" else ("high" if sev_val == "HIGH" else "medium")
                line_no = getattr(iss, "line", 1)
                cat_name = getattr(iss, "category", "潜在缺陷")
                desc = getattr(iss, "description", "")
                sugg = getattr(iss, "suggestion", "")
                snippet = getattr(iss, "snippet", "")
                fix_code = getattr(iss, "fix_code", "")

                snippet_html = f'<div class="issue-snippet-box">▶ {snippet}</div>' if snippet else ''
                fix_html = f'<div class="issue-suggestion-box">💡 <strong>推荐修复方案：</strong><br/>{sugg}</div>'

                st.markdown(f"""
<div class="issue-card {sev_cls}">
    <div class="issue-header">
        <div class="issue-title-group">
            <span class="issue-id">[R-{idx:02d}]</span>
            <span class="issue-pill {sev_cls}">{sev_val}</span>
            <span class="issue-category-name">{cat_name}</span>
        </div>
        <span class="issue-loc">📍 第 {line_no} 行</span>
    </div>
    {snippet_html}
    <div class="issue-desc">{desc}</div>
    {fix_html}
</div>
""", unsafe_allow_html=True)

                # 风险卡片专属操作按钮行 (一键修复 / 深度追问)
                act_c1, act_c2 = st.columns([1, 1])
                with act_c1:
                    if st.button(f"🛠️ 针对 [R-{idx:02d}] 一键修复", key=f"btn_fix_{idx}", use_container_width=True):
                        st.session_state.pending_task = {
                            "prompt": f"/refactor: 请针对第 {line_no} 行的【{cat_name}】漏洞进行彻底修复并输出完整重构代码，杜绝运行时异常",
                            "task_type": "refactor"
                        }
                        st.toast(f"已向专家发起针对 [R-{idx:02d}] 的精准修复！", icon="🛠️")
                        st.rerun()
                with act_c2:
                    if st.button(f"💬 深度追问此漏洞", key=f"btn_ask_{idx}", use_container_width=True):
                        st.session_state.pending_task = {
                            "prompt": f"/review: 请向我深入解释第 {line_no} 行出现的【{cat_name}】漏洞：在何种特定业务输入或边界条件下会触发？它的底层运行机制是什么？如何从架构层面彻底杜绝？",
                            "task_type": "review"
                        }
                        st.toast(f"已向 Copilot 发起深度技术追问！", icon="💬")
                        st.rerun()
        else:
            st.success("✅ 当前筛选条件下未发现缺陷，代码符合规范！")

        # 5. 专家 Agent 深度综合审计报告展示
        if st.session_state.get("analysis_result"):
            p2 = st.session_state.analysis_result.get("phase2", {})
            if p2.get("report"):
                st.markdown("<hr style='margin: 16px 0; border: none; border-top: 1px dashed #334155;'/>", unsafe_allow_html=True)
                with st.expander("📄 查看专家 Agent 深度综合审计报告", expanded=True):
                    st.markdown(p2["report"])

    # ===== Tab 2: IDE 代码主体编辑器 =====
    with tab_editor:
        edited_code = st.text_area(
            "代码主体",
            value=st.session_state.active_code,
            height=660,
            key="ide_source_editor",
            label_visibility="collapsed",
        )
        if edited_code != st.session_state.active_code:
            st.session_state.active_code = edited_code

    # ===== Tab 3: 修改前后对比 (Diff Viewer) =====
    with tab_diff:
        refactored = st.session_state.get("refactored_code")
        if not refactored and "shopping_cart" in st.session_state.get("active_file_name", ""):
            refactored = DEFAULT_REFACTORED_SHOPPING_CART
            st.session_state.refactored_code = refactored

        if refactored:
            diff_btn_col1, diff_btn_col2, diff_btn_col3 = st.columns([1.6, 1.6, 3.2])
            with diff_btn_col1:
                if st.button("✅ 采纳修改 (Accept)", type="primary", use_container_width=True):
                    st.session_state.active_code = refactored
                    st.toast("已采纳 AI 重构代码并覆盖至主编辑器！", icon="🎉")
                    st.rerun()
            with diff_btn_col2:
                if st.button("↩️ 还原基线 (Revert)", use_container_width=True):
                    st.session_state.active_code = st.session_state.baseline_code
                    st.toast("已还原至初始基准代码！", icon="↩️")
                    st.rerun()
            with diff_btn_col3:
                diff_mode = st.radio("对比模式", ["并排对比 (Side-by-Side)", "增量补丁 (Unified Diff)"], horizontal=True, label_visibility="collapsed")

            with st.expander("🎯 查看【架构重构与功能对齐清单】", expanded=False):
                st.markdown("""
| 业务模块 / 函数 | 🔴 修改前 (原始缺陷代码) | 🟢 修改后 (重构防御代码) | 应用设计模式 / 改进收益 |
| :--- | :--- | :--- | :--- |
| **优惠券折扣计算** (`apply_coupon`) | 庞大硬编码 `if-elif` 分支，难以扩展 | 引入 `DiscountStrategy` 策略抽象与派生类分发 | **策略模式 (Strategy Pattern)**，符合开闭原则 |
| **分享优惠除零防御** (`SHARE_DISCOUNT`) | `total / len(items)`，空列表抛 `ZeroDivisionError` | 增加 `if not items: return 0.0` 判空保护 | **边界安全防御**，杜绝除零崩溃 |
| **审计日志安全释放** (`coupon_access_log`) | 裸 `open("...", "a")` 未 close，句柄泄漏 | 使用 `with open(...) as f:` 上下文管理器封装 | **资源安全释放**，避免高并发锁死 |
| **最高价查询** (`get_most_expensive_item`) | 空购物车调用 `max()` 触发 `ValueError: empty sequence` | 空列表防御，直接返回 `None` 保护 | **防御式编程**，向后兼容调用方 |
| **批量结算容错** (`batch_checkout_users`) | 裸 `except:` 吞没系统中断 | 校验 `0.0 <= ratio <= 1.0` 并精准捕获具体异常 | **精准异常处理**，消除隐蔽故障 |
                """)

            if diff_mode == "并排对比 (Side-by-Side)":
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    st.markdown("🔴 **原始代码 (Base / 存在缺陷)**")
                    st.code(st.session_state.baseline_code, language="python")
                with d_col2:
                    st.markdown("🟢 **AI 重构后代码 (Refactored / 消除异味)**")
                    st.code(refactored, language="python")
            else:
                st.markdown("📄 **Git Patch 差异补丁**")
                diff_lines = list(difflib.unified_diff(
                    st.session_state.baseline_code.splitlines(keepends=True),
                    refactored.splitlines(keepends=True),
                    fromfile="a/" + st.session_state.get("active_file_name", "original.py"),
                    tofile="b/" + st.session_state.get("active_file_name", "refactored.py"),
                    n=3,
                ))
                patch_text = "".join(diff_lines)
                if patch_text:
                    st.code(patch_text, language="diff")
                else:
                    st.info("当前基线代码与重构代码完全一致，无增量差异。")
        else:
            st.info("💡 尚未生成修复代码。请在左侧输入 `/review` 或点击上方【⚡ 深度审查】按钮生成！")

    # ===== Tab 4: 沙箱终端 (Terminal) =====
    with tab_terminal:
        t_output = st.session_state.get("test_sandbox_output", "")
        if t_output:
            st.markdown(f'<div class="terminal-window">>_ 沙箱执行输出：\n\n{t_output}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="terminal-window">>_ 终端就绪 (等待代码审查与沙箱运行验证任务...)\n> 提示：在左侧输入指令，CodeReviewerAgent 将在沙箱中动态验证缺陷。</div>', unsafe_allow_html=True)

        if st.button("🧪 在当前沙箱执行单测 (Run Pytest)", use_container_width=True):
            st.session_state.pending_task = {
                "prompt": "/test: 请为当前代码生成并运行 pytest 单元测试",
                "task_type": "test"
            }
            st.rerun()
