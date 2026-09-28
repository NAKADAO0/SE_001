# 🤖 CodeMate-Agent: 工业级多智能体协同代码分析与研发工作台

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/Architecture-Multi--Agent%20Pipeline-orange.svg)]()
[![LLM Support](https://img.shields.io/badge/LLM-DeepSeek%20(deepseek--flash)-purple.svg)]()
[![Backend](https://img.shields.io/badge/Backend-FastAPI-teal.svg)]()
[![Tests](https://img.shields.io/badge/tests-32%20passed-brightgreen.svg)]()

> **CodeMate-Agent** 是参考大型工业级智能体系统（`ruanfu_sheng`）架构规范深度打造的代码助手智能体系统。系统采用 **两阶段编排流水线 (Two-Phase Pipeline)** + **垂直领域多 Agent 专家矩阵 (Multi-Agent Team)** 范式，原生适配 **DeepSeek (默认 deepseek-flash)** 与 OpenAI API，融合了**代码审查、逻辑解释、单元测试自动生成与沙箱验证、架构设计模式重构**四大核心能力，支持微服务化解耦部署与一键运维。

---

## 📂 工业级项目工程结构

```text
SoftEngineeing/
├── backend/                       # RESTful 微服务层 (FastAPI)
│   ├── app.py                     # API 服务主入口 (提供 /review, /test, /refactor, /explain 等路由)
│   └── schemas.py                 # Pydantic 强类型请求与响应契约
├── code_analyzer/                 # 核心分析与多智能体引擎 (对标 ruanfu_sheng/risk_analyzer)
│   ├── core/                      # 基础核心模块
│   │   ├── config.py              # 配置中心 (优先加载 deepseek-flash)
│   │   ├── llm_client.py          # LLM 客户端 (带 Tenacity 指数退避重试)
│   │   └── memory.py              # 上下文记忆与滑动窗口
│   ├── schemas/                   # 领域数据实体模型
│   │   └── code_types.py          # ReviewReport, BugItem, TestExecutionResult, RefactorPlan
│   ├── query/                     # 核心分析管线
│   │   ├── pipeline.py            # 两阶段核心流水线编排器 (Phase 1 规则初筛 -> Phase 2 Agent 分发 -> Verifier)
│   │   ├── rule_engine.py         # 静态语法规则与 AST 异味引擎
│   │   └── verifier.py            # 结果交叉校验与去重聚合器
│   ├── agents/                    # 垂直领域多 Agent 专家矩阵 (对标 ruanfu_sheng/query/agents)
│   │   ├── base_agent.py          # 智能体基类 (ReAct 循环、Tool 分发与观察者模式)
│   │   ├── reviewer_agent.py      # Agent 1: 代码质量与安全审计专家
│   │   ├── explainer_agent.py     # Agent 2: 逻辑解构与时空复杂度专家
│   │   ├── tester_agent.py        # Agent 3: 单元测试自动生成与执行验证专家 (自纠错闭环)
│   │   └── refactor_agent.py      # Agent 4: 架构坏味道消除与设计模式重构专家
│   └── tools/                     # 工具层
│       ├── registry.py            # 工具注册表 (@tool 装饰器、JSON Schema 反射)
│       ├── file_tools.py          # 文件工具集 (read_file, write_file, list_directory)
│       └── exec_tools.py          # 隔离执行沙箱 (execute_python_code, run_pytest，带超时防死循环)
├── frontend/                      # 现代化前端界面
│   └── web_app.py                 # 交互式 Web 控制台
├── tests/                         # 全面自动化测试套件 (32 个用例全部通过)
│   ├── test_pipeline.py           # 两阶段流水线与规则引擎测试
│   ├── test_agent.py              # Agent ReAct 循环测试 (Mock LLM)
│   ├── test_tools.py              # 6 个核心工具单元测试
│   ├── test_memory.py             # 记忆与滑动窗口测试
│   └── test_config.py             # 配置模块测试
├── samples/                       # 演示代码资产
│   ├── demo_shopping_cart.py      # 电商购物车与结算模块 (涵盖除零、句柄泄露、空车崩溃等典型缺陷)
│   ├── buggy_code.py              # 缺陷样例
│   └── math_utils.py              # 算法样例
├── start_all.bat                  # 一键启动全部微服务 (对标 ruanfu_sheng/start_all.bat)
├── kill_all.bat                   # 一键停止全部后台服务 (对标 ruanfu_sheng/kill_all.bat)
├── AGENTS.md                      # 多智能体架构约定与端口清单 (对标 ruanfu_sheng/AGENTS.md)
├── docs/                          # 规范工程文档
│   ├── api_spec.md                # RESTful API 接口规范
│   └── plans/                     # 实施计划与架构演进稿
├── package_submission.py          # 一键作业打包脚本 (学号姓名.zip，远小于 200MB)
├── requirements.txt               # 依赖清单
├── .env.example                   # 环境变量配置模板
├── README.md                      # 本手册
└── Design.md / Desgin.md          # 深度系统架构设计文档
```

---

## 🌟 架构核心亮点

1. **两阶段混合编排流水线 (Two-Phase Pipeline)**：
   - **Phase 1 (Fast Path 零 LLM)**：通过 AST 语法树在毫秒级内完成语法校验、函数类要素抽取及初步代码坏味道扫描；
   - **Phase 2 (Deep Reasoning)**：将结构化线索注入垂直领域专家 Agent，按需调用隔离执行沙箱深入排查；
   - **Phase 3 (Verifier)**：交叉去重并按 `CRITICAL > HIGH > MEDIUM > LOW` 定级排序。
2. **多 Agent 专家协同体系**：
   - 包含 **CodeReviewerAgent**、**TestGeneratorAgent**、**CodeRefactorAgent** 与 **CodeExplainerAgent** 四大独立专家，分工极度明确。
3. **沉浸式交互工作台 (Master Studio Layout)**：
   - **最左侧**：**一整个完整的 AI Agent 对话栏**，支持多轮连续对话进行各种代码修改；支持 `/review`、`/refactor`、`/test`、`/explain` 四大斜杠指令快速派发任务；
   - **右侧栏**：**代码与对比工作区**，包含当前源码在线编辑、**修改前后对比 (Diff Viewer)**（并排 Side-by-Side 与 Git 增量视图）、缺陷诊断清单及自动化单元测试沙箱执行反馈。
4. **闭环自纠错 (Self-Correction Loop)**：
   - 单测生成与代码修复不仅提供文本，更能**主动调用子进程沙箱执行代码，根据 Traceback 报错自主修正并重新运行**，直到测试 100% 通过。
5. **工业级一键运维体验**：
   - 提供 `start_all.bat` 与 `kill_all.bat`，自动探测并释放旧端口占用，一键多窗口拉起后端与前端。

---

## 🚀 极速上手与运行指南

### 1. 配置 API Key
在根目录 `.env` 中配置您的 DeepSeek API Key（系统默认模型已锁定为 `deepseek-flash`）：
```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-flash
```

### 2. 一键启动全套服务 (推荐)
直接双击运行或在命令行执行：
```powershell
.\start_all.bat
```
脚本将自动清理旧占用端口，并同时启动：
- **Web 工作台**：`http://localhost:8501`
- **FastAPI 后端 & Swagger 文档**：`http://localhost:8000/docs`

如需一键停止所有服务，运行：
```powershell
.\kill_all.bat
```

### 3. 运行自动化测试套件
```powershell
python -m pytest -v
```
运行输出：**32 个测试用例全部 PASSED (100% 通过率)**！

### 4. 一键作业提交打包
```powershell
python package_submission.py 10086张三
```
将自动排除 `.git`、`.venv`、缓存等文件，生成仅数十 KB 的标准作业提交包 `10086张三.zip`。
