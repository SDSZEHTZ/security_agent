import argparse
import json
import os

from agents.code_analysis import CodeAnalysisAgent
from agents.report import ReportAgent
from agents.verification import VerificationAgent
from planner.demo_planner import DemoPlanner
from planner.llm_planner import LLMPlanner
from runtime.orchestrator import AgentRuntime
from runtime.phase_manager import PhaseManager
from runtime.plan_compiler import PlanCompiler
from runtime.plan_validator import PlanValidator
from runtime.planning_context import PlanningContextBuilder
from runtime.registry import AgentRegistry
from runtime.scheduler import TaskScheduler
from runtime.state_manager import StateManager
from runtime.supervisor import Supervisor
from runtime.tool_executor import ToolExecutor
from runtime.tool_registry import ToolRegistry
from runtime.workflow import WorkflowEngine
from state import AgentState
from tools.controlled_http import ControlledHttpCheckTool
from tools.read_source import ReadSourceTool
from tools.search_code import SearchCodeTool


def build_tool_executor():
    tool_registry = ToolRegistry()
    tool_registry.register(ReadSourceTool())
    tool_registry.register(SearchCodeTool())
    tool_registry.register(ControlledHttpCheckTool())
    return ToolExecutor(tool_registry, {
        ("CodeAnalysisAgent", "analyze_code"): {"search_code", "read_source"},
        ("CodeAnalysisAgent", "read_file"): {"read_source"},
        ("VerificationAgent", "check_http_baseline"): {"controlled_http_check"},
    })


def build_registry(tool_executor):
    registry = AgentRegistry()
    registry.register("CodeAnalysisAgent", CodeAnalysisAgent(tool_executor), ["analyze_code", "read_file"])
    registry.register("VerificationAgent", VerificationAgent(tool_executor),
                      ["check_http_baseline", "verify_sqli", "verify_ssrf"])
    registry.register("ReportAgent", ReportAgent(), ["generate_report"])
    return registry


def build_runtime(planner):
    tool_executor = build_tool_executor()
    registry = build_registry(tool_executor)
    state_manager = StateManager()
    workflow = WorkflowEngine()
    supervisor = Supervisor(registry, workflow=workflow, state_manager=state_manager)
    return AgentRuntime(
        planner=planner, supervisor=supervisor, scheduler=TaskScheduler(),
        plan_validator=PlanValidator(workflow), plan_compiler=PlanCompiler(),
        context_builder=PlanningContextBuilder(), phase_manager=PhaseManager(),
        state_manager=state_manager, registry=registry,
    )


def main(planner=None, target="./demo_app", goal=None, authorized_origin=None):
    state = AgentState(target, authorized_origin=authorized_origin)
    runtime = build_runtime(planner if planner is not None else DemoPlanner())
    result = runtime.run_until_blocked(
        goal or f"Analyze {target} for web security issues.", state,
    )
    print("v0.7: source tools and HTTP baseline are real; SQLi/SSRF verification and report tasks remain demos.")
    print("\n=== Result ===")
    print(json.dumps(result, indent=4, ensure_ascii=False))
    print("\n=== Tasks ===")
    print(json.dumps([
        {"id": task.id, "phase": task.phase, "action": task.action,
         "status": task.status, "block_reason": task.block_reason}
        for task in state.tasks
    ], indent=4, ensure_ascii=False))
    for label, items in (
        ("Observations", state.observations),
        ("Evidence", state.evidence),
        ("Findings", state.findings),
    ):
        print(f"\n=== {label} ===")
        print(json.dumps([item.model_dump() for item in items], indent=4, ensure_ascii=False))
    return result


def cli():
    parser = argparse.ArgumentParser(description="v0.7 security runtime (source tools and HTTP baseline)")
    parser.add_argument("--target", default="./demo_app", help="Existing authorized source directory")
    parser.add_argument("--origin", help="Authorized HTTP origin, for example http://127.0.0.1:5000")
    parser.add_argument("--goal")
    parser.add_argument("--model", help="Enable real LLM planning using this model; requires OPENAI_API_KEY")
    args = parser.parse_args()
    if args.model and not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required with --model")
    planner = LLMPlanner(args.model) if args.model else DemoPlanner()
    result = main(planner, args.target, args.goal, args.origin)
    return 0 if result["status"] == "COMPLETED" and not result["failed_task_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(cli())
