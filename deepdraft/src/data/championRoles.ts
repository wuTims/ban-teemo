// deepdraft/src/data/championRoles.ts
// TypeScript helpers for champion role filtering
// Uses data from championRoles.json (extracted from pro play data)

import championRolesData from "./championRoles.json";

type RoleData = {
  canonical_all: string[];
  canonical_role: string | null;
};

const CHAMPION_ROLES: Record<string, RoleData> = championRolesData;

/**
 * Check if a champion plays a given role.
 * @param champion - Champion name (e.g., "Aatrox")
 * @param role - Role code: "TOP", "JNG", "MID", "ADC", "SUP", or "All"
 * @returns true if the champion plays that role (or role is "All")
 */
export function championPlaysRole(champion: string, role: string): boolean {
  if (role === "All") return true;
  const data = CHAMPION_ROLES[champion];
  if (!data) return false;
  return data.canonical_all.includes(role);
}

/**
 * Get all champions that can play a given role.
 * @param role - Role code: "TOP", "JNG", "MID", "ADC", "SUP", or "All"
 * @returns Array of champion names
 */
export function getChampionsByRole(role: string): string[] {
  if (role === "All") {
    return Object.keys(CHAMPION_ROLES);
  }
  return Object.entries(CHAMPION_ROLES)
    .filter(([, data]) => data.canonical_all.includes(role))
    .map(([name]) => name);
}

/**
 * Get the primary role for a champion.
 * @param champion - Champion name
 * @returns Primary role or null if unknown
 */
export function getPrimaryRole(champion: string): string | null {
  return CHAMPION_ROLES[champion]?.canonical_role ?? null;
}

/**
 * Get all roles a champion can play.
 * @param champion - Champion name
 * @returns Array of role codes
 */
export function getChampionRoles(champion: string): string[] {
  return CHAMPION_ROLES[champion]?.canonical_all ?? [];
}
