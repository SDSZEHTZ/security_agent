import os
import unittest

from main import build_registry, build_tool_executor
from planner.llm_planner import LLMPlanner
from runtime.plan_validator import PlanValidator
from runtime.planning_context import PlanningContextBuilder
from runtime.workflow import WorkflowEngine
from state import AgentState


@unittest.skipUnless(os.environ.get("RUN_LLM_INTEGRATION") == "1", "Live API test is opt-in")
class LivePlannerTests(unittest.TestCase):
    def test_live_analyze_proposal_passes_runtime_validation(self):
        model = os.environ.get("OPENAI_MODEL")
        if not model or not os.environ.get("OPENAI_API_KEY"):
            self.skipTest("OPENAI_MODEL and OPENAI_API_KEY are required")
        state = AgentState("./demo_app")
        registry = build_registry(build_tool_executor())
        plan = LLMPlanner(model).plan_phase(
            "Analyze the authorized demo app; propose one analyze_code task.",
            state.phase, PlanningContextBuilder().build(state, registry),
        )
        PlanValidator(WorkflowEngine()).validate(plan, state.phase, state, registry)


if __name__ == "__main__":
    unittest.main()
