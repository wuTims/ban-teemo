// deepdraft/src/components/SimulatorView/index.tsx
import { useMemo } from "react";
import { PhaseIndicator, TeamPanel, BanRow } from "../draft";
import { ChampionPool } from "../ChampionPool";
import { ChampionPortrait } from "../shared/ChampionPortrait";
import type {
  TeamContext,
  DraftState,
  SimulatorRecommendation,
  SimulatorPickRecommendation,
  SimulatorBanRecommendation,
  FearlessBlocked,
  DraftMode,
} from "../../types";

// Static champion list - could be fetched from API
const ALL_CHAMPIONS = [
  "Aatrox", "Ahri", "Akali", "Akshan", "Alistar", "Amumu", "Anivia", "Annie", "Aphelios",
  "Ashe", "Aurelion Sol", "Aurora", "Azir", "Bard", "Bel'Veth", "Blitzcrank", "Brand",
  "Braum", "Briar", "Caitlyn", "Camille", "Cassiopeia", "Cho'Gath", "Corki", "Darius",
  "Diana", "Dr. Mundo", "Draven", "Ekko", "Elise", "Evelynn", "Ezreal", "Fiddlesticks",
  "Fiora", "Fizz", "Galio", "Gangplank", "Garen", "Gnar", "Gragas", "Graves", "Gwen",
  "Hecarim", "Heimerdinger", "Illaoi", "Irelia", "Ivern", "Janna", "Jarvan IV", "Jax",
  "Jayce", "Jhin", "Jinx", "K'Sante", "Kai'Sa", "Kalista", "Karma", "Karthus", "Kassadin",
  "Katarina", "Kayle", "Kayn", "Kennen", "Kha'Zix", "Kindred", "Kled", "Kog'Maw", "LeBlanc",
  "Lee Sin", "Leona", "Lillia", "Lissandra", "Lucian", "Lulu", "Lux", "Malphite", "Malzahar",
  "Maokai", "Master Yi", "Milio", "Miss Fortune", "Mordekaiser", "Morgana", "Naafiri",
  "Nami", "Nasus", "Nautilus", "Neeko", "Nidalee", "Nilah", "Nocturne", "Nunu", "Olaf",
  "Orianna", "Ornn", "Pantheon", "Poppy", "Pyke", "Qiyana", "Quinn", "Rakan", "Rammus",
  "Rek'Sai", "Rell", "Renata Glasc", "Renekton", "Rengar", "Riven", "Rumble", "Ryze",
  "Samira", "Sejuani", "Senna", "Seraphine", "Sett", "Shaco", "Shen", "Shyvana", "Singed",
  "Sion", "Sivir", "Skarner", "Smolder", "Sona", "Soraka", "Swain", "Sylas", "Syndra",
  "Tahm Kench", "Taliyah", "Talon", "Taric", "Teemo", "Thresh", "Tristana", "Trundle",
  "Tryndamere", "Twisted Fate", "Twitch", "Udyr", "Urgot", "Varus", "Vayne", "Veigar",
  "Vel'Koz", "Vex", "Vi", "Viego", "Viktor", "Vladimir", "Volibear", "Warwick", "Wukong",
  "Xayah", "Xerath", "Xin Zhao", "Yasuo", "Yone", "Yorick", "Yuumi", "Zac", "Zed", "Zeri",
  "Ziggs", "Zilean", "Zoe", "Zyra"
];

// Type guard to differentiate recommendation types
function isPickRecommendation(rec: SimulatorRecommendation): rec is SimulatorPickRecommendation {
  return "score" in rec && "suggested_role" in rec;
}

function isBanRecommendation(rec: SimulatorRecommendation): rec is SimulatorBanRecommendation {
  return "priority" in rec && "target_player" in rec;
}

interface SimulatorViewProps {
  blueTeam: TeamContext;
  redTeam: TeamContext;
  coachingSide: "blue" | "red";
  draftState: DraftState;
  recommendations: SimulatorRecommendation[] | null;
  isOurTurn: boolean;
  isEnemyThinking: boolean;
  gameNumber: number;
  seriesScore: [number, number];
  fearlessBlocked: FearlessBlocked;
  draftMode: DraftMode;
  onChampionSelect: (champion: string) => void;
}

