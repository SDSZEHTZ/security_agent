from models.plan import PlanProposal
from pydantic import ValidationError
from runtime.finding_rules import finding_error


class PlanValidationError(ValueError):
    pass


class PlanValidator:

    MAX_TASKS = 10


    def __init__(
        self,
        workflow,
    ):
        self.workflow = workflow


    def validate(
        self,
        proposal,
        expected_phase,
        state,
        registry,
    ):

        try:
            # Revalidate even model_construct()/mutated Pydantic instances.
            proposal = PlanProposal.model_validate(proposal.model_dump())
        except (AttributeError, ValidationError, TypeError, ValueError) as exc:
            raise PlanValidationError("INVALID_PLAN_SCHEMA") from exc

        # Phase 必须由 Runtime 指定
        if proposal.phase != expected_phase or expected_phase != state.phase:

            raise PlanValidationError(
                "INVALID_PLAN_PHASE"
            )

        # 防止 LLM 一次生成巨大计划
        if len(proposal.tasks) > self.MAX_TASKS:

            raise PlanValidationError(
                "TOO_MANY_TASKS"
            )


        keys = [
            task.key
            for task in proposal.tasks
        ]

        # key 必须唯一
        if len(keys) != len(set(keys)):

            raise PlanValidationError(
                "DUPLICATE_TASK_KEY"
            )


        key_set = set(keys)


        for task in proposal.tasks:

            # Agent 必须真的存在
            agent_info = registry.get(
                task.agent
            )

            if agent_info is None:

                raise PlanValidationError(
                    "UNKNOWN_AGENT"
                )


            # Planner 不能给 Agent
            # 分配它没有的能力
            if task.action not in (
                agent_info["capabilities"]
            ):

                raise PlanValidationError(
                    "CAPABILITY_NOT_ALLOWED"
                )


            # Action 必须符合当前 Phase
            if not self.workflow.is_allowed(
                expected_phase,
                task.action,
            ):

                raise PlanValidationError(
                    "ACTION_NOT_ALLOWED_IN_PHASE"
                )


            # 规划阶段提前做 Scope fail-fast
            if task.target != state.target:

                raise PlanValidationError(
                    "TARGET_OUT_OF_SCOPE"
                )


            error = finding_error(task, state, require_finding=True)
            if error:
                raise PlanValidationError(error)


            # 当前 Plan 内依赖必须存在
            for dependency in task.depends_on:

                if dependency not in key_set:

                    raise PlanValidationError(
                        "UNKNOWN_PLAN_DEPENDENCY"
                    )

                if dependency == task.key:

                    raise PlanValidationError(
                        "SELF_DEPENDENCY"
                    )


        self._check_cycles(
            proposal
        )

    def _check_cycles(
        self,
        proposal,
    ):

        graph = {
            task.key: task.depends_on
            for task in proposal.tasks
        }

        visiting = set()
        visited = set()


        def dfs(key):

            if key in visiting:
                return True

            if key in visited:
                return False

            visiting.add(key)

            for dependency in graph[key]:

                if dfs(dependency):
                    return True

            visiting.remove(key)
            visited.add(key)

            return False


        for key in graph:

            if dfs(key):

                raise PlanValidationError(
                    "CYCLIC_PLAN"
                )
