import unittest
from unittest.mock import Mock, patch

from models.task import Task
from runtime.registry import AgentRegistry
from runtime.runner import RuntimeRunner
from runtime.scheduler import TaskGraphError, TaskScheduler
from runtime.supervisor import Supervisor
from state import AgentState


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.state = AgentState("./demo_app")
        self.scheduler = TaskScheduler()

    def task(self, task_id, **kwargs):
        task = Task(
            task_id, "CodeAnalysisAgent", "analyze_code", self.state.target,
            **kwargs,
        )
        self.state.add_task(task)
        return task

    def test_dependency_lists_are_not_shared(self):
        first = self.task("T1")
        second = self.task("T2")
        first.dependencies.append("T2")
        self.assertEqual(second.dependencies, [])

    def test_root_ready_and_dependency_waits_until_completed(self):
        root = self.task("T1")
        child = self.task("T2", dependencies=["T1"])
        self.scheduler.validate_graph(self.state)
        self.scheduler.refresh(self.state)
        self.assertEqual(root.status, "READY")
        self.assertEqual(child.status, "PENDING")
        self.assertEqual(self.scheduler.ready_tasks(self.state), [root])

        root.status = "COMPLETED"
        self.scheduler.refresh(self.state)
        self.assertEqual(child.status, "READY")
        self.assertEqual(self.scheduler.ready_tasks(self.state), [child])

    def test_failed_or_blocked_dependency_propagates_in_reverse_order(self):
        leaf = self.task("T3", dependencies=["T2"])
        middle = self.task("T2", dependencies=["T1"])
        root = self.task("T1")
        for status in ("FAILED", "BLOCKED"):
            with self.subTest(status=status):
                root.status = status
                middle.status = leaf.status = "PENDING"
                self.scheduler.refresh(self.state)
                for task in (middle, leaf):
                    self.assertEqual(task.status, "BLOCKED")
                    self.assertEqual(task.block_reason, "DEPENDENCY_FAILED")
                self.assertEqual(self.scheduler.ready_tasks(self.state), [])

    def test_waiting_confirmation_keeps_downstream_pending(self):
        root = self.task("T1", status="WAITING_CONFIRMATION")
        child = self.task("T2", dependencies=["T1"])
        self.scheduler.refresh(self.state)
        self.assertEqual(root.status, "WAITING_CONFIRMATION")
        self.assertEqual(child.status, "PENDING")
        self.assertIsNone(child.block_reason)
        self.assertEqual(self.scheduler.ready_tasks(self.state), [])

    def test_invalid_graphs_are_rejected_before_delegation(self):
        cases = [
            ([("T1", []), ("T1", [])], "DUPLICATE_TASK_ID"),
            ([("T1", ["T999"])], "UNKNOWN_DEPENDENCY"),
            ([("T1", ["T1"])], "SELF_DEPENDENCY"),
            ([("T1", ["T2"]), ("T2", ["T1"])], "CYCLIC_DEPENDENCY"),
        ]
        for tasks, reason in cases:
            with self.subTest(reason=reason):
                self.state.tasks = []
                for task_id, dependencies in tasks:
                    self.task(task_id, dependencies=dependencies)
                supervisor = Mock()
                with self.assertRaisesRegex(TaskGraphError, reason):
                    RuntimeRunner(supervisor).run_until_blocked(self.state)
                supervisor.delegate.assert_not_called()
                self.assertTrue(all(t.status == "PENDING" for t in self.state.tasks))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.state = AgentState("./demo_app")
        self.registry = AgentRegistry()
        self.agent = Mock()
        self.agent.run.side_effect = lambda task, tool_context: {
            "agent": task.agent,
            "task_id": task.id,
            "execution_status": "SUCCESS",
            "data": {},
        }
        self.registry.register("CodeAnalysisAgent", self.agent, ["analyze_code"])
        self.supervisor = Supervisor(self.registry)
        self.runner = RuntimeRunner(self.supervisor)

    def task(self, task_id, **kwargs):
        task = Task(
            task_id, "CodeAnalysisAgent", "analyze_code", self.state.target,
            **kwargs,
        )
        self.state.add_task(task)
        return task

    def test_dependency_diamond_progresses_once_in_dependency_order(self):
        self.task("T4", dependencies=["T2", "T3"])
        self.task("T3", dependencies=["T1"])
        self.task("T2", dependencies=["T1"])
        self.task("T1")
        results = self.runner.run_until_blocked(self.state)
        order = [item["task_id"] for item in results]
        self.assertEqual(order[0], "T1")
        self.assertEqual(set(order[1:3]), {"T2", "T3"})
        self.assertEqual(order[3], "T4")
        self.assertTrue(all(t.status == "COMPLETED" for t in self.state.tasks))
        self.assertEqual(self.agent.run.call_count, 4)
        self.assertEqual(self.runner.run_until_blocked(self.state), [])
        self.assertEqual(self.agent.run.call_count, 4)

    def test_denied_task_stops_and_blocks_downstream(self):
        for invalid_schema in (False, True):
            with self.subTest(invalid_schema=invalid_schema):
                self.state.tasks = []
                root = self.task("T1")
                if invalid_schema:
                    root.action = "invalid_action"
                    reason = "INVALID_SCHEMA"
                else:
                    root.agent = "MissingAgent"
                    reason = "UNKNOWN_AGENT"
                child = self.task("T2", dependencies=["T1"])
                # Fail promptly if a regression causes repeated dispatch.
                delegate = self.supervisor.delegate

                def delegate_once(task, state):
                    self.assertEqual(dispatch.call_count, 1, "Repeated dispatch")
                    return delegate(task, state)

                with patch.object(
                    self.supervisor, "delegate",
                    side_effect=delegate_once,
                ) as dispatch:
                    results = self.runner.run_until_blocked(self.state)
                    dispatch.assert_called_once_with(root, self.state)
                self.assertEqual(len(results), 1)
                self.assertEqual(root.status, "BLOCKED")
                self.assertEqual(root.block_reason, reason)
                self.assertEqual(child.status, "BLOCKED")
                self.assertEqual(child.block_reason, "DEPENDENCY_FAILED")
                self.agent.run.assert_not_called()

    def test_waiting_confirmation_resumes_after_approval(self):
        self.state.phase = "VERIFY"
        self.registry.register(
            "VerificationAgent", self.agent, ["verify_ssrf", "verify_sqli"],
        )
        root = Task("T1", "VerificationAgent", "verify_ssrf", self.state.target, phase="VERIFY")
        child = Task(
            "T2", "VerificationAgent", "verify_sqli", self.state.target,
            dependencies=["T1"],
            phase="VERIFY",
        )
        self.state.tasks = [child, root]
        results = self.runner.run_until_blocked(self.state)
        self.assertEqual(len(results), 1)
        self.assertEqual(root.status, "WAITING_CONFIRMATION")
        self.assertEqual(child.status, "PENDING")
        self.agent.run.assert_not_called()
        self.assertEqual(self.runner.run_until_blocked(self.state), [])
        self.assertEqual(len(self.supervisor.approval_store.actions), 1)

        self.supervisor.approve(results[0]["result"]["action_id"], self.state)
        self.assertEqual(root.status, "COMPLETED")
        resumed = self.runner.run_until_blocked(self.state)
        self.assertEqual([item["task_id"] for item in resumed], ["T2"])
        self.assertEqual(child.status, "COMPLETED")
        self.assertEqual(self.agent.run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
