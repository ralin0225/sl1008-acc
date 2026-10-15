"""Structural validation complements, but never replaces, deterministic checks."""
import sys
from compliance_contract import ACC, read

sys.path[:0] = [str(ACC / ".python_deps"), str(ACC / ".semantic_deps")]
from jsonschema import Draft202012Validator


def validate(name, value):
    schema = read(ACC / "schemas" / f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
