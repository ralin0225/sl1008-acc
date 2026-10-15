"""Rebuild and validate ACC foundation only; never rerun completed PDF/RDF steps."""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent


def main():
    for name in ["build_acc_foundation.py", "build_rule_context.py", "build_mvp_catalog.py", "generate_acc_ids.py", "validate_acc_foundation.py"]:
        print(f"Running {name}", flush=True)
        outcome = subprocess.run([sys.executable, str(SRC / name)], check=False)
        if outcome.returncode:
            return outcome.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
