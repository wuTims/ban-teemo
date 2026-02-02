/**
 * Centralized score component labels for consistent display across the app.
 *
 * All component labels should use FULL DESCRIPTIVE NAMES for clarity.
 * This is the single source of truth for label display.
 */

// Pick recommendation component labels (full names)
export const PICK_COMPONENT_LABELS: Record<string, string> = {
  // Tournament meta components
  tournament_priority: "Tournament Priority",
  tournament_performance: "Tournament Performance",

  // Scoring components
  matchup_counter: "Matchup Counter",
  matchup: "Lane Matchup",
  counter: "Team Counter",
  archetype: "Archetype Fit",
  synergy: "Team Synergy",
  proficiency: "Player Proficiency",
  meta: "Meta Strength",
};

// Ban recommendation component labels (full names)
export const BAN_COMPONENT_LABELS: Record<string, string> = {
  // Tournament meta components (Phase 1 primary)
  tournament_priority: "Tournament Priority",

  // Phase 1 components
  meta: "Meta Strength",
  presence: "Pro Presence",
  flex: "Flex Value",
  proficiency: "Player Proficiency",
  tier_bonus: "Tier Bonus",

  // Phase 2 components
  comfort: "Comfort Level",
  confidence: "Data Confidence",

  // Contextual ban components (Phase 2)
  archetype_counter: "Archetype Disruption",
  synergy_denial: "Synergy Denial",
  role_denial: "Role Denial",
  counter_our_picks: "Counters Our Picks",
  counter: "Counter Threat",
};

// Order for displaying ban components (most important first)
export const BAN_COMPONENT_ORDER = [
  "tournament_priority",
  "meta",
  "presence",
  "flex",
  "proficiency",
  "tier_bonus",
  "comfort",
  "confidence",
  "archetype_counter",
  "synergy_denial",
  "role_denial",
  "counter_our_picks",
  "counter",
];

// Component explanations for tooltips
export const COMPONENT_EXPLANATIONS: Record<string, string> = {
  // Tournament meta
  tournament_priority: "How often pros pick/ban this champion in recent tournaments",
  tournament_performance: "Role-specific winrate in recent pro play, adjusted for sample size",

  // Pick components
  archetype: "How well this champion fits your team's strategic identity (engage, poke, protect, etc.)",
  meta: "Champion's current strength in pro meta based on win rate and pick/ban rate",
  matchup_counter: "Combined lane matchup and team-wide counter advantage",
  matchup: "Lane matchup advantage against your opponent",
  counter: "Team-wide counter potential against enemy composition",
  proficiency: "Player's comfort and experience with this champion",
  synergy: "How well this champion synergizes with teammates",

  // Ban components
  presence: "How contested this champion is (pick rate + ban rate)",
  flex: "Role versatility - harder to plan against",
  comfort: "Player familiarity based on games played",
  confidence: "Data quality - HIGH/MEDIUM/LOW based on sample size",
  tier_bonus: "Bonus for matching high-priority tier conditions",

  // Contextual ban components
  archetype_counter: "How much banning this disrupts enemy's team composition direction",
  synergy_denial: "Denies strong synergy completion with enemy picks",
  role_denial: "Fills a role enemy still needs with a player's comfort pick",
  counter_our_picks: "This champion counters what we've already picked",
};

/**
 * Get display label for a component key.
 * Falls back to formatting the key if not found.
 */
export function getComponentLabel(key: string, isPick: boolean): string {
  const labels = isPick ? PICK_COMPONENT_LABELS : BAN_COMPONENT_LABELS;
  if (labels[key]) {
    return labels[key];
  }
  // Fallback: format the key (e.g., "counter_our_picks" -> "Counter Our Picks")
  return key
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Get explanation for a component (for tooltips).
 */
export function getComponentExplanation(key: string): string | undefined {
  return COMPONENT_EXPLANATIONS[key];
}

/**
 * Get top N ban components sorted by value, with labels.
 */
export function getTopBanComponents(
  components: Record<string, number> | undefined,
  limit: number = 5
): Array<{ key: string; label: string; value: number }> {
  if (!components) return [];

  return Object.entries(components)
    .filter(([key, value]) =>
      BAN_COMPONENT_LABELS[key] &&
      value !== undefined &&
      key !== "tier" // Exclude tier string values
    )
    .map(([key, value]) => ({
      key,
      label: BAN_COMPONENT_LABELS[key],
      value,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}
