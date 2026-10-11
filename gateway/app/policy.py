from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class Scope(str, Enum):
    FILTER = "filter"
    LIGHTING = "lighting"
    CROP = "crop"
    BACKGROUND = "background"
    FACE_SWAP = "face_swap"
    PHOTO_ANIMATION = "photo_animation"
    BODY_EDIT = "body_edit"
    VOICE_CLONE = "voice_clone"
    SEXUAL_TRANSFORMATION = "sexual_transformation"
    NUDE_TRANSFORMATION = "nude_transformation"


class Tier(int, Enum):
    BENIGN = 0
    IDENTITY_ALTERING = 1
    SEXUAL_REAL_FACE = 2


SCOPE_TIERS = MappingProxyType(
    {
        Scope.FILTER: Tier.BENIGN,
        Scope.LIGHTING: Tier.BENIGN,
        Scope.CROP: Tier.BENIGN,
        Scope.BACKGROUND: Tier.BENIGN,
        Scope.FACE_SWAP: Tier.IDENTITY_ALTERING,
        Scope.PHOTO_ANIMATION: Tier.IDENTITY_ALTERING,
        Scope.BODY_EDIT: Tier.IDENTITY_ALTERING,
        Scope.VOICE_CLONE: Tier.IDENTITY_ALTERING,
        Scope.SEXUAL_TRANSFORMATION: Tier.SEXUAL_REAL_FACE,
        Scope.NUDE_TRANSFORMATION: Tier.SEXUAL_REAL_FACE,
    }
)

RISK_BLOCK_THRESHOLD = 0.85


def validate_policy() -> None:
    if set(SCOPE_TIERS) != set(Scope):
        raise ValueError("Every supported scope must have exactly one policy tier.")
    if any(not isinstance(tier, Tier) for tier in SCOPE_TIERS.values()):
        raise ValueError("Policy tiers must use the Tier enum.")
    if not 0 <= RISK_BLOCK_THRESHOLD <= 1:
        raise ValueError("The request-risk threshold must be between 0 and 1.")
