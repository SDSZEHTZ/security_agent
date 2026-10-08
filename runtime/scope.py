class ScopeEngine:

    def is_allowed(
        self,
        request_target,
        state_target
    ):

        return request_target == state_target