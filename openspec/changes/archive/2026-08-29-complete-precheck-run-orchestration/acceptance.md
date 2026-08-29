## Acceptance state

Human acceptance was granted on 2026-08-30. The accepted implementation keeps
the public Run lifecycle separate from the private host worker that advances
long-running execution.

Acceptance requires a source-bound public `start` to return immediately, a host worker to reach one readable immutable Result, external control during execution, honest failure states, recovery without duplicate low-level work, and passing 500 → 3 → 200 coverage. Production-scale and model-quality certification remain separately named follow-up work.
