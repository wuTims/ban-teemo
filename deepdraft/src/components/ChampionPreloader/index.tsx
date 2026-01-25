import { useState, useEffect, type ReactNode } from "react";
import { preloadChampionIcons } from "../../utils/dataDragon";

interface ChampionPreloaderProps {
  children: ReactNode;
}

export function ChampionPreloader({ children }: ChampionPreloaderProps) {
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ loaded: 0, total: 0 });

  useEffect(() => {
    let mounted = true;

    preloadChampionIcons((loaded, total) => {
      if (mounted) {
        setProgress({ loaded, total });
      }
    }).then(() => {
      if (mounted) {
        setLoading(false);
      }
    });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    const percent = progress.total > 0
      ? Math.round((progress.loaded / progress.total) * 100)
      : 0;

    return (
      <div className="min-h-screen bg-lol-darkest flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-text-secondary text-sm">
            Loading champion assets...
          </p>

          {/* Progress bar container */}
          <div className="w-64 h-2 bg-lol-dark rounded-full overflow-hidden">
            <div
              className="h-full bg-gold-bright transition-all duration-150 ease-out"
              style={{ width: `${percent}%` }}
            />
          </div>

          {/* Progress count */}
          <p className="text-text-tertiary text-xs">
            {progress.loaded}/{progress.total}
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
