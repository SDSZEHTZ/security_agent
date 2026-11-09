class TaskGraphError(ValueError):
    pass


class TaskScheduler:

    def validate_graph(self, state):

        task_map = {}
        phases = {"ANALYZE": 0, "VERIFY": 1, "REPORT": 2}

        # 1. Duplicate task IDs
        for task in state.tasks:

            if task.phase not in phases:
                raise TaskGraphError(f"INVALID_TASK_PHASE: {task.id}")

            if task.id in task_map:

                raise TaskGraphError(
                    f"DUPLICATE_TASK_ID: {task.id}"
                )

            task_map[task.id] = task

        # 2. Missing dependencies
        for task in state.tasks:

            for dependency_id in task.dependencies:

                if dependency_id not in task_map:

                    raise TaskGraphError(
                        "UNKNOWN_DEPENDENCY: "
                        f"{dependency_id}"
                    )

                if dependency_id == task.id:

                    raise TaskGraphError(
                        f"SELF_DEPENDENCY: {task.id}"
                    )

                if phases[task_map[dependency_id].phase] > phases[task.phase]:
                    raise TaskGraphError(f"FUTURE_PHASE_DEPENDENCY: {task.id}")

        # 3. Cycle detection
        visited = set()
        visiting = set()

        def dfs(task_id):

            if task_id in visiting:
                return True

            if task_id in visited:
                return False

            visiting.add(task_id)

            task = task_map[task_id]

            for dependency_id in task.dependencies:

                if dfs(dependency_id):
                    return True

            visiting.remove(task_id)
            visited.add(task_id)

            return False

        for task_id in task_map:

            if dfs(task_id):

                raise TaskGraphError(
                    "CYCLIC_DEPENDENCY"
                )

    def refresh(self, state):

        task_map = {
            task.id: task
            for task in state.tasks
        }

        changed = True

        while changed:

            changed = False

            for task in state.tasks:

                if task.status != "PENDING":
                    continue

                if task.phase != state.phase:
                    continue

                dependencies = [
                    task_map[dependency_id]
                    for dependency_id
                    in task.dependencies
                ]

                if any(
                    dependency.status
                    in {"FAILED", "BLOCKED", "TIMEOUT"}
                    for dependency
                    in dependencies
                ):

                    task.status = "BLOCKED"
                    task.block_reason = (
                        "DEPENDENCY_FAILED"
                    )

                    changed = True
                    continue

                if all(
                    dependency.status
                    == "COMPLETED"
                    for dependency
                    in dependencies
                ):

                    task.status = "READY"
                    changed = True

    def ready_tasks(self, state):

        return [
            task
            for task in state.tasks
            if task.status == "READY" and task.phase == state.phase
        ]
