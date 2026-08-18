# Career Scout AU

Career Scout AU is the job-discovery and opportunity-ranking companion to Career Operator AU.

## Prototype 0.2 pipeline

1. Discover current SEEK vacancies through structured search.
2. Capture job ID and direct vacancy URL.
3. Verify each individual vacancy is currently live before ranking it.
4. Retrieve and normalise the full job description.
5. Deduplicate jobs and reposts.
6. Apply Career Scout preferences from the Career Operator Vault.
7. Score against the Career Operator matching profile.
8. Analyse mandatory gaps, JD openness/rigidity, transferable-experience tolerance and working-style alignment.
9. Produce a ranked, directly clickable shortlist for human review.

## Source of truth

Candidate evidence and preferences are intentionally not duplicated here.

- `career-operator-vault/10_Job_Scout/MATCHING_PROFILE.json`
- `career-operator-vault/10_Job_Scout/SCOUT_PREFERENCES.json`

Career Operator remains authoritative for career evidence. Career Scout consumes that evidence for discovery and ranking.

## Core guardrail

A job cannot enter the actionable shortlist unless its individual vacancy is verified as currently live. Search-engine/indexed results alone are not sufficient evidence that a job is live.
