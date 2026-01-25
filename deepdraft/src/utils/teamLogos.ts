import teamLogosData from "../data/team-logos.json";

interface TeamLogoEntry {
  name: string;
  logoUrl: string;
}

const teamLogos = teamLogosData as Record<string, TeamLogoEntry>;

/**
 * Get the logo URL for a team by ID.
 * Returns path to locally-served logo in /team-logos/
 */
export function getTeamLogoUrl(teamId: string): string | null {
  const entry = teamLogos[teamId];
  if (!entry) return null;
  // Serve from local public directory
  return `/team-logos/${teamId}.png`;
}

/**
 * Get the logo URL for a team by name (fallback if ID not available)
 */
export function getTeamLogoByName(teamName: string): string | null {
  const entry = Object.values(teamLogos).find(
    (t) => t.name.toLowerCase() === teamName.toLowerCase()
  );
  return entry?.logoUrl ?? null;
}

/**
 * Get team initials as fallback when logo not available
 */
export function getTeamInitials(teamName: string): string {
  const words = teamName.split(/\s+/);
  if (words.length === 1) {
    return teamName.slice(0, 2).toUpperCase();
  }
  return words
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}
