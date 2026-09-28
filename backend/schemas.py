"""
Backend 请求与响应数据契约 (Pydantic)
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CodeAnalyzeRequest(BaseModel):
    code: Optional[str] = Field(None, description="源代码内容字符串")
    file_path: Optional[str] = Field(None, description="目标代码文件路径")
    task_type: str = Field("review", description="分析任务类型: review | test | refactor | explain")


class CommonResponse(BaseModel):
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="状态说明")
    data: Optional[Dict[str, Any]] = Field(None, description="业务数据")
