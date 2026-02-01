"""Helpers for determining current role viability from role history data."""
from typing import Optional, Iterable

from ban_teemo.utils.role_normalizer import normalize_role, CANONICAL_ROLES


CURRENT_ROLE_THRESHOLD = 0.10


def _normalize_roles(roles: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for role in roles:
        normalized_role = normalize_role(role)
        if normalized_role in CANONICAL_ROLES:
            normalized.add(normalized_role)
    return normalized


def extract_current_role_viability(
    champ_data: Optional[dict], threshold: float = CURRENT_ROLE_THRESHOLD
) -> tuple[Optional[set[str]], bool]:
    """Extract current viable roles for a champion.

    Returns:
        (roles, has_current_data)
        - roles is a set of canonical roles, possibly empty if current data exists but no viable roles.
        - has_current_data indicates if current_* fields were present (even if empty).
    """
    if not isinstance(champ_data, dict):
        return None, False

    if "current_viable_roles" in champ_data:
        roles = champ_data.get("current_viable_roles") or []
        return _normalize_roles(roles), True

    if "current_distribution" in champ_data:
        distribution = champ_data.get("current_distribution") or {}
        roles = set()
        for role, pct in distribution.items():
            try:
                pct_val = float(pct)
            except (TypeError, ValueError):
                continue
            if pct_val >= threshold:
                normalized_role = normalize_role(role)
                if normalized_role in CANONICAL_ROLES:
                    roles.add(normalized_role)
        return roles, True

    return None, False
