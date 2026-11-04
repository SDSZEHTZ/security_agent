from models.task import Task


class PlanCompiler:
    """Compile a validated proposal without mutating state."""

    def compile(self, proposal, state):
        existing_ids = {task.id for task in state.tasks}
        mapping = {}
        next_number = 1
        for planned in proposal.tasks:
            while f"T{next_number}" in existing_ids:
                next_number += 1
            task_id = f"T{next_number}"
            mapping[planned.key] = task_id
            existing_ids.add(task_id)
            next_number += 1

        return [
            Task(
                id=mapping[planned.key],
                agent=planned.agent,
                action=planned.action,
                target=planned.target,
                dependencies=[mapping[key] for key in planned.depends_on],
                finding_id=planned.finding_id,
                phase=proposal.phase,
            )
            for planned in proposal.tasks
        ]
