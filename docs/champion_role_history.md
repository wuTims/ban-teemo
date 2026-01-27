# Champion Role History Dataset

This dataset tracks champion role evolution over time and detects meta shifts.

## Purpose

Solves the "stale meta" problem where historical off-meta picks persist in recommendations after the meta ends.

## Key Fields

### Per Champion

| Field | Description |
|-------|-------------|
| `canonical_role` | The champion's "intended" role from knowledge_base.json |
| `canonical_all` | All canonical roles including flex positions |
| `current_viable_roles` | **Use this for recommendations** - roles that are currently playable |
| `current_distribution` | Role rates in recent patches |
| `meta_shifts` | History of off-meta role emergence and endings |
| `role_by_patch` | Detailed per-patch role distributions |

### Meta Shift Object

```json
{
  "role": "JUNGLE",
  "started_patch": "15.10",
  "ended_patch": "15.15",      // null if still active
  "peak_patch": "15.12",
  "peak_rate": 0.52,
  "status": "ended",           // "active" or "ended"
  "reason": "no_recent_picks"
}
```

## Usage Example

```python
import json

with open('knowledge/champion_role_history.json') as f:
    role_history = json.load(f)

def get_viable_roles(champion: str) -> list[str]:
    """Get roles that should be recommended for this champion."""
    if champion in role_history['champions']:
        return role_history['champions'][champion]['current_viable_roles']
    return []

# Example
viable = get_viable_roles("Zyra")  
# Returns ['JUNGLE', 'SUP'] if Zyra JNG is still meta
# Returns ['SUP'] if Zyra JNG meta ended
```

## How "Current Viable" is Determined

1. **Always includes canonical role** - Safe fallback, always valid
2. **Adds roles with ≥10% play rate in last 3 patches** - Currently being played
3. **Excludes ended meta shifts** - No longer viable

## Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `meta_window_patches` | 3 | Patches to consider "recent" |
| `min_role_rate_for_viable` | 0.10 | 10% threshold for viability |
| `meta_shift_threshold` | 0.15 | 15% threshold to detect meta shift |

## Example: Anivia Fix

**Before (flex_champions.json):**
- Showed 77.8% TOP because of 9 historical games
- Would incorrectly suggest Anivia TOP

**After (champion_role_history.json):**
- `canonical_role: "MID"`
- `current_viable_roles: ["MID"]`
- `meta_shifts: [{role: "TOP", status: "ended", ended_patch: "15.10"}]`
- Correctly only suggests MID
