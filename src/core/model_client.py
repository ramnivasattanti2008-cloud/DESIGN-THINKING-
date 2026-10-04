"""ModelClient: the single place a model provider is called.

Only the fake provider exists so far. It is deterministic and reads Frame.fake_labels,
so it proves the loop and the policy, not real perception. Real providers (see D-002)
plug in behind the same Protocol.
"""
from typing import Protocol

from .models import Frame, Observation


class ModelClient(Protocol):
    def observe(self, frames: list[Frame]) -> list[Observation]: ...


class FakeModelClient:
    """Test double. Labels are written as `name` (confidence 0.9) or `name:0.4`."""

    def observe(self, frames: list[Frame]) -> list[Observation]:
        out: list[Observation] = []
        for frame in frames:
            for i, raw in enumerate(frame.fake_labels):
                label, _, conf = raw.partition(":")
                out.append(
                    Observation(
                        id=f"{frame.id}-{i}",
                        label=label.strip().lower(),
                        confidence=float(conf) if conf else 0.9,
                        source_frame=frame.id,
                    )
                )
        return out
