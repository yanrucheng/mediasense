## 1. Release contract

- [x] 1.1 Update the single application version and all `0.4.x` compatibility declarations.
- [x] 1.2 Update installation, upgrade, clean-start, and rollback documentation for the 0.4/schema-17 boundary.

## 2. Skill upgrade

- [x] 2.1 Implement transactional `mediasense skills upgrade --target` for the four packaged Skill names.
- [x] 2.2 Add success, idempotency, unrelated-content, conflict, and injected rollback tests.

## 3. Release verification

- [x] 3.1 Run Ruff, focused tests, non-Hong-Kong regression tests, and strict OpenSpec validation.
- [x] 3.2 Build and inspect the exact 0.4.0 wheel and verify it in an isolated clean installation.

## 4. Local installation

- [x] 4.1 Replace the local uv tool with the verified wheel and verify version, doctor, and Tool descriptors.
- [x] 4.2 Verify packaged Skill install and upgrade against an explicit temporary Honeycomb, leaving Dataset workspaces and MCP configuration unchanged.
- [x] 4.3 Remove the mistaken repository-local MediaSense Skill activation and add regression coverage that keeps the source checkout separate from operational Honeycombs.
