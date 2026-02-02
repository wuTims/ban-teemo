interface MetricBarProps {
  label: string;
  value: number; // 0-1 scale
  explanation: string;
  className?: string;
}

function getBarColor(value: number): string {
  if (value >= 0.7) return "bg-success";
  if (value >= 0.5) return "bg-warning";
  return "bg-danger";
}

export function MetricBar({ label, value, explanation, className = "" }: MetricBarProps) {
  const percentage = Math.round(value * 100);

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-text-secondary uppercase tracking-wide">{label}</span>
        <span className="text-xs font-mono text-text-primary">{percentage}%</span>
      </div>
      <div className="h-2 bg-lol-dark rounded-full overflow-hidden">
        <div
          className={`h-full ${getBarColor(value)} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="text-[10px] text-text-tertiary">{explanation}</p>
    </div>
  );
}
