## 1. Durable coordination

- [x] 1.1 Add persisted Run execution configuration and diagnostic checkpoint fields with migration coverage.
- [x] 1.2 Implement one private dependency-driven coordinator over existing Working Run, Work, Artifact, Result, and resource authorities.
- [x] 1.3 Make source-bound `start` and `resume` return immediately while the host invokes private `advance(run_ref)`, without adding a public action or service.

## 2. Recovery and failure behavior

- [x] 2.1 Re-derive producer demand on restart and reuse semantically valid Work and Artifacts.
- [x] 2.2 Honor pause and cancellation at admission boundaries and preserve localized terminal failures as exception paths.
- [x] 2.3 Recover idempotently across the pre-seal, post-publication, and post-registration crash windows.

## 3. End-to-end verification

- [x] 3.1 Add start-plus-worker-driven mixed image, video, GPX, embedding, sensitivity, bundle, compression, seal, and Read coverage.
- [x] 3.2 Add default-zero-network and fake-provider confirmation coverage.
- [x] 3.3 Add interruption, external pause/resume/cancel, localized failure, and cross-Run reuse coverage.
- [x] 3.4 Replace the manual 500 → 3 → 200 scale assembly with three independent public Run executions.
- [x] 3.5 Run the final repository quality and boundary gates and record them in verification.md.

## 4. Human review

- [x] 4.1 Obtain human acceptance before archiving the change.
