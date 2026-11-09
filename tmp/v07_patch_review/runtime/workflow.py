class WorkflowEngine:

    ALLOWED_ACTIONS = {
        "ANALYZE": {
            "analyze_code",
            "read_file",
        },

        "VERIFY": {
            "read_file",
            "check_http_baseline",
            "verify_sqli",
            "verify_ssrf",
            "execute_command",
        },

        "REPORT": {
            "generate_report",
        },
    }

    def is_allowed(self, phase, action):

        allowed = self.ALLOWED_ACTIONS.get(
            phase,
            set()
        )

        return action in allowed
