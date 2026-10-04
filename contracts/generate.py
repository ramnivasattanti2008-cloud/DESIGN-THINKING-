"""Regenerate contracts/*.schema.json from src/core/models.py. Run: python contracts/generate.py"""
import json
import pathlib

from src.core import models

HERE = pathlib.Path(__file__).parent
for name in ["Observation", "WorldState", "Step", "GateDecision", "VerifyResult", "Frame"]:
    schema = getattr(models, name).model_json_schema()
    (HERE / f"{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
