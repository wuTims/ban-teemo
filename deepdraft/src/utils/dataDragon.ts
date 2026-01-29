/**
 * Data Dragon utility for champion icons from Riot's CDN.
 *
 * Data Dragon is Riot's static data API that provides game assets.
 * Champion icons require a "riot key" which differs from display names
 * (e.g., "K'Sante" → "KSante", "Wukong" → "MonkeyKing").
 *
 * CDN URL pattern:
 * https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{RiotKey}.png
 */

// Current Data Dragon version - update when new patches release
// You can fetch latest from: https://ddragon.leagueoflegends.com/api/versions.json
const DEFAULT_DDRAGON_VERSION = "16.2.1";

const DDRAGON_CDN = "https://ddragon.leagueoflegends.com/cdn";

/**
 * Mapping from GRID API champion names to Riot Data Dragon keys.
 * Handles special characters, spaces, and edge cases like "Wukong" → "MonkeyKing".
 */
const GRID_TO_RIOT_KEY: Record<string, string> = {
  "Aatrox": "Aatrox",
  "Ahri": "Ahri",
  "Akali": "Akali",
  "Akshan": "Akshan",
  "Alistar": "Alistar",
  "Ambessa": "Ambessa",
  "Amumu": "Amumu",
  "Anivia": "Anivia",
  "Annie": "Annie",
  "Aphelios": "Aphelios",
  "Ashe": "Ashe",
  "Aurelion Sol": "AurelionSol",
  "Aurora": "Aurora",
  "Azir": "Azir",
  "Bard": "Bard",
  "Bel'Veth": "Belveth",
  "Blitzcrank": "Blitzcrank",
  "Brand": "Brand",
  "Braum": "Braum",
  "Briar": "Briar",
  "Caitlyn": "Caitlyn",
  "Camille": "Camille",
  "Cassiopeia": "Cassiopeia",
  "Cho'Gath": "Chogath",
  "Corki": "Corki",
  "Darius": "Darius",
  "Diana": "Diana",
  "Dr. Mundo": "DrMundo",
  "Draven": "Draven",
  "Ekko": "Ekko",
  "Elise": "Elise",
  "Evelynn": "Evelynn",
  "Ezreal": "Ezreal",
  "Fiddlesticks": "Fiddlesticks",
  "Fiora": "Fiora",
  "Fizz": "Fizz",
  "Galio": "Galio",
  "Gangplank": "Gangplank",
  "Garen": "Garen",
  "Gnar": "Gnar",
  "Gragas": "Gragas",
  "Graves": "Graves",
  "Gwen": "Gwen",
  "Hecarim": "Hecarim",
  "Heimerdinger": "Heimerdinger",
  "Hwei": "Hwei",
  "Illaoi": "Illaoi",
  "Irelia": "Irelia",
  "Ivern": "Ivern",
  "Janna": "Janna",
  "Jarvan IV": "JarvanIV",
  "Jax": "Jax",
  "Jayce": "Jayce",
  "Jhin": "Jhin",
  "Jinx": "Jinx",
  "K'Sante": "KSante",
  "Kai'Sa": "Kaisa",
  "Kalista": "Kalista",
  "Karma": "Karma",
  "Karthus": "Karthus",
  "Kassadin": "Kassadin",
  "Katarina": "Katarina",
  "Kayle": "Kayle",
  "Kayn": "Kayn",
  "Kennen": "Kennen",
  "Kha'Zix": "Khazix",
  "Kindred": "Kindred",
  "Kled": "Kled",
  "Kog'Maw": "KogMaw",
  "LeBlanc": "Leblanc",
  "Lee Sin": "LeeSin",
  "Leona": "Leona",
  "Lillia": "Lillia",
  "Lissandra": "Lissandra",
  "Lucian": "Lucian",
  "Lulu": "Lulu",
  "Lux": "Lux",
  "Malphite": "Malphite",
  "Malzahar": "Malzahar",
  "Maokai": "Maokai",
  "Master Yi": "MasterYi",
  "Mel": "Mel",
  "Milio": "Milio",
  "Miss Fortune": "MissFortune",
  "Mordekaiser": "Mordekaiser",
  "Morgana": "Morgana",
  "Naafiri": "Naafiri",
  "Nami": "Nami",
  "Nasus": "Nasus",
  "Nautilus": "Nautilus",
  "Neeko": "Neeko",
  "Nidalee": "Nidalee",
  "Nilah": "Nilah",
  "Nocturne": "Nocturne",
  "Nunu & Willump": "Nunu",
  "Olaf": "Olaf",
  "Orianna": "Orianna",
  "Ornn": "Ornn",
  "Pantheon": "Pantheon",
  "Poppy": "Poppy",
  "Pyke": "Pyke",
  "Qiyana": "Qiyana",
  "Quinn": "Quinn",
  "Rakan": "Rakan",
  "Rammus": "Rammus",
  "Rek'Sai": "RekSai",
  "Rell": "Rell",
  "Renata Glasc": "Renata",
  "Renekton": "Renekton",
  "Rengar": "Rengar",
  "Riven": "Riven",
  "Rumble": "Rumble",
  "Ryze": "Ryze",
  "Samira": "Samira",
  "Sejuani": "Sejuani",
  "Senna": "Senna",
  "Seraphine": "Seraphine",
  "Sett": "Sett",
  "Shaco": "Shaco",
  "Shen": "Shen",
  "Shyvana": "Shyvana",
  "Singed": "Singed",
  "Sion": "Sion",
  "Sivir": "Sivir",
  "Skarner": "Skarner",
  "Smolder": "Smolder",
  "Sona": "Sona",
  "Soraka": "Soraka",
  "Swain": "Swain",
  "Sylas": "Sylas",
  "Syndra": "Syndra",
  "Tahm Kench": "TahmKench",
  "Taliyah": "Taliyah",
  "Talon": "Talon",
  "Taric": "Taric",
  "Teemo": "Teemo",
  "Thresh": "Thresh",
  "Tristana": "Tristana",
  "Trundle": "Trundle",
  "Tryndamere": "Tryndamere",
  "Twisted Fate": "TwistedFate",
  "Twitch": "Twitch",
  "Udyr": "Udyr",
  "Urgot": "Urgot",
  "Varus": "Varus",
  "Vayne": "Vayne",
  "Veigar": "Veigar",
  "Vel'Koz": "Velkoz",
  "Vex": "Vex",
  "Vi": "Vi",
  "Viego": "Viego",
  "Viktor": "Viktor",
  "Vladimir": "Vladimir",
  "Volibear": "Volibear",
  "Warwick": "Warwick",
  "Wukong": "MonkeyKing",
  "Xayah": "Xayah",
  "Xerath": "Xerath",
  "Xin Zhao": "XinZhao",
  "Yasuo": "Yasuo",
  "Yone": "Yone",
  "Yorick": "Yorick",
  "Yunara": "Yunara",
  "Yuumi": "Yuumi",
  "Zaahen": "Zaahen",
  "Zac": "Zac",
  "Zed": "Zed",
  "Zeri": "Zeri",
  "Ziggs": "Ziggs",
  "Zilean": "Zilean",
  "Zoe": "Zoe",
  "Zyra": "Zyra",
};

/**
 * Get the Riot Data Dragon key for a champion name.
 * Falls back to removing special characters if not found in mapping.
 */
export function getRiotKey(championName: string): string {
  // Direct lookup
  if (GRID_TO_RIOT_KEY[championName]) {
    return GRID_TO_RIOT_KEY[championName];
  }

  // Fallback: remove special characters and spaces
  return championName
    .replace(/['\s.&]/g, "")
    .replace(/^(.)/, (m) => m.toUpperCase());
}

/**
 * Get the Data Dragon icon URL for a champion.
 *
 * @param championName - Display name (e.g., "K'Sante", "Wukong")
 * @param version - Data Dragon version (defaults to current patch)
 * @returns Full CDN URL to the champion square icon (120x120)
 *
 * @example
 * getChampionIconUrl("K'Sante")
 * // → "https://ddragon.leagueoflegends.com/cdn/16.2.1/img/champion/KSante.png"
 */
export function getChampionIconUrl(
  championName: string,
  version: string = DEFAULT_DDRAGON_VERSION
): string {
  const riotKey = getRiotKey(championName);
  return `${DDRAGON_CDN}/${version}/img/champion/${riotKey}.png`;
}

/**
 * Get the Data Dragon splash art URL for a champion.
 *
 * @param championName - Display name (e.g., "K'Sante")
 * @param skinNum - Skin number (0 = default skin)
 * @returns Full URL to the champion splash art
 */
export function getChampionSplashUrl(
  championName: string,
  skinNum: number = 0
): string {
  const riotKey = getRiotKey(championName);
  return `${DDRAGON_CDN}/img/champion/splash/${riotKey}_${skinNum}.jpg`;
}

/**
 * Get the Data Dragon loading screen art URL for a champion.
 *
 * @param championName - Display name
 * @param skinNum - Skin number (0 = default skin)
 */
export function getChampionLoadingUrl(
  championName: string,
  skinNum: number = 0
): string {
  const riotKey = getRiotKey(championName);
  return `${DDRAGON_CDN}/img/champion/loading/${riotKey}_${skinNum}.jpg`;
}

/**
 * Fetch the latest Data Dragon version from Riot's API.
 * Useful for ensuring icons are always up-to-date.
 *
 * @returns Promise resolving to the latest version string
 */
export async function fetchLatestVersion(): Promise<string> {
  try {
    const response = await fetch(
      "https://ddragon.leagueoflegends.com/api/versions.json"
    );
    const versions: string[] = await response.json();
    return versions[0]; // First element is always the latest
  } catch {
    return DEFAULT_DDRAGON_VERSION;
  }
}

/**
 * Check if a champion name exists in the mapping.
 */
export function isKnownChampion(championName: string): boolean {
  return championName in GRID_TO_RIOT_KEY;
}

/**
 * Get all known champion names.
 */
export function getAllChampionNames(): string[] {
  return Object.keys(GRID_TO_RIOT_KEY);
}

// Global cache for preloaded image blob URLs
// Using blob URLs ensures instant rendering without network requests
const imageCache = new Map<string, string>();

/**
 * Get cached blob URL for a champion icon, or fall back to CDN URL.
 */
export function getCachedChampionIconUrl(championName: string): string {
  const cdnUrl = getChampionIconUrl(championName);
  return imageCache.get(cdnUrl) || cdnUrl;
}

/**
 * Check if all champion icons have been preloaded.
 */
export function areIconsPreloaded(): boolean {
  return imageCache.size > 0;
}

/**
 * Preload all champion icons and store as blob URLs for instant rendering.
 * Blob URLs bypass the browser's image decode step since data is already in memory.
 *
 * @param onProgress - Callback for progress updates
 * @returns Promise that resolves when all icons are loaded or timeout is reached
 */
export async function preloadChampionIcons(
  onProgress?: (loaded: number, total: number) => void
): Promise<void> {
  const championNames = getAllChampionNames();
  const total = championNames.length;
  let loaded = 0;

  const loadPromises = championNames.map(async (name) => {
    const cdnUrl = getChampionIconUrl(name);
    try {
      const response = await fetch(cdnUrl);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      imageCache.set(cdnUrl, blobUrl);

      // Pre-decode the blob URL to ensure it's ready for instant painting
      const img = new Image();
      img.src = blobUrl;
      await img.decode().catch(() => {});
    } catch {
      // Fall back to CDN URL on error
    }
    loaded++;
    onProgress?.(loaded, total);
  });

  // Race against timeout to prevent blocking forever
  await Promise.race([
    Promise.all(loadPromises),
    new Promise((resolve) => setTimeout(resolve, 15000)),
  ]);
}

export { DEFAULT_DDRAGON_VERSION, DDRAGON_CDN, GRID_TO_RIOT_KEY };
