## v0.3.0 - Secure HITL Approval Flow

### Added

- PendingAction lifecycle
- Immutable approval snapshots
- Runtime approval store
- Action IDs
- User approval flow
- Secondary runtime validation
- Approval replay protection

### Security

- Prevent approval laundering
- Detect task mutation after confirmation request
- Re-check capability, policy and scope before execution
- Prevent duplicate execution of approved actions
- Ensure CONFIRM does not bypass runtime security gates