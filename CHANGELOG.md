# Changelog

## v0.2.0 - Runtime Security Gates

### Added

- Pydantic task schema validation
- Workflow phase validation
- Policy engine
- Scope validation
- ALLOW / CONFIRM / DENY decisions
- Security regression tests

### Security

- Invalid actions are rejected before execution
- Agents cannot execute actions outside the current workflow phase
- Policy DENY prevents execution even when capability exists
- Out-of-scope targets are rejected
- CONFIRM actions cannot execute before approval