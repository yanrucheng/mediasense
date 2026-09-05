## REMOVED Requirements

### Requirement: Geo exposes progressive caller-meaningful operations
**Reason**: No independent Agent-facing caller remains after Plan Geo acquisition is removed.

**Migration**: PreCheck invokes only its internal reverse-geocode kernel for the frozen batch; there is no public operation migration.

### Requirement: Every external effect is bound to exact authority
**Reason**: This responsibility moves to the existing PreCheck Run frozen-batch authorization boundary.

**Migration**: Authorize the exact PreCheck confirmation disclosure and start or resume that Run.

### Requirement: Geo enforces coordinate-only data egress
**Reason**: The invariant is now enforced by PreCheck and its internal provider adapters rather than a public Tool.

**Migration**: Use PreCheck Run; no direct public Geo request is supported.

### Requirement: Results preserve component outcomes and effect evidence
**Reason**: Component outcomes and effects now belong to immutable PreCheck Result Evidence and execution accounting.

**Migration**: Read them through `mediasense.precheck.read/geo_summary` and ordinary Result expansion.

### Requirement: Geo request validation is strict and contract-conformant
**Reason**: The public Geo request contract is deleted.

**Migration**: PreCheck derives subjects from its frozen Result-bound batch; callers supply no Geo request.

### Requirement: Provider replacement preserves capability semantics
**Reason**: Provider replacement remains an internal kernel invariant, not a public Tool-family contract.

**Migration**: Provider adapters continue to satisfy PreCheck's internal provider-neutral port.

### Requirement: Routing and caller state remain isolated
**Reason**: There is no caller-selected Geo state or retention after observations become fixed Result evidence.

**Migration**: Routing stays internal to PreCheck and accepted observations retain immutable Result ownership.

### Requirement: Credentials remain outside durable identity and evidence
**Reason**: The invariant remains in PreCheck/provider implementation but no longer defines an independent public capability.

**Migration**: Configure provider credential environment names; credentials remain absent from Run and Result identity.

### Requirement: Effectful request replay is safe
**Reason**: The public Geo journal and request replay lifecycle are deleted with the Tool.

**Migration**: PreCheck reuses dependency-complete per-coordinate Work and reports indeterminate provider effects honestly; no standalone request replay is available.

