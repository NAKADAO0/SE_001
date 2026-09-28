# 📐 CodeMate-Agent 系统架构与深度设计规范文档 (Desgin.md)

> **说明**：本文件为兼容作业 PPT 中文件名拼写要求之副本，完整架构内容请参见 [Design.md](file:///e:/python_project/SoftEngineeing/Design.md)。

---

## 1. 系统总体架构与分层设计 (System Architecture)

系统遵循工业级微服务与分层解耦架构，划分为表现层、服务中台层、智能体流水线编排层、专家智能体层、工具与沙箱层以及基础设施层：

```mermaid
graph TD
    subgraph ClientLayer ["1. 交互与表现层 (Client Layer)"]
        WebUI["Streamlit 交互工作台 (Port: 8501)<br/>左: 完整 AI 对话 Agent (/review, /refactor, /test, /explain)<br/>右: 代码编辑与修改前后对比 (Diff Viewer)"]
        CLI["Rich 终端控制台 (cli.py)"]
        Swagger["Swagger / OpenAPI UI (Port: 8000/docs)"]
    end

    subgraph BackendLayer ["2. RESTful 微服务层 (backend/)"]
        FastAPIApp["FastAPI 调度服务 (backend/app.py)"]
        Schemas["Pydantic 数据契约 (backend/schemas.py)"]
    end

    subgraph PipelineLayer ["3. 核心流水线编排层 (code_analyzer/query/)"]
        Pipeline["两阶段流水线编排器 (pipeline.py)"]
        RuleEngine["Phase 1: 静态规则引擎 (rule_engine.py)"]
        Verifier["Phase 3: 结果去重与校验器 (verifier.py)"]
    end

    subgraph AgentLayer ["4. 垂直领域多 Agent 专家矩阵 (code_analyzer/agents/)"]
        Reviewer["Agent 1: CodeReviewerAgent<br/>代码审计专家"]
        Tester["Agent 2: TestGeneratorAgent<br/>单测生成与自验证专家"]
        Refactor["Agent 3: CodeRefactorAgent<br/>架构重构专家"]
        Explainer["Agent 4: CodeExplainerAgent<br/>逻辑与复杂度专家"]
    end

    subgraph ToolLayer ["5. 扩展工具与隔离沙箱层 (code_analyzer/tools/)"]
        Registry["ToolRegistry 工具注册中心"]
        FileTools["文件工具 (read/write/list)"]
        ExecSandbox["子进程执行沙箱 (execute_code/run_pytest)"]
        ASTTools["AST 抽象语法树分析 (lint_code)"]
    end

    subgraph InfraLayer ["6. 基础设施层 (code_analyzer/core/)"]
        Config["配置中心 (默认 deepseek-flash)"]
        LLMClient["LLM 统一客户端 (Tenacity 指数退避重试)"]
        Memory["滑动窗口上下文记忆管理"]
    end

    WebUI --> FastAPIApp
    Swagger --> FastAPIApp
    CLI --> Pipeline
    FastAPIApp --> Schemas
    FastAPIApp --> Pipeline
    Pipeline --> RuleEngine
    Pipeline --> Reviewer & Tester & Refactor & Explainer
    Reviewer & Tester & Refactor & Explainer --> Verifier
    Reviewer & Tester & Refactor & Explainer --> Registry
    Registry --> FileTools & ExecSandbox & ASTTools
    Reviewer & Tester & Refactor & Explainer --> LLMClient & Memory
    LLMClient --> Config
```

---

## 2. 核心设计思想与对标创新点

### 2.1 两阶段混合分析范式 (Two-Phase Hybrid Pipeline)
- **Phase 1: 零 LLM 快速特征扫描与 AST 规则初筛 (Fast Path)**
  - 使用 Python 原生 `ast` 抽象语法树，在毫秒级内完成语法合法性校验、提取函数与类列表、定位参数过多与裸 except 异味；
- **Phase 2: 垂直领域专业 Agent 定向深度推理 (Deep Reasoning)**
  - 将 Phase 1 抽取的结构化线索作为先验知识注入对应专家 Agent，结合 ReAct 机制自主调度本地工具深度验证；
- **Phase 3: 校验、去重与严重度定级 (Verifier & Dedup)**
  - 将规则引擎发现的问题与 Agent 深度推理成果进行特征聚类与去重，按照 `CRITICAL > HIGH > MEDIUM > LOW` 严格排序输出。

### 2.2 多 Agent 专家团队架构 (Multi-Agent Team Architecture)
- **CodeReviewerAgent**：代码质量与安全审计专家
- **TestGeneratorAgent**：单元测试与自动化验证专家（测试-执行-纠错闭环）
- **CodeRefactorAgent**：架构风险隐患消除与重构专家（模式化重构）
- **CodeExplainerAgent**：逻辑解构与时空复杂度专家

---

## 3. 自动化测试报告
```bash
python -m pytest -v
```
**测试结果：32 个测试用例全部 PASSED (100% 通过率)**。
