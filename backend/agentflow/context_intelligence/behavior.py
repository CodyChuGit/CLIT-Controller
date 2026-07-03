"""Behavior policy: Ponytail owns the rules; this only exposes them typed."""

from __future__ import annotations

from .. import ponytail
from .types import BehaviorPolicy


def build_policy() -> BehaviorPolicy:
    """Structured Ponytail policy. When the level is ``off`` the block is empty,
    matching how live prompts behave today. The rules text itself lives in
    ``ponytail.py`` and is never duplicated here."""
    level = ponytail.level()
    return BehaviorPolicy(level=level, block=ponytail.block(level))
