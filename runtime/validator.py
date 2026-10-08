from models.observation import Observation
from models.request import TaskRequest


class RequestValidator:

    def validate(self, task):

        return TaskRequest.model_validate(
            task
        )


class ObservationValidator:

    def validate(self, raw_result):

        return Observation.model_validate(
            raw_result
        )