/**
 * Team name to abbreviation mapping for display purposes.
 * Sources: Liquipedia, Leaguepedia, LoL Esports official
 */

// Map from full team name (as stored in DB) to abbreviated code
export const TEAM_ABBREVIATIONS: Record<string, string> = {
  // LCK (Korea)
  "Hanwha Life Esports": "HLE",
  "DN FREECS": "DNF",
  "DRX": "DRX",
  "KT Rolster": "KT",
  "NONGSHIM RED FORCE": "NS",
  "Gen.G Esports": "GEN",
  "Dplus KIA": "DK",
  "T1": "T1",
  "BNK FearX": "BFX",
  "OKSavingsBank BRION": "BRO",

  // LPL (China)
  "BILIBILI GAMING DREAMSMART": "BLG",
  "TopEsports": "TES",
  "Invictus Gaming": "IG",
  "SHANGHAI EDWARD GAMING HYCAN": "EDG",
  "WeiboGaming TapTap": "WBG",
  "THUNDERTALKGAMING": "TT",
  "Shenzhen NINJAS IN PYJAMAS": "NIP",
  "FunPlus Phoenix": "FPX",
  "Oh My God": "OMG",
  "Suzhou LNG Ninebot Esports": "LNG",
  "Anyone's Legend": "AL",
  "LGD Gaming": "LGD",
  "Xi'an Team WE": "WE",
  "Beijing JDG Intel Esports": "JDG",
  "Royal Never Give Up": "RNG",
  "Ultra Prime": "UP",
  "Rare Atom": "RA",

  // LEC (EMEA)
  "SK Gaming": "SK",
  "Movistar KOI": "KOI",
  "Team Heretics": "TH",
  "Team Vitality": "VIT",
  "Karmine Corp": "KC",
  "Rogue": "RGE",
  "G2 Esports": "G2",
  "Team BDS": "BDS",
  "GIANTX": "GX",
  "Fnatic": "FNC",
  "Natus Vincere": "NAVI",

  // LTA North (formerly LCS)
  "FlyQuest": "FLY",
  "Disguised": "DSG",
  "Shopify Rebellion": "SR",
  "Cloud9 Kia": "C9",
  "NRG Kia": "NRG",
  "Dignitas": "DIG",
  "Team Liquid": "TL",
  "100 Thieves": "100T",
  "Immortals Progressive": "IMT",
  "LYON": "LYON",

  // LTA South (CBLOL/LLA)
  "Pain Gaming": "PNG",
  "Isurus Estral": "ISG",
  "FURIA": "FUR",
  "RED Kalunga": "RED",
  "Vivo Keyd Stars": "VKS",
  "LOUD": "LOUD",
  "Fluxo W7M": "FLX",
  "LEVIATÁN": "LEV",
};

/**
 * Get the abbreviated team name, falling back to first 3 chars if not mapped.
 */
export function getTeamAbbreviation(teamName: string): string {
  // Check exact match first
  if (TEAM_ABBREVIATIONS[teamName]) {
    return TEAM_ABBREVIATIONS[teamName];
  }

  // Try case-insensitive match
  const lowerName = teamName.toLowerCase();
  for (const [key, value] of Object.entries(TEAM_ABBREVIATIONS)) {
    if (key.toLowerCase() === lowerName) {
      return value;
    }
  }

  // Fallback: generate abbreviation from initials or first 3 chars
  const words = teamName.split(/\s+/);
  if (words.length >= 2) {
    // Take first letter of each word (up to 4)
    return words
      .slice(0, 4)
      .map((w) => w[0])
      .join("")
      .toUpperCase();
  }

  // Single word: take first 3 characters
  return teamName.slice(0, 3).toUpperCase();
}
