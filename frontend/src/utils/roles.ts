/**
 * Centralized role utilities for the frontend.
 *
 * Role formats:
 * - Backend (canonical): lowercase - "top", "jungle", "mid", "bot", "support"
 * - Display (abbreviated): uppercase - "TOP", "JNG", "MID", "ADC", "SUP"
 * - Friendly (full names): title case - "Top", "Jungle", "Mid", "Bot", "Support"
 */

// Backend canonical role names (what the API sends/receives)
export const BACKEND_ROLES = ["top", "jungle", "mid", "bot", "support"] as const;
export type BackendRole = typeof BACKEND_ROLES[number];

// Display role abbreviations (used in UI)
export const DISPLAY_ROLES = ["TOP", "JNG", "MID", "ADC", "SUP"] as const;
export type DisplayRole = typeof DISPLAY_ROLES[number];

// Friendly role names (for labels and descriptions)
export const FRIENDLY_ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"] as const;
export type FriendlyRole = typeof FRIENDLY_ROLES[number];

// Role order for iteration (using display format)
export const ROLE_ORDER = DISPLAY_ROLES;

// Mapping: backend -> display
export const BACKEND_TO_DISPLAY: Record<BackendRole, DisplayRole> = {
  top: "TOP",
  jungle: "JNG",
  mid: "MID",
  bot: "ADC",
  support: "SUP",
};

// Mapping: display -> backend
export const DISPLAY_TO_BACKEND: Record<DisplayRole, BackendRole> = {
  TOP: "top",
  JNG: "jungle",
  MID: "mid",
  ADC: "bot",
  SUP: "support",
};

// Mapping: display -> friendly
export const DISPLAY_TO_FRIENDLY: Record<DisplayRole, FriendlyRole> = {
  TOP: "Top",
  JNG: "Jungle",
  MID: "Mid",
  ADC: "Bot",
  SUP: "Support",
};

// Mapping: backend -> friendly
export const BACKEND_TO_FRIENDLY: Record<BackendRole, FriendlyRole> = {
  top: "Top",
  jungle: "Jungle",
  mid: "Mid",
  bot: "Bot",
  support: "Support",
};

// Combined role info for iteration
export const ROLE_INFO = [
  { backend: "top", display: "TOP", friendly: "Top" },
  { backend: "jungle", display: "JNG", friendly: "Jungle" },
  { backend: "mid", display: "MID", friendly: "Mid" },
  { backend: "bot", display: "ADC", friendly: "Bot" },
  { backend: "support", display: "SUP", friendly: "Support" },
] as const;

/**
 * Convert any role format to display format (TOP, JNG, MID, ADC, SUP)
 * Handles: backend lowercase, display uppercase, or mixed case
 */
export function toDisplayRole(role: string): DisplayRole {
  const lower = role.toLowerCase().trim();

  // Check if it's a backend role
  if (lower in BACKEND_TO_DISPLAY) {
    return BACKEND_TO_DISPLAY[lower as BackendRole];
  }

  // Check if it's already a display role (case-insensitive)
  const upper = role.toUpperCase().trim();
  if (DISPLAY_ROLES.includes(upper as DisplayRole)) {
    return upper as DisplayRole;
  }

  // Handle common aliases
  const aliases: Record<string, DisplayRole> = {
    "jungler": "JNG",
    "jg": "JNG",
    "middle": "MID",
    "adc": "ADC",
    "bottom": "ADC",
    "carry": "ADC",
    "sup": "SUP",
    "supp": "SUP",
  };

  if (lower in aliases) {
    return aliases[lower];
  }

  // Fallback: return as-is uppercase (will be caught by type system if wrong)
  console.warn(`Unknown role format: ${role}`);
  return upper as DisplayRole;
}

/**
 * Convert any role format to backend format (top, jungle, mid, bot, support)
 */
export function toBackendRole(role: string): BackendRole {
  const display = toDisplayRole(role);
  return DISPLAY_TO_BACKEND[display];
}

/**
 * Convert any role format to friendly format (Top, Jungle, Mid, Bot, Support)
 */
export function toFriendlyRole(role: string): FriendlyRole {
  const display = toDisplayRole(role);
  return DISPLAY_TO_FRIENDLY[display];
}

/**
 * Check if a string is a valid role in any format
 */
export function isValidRole(role: string): boolean {
  const lower = role.toLowerCase().trim();
  const upper = role.toUpperCase().trim();

  return (
    BACKEND_ROLES.includes(lower as BackendRole) ||
    DISPLAY_ROLES.includes(upper as DisplayRole) ||
    lower === "jng" || lower === "adc" || lower === "sup"
  );
}

/**
 * Get role index in standard order (0=top, 1=jungle, 2=mid, 3=bot, 4=support)
 */
export function getRoleIndex(role: string): number {
  const display = toDisplayRole(role);
  return DISPLAY_ROLES.indexOf(display);
}

/**
 * Sort items by role in standard order
 */
export function sortByRole<T>(items: T[], getRoleFn: (item: T) => string): T[] {
  return [...items].sort((a, b) => {
    const indexA = getRoleIndex(getRoleFn(a));
    const indexB = getRoleIndex(getRoleFn(b));
    return indexA - indexB;
  });
}
