## ADDED Requirements

### Requirement: Runtime configuration exposes capability facts without an offline mode
MediaSense configuration and diagnostics SHALL expose configured provider
credential state, provider capability availability, provider-policy disclosure,
and configuration provenance. They SHALL NOT expose a product `offline` mode or
use a global mode to authorize effects. Every provider request SHALL remain gated
by exact Run authority.

#### Scenario: No provider credential is configured
- **WHEN** Dataset open or doctor evaluates runtime configuration without map-provider credentials
- **THEN** it reports providers as unavailable without describing the product as offline

#### Scenario: Provider credential is configured
- **WHEN** a supported provider credential is present
- **THEN** diagnostics report capability availability while stating that credential presence grants no effect authority

#### Scenario: Legacy offline key is supplied
- **WHEN** a configuration file contains `runtime.offline`
- **THEN** configuration validation rejects the obsolete product key instead of silently accepting or translating it

### Requirement: Distribution verification follows exact public resources
The clean-install wheel smoke SHALL compare packaged contract paths, Skill paths,
CLI Tool names, and MCP Tool names with explicit expected sets rather than stale
aggregate counts.

#### Scenario: Shared Geo resources are packaged
- **WHEN** a wheel is built with the stage-neutral Geo capability
- **THEN** clean-install verification accepts the Geo Tool contract, exactly seven public Tool names, and the current Skill set while rejecting missing or unexpected paths
