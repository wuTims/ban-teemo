# Data Organization Design

**Status:** Approved
**Date:** 2026-01-25

---

## Problem

Data files are scattered across the repository with no clear organization:
- 114 MB of outputs too large to commit
- Pre-computed analytics in `knowledge/` not tracked
- Root-level data files (`synergies.json`, `knowledge_base.json`, etc.) scattered
- Two CSV versions (v1 and v2) with unclear status
- Documentation references outdated file structures

---

## Decisions

| Decision | Choice |
|----------|--------|
| Large data storage | GitHub Release |
| Release versioning | Semantic (`data-v1.0.0`) |
| knowledge/ directory | Committed to repo |
| Root data files | Move to `knowledge/` |
| CSV versions | v2 only, v1 archived |
| Raw JSON files | Included in release |
| Documentation | Update all three spec docs |

---

## Directory Structure

```
ban-teemo/
├── knowledge/                    # Committed to repo (~3 MB)
│   ├── champion_counters.json    # Computed matchup data
│   ├── champion_synergies.json   # Computed synergy data
│   ├── flex_champions.json       # Multi-role champions
│   ├── meta_stats.json           # Current meta statistics
│   ├── patch_info.json           # Patch dates & game counts
│   ├── player_proficiency.json   # Player performance data
│   ├── role_baselines.json       # Stat normalization baselines
│   ├── skill_transfers.json      # Champion similarity
│   ├── knowledge_base.json       # Champion metadata (moved from root)
│   ├── synergies.json            # Detailed synergy relationships (moved)
│   ├── player_roles.json         # Player primary roles (moved)
│   ├── patch_dates.json          # Patch version → date mapping (moved)
│   └── rework_patch_mapping.json # Champion rework history (moved)
│
├── outputs/                      # .gitignore'd, from release
│   └── full_2024_2025_v2/
│       ├── csv/                  # Processed data
│       └── raw/                  # Original GRID API responses
│
├── scripts/
│   └── download-data.sh          # Downloads release data
│
└── docs/                         # Updated documentation
```

---

## GitHub Release Structure

**Tag:** `data-v1.0.0`

**Assets:**
```
data-v1.0.0.tar.gz
└── full_2024_2025_v2/
    ├── csv/
    │   ├── champions.csv          # 7.2 KB
    │   ├── draft_actions.csv      # 6.8 MB
    │   ├── games.csv              # 210 KB
    │   ├── player_game_stats.csv  # 13 MB
    │   ├── players.csv            # 17 KB
    │   ├── series.csv             # 207 KB
    │   ├── teams.csv              # 1.2 KB
    │   ├── team_objectives.csv    # 6.8 MB (v2 new)
    │   └── tournaments.csv        # 4.6 KB (v2 new)
    └── raw/
        └── series_*.json          # ~2,973 files
```

**Version bump rules:**
- Patch (`v1.0.1`): Bug fixes, re-fetch same timeframe
- Minor (`v1.1.0`): New data, same schema
- Major (`v2.0.0`): Schema changes

---

## Implementation Phases

### Phase 1: File Organization
1. Move root data files to `knowledge/`
2. Update `.gitignore`
3. Delete `outputs/full_2024_2025/` (v1)

### Phase 2: Setup Script
4. Create `scripts/download-data.sh`

### Phase 3: Documentation
5. Update `lol_draft_assistant_hackathon_spec_v2.md`
6. Update `recommendation-service-overview.md`
7. Update `recommendation-service-architecture.md`

### Phase 4: Git & Release
8. Commit changes
9. Create tarball from v2 data
10. Create GitHub release `data-v1.0.0`
11. Upload tarball as release asset

### Phase 5: Cleanup
12. Verify download script
13. Remove local `outputs/`

---

*Design approved 2026-01-25*
