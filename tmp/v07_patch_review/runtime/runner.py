from runtime.scheduler import TaskScheduler


class RuntimeRunner:

    def __init__(
        self,
        supervisor,
        scheduler=None,
    ):

        self.supervisor = supervisor

        self.scheduler = (
            scheduler
            or TaskScheduler()
        )

    def run_until_blocked(
        self,
        state,
    ):

        self.scheduler.validate_graph(
            state
        )

        results = []

        while True:

            self.scheduler.refresh(
                state
            )

            ready = (
                self.scheduler.ready_tasks(
                    state
                )
            )

            if not ready:
                break

            for task in ready:

                result = (
                    self.supervisor.delegate(
                        task,
                        state,
                    )
                )

                results.append(
                    {
                        "task_id": task.id,
                        "result": result,
                    }
                )

        return results