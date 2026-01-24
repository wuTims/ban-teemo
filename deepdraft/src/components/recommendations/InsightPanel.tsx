// deepdraft/src/components/recommendations/InsightPanel.tsx
interface InsightPanelProps {
  insight: string | null;
  isLoading?: boolean;
}

export function InsightPanel({ insight, isLoading = false }: InsightPanelProps) {
  return (
    <div className="
      bg-gradient-to-br from-lol-dark to-lol-medium
      rounded-lg p-4 border border-magic/30
      relative overflow-hidden
      h-full
    ">
      {/* Ambient glow background */}
      <div className="absolute inset-0 bg-magic/5" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-32 bg-magic/10 rounded-full blur-3xl" />

      {/* Header */}
      <div className="relative flex items-center gap-2 mb-3">
        <h3 className="font-semibold text-sm uppercase tracking-widest text-magic">
          AI Insight
        </h3>
      </div>

      {/* Content */}
      <div className="relative">
        {isLoading ? (
          <div className="flex items-center gap-2 text-text-secondary">
            <div className="w-4 h-4 border-2 border-magic border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Analyzing draft...</span>
          </div>
        ) : insight ? (
          <p className="text-sm text-gold-bright leading-relaxed">
            "{insight}"
          </p>
        ) : (
          <p className="text-sm text-text-tertiary italic">
            Insights will appear as the draft progresses...
          </p>
        )}
      </div>
    </div>
  );
}