function RecommendationCard({
  recommendation,
  isTopPick,
  onClick,
}: {
  recommendation: SimulatorRecommendation;
  isTopPick?: boolean;
  onClick: (champion: string) => void;
}) {
  const championName = recommendation.champion_name;
  const reasons = recommendation.reasons;

  // Determine score/priority for display
  let displayScore: number;
  let displayLabel: string;
  let targetInfo: string | null = null;

  if (isPickRecommendation(recommendation)) {
    displayScore = recommendation.score;
    displayLabel = `${Math.round(displayScore * 100)}%`;
  } else if (isBanRecommendation(recommendation)) {
    displayScore = recommendation.priority;
    displayLabel = `${Math.round(displayScore * 100)}%`;
    targetInfo = recommendation.target_player;
  } else {
    displayScore = 0.5;
    displayLabel = "N/A";
  }

  const scoreColor =
    displayScore >= 0.7 ? "text-success" :
    displayScore >= 0.5 ? "text-warning" : "text-danger";

  const cardBorder = isTopPick
    ? "border-magic-bright shadow-[0_0_20px_rgba(10,200,185,0.4)]"
    : "border-gold-dim/50";

  return (
    <button
      onClick={() => onClick(championName)}
      className={`
        bg-lol-light rounded-lg p-3 border ${cardBorder}
        transition-all duration-200
        hover:border-magic hover:shadow-[0_0_20px_rgba(10,200,185,0.4)]
        text-left w-full
      `}
    >
      <div className="flex items-center gap-3">
        <ChampionPortrait
          championName={championName}
          state="picked"
          size="md"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-sm uppercase text-gold-bright truncate">
              {championName}
            </h3>
            <span className={`text-sm font-bold ${scoreColor}`}>
              {displayLabel}
            </span>
          </div>
          {targetInfo && (
            <div className="text-xs text-text-tertiary">
              Target: {targetInfo}
            </div>
          )}
          {reasons[0] && (
            <div className="text-xs text-text-secondary truncate mt-1">
              {reasons[0]}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

export function SimulatorView({
  blueTeam,
  redTeam,
  coachingSide,
  draftState,
  recommendations,
  isOurTurn,
  isEnemyThinking,
  gameNumber,
  seriesScore,
  fearlessBlocked,
  draftMode,
  onChampionSelect,
}: SimulatorViewProps) {
  const unavailable = useMemo(() => {
    return new Set([
      ...draftState.blue_bans,
      ...draftState.red_bans,
      ...draftState.blue_picks,
      ...draftState.red_picks,
    ]);
  }, [draftState]);

  const fearlessCount = Object.keys(fearlessBlocked).length;
  const isBanPhase = draftState.next_action === "ban";

  return (
    <div className="space-y-4">
      {/* Series Status */}
      <div className="flex justify-center items-center gap-4 text-sm">
        <span className="text-text-secondary">Game {gameNumber}</span>
        <span className="text-gold-bright font-bold">
          {blueTeam.name} {seriesScore[0]} - {seriesScore[1]} {redTeam.name}
        </span>
        {draftMode === "fearless" && fearlessCount > 0 && (
          <span className="text-danger text-xs">
            Fearless: {fearlessCount} blocked
          </span>
        )}
      </div>

      {/* Phase Indicator */}
      <div className="flex justify-center items-center gap-4">
        <PhaseIndicator
          currentPhase={draftState.phase}
          nextTeam={draftState.next_team}
          nextAction={draftState.next_action}
        />
        {isEnemyThinking && (
          <span className="text-text-tertiary animate-pulse text-sm">
            Enemy thinking...
          </span>
        )}
      </div>

      {/* Main 3-Column Layout */}
      <div className="grid grid-cols-[220px_1fr_220px] gap-4 min-h-[500px]">
        {/* Blue Team */}
        <div className={coachingSide === "blue" ? "ring-2 ring-magic rounded-lg" : ""}>
          <TeamPanel
            team={blueTeam}
            picks={draftState.blue_picks}
            side="blue"
            isActive={draftState.next_team === "blue" && draftState.next_action === "pick"}
          />
          {coachingSide === "blue" && (
            <div className="text-center text-xs text-magic mt-1 font-medium">
              Your Team
            </div>
          )}
        </div>

        {/* Champion Pool */}
        <ChampionPool
          allChampions={ALL_CHAMPIONS}
          unavailable={unavailable}
          fearlessBlocked={fearlessBlocked}
          onSelect={onChampionSelect}
          disabled={!isOurTurn}
        />

        {/* Red Team */}
        <div className={coachingSide === "red" ? "ring-2 ring-magic rounded-lg" : ""}>
          <TeamPanel
            team={redTeam}
            picks={draftState.red_picks}
            side="red"
            isActive={draftState.next_team === "red" && draftState.next_action === "pick"}
          />
          {coachingSide === "red" && (
            <div className="text-center text-xs text-magic mt-1 font-medium">
              Your Team
            </div>
          )}
        </div>
      </div>

      {/* Ban Row */}
      <BanRow blueBans={draftState.blue_bans} redBans={draftState.red_bans} />

      {/* Recommendations */}
      {isOurTurn && recommendations && recommendations.length > 0 && (
        <div className="bg-lol-dark rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gold-bright">
              {isBanPhase ? "Ban" : "Pick"} Recommendations
            </h3>
            <span className={`
              text-xs font-medium uppercase px-2 py-0.5 rounded
              ${coachingSide === "blue" ? "bg-blue-team/20 text-blue-team" : "bg-red-team/20 text-red-team"}
            `}>
              Your Turn
            </span>
          </div>
          <div className="grid grid-cols-5 gap-3">
            {recommendations.slice(0, 5).map((rec, i) => (
              <RecommendationCard
                key={rec.champion_name}
                recommendation={rec}
                isTopPick={i === 0}
                onClick={onChampionSelect}
              />
            ))}
          </div>
        </div>
      )}

      {/* Waiting indicator when not our turn */}
      {!isOurTurn && !isEnemyThinking && draftState.phase !== "COMPLETE" && (
        <div className="bg-lol-dark rounded-lg p-4 text-center">
          <span className="text-text-tertiary">
            Waiting for {draftState.next_team === "blue" ? blueTeam.name : redTeam.name}...
          </span>
        </div>
      )}
    </div>
  );
}
