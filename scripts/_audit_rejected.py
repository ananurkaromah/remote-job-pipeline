import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rjp.extract.himalayas import HimalayasExtractor
from rjp.extract.registry import extract_all_sources
from rjp.extract.remoteok import RemoteOKExtractor
from rjp.extract.remotive import RemotiveExtractor
from rjp.transform.pipeline import transform_all

results = extract_all_sources([RemoteOKExtractor(), RemotiveExtractor(), HimalayasExtractor()])
raw_jobs = [j for r in results for j in r.jobs]
kept, rejected, skipped = transform_all(raw_jobs)

for r in rejected:
    if r["reason"] == "dropped:not_data_engineering_role":
        print(r.get("title"))