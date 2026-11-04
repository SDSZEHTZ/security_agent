VERIFICATION_TYPES = {
    "verify_sqli": "SQL Injection",
    "verify_ssrf": "SSRF",
}


def finding_error(task, state, require_finding=False):
    """Shared plan-time and execution-time relationship validation."""
    if task.finding_id is None:
        if require_finding and task.action in VERIFICATION_TYPES:
            return "FINDING_REQUIRED"
        return None
    matches = [f for f in state.findings if f.id == task.finding_id]
    if not matches:
        return "UNKNOWN_FINDING"
    if len(matches) != 1:
        return "AMBIGUOUS_FINDING"
    finding = matches[0]
    if finding.target != task.target or finding.target != state.target:
        return "FINDING_TARGET_MISMATCH"
    if task.action not in VERIFICATION_TYPES:
        return "FINDING_ACTION_MISMATCH"
    if finding.finding_type != VERIFICATION_TYPES[task.action]:
        return "FINDING_TYPE_MISMATCH"
    if finding.status not in {"POTENTIAL", "UNCONFIRMED"}:
        return "FINDING_ALREADY_TERMINAL"
    return None
