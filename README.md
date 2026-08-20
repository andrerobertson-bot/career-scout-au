# Career Scout AU

Career Scout AU is the SEEK-first job-discovery and opportunity-ranking companion to Career Operator AU.

## v1 pipeline

1. Search broadly across senior Sydney program, delivery and transformation role families on SEEK using a rolling seven-day window.
2. Capture the SEEK job ID and canonical individual `/job/<ID>` URL.
3. Deduplicate against both the current run and the persistent Career Operator Vault role ledger.
4. Apply Career Scout location, remuneration and employer-environment preferences from the Vault.
5. Score against the evidence-aware Career Operator matching profile and reject genuine hard gaps.
6. Open the individual vacancy in a rendered browser and verify that it is still live before publication.
7. Re-evaluate page-derived details after verification and rank only actionable opportunities.
8. Persist the latest run status/shortlist for auditability while keeping candidate evidence and application state authoritative in the private Vault.

## Source of truth

Career Operator AU remains authoritative for candidate evidence, preferences and application state. Career Scout reads:

- `career-operator-vault/10_Job_Scout/MATCHING_PROFILE.json`
- `career-operator-vault/10_Job_Scout/SCOUT_PREFERENCES.json`
- `career-operator-vault/10_Job_Scout/ROLE_LEDGER.json`

`ROLE_LEDGER.json` uses `<source>:<job_id>` as its persistent key (for example `seek:93977247`). Roles already shortlisted, CV-created, applied, interviewing, rejected, closed or expired are suppressed as new discoveries.

## SEEK guardrail

A SEEK role cannot enter the actionable shortlist unless the individual vacancy URL resolves to the same SEEK job ID and the vacancy is verified as currently live. Search cards, search-engine snippets and stale indexed pages are discovery evidence only, never final live-state evidence.

## Runtime

The GitHub Action runs daily at 8:00am Australia/Sydney. It uses SEEK as the primary/only automated source, searches a rolling seven-day window, reads the private Career Operator Vault through `CAREER_OPERATOR_TOKEN`, and uses `APIFY_TOKEN` for managed SEEK acquisition and rendered verification.
