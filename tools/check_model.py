"""One real model call with one photo: what would MIRROR see, and how long does it take?

Usage (PowerShell):
    $env:MIRROR_MODEL_PROVIDER = "gemini"          # or "anthropic"
    $env:MIRROR_MODEL_API_KEY = "<your key>"       # Google AI Studio gives a free Gemini key
    python tools/check_model.py path\\to\\photo.jpg

This SENDS the photo to the model provider. Use a photo you are happy to share (no people,
documents or screens). It refuses to run with the fake provider, because that would prove nothing.
The result is one measurement, not an accuracy or latency benchmark.
"""
from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.engine import CLUTTER, HAZARDS, NEEDS  # noqa: E402
from src.core.model_client import FakeModelClient, ModelClient, ModelError, build_model_client  # noqa: E402
from src.core.models import Frame  # noqa: E402

MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_BYTES = 4 * 1024 * 1024


def vocabulary() -> list[str]:
    """The same word list the backend gives the model."""
    return sorted(CLUTTER | HAZARDS | {i for items in NEEDS.values() for i in items} | {"desk"})


def run(photo: Path, client: ModelClient, out=print) -> int:
    """Returns 0 on success, 1 if the model call failed, 2 if the check could not be set up."""
    if isinstance(client, FakeModelClient):
        out("The fake provider cannot read photos, so this check would prove nothing. "
            "Set MIRROR_MODEL_PROVIDER=gemini (or anthropic) and MIRROR_MODEL_API_KEY.")
        return 2
    media = MEDIA.get(photo.suffix.lower())
    if media is None:
        out(f"Unsupported file type {photo.suffix!r}. Use .jpg, .png or .webp.")
        return 2
    try:
        data = photo.read_bytes()
    except OSError as exc:
        out(f"Cannot read {photo}: {exc.strerror}")
        return 2
    if len(data) > MAX_BYTES:
        out("The photo is larger than 4 MB. Resize it first.")
        return 2
    frame = Frame(id="check-1", data_b64=base64.b64encode(data).decode("ascii"), media_type=media)
    start = time.perf_counter()
    try:
        observations = client.observe([frame])
    except ModelError as exc:
        out(f"MODEL ERROR: {exc}")
        return 1
    seconds = time.perf_counter() - start
    out(f"Provider: {type(client).__name__} | one call took {seconds:.1f} s | {len(observations)} object(s)")
    for o in sorted(observations, key=lambda o: -o.confidence):
        out(f"  {o.label:<24} confidence {o.confidence:.2f}  {o.where_hint}".rstrip())
    out("This is a single measurement, not an accuracy or latency benchmark.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make one real model call with one photo.")
    parser.add_argument("photo", type=Path, help="path to a .jpg, .png or .webp photo")
    args = parser.parse_args(argv)
    try:
        client = build_model_client(vocabulary())
    except ModelError as exc:
        print(f"CONFIG ERROR: {exc}")
        return 2
    return run(args.photo, client)


if __name__ == "__main__":
    sys.exit(main())
