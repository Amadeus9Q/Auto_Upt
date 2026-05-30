from backend.app.agents.orchestrator import SimulatedAgentOrchestrator
from backend.app.schemas.agent import AgentRunRequest, AgentRunResponse


class AgentService:
    def __init__(self) -> None:
        self.orchestrator = SimulatedAgentOrchestrator()

    def create_preview_run(self, request: AgentRunRequest) -> AgentRunResponse:
        return self.orchestrator.run_preview_workflow(request)
