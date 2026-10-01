#!/usr/bin/env python3
"""Diagnostic: inspect the real shape of each source's API response.

Run this directly (no rjp import needed) to see exactly what changed
compared to what the extractors currently assume.

Usage:
    python diagnose_sources.py
"""
import json

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def show(name, url, params=None):
    print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        print(f"status: {resp.status_code}")
        payload = resp.json()
    except Exception as e:
        print(f"ERROR: {e}")
        return

    if isinstance(payload, dict):
        print(f"top-level keys: {list(payload.keys())}")
        for key in payload:
            val = payload[key]
            if isinstance(val, list):
                print(f"  '{key}' is a LIST with {len(val)} items")
                if val:
                    print(f"    first item keys: {list(val[0].keys()) if isinstance(val[0], dict) else type(val[0])}")
                    print(f"    first item sample: {json.dumps(val[0], ensure_ascii=False)[:400]}")
    elif isinstance(payload, list):
        print(f"top-level is a LIST with {len(payload)} items")
        real_jobs = [e for e in payload if isinstance(e, dict) and "position" in e]
        print(f"items with a 'position' key: {len(real_jobs)}")
        if real_jobs:
            print(f"sample title: {real_jobs[0].get('position')!r}")
            titles_matching = [e for e in real_jobs if "data engineer" in (e.get("position") or "").lower()
                                or "etl" in (e.get("position") or "").lower()]
            print(f"titles matching 'data engineer' or 'etl': {len(titles_matching)}")


show("Remotive", "https://remotive.com/api/remote-jobs", params={"search": "data engineer"})
show("RemoteOK (with tags param)", "https://remoteok.com/api", params={"tags": "data-engineer"})
show("RemoteOK (no params)", "https://remoteok.com/api")
show("Himalayas", "https://himalayas.app/jobs/api", params={"limit": 20})
