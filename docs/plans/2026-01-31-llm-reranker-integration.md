# LLM Reranker Integration Plan

**Status:** Experiments Complete | Integration Deferred
**Last Updated:** 2026-01-31

---

## Executive Summary

After extensive experimentation, the LLM reranker provides **strategic insights but no accuracy improvement** over the baseline algorithm. The recommendation is to use LLM for **insight generation only**, not for reranking.

### Key Metrics

| Metric | Baseline | LLM | Delta |
|--------|----------|-----|-------|
| **Overall hit rate** | 10/20 (50%) | 10/20 (50%) | 0% |
| Pick accuracy (in top 5) | 6/10 (60%) | 6/10 (60%) | 0% |
| Ban accuracy (in top 5) | 4/10 (40%) | 4/10 (40%) | 0% |
| LLM ranking improvements | - | 3 actions | +15% |
| LLM ranking degradations | - | 1 action | -5% |

---

## Experiment Findings

### Finding 1: Phase 1 vs Phase 2 Value

| Phase | Ranking Improvements | Insight Quality |
|-------|---------------------|-----------------|
| **Phase 1** (Actions 1-12) | 3 improvements (Wukong, Orianna, Vi) | Generic ("focus on meta champions") |
| **Phase 2** (Actions 13-20) | 0 improvements | Specific ("Enemy building engage with Vi and Galio") |

**Insight:** LLM provides more ranking value in Phase 1 (player comfort/meta power), but better analytical insights in Phase 2 (draft strategy analysis).

### Finding 2: LLM Cannot Predict Missing Champions

Of 10 missed recommendations:
- **3 champions** were suggested by LLM elsewhere (Xin Zhao, Galio, Rakan)
- **7 champions** were NEVER suggested (Bard, Jarvan IV, Pantheon, Corki, Aurora, Renekton, Ambessa)

**Root cause:** LLM lacks:
1. Real-time meta knowledge (patch-specific champion strength)
2. Team-specific strategy (actual game plan)
3. Recent scrim/practice data
4. Player champion pool updates

### Finding 3: Expanding Candidate Pool Won't Help

The LLM suggests generic "safe" picks repeatedly:
- Aatrox (5x), Janna (5x), Ahri (4x), Alistar (3x)

These don't match actual picks which are strategic/situational. The LLM can reorder what it's given but cannot identify truly correct picks.

### Finding 4: Web Search Removed

Tavily web search was removed because:
1. Generic tier lists don't help with player-specific decisions
2. No domain targeting for esports sources
3. Added latency (~500ms) without accuracy benefit
4. Cost ($0.01/query) without value

---

## Architectural Decisions

### Decision 1: LLM for Insights Only

**Use LLM to generate `draft_analysis` text, not to rerank recommendations.**

Current output format works well for insights:
```json
{
  "draft_analysis": "Enemy strategy: Engage-focused composition with Vi and Galio.
   Counter picks: Rumble and Sion for Kiin (top) because they provide strong area
   control against engage. Rell and Braum for Duro (support) for peel and protection."
}
```

### Decision 2: Phase 2 Only (Cost Optimization)

Run LLM on Phase 2 actions only (8 of 20):
- **60% cost reduction** ($0.025 vs $0.062 per game)
- **Better insight quality** in Phase 2
- Phase 1 insights are too generic to be valuable

### Decision 3: Keep Baseline Rankings

Show baseline algorithm rankings as primary recommendations. LLM insights are supplementary context, not replacements.

---

## Implementation Status

### Completed

- [x] LLMReranker service with strategic context
- [x] Phase-specific prompting (Phase 1 vs Phase 2)
- [x] Available champions by role context
- [x] Player-specific recommendation format
- [x] Role filtering (don't recommend filled roles)
- [x] Flex champion awareness
- [x] Experiment scripts (`run_llm_experiment.py`)
- [x] Web search removed (no benefit)

### Deferred (Not Recommended)

- [ ] WebSocket integration for live reranking
- [ ] Frontend `LLMInsightsPanel` component
- [ ] Real-time LLM calls during replay

### Optional Future Work

- [ ] Display `draft_analysis` as insight text in UI
- [ ] Add "LLM Insight" toggle to show/hide analysis
- [ ] Log insights for coaching review

---

## Cost Analysis

| Configuration | Actions/Game | Cost/Game | Cost/100 Games |
|---------------|--------------|-----------|----------------|
| All phases | 20 | $0.062 | $6.20 |
| Phase 2 only | 8 | $0.025 | $2.50 |
| Insights only (no rerank) | 4-8 | $0.012-0.025 | $1.25-2.50 |

Model: DeepSeek-V3-0324-fast via Nebius (~2.6s latency, ~$0.003/call)

---

## Files Modified

```
backend/src/ban_teemo/services/llm_reranker.py  # Core service
backend/tests/test_llm_reranker.py              # Tests updated
scripts/run_llm_experiment.py                    # Experiment runner
results/experiment_fixed.json                    # Latest results
```

---

## Recommendation

**Do not integrate LLM reranking into production.** The accuracy benefit is zero, and the cost/latency overhead isn't justified.

**Consider instead:**
1. Display LLM `draft_analysis` as coaching insight text
2. Use for post-game analysis rather than live recommendations
3. Invest in improving baseline algorithm (champion pool data, meta tier lists)

---

## Appendix: Sample Outputs

### Phase 1 Insight (Generic)
```
Phase 1 ban strategy should focus on removing high-priority comfort picks
from T1's players, particularly targeting Faker's Azir and Keria's Poppy.
```

### Phase 2 Insight (Specific)
```
Enemy strategy: Engage-focused composition with Vi and Galio.
Counter picks: Rumble and Sion for Kiin (top) because they provide
strong area control and disruption against engage. Rell and Braum
for Duro (support) because they offer peel and protection against dive.
```

### Ranking Improvement Example
```
Action 10: Vi
- Baseline rank: #5
- LLM rank: #3 (↑2)
- Reasoning: "Strong team proficiency and favorable lane matchups"
```
