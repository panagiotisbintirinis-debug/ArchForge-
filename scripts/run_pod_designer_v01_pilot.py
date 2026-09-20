"""Run the reproducible Pod Designer v0.1 evidence pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make direct "python scripts/..." execution work from a source checkout.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archforge.pilot_v01 import write_evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute Pod Designer v0.1 and write machine/human-readable evidence."
    )
    parser.add_argument(
        "--output-dir",
        default="pilot_artifacts/v01",
        help="Directory for .archforge runs, JSON evidence, and text summary.",
    )
    args = parser.parse_args()

    json_path, summary_path, evidence = write_evidence(Path(args.output_dir))
    print(json.dumps({
        "outcome": evidence["outcome"],
        "evidence": str(json_path),
        "summary": str(summary_path),
        "fingerprint": evidence["determinism"]["run_1_fingerprint"],
        "evidence_hash": evidence["evidence_hash"],
    }, indent=2, sort_keys=True))
    return 0 if evidence["outcome"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
