class PolicyEngine:

    DEFAULT_RULES = {
        "analyze_code": "ALLOW",
        "read_file": "ALLOW",
        "check_http_baseline": "ALLOW",

        "verify_sqli": "ALLOW",

        "verify_ssrf": "CONFIRM",

        "execute_command": "DENY",

        "generate_report": "ALLOW",
    }

    def __init__(self, rules=None):

        if rules is None:
            rules = self.DEFAULT_RULES

        self.rules = dict(rules)

    def evaluate(self, action):
        return self.rules.get(
            action,
            "DENY"
        )
