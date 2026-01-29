"""Centralized role normalization utility.

All role normalization in the codebase should use this module to ensure
consistency. The canonical format is lowercase: top, jungle, mid, bot, support.
"""

from typing import Optional

# Canonical roles - the standard format used throughout the application
CANONICAL_ROLES = frozenset({"top", "jungle", "mid", "bot", "support"})

# Comprehensive mapping from any known role format to canonical lowercase
ROLE_ALIASES: dict[str, str] = {
    # Top lane variations
    "top": "top",
    "TOP": "top",
    "top laner": "top",
    "toplane": "top",
    "topside": "top",

    # Jungle variations
    "jungle": "jungle",
    "JUNGLE": "jungle",
    "jungler": "jungle",
    "jng": "jungle",
    "JNG": "jungle",
    "jg": "jungle",
    "JG": "jungle",

    # Mid lane variations
    "mid": "mid",
    "MID": "mid",
    "middle": "mid",
    "MIDDLE": "mid",
    "mid laner": "mid",
    "midlane": "mid",

    # Bot/ADC variations - all normalize to "bot"
    "bot": "bot",
    "BOT": "bot",
    "adc": "bot",
    "ADC": "bot",
    "bottom": "bot",
    "BOTTOM": "bot",
    "bot laner": "bot",
    "ad carry": "bot",
    "marksman": "bot",
    "carry": "bot",

    # Support variations
    "support": "support",
    "SUPPORT": "support",
    "sup": "support",
    "SUP": "support",
    "supp": "support",
}


def normalize_role(role: Optional[str]) -> Optional[str]:
    """Normalize a role string to canonical lowercase format.

    Args:
        role: Role string in any known format (e.g., "JNG", "jungle", "ADC", "bot")

    Returns:
        Normalized role string (top/jungle/mid/bot/support) or None if invalid/None

    Examples:
        >>> normalize_role("JNG")
        'jungle'
        >>> normalize_role("ADC")
        'bot'
        >>> normalize_role("SUPPORT")
        'support'
        >>> normalize_role(None)
        None
    """
    if role is None:
        return None

    role_lower = role.strip().lower()

    # Try direct lookup first
    if role in ROLE_ALIASES:
        return ROLE_ALIASES[role]

    # Try lowercase lookup
    if role_lower in ROLE_ALIASES:
        return ROLE_ALIASES[role_lower]

    # If already canonical, return as-is
    if role_lower in CANONICAL_ROLES:
        return role_lower

    # Unknown role - return None to indicate invalid
    return None


def normalize_role_strict(role: str) -> str:
    """Normalize a role string, raising ValueError if unknown.

    Args:
        role: Role string in any known format

    Returns:
        Normalized role string (top/jungle/mid/bot/support)

    Raises:
        ValueError: If role is not recognized
    """
    normalized = normalize_role(role)
    if normalized is None:
        raise ValueError(f"Unknown role: {role}")
    return normalized


def is_valid_role(role: Optional[str]) -> bool:
    """Check if a role string is valid (can be normalized).

    Args:
        role: Role string to check

    Returns:
        True if role can be normalized to a canonical role
    """
    return normalize_role(role) is not None


def get_canonical_roles() -> frozenset[str]:
    """Get the set of canonical role names.

    Returns:
        Frozenset of canonical roles: {top, jungle, mid, bot, support}
    """
    return CANONICAL_ROLES


# Role ordering for consistent display/sorting
ROLE_ORDER = ["top", "jungle", "mid", "bot", "support"]


def sort_by_role(players: list[dict], role_key: str = "role") -> list[dict]:
    """Sort a list of player dicts by role in standard order.

    Args:
        players: List of player dicts with role field
        role_key: Key name for the role field (default: "role")

    Returns:
        Sorted list of players (top, jungle, mid, bot, support)
    """
    def role_sort_key(player: dict) -> int:
        role = normalize_role(player.get(role_key))
        try:
            return ROLE_ORDER.index(role) if role else 99
        except ValueError:
            return 99

    return sorted(players, key=role_sort_key)
