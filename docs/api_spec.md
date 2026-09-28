# 📑 CodeMate-Agent RESTful API 接口规范文档 (api_spec.md)

本文档定义 CodeMate-Agent 后端微服务（FastAPI）的标准对外接口协议。服务默认监听 `http://127.0.0.1:8000`。
交互式 Swagger UI 可直接访问：`http://127.0.0.1:8000/docs`。

---

## 1. 基础服务协议

- **协议格式**：HTTP / JSON
- **字符编码**：UTF-8
- **跨域支持**：全量开启 CORS

---

## 2. API 端点定义

### 2.1 健康检查与模型状态
- **URL**: `GET /api/health`
- **响应示例**:
```json
{
  "code": 200,
  "message": "CodeMate Backend is running",
  "data": {
    "status": "healthy",
    "model": "deepseek-flash",
    "has_key": true
  }
}
```

---

### 2.2 获取可用工具集
- **URL**: `GET /api/tools`
- **响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 6,
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "read_file",
          "description": "读取指定路径的代码或文本文件内容，支持按行切片读取"
        }
      }
    ]
  }
}
```

---

### 2.3 统一两阶段流水线分析 (Pipeline)
- **URL**: `POST /api/pipeline/analyze`
- **请求体**:
```json
{
  "code": "def process(x): return x / 0",
  "file_path": null,
  "task_type": "review"
}
```
- **核心逻辑**:
  1. **Phase 1**: 规则引擎进行 AST 解析，提取静态特征与初筛坏味道；
  2. **Phase 2**: 根据 `task_type` 自动分发至对应的 Agent 专家（`review` -> `CodeReviewerAgent`, `test` -> `TestGeneratorAgent`, `refactor` -> `CodeRefactorAgent`, `explain` -> `CodeExplainerAgent`）；
  3. **Phase 3**: 缺陷严重度定级排序与结果去重聚合。
- **响应示例**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "success": true,
    "task_type": "review",
    "target": "inline_code",
    "phase1": {
      "syntax_valid": true,
      "functions": ["process"],
      "classes": [],
      "rule_issues": []
    },
    "phase2": {
      "agent_name": "CodeReviewerAgent",
      "report": "### 代码审查报告\n1. 发现除以0运行时崩溃风险..."
    }
  }
}
```

---

### 2.4 定向业务端点 (快捷路由)
- `POST /api/review`：代码质量审查
- `POST /api/test/generate`：单测自动生成与沙箱执行验证
- `POST /api/refactor`：消除坏味道与架构重构建议
- `POST /api/explain`：代码逐步解释与复杂度评估
