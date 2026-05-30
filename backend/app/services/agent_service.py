from backend.app.agents.orchestrator import SimulatedAgentOrchestrator
from backend.app.agents.tool_orchestrator import ToolDrivenAgentOrchestrator
from backend.app.schemas.agent import (
    AgentAdaptPreviewRequest,
    AgentAdaptPreviewResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentToolListResponse,
)


class AgentService:
    def __init__(self) -> None:
        self.orchestrator = SimulatedAgentOrchestrator()

    def create_preview_run(self, request: AgentRunRequest) -> AgentRunResponse:
        return self.orchestrator.run_preview_workflow(request)


class PersistentAgentService:
    def __init__(self, session) -> None:
        self.orchestrator = ToolDrivenAgentOrchestrator(session)

    def list_tools(self) -> AgentToolListResponse:
        return self.orchestrator.list_tools()

    async def create_adapt_preview_run(
        self,
        request: AgentAdaptPreviewRequest,
    ) -> AgentAdaptPreviewResponse:
        return await self.orchestrator.run_adapt_preview(request)

    async def get_adapt_preview_run(self, run_id: str) -> AgentAdaptPreviewResponse | None:
        return await self.orchestrator.get_run(run_id)
