"""Generate contracts/<Name>.schema.json from src/core/models.py.

Run from the repo root:  python -m contracts.generate
(`python contracts/generate.py` does not work: `src` is not importable from inside contracts/.)

The models are the source of truth. The committed schemas must equal what schemas() returns;
src/core/tests/test_contract_responses.py fails when they do not, so rerun this after any model change.
"""
import json
import pathlib

from pydantic import BaseModel, TypeAdapter

from src.core import models

HERE = pathlib.Path(__file__).parent

# Inner shapes first, then the enum, then the response bodies of src/api/main.py.
NAMES = [
    "Observation", "WorldState", "Step", "GateDecision", "VerifyResult", "Frame",
    "PlanOutcome",
    "SessionCreated", "PlanReply", "SessionDetail", "Health",
]


def _json_schema(shape) -> dict:
    if isinstance(shape, type) and issubclass(shape, BaseModel):
        return shape.model_json_schema()
    return TypeAdapter(shape).json_schema()  # plain enums have no model_json_schema()


def schemas() -> dict[str, dict]:
    """Name -> JSON Schema for every contract shape, built fresh from src/core/models.py."""
    return {name: _json_schema(getattr(models, name)) for name in NAMES}


def render(schema: dict) -> str:
    """The exact text of a schema file: indent 2, trailing newline."""
    return json.dumps(schema, indent=2) + "\n"


def main(out_dir: pathlib.Path = HERE) -> None:
    """Write contracts/<Name>.schema.json for every name in schemas(). LF line endings on every OS."""
    for name, schema in schemas().items():
        (out_dir / f"{name}.schema.json").write_text(render(schema), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
