"""Restore XML identifiers omitted by IfcTester 0.9.0's Specification.parse."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".python_deps"))
from defusedxml import ElementTree
import ifctester


def load_ids(path):
    model = ifctester.open(str(path))
    xml_specs = ElementTree.parse(path).findall("{http://standards.buildingsmart.org/IDS}specifications/{http://standards.buildingsmart.org/IDS}specification")
    if len(xml_specs) != len(model.specifications):
        raise ValueError("IDS XML/specification count mismatch")
    for spec, element in zip(model.specifications, xml_specs):
        if spec.name != element.get("name"):
            raise ValueError("IDS specification ordering mismatch")
        spec.identifier = element.get("identifier")
        if not spec.identifier:
            raise ValueError(f"IDS specification missing source identifier: {spec.name}")
    return model
