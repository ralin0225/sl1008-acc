"""Publish local compliance snapshots for the existing Viewer, retaining history."""
import sys
from pathlib import Path

VIEWER = Path(__file__).resolve().parent
ACC = VIEWER.parent
sys.path.insert(0, str(ACC / "src"))
from compliance_contract import read, save, load_contracts
from compliance_runner import run
from model_catalog import model_paths


def main():
    save(VIEWER / "dist/data/check-contracts.json", load_contracts())
    for model_id, path in model_paths().items():
        facts_path = ACC / "reviewed_facts" / f"{model_id}.json"
        report = run(path, model_id, read(facts_path) if facts_path.exists() else None)
        save(VIEWER / "dist/data" / f"compliance-{model_id}.json", report)
        print(model_id, report["summary"])


if __name__ == "__main__":
    main()
