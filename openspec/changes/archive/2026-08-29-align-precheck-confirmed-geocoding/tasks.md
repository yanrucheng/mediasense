## 1. Contract alignment

- [x] 1.1 Replace absolute-offline wording with the approved local-first, default-disabled boundary.
- [x] 1.2 Specify post-compression freezing, deduplication, exact logical-query confirmation, and re-confirmation after scope change.
- [x] 1.3 Expose external-effect evidence through the immutable Result view without permitting media, rendition, embedding, prompt, or general-metadata egress.

## 2. Implementation and verification

- [x] 2.1 Reuse the existing Run confirmation state and stage-neutral geo adapter rather than create another service or public action.
- [x] 2.2 Preserve provider routing, fallback, datum, language, retry, failure, request-count, and authorization provenance in Work and Result.
- [x] 2.3 Add fake-provider tests for exact frozen counts, no-call paths, changed sets, cancellation, reuse, and Result projection.
- [x] 2.4 Run the final repository quality and boundary gates and record them in verification.md.

## 3. Human review

- [x] 3.1 Obtain human acceptance before archiving the change.
