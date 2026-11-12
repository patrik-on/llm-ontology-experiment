"""Model-free broader static EVAL census; bounded streaming, source not printed."""

import json
import tarfile
from pathlib import Path
from collections import Counter
from llm_ontology.benchmarks.methods2test_selection import infer_spec, ARCHIVE
from llm_ontology.benchmarks.defects4j_execution import write_json

out = Path("artifacts/methods2test_hundred_census")
out.mkdir(exist_ok=False)
reasons = Counter()
eligible = []
records = 0
size = 0
projects = set()
with tarfile.open(ARCHIVE, "r|bz2") as tar:
    for member in tar:
        if not member.isfile() or not member.name.endswith(".json"):
            continue
        records += 1
        size += member.size
        if records > 80000 or size > 3000000000:
            break
        if member.size > 4000000:
            reasons["member_size"] += 1
            continue
        d = json.load(tar.extractfile(member))
        projects.add(str(d["repository"]["repo_id"]))
        try:
            spec = infer_spec(d)
        except ValueError as exc:
            reasons[str(exc)] += 1
            continue
        eligible.append(
            {
                "id": Path(member.name).stem,
                "repository": d["repository"]["url"],
                "focal_bytes": len(d["focal_method"]["body"].encode()),
                "reference_bytes": len(d["test_case"]["body"].encode()),
            }
        )
        if records % 1000 == 0:
            print("CENSUS", records, "ELIGIBLE", len(eligible), flush=True)
write_json(
    out / "census.json",
    {
        "records": records,
        "payload_bytes": size,
        "projects": len(projects),
        "eligible": eligible,
        "rejections": dict(reasons),
        "model_calls": 0,
    },
)
print("CENSUS_COMPLETE", records, "PROJECTS", len(projects), "ELIGIBLE", len(eligible), flush=True)
