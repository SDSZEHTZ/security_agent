from copy import deepcopy

from models.approval import (
    ApprovalSnapshot,
    PendingAction,
)


class ApprovalStore:

    def __init__(self):

        self.actions = {}

        self._next_id = 1


    def create(self, task):

        copied_task = deepcopy(task)

        snapshot = (
            ApprovalSnapshot.model_validate(
                copied_task
            )
        )

        action_id = (
            f"A{self._next_id:03d}"
        )

        self._next_id += 1

        pending = PendingAction(
            action_id=action_id,
            snapshot=snapshot,
        )

        self.actions[action_id] = pending

        return pending


    def get(self, action_id):

        return self.actions.get(
            action_id
        )


    def approve(self, action_id):

        pending = self.get(action_id)

        if pending is None:
            return None

        if (
            pending.status
            != "WAITING_CONFIRMATION"
        ):
            return None

        pending.status = "APPROVED"

        return pending


    def mark_executed(self, action_id):

        pending = self.get(action_id)

        if pending is not None:
            pending.status = "EXECUTED"


    def mark_rejected(self, action_id):

        pending = self.get(action_id)

        if pending is not None:
            pending.status = "REJECTED"
