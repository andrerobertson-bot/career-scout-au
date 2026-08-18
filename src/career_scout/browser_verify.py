from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from career_scout.models import Job


class BrowserVerifier:
    """Final rendered publication gate using Apify Playwright Scraper.

    Discovery sources are never authoritative. This verifier opens the canonical
    individual vacancy in Chromium immediately before publication and extracts the
    rendered visible text, URL and posted-age signal.
    """

    ACTOR = "apify~playwright-scraper"
    API = "https://api.apify.com/v2"

    SEEK_CLOSED = (
        "this job is no longer advertised",
        "this job has expired",
        "job has expired",
        "this job is no longer available",
        "no longer accepting applications",
    )
    LINKEDIN_CLOSED = (
        "no longer accepting applications",
        "this job is no longer available",
        "job is no longer available",
        "position has been filled",
    )

    def __init__(self, token: str | None = None, timeout: float = 180.0) -> None:
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is required for browser verification")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self.client.close()

    def verify(self, job: Job) -> Job:
        if not job.canonical_url:
            job.canonical_url = job.url
        if not job.canonical_url:
            job.is_live = False
            job.status = "NO_CANONICAL_URL"
            return job

        page_function = r'''
async function pageFunction(context) {
  const { page, request, log } = context;
  try { await page.waitForLoadState('networkidle', { timeout: 15000 }); } catch (e) {}
  await page.waitForTimeout(1500);
  const bodyText = await page.locator('body').innerText().catch(() => '');
  const title = await page.title().catch(() => '');
  const url = page.url();
  const postedMatches = bodyText.match(/(?:Posted|Listed)\s+([^\n]{1,40}?)(?:\n|$)/i);
  return {
    url,
    requestedUrl: request.url,
    title,
    bodyText,
    postedText: postedMatches ? postedMatches[0].trim() : null
  };
}
'''
        endpoint = f"{self.API}/acts/{self.ACTOR}/run-sync-get-dataset-items"
        payload = {
            "startUrls": [{"url": job.canonical_url}],
            "maxRequestsPerCrawl": 1,
            "pageFunction": page_function,
            "proxyConfiguration": {"useApifyProxy": True},
        }
        try:
            response = self.client.post(endpoint, params={"token": self.token}, json=payload)
            response.raise_for_status()
            rows = response.json()
        except (httpx.HTTPError, ValueError):
            job.is_live = False
            job.status = "BROWSER_VERIFICATION_FAILED"
            return job

        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            job.is_live = False
            job.status = "BROWSER_NO_RESULT"
            return job

        row = rows[0]
        final_url = str(row.get("url") or "")
        body = str(row.get("bodyText") or "")
        lower = body.lower()
        posted_text = row.get("postedText")
        job.verified_at = datetime.now(timezone.utc).isoformat()
        job.verification_method = "apify_playwright_rendered_page"

        if job.source == "seek":
            exact = f"/job/{job.source_job_id}" in final_url
            closed = any(marker in lower for marker in self.SEEK_CLOSED)
            active_apply = any(x in lower for x in ("quick apply", "apply now", "apply for this job"))
            if not exact or closed or not active_apply:
                job.is_live = False
                job.is_expired = closed
                job.status = "CLOSED" if closed else "UNVERIFIED_RENDERED_SEEK"
                return job
        elif job.source == "linkedin":
            exact = job.source_job_id in final_url or job.source_job_id in body
            closed = any(marker in lower for marker in self.LINKEDIN_CLOSED)
            active_apply = "apply" in lower
            if not exact or closed or not active_apply:
                job.is_live = False
                job.is_expired = closed
                job.status = "CLOSED" if closed else "UNVERIFIED_RENDERED_LINKEDIN"
                return job
        else:
            job.is_live = False
            job.status = "UNSUPPORTED_SOURCE"
            return job

        # Page-derived freshness only. Discovery timestamps are never promoted as
        # authoritative posting age.
        job.posted_at = str(posted_text).strip() if posted_text else None
        job.is_live = True
        job.is_expired = False
        job.status = "VERIFIED_LIVE_RENDERED"
        return job
