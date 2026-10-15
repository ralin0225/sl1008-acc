"""One local model registry shared by exporters and the Viewer run endpoint."""
import json
from pathlib import Path

ACC = Path(__file__).resolve().parents[1]


def model_catalog():
    entries = json.loads((ACC / "models/catalog.json").read_text(encoding="utf-8"))["models"]
    ids = set()
    for entry in entries:
        identifier, filename = entry["id"], entry["filename"]
        if identifier in ids or not identifier or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in identifier):
            raise ValueError("Invalid or duplicate model identifier")
        if Path(filename).name != filename or not filename.lower().endswith(".ifc"):
            raise ValueError("Model filename must be a local IFC filename")
        ids.add(identifier)
    return entries


def model_paths():
    return {entry["id"]: ACC / "models" / entry["id"] / entry["filename"] for entry in model_catalog()}
