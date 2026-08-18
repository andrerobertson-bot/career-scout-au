from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from career_scout.models import Job


class SeekCollector:
    """SEEK AU collector for Prototype 0.2.

    Discovery uses SEEK's public job-search JSON endpoint used by its web app.
    Detail verification uses the web application's job-detail GraphQL endpoint.
    These web endpoints are not the authenticated SEEK Partner API.

    Endpoint shapes can change, so parsing is intentionally defensive and the
    pipeline fails closed: an unverified job never becomes actionable.
    """

    BASE_URL = "https://www.seek.com.au"
    SEARCH_URL = f"{BASE_URL}/api/jobsearch/v5/search"
    GRAPHQL_URL = f"{BASE_URL}/graphql"

    def __init__(self, timeout: float = 20.0) -> None:
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CareerScoutAU/0.1; +personal-job-search)",
                "Accept": "application/json",
                "Accept-Language": "en-AU,en;q=0.9",
            },
        )

    def close(self) -> None:
        self.client.close()

    def search(
        self,
        keywords: str,
        *,
        where: str = "All Sydney NSW",
        page: int = 1,
        sortmode: str = "ListedDate",
    ) -> list[Job]:
        params = {
            "siteKey": "AU-Main",
            "sourcesystem": "houston",
            "userqueryid": "",
            "page": page,
            "keywords": keywords,
            "where": where,
            "sortmode": sortmode,
        }
        response = self.client.get(self.SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

        rows = (
            payload.get("data")
            or payload.get("jobs")
            or payload.get("results")
            or []
        )
        if isinstance(rows, dict):
            rows = rows.get("jobs") or rows.get("results") or []

        jobs: list[Job] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            job_id = str(row.get("id") or row.get("jobId") or row.get("jobid") or "")
            title = row.get("title") or row.get("jobTitle")
            if not job_id or not title:
                continue
            company = row.get("companyName") or row.get("advertiser", {}).get("description")
            location = row.get("location") or row.get("where")
            url = row.get("jobUrl") or row.get("url") or f"{self.BASE_URL}/job/{job_id}"
            jobs.append(
                Job(
                    source="seek",
                    source_job_id=job_id,
                    title=str(title),
                    company=str(company) if company else None,
                    location=str(location) if location else None,
                    work_arrangement=row.get("workArrangements") or row.get("workArrangement"),
                    employment_type=row.get("workType") or row.get("employmentType"),
                    salary_text=row.get("salary") or row.get("salaryText"),
                    url=url,
                    posted_at=row.get("listingDate") or row.get("postedDate"),
                    teaser=row.get("teaser"),
                    bullet_points=[str(x) for x in (row.get("bulletPoints") or [])],
                    raw=row,
                )
            )
        return jobs

    def verify_and_enrich(self, job: Job) -> Job:
        """Fetch current job details and mark whether the individual vacancy is live.

        Fail-closed rule: network/schema errors leave is_live=False. This prevents
        stale search/index results from entering the actionable shortlist.
        """
        now = datetime.now(timezone.utc).isoformat()
        job.verified_at = now
        try:
            payload = {
                "operationName": "jobDetails",
                "variables": {"jobId": job.source_job_id},
                "query": """
                query jobDetails($jobId: ID!) {
                  jobDetails(id: $jobId) {
                    id
                    title
                    status
                    isExpired
                    expiresAt
                    description
                    applyUrl
                  }
                }
                """,
            }
            response = self.client.post(self.GRAPHQL_URL, json=payload)
            response.raise_for_status()
            body = response.json()
            details = (body.get("data") or {}).get("jobDetails")
            if not details:
                job.is_live = False
                job.status = "UNVERIFIED"
                return job

            job.status = str(details.get("status") or "") or None
            job.is_expired = bool(details.get("isExpired"))
            job.valid_through = details.get("expiresAt") or job.valid_through
            job.description = details.get("description") or job.description
            job.apply_url = details.get("applyUrl") or job.apply_url
            job.title = details.get("title") or job.title
            status_text = (job.status or "").lower()
            job.is_live = not job.is_expired and status_text not in {
                "expired", "closed", "removed", "deleted", "unavailable"
            }
            return job
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            job.is_live = False
            job.status = "UNVERIFIED"
            return job
