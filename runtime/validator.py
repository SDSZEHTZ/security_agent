from models.request import TaskRequest


class RequestValidator:

    def validate(self, task):
        return TaskRequest.model_validate(task)