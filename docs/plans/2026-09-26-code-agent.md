# CodeMate-Agent (智能代码助手智能体) 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 搭建一个基于原生 OpenAI/DeepSeek API 的轻量高效全能代码助手 Agent，具备输入-推理-工具调用-输出的完整 ReAct 循环，集成代码执行、文件读写、静态分析工具，支持上下文记忆与自纠错，提供 CLI 与 Streamlit Web 双交互界面。

**Architecture:** 采用分层模块化架构：工具注册层（Registry）+ 记忆管理层（Memory）+ LLM抽象层（LLM Client）+ 核心调度层（CodeAgent ReAct Loop）+ 双展示层（Rich CLI / Streamlit Web）。

**Tech Stack:** Python 3.10+, OpenAI SDK (DeepSeek API 兼容), Rich, Streamlit, Pytest, Tenacity, Pydantic.

---

### Task 1: 项目基础骨架与环境配置
**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `codemate/__init__.py`
- Create: `codemate/config.py`
- Test: `tests/test_config.py`

**Step 1: 编写测试用例 `tests/test_config.py`**
验证环境变量加载与默认配置行为。
**Step 2: 运行测试验证失败**
**Step 3: 实现 `codemate/config.py` 配置模块**
**Step 4: 运行测试验证通过**

---

### Task 2: 工具层实现 (Tool Registry & Builtin Tools)
**Files:**
- Create: `codemate/tools/__init__.py`
- Create: `codemate/tools/registry.py`
- Create: `codemate/tools/file_tools.py`
- Create: `codemate/tools/exec_tools.py`
- Create: `codemate/tools/analysis_tools.py`
- Test: `tests/test_tools.py`

**Step 1: 编写工具系统测试 `tests/test_tools.py`**
测试工具装饰器、参数校验、文件读写、安全代码执行（沙箱与超时）与 AST 静态语法检查。
**Step 2: 运行测试验证失败**
**Step 3: 实现工具注册中心与具体代码工具**
**Step 4: 运行测试验证通过**

---

### Task 3: 上下文记忆管理与 Prompt 模板
**Files:**
- Create: `codemate/memory.py`
- Create: `codemate/prompts.py`
- Test: `tests/test_memory.py`

**Step 1: 编写记忆系统测试 `tests/test_memory.py`**
测试多轮对话记录、滑动窗口裁剪、工具调用序列回填与历史清空。
**Step 2: 运行测试验证失败**
**Step 3: 实现 `codemate/memory.py` 与 `codemate/prompts.py`**
**Step 4: 运行测试验证通过**

---

### Task 4: LLM 客户端与核心 Agent 循环 (ReAct + Self-Correction)
**Files:**
- Create: `codemate/llm.py`
- Create: `codemate/agent.py`
- Test: `tests/test_agent.py`

**Step 1: 编写 Agent 逻辑测试 `tests/test_agent.py`（使用 Mock LLM）**
测试意图理解、工具调用分发、结果反馈再推理以及最大迭代防死循环机制。
**Step 2: 运行测试验证失败**
**Step 3: 实现 `codemate/llm.py` 与 `codemate/agent.py`**
**Step 4: 运行测试验证通过**

---

### Task 5: 交互界面构建 (Rich CLI + Streamlit Web)
**Files:**
- Create: `cli.py`
- Create: `web_app.py`
- Create: `samples/buggy_code.py`
- Create: `samples/math_utils.py`

**Step 1: 编写示例代码用于演示（带有典型Bug和待优化设计）**
**Step 2: 构建美观终端交互 CLI（支持流式/动画/Markdown/快捷指令）**
**Step 3: 构建现代化 Streamlit Web 应用（工具调用可视化卡片、会话管理、侧边栏配置）**
**Step 4: 验证 CLI 与 Web UI 启动与交互**

---

### Task 6: 编写工程文档与设计方案 (README.md & Design.md)
**Files:**
- Create: `README.md`
- Create: `Design.md`

**Step 1: 编写高标准 README.md（快速启动、环境配置、功能图谱、示例演示）**
**Step 2: 编写专业课程设计报告级 Design.md（C4架构图、时序图、设计模式、容错设计、创新点）**
**Step 3: 全套测试验证与代码打包准备**
