from models.approval import (
    ApprovalSnapshot,
    PendingAction,
)


class ApprovalStore:

    def __init__(self):

        self.actions = {}
        self._owners = {}

        self._next_id = 1


    def create(self, task, state):

        snapshot = ApprovalSnapshot.from_task(task)

        action_id = (
            f"A{self._next_id:03d}"
        )

        self._next_id += 1

        pending = PendingAction(
            action_id=action_id,
            snapshot=snapshot,
        )

        self.actions[action_id] = pending
        self._owners[action_id] = state

        return pending

    def belongs_to(self, action_id, state):
        return self._owners.get(action_id) is state


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
