# SDD ledger — plan: /home/varane/Documents/Codex/2026-10-27/i-w/outputs/sports-analysis-implementation-plan.md

Execution: direct implementation authorised by “done lets move on”.

Ruling: No parent Git repository exists; create a new isolated repository under work/matchlens on feature/matchlens-mvp. No user code is overwritten.
Ruling: SQLite is supported for convenient local startup; PostgreSQL remains mandatory for hosted deployment and is tested separately. Local-only storage is never proposed for an ephemeral host.
Pre-flight: tasks 1–8 share domain records and SQLAlchemy sessions; model dates are UTC aware at boundaries and stored as ISO UTC strings to avoid SQLite/PostgreSQL timezone differences. Historical dates without times are assigned end-of-day UTC for leakage-safe training only.
Pre-flight: task 4 gates are provisional engineering defaults, not established accuracy; disabled combinations remain disabled when validation fails.
Pre-flight: credentials and deployment accounts are not yet available. Build/test locally; do not claim live API verification or remote publication.

- Task 1: implemented; initial authentication/storage tests passed, local setup extension under verification.
- Task 2: implemented; provider tests passed; 7,181 real OpenFootball results imported across PL/BL1/PD/SA/FL1 at revision e6744429ee395bc86f247348c6184bb08d4eb361. Latest source results 2026-09-20. Live API credentials not supplied.
- Task 3: implemented; analytical probability, settlement, rate validation and leakage tests passed (19 tests across model/provider files).
- Task 4: first real chronological backtest complete; report outputs/model-validation-results.json. Several outcomes passed initial gates in each league; prediction activation also requires fresh history and adequate band samples.
- Task 5: implemented; value/ranking tests passed; exact-line optional reference odds adapter under verification.
- Task 6: dashboard implemented; visual/browser verification pending.
- Task 7: jobs implemented; concurrency/release tests pending.
- Task 8: pending — release verification; external deployment dependent on owner accounts.

Ruling: Add one-time localhost setup and authenticated local API-key configuration, so the owner can enter secrets without chat or terminal copying. Remote setup is prohibited; deployment uses environment secrets.
Ruling: Tighten the recent-history gate to 14 days. A 37-day-old imported season must not masquerade as current form. Cost: no live candidates until the owner's current-results API sync succeeds.
Ruling: Implement initial schema creation through SQLAlchemy for this new v0.1 database; migrations are required before changing an existing deployed schema in a later release.
Execution note: a new user turn revoked the prior network grant; synchronous ASGI tests stalled on event-loop wakeup under the sandbox. Bounded diagnostics isolated the wait; network access was requested again for localhost verification. Do not treat stalled runs as passing tests.
