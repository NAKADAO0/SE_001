"""
后端 RESTful API 服务器 (FastAPI)
企业级微服务 RESTful API 路由架构。
"""

import sys
from pathlib import Path

# 将项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from code_analyzer.query.pipeline import CodePipeline
from code_analyzer.core.config import Config
from backend.schemas import CodeAnalyzeRequest, CommonResponse


app = FastAPI(
    title="CodeMate-Agent OpenAPI",
    description="工业级两阶段多 Agent 代码质量审查、生成、解释与重构分析服务",
    version="2.0.0",
)

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = CodePipeline()


@app.get("/api/health", response_model=CommonResponse)
def health_check():
    """服务健康检查接口"""
    return CommonResponse(
        code=200,
        message="CodeMate Backend is running",
        data={
            "status": "healthy",
            "model": pipeline.config.model_name,
            "has_key": pipeline.config.has_valid_api_key(),
        },
    )


@app.get("/api/tools", response_model=CommonResponse)
def get_tools():
    """获取所有已加载的工具清单"""
    schemas = pipeline.reviewer_agent.tool_registry.get_tools_schema()
    return CommonResponse(
        code=200,
        message="success",
        data={"total": len(schemas), "tools": schemas},
    )


@app.post("/api/pipeline/analyze", response_model=CommonResponse)
def analyze_code(req: CodeAnalyzeRequest):
    """
    两阶段流水线统一分析入口
    Phase 1: 静态规则引擎提取 AST 风险点
    Phase 2: 专业 Agent 深度推理与工具调用自纠错
    Phase 3: 校验与结果聚合
    """
    target = req.code or req.file_path
    if not target:
        raise HTTPException(status_code=400, detail="code 或 file_path 必须提供至少一个")

    result = pipeline.run_pipeline(
        target=target,
        task_type=req.task_type,
    )
    return CommonResponse(code=200, message="success", data=result)


@app.post("/api/review", response_model=CommonResponse)
def review_endpoint(req: CodeAnalyzeRequest):
    """代码审查接口"""
    req.task_type = "review"
    return analyze_code(req)


@app.post("/api/test/generate", response_model=CommonResponse)
def test_endpoint(req: CodeAnalyzeRequest):
    """单元测试生成与执行接口"""
    req.task_type = "test"
    return analyze_code(req)


@app.post("/api/refactor", response_model=CommonResponse)
def refactor_endpoint(req: CodeAnalyzeRequest):
    """重构建议接口"""
    req.task_type = "refactor"
    return analyze_code(req)


@app.post("/api/explain", response_model=CommonResponse)
def explain_endpoint(req: CodeAnalyzeRequest):
    """代码解释接口"""
    req.task_type = "explain"
    return analyze_code(req)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
