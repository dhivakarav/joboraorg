"""TEMPORARY verification probe — fetches 10 India internship jobs via the JSearch
provider and prints title / company / location / apply URL.

Read-only: it calls the existing JSearchProvider.fetch() and modifies NO state and
NO pipelines. Delete this file after verifying.

Run:
    cd backend
    JSEARCH_API_KEY=<your-rapidapi-key> .venv/bin/python -m scripts.jsearch_probe
"""
import asyncio
import os
import sys

import httpx

from app.jobs.providers.jsearch import JSearchProvider


async def main():
    if not os.getenv("JSEARCH_API_KEY"):
        print("JSEARCH_API_KEY is not set — JSearch is gated off.\n"
              "Get a free key (RapidAPI → JSearch → Basic plan) and run:\n"
              "  JSEARCH_API_KEY=<your-key> .venv/bin/python -m scripts.jsearch_probe")
        sys.exit(1)

    prov = JSearchProvider()
    async with httpx.AsyncClient(timeout=20) as client:
        jobs = await prov.fetch(client, query="internship", location="India", limit=10)

    print(f"\nJSearch → 'internship in India' : {len(jobs)} job(s)\n")
    print(f"{'#':>2}  {'Title':38}  {'Company':22}  {'Location':20}  Apply URL")
    print("-" * 120)
    for i, j in enumerate(jobs[:10], 1):
        print(f"{i:>2}. {j.title[:38]:38}  {j.company[:22]:22}  {j.location[:20]:20}  {j.apply_url}")
    if not jobs:
        print("(no results — check the key, the 200/month free quota, or try a broader query)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
