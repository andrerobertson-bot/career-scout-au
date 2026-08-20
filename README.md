# Career Scout AU

Career Scout AU is the SEEK-first job-discovery, verification and opportunity-ranking companion to Career Operator AU.

## v1.1 pipeline

1. Discover SEEK vacancies through broad, overlapping senior-role searches using a rolling seven-day window.
2. Capture the SEEK job ID and canonical individual `/job/<id>` URL.
3. Consult the Career Operator role ledger before expensive verification so previously processed opportunities are not presented as new.
4. Retrieve and normalise the full job description.
5. Apply Career Scout preferences and Career Operator evidence-aware fit scoring.
6. Reject genuine mandatory hard gaps; do not convert adjacency into specialist expertise.
7. Render/open the individual vacancy and verify that it is currently live before publication.
8. Re-run preference and fit gates on page-derived data.
9. Re-check the ledger before publication and suppress roles already shortlisted, CV-created, applied, interviewed, rejected, closed or expired.
10. Produce a ranked, directly clickable shortlist for human review.

## Source of truth

Candidate evidence and preferences are intentionally not duplicated here. Career Operator remains authoritative.

- `career-operator-vault/10_Job_Scout/MATCHING_PROFILE.json`
- `career-operator-vault/10_Job_Scout/SCOUT_PREFERENCES.json`
- `career-operator-vault/10_Job_Scout/ROLE_LEDGER.json`

The role ledger is the persistent opportunity-state store. SEEK uses `seek:<job_id>` as the primary identity key.

## Closed-loop role states

Supported states are:

`NEW -> SHORTLISTED -> CV_CREATED -> APPLIED -> INTERVIEW`

Terminal/exit states are `REJECTED`, `CLOSED` and `EXPIRED`.

Career Operator should write back user-confirmed application changes immediately when the vacancy identity is unambiguous. Successful CV creation should move a tracked role to `CV_CREATED` unless it is already further through the funnel. Scout-confirmed expiry may move a tracked pre-application role to `EXPIRED`; it must not overwrite an `APPLIED` or `INTERVIEW` state because an advert closing does not prove the candidacy has ended.

## Core guardrail

A job cannot enter the actionable shortlist unless its individual vacancy is verified as currently live. Search/index results alone are never sufficient evidence that a job is live.

A role already present in the role ledger with a suppressed status cannot be presented as a new opportunity, even if SEEK reposts or refreshes the vacancy metadata.
