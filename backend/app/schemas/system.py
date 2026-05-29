from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态。正常时返回 ok。")
    app: str = Field(description="应用名称。")
    environment: str = Field(description="当前运行环境，例如 development。")
