#!/usr/bin/env python3
"""Diagnostic: inspect the real shape of JSearch's /search-v2 response.

Usage:
    export RAPIDAPI_KEY=your_key_here
    python diagnose_jsearch.py
"""
import json
import os

import requests

API_URL = "https://jsearch.p.rapidapi.com/search-v2"

key = os.environ.get("RAPIDAPI_KEY")
if not key:
    raise SystemExit("Set RAPIDAPI_KEY environment variable first.")

headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
params = {"query": "data engineer remote", "date_posted": "week"}

print(f"Calling {API_URL} with params={params} ...")
resp = requests.get(API_URL, headers=headers, params=params, timeout=45)
print(f"status: {resp.status_code}")

payload = resp.json()
print(f"\ntop-level type: {type(payload)}")

if isinstance(payload, dict):
    print(f"top-level keys: {list(payload.keys())}")
    for key_name, val in payload.items():
        print(f"  '{key_name}': type={type(val).__name__}", end="")
        if isinstance(val, (list, str)):
            print(f", len={len(val)}")
        else:
            print()

    # Try to find the actual jobs list, whatever it's nested under
    data = payload.get("data")
    print(f"\npayload['data'] type: {type(data)}")
    if isinstance(data, str):
        print(f"payload['data'] as string (first 300 chars): {data[:300]!r}")
    elif isinstance(data, list):
        print(f"payload['data'] is a list with {len(data)} items")
        if data:
            print(f"first item type: {type(data[0])}")
            print(f"first item: {json.dumps(data[0], ensure_ascii=False, default=str)[:500] if isinstance(data[0], dict) else data[0]!r}")
    elif isinstance(data, dict):
        print(f"payload['data'] is a dict with keys: {list(data.keys())}")

print("\nFull raw response (first 1500 chars):")
print(resp.text[:1500])