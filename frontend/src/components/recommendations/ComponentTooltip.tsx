// frontend/src/components/recommendations/ComponentTooltip.tsx
import React, { useState, useRef, useEffect } from "react";

/**
 * Explanations for each scoring component.
 * Keys match the component names from the backend scoring system.
 */
export const COMPONENT_EXPLANATIONS: Record<string, string> = {
  archetype: "Fit with team's strategic identity (engage, poke, protect, etc.)",
  meta: "Champion's current strength in pro meta (win rate, pick/ban rate)",
  matchup_counter: "Combined lane matchup and team-wide counter advantage",
  proficiency: "Player's comfort and experience with this champion",
  synergy: "How well this champion works with teammates",
  // Legacy component names for backwards compatibility
  matchup: "Lane matchup advantage against opponent",
  counter: "Team-wide counter potential against enemy composition",
};

/**
 * Short labels for display in compact spaces.
 */
export const COMPONENT_LABELS: Record<string, string> = {
  archetype: "Arch",
  meta: "Meta",
  matchup_counter: "Match",
  proficiency: "Prof",
  synergy: "Syn",
  // Legacy
  matchup: "Match",
  counter: "Cntr",
};

interface ComponentTooltipProps {
  /** The component key (e.g., "meta", "proficiency") */
  componentKey: string;
  /** The component value (0-1 score) */
  value?: number;
  /** Optional custom label override */
  label?: string;
  /** Optional children to wrap with tooltip */
  children?: React.ReactNode;
  /** Additional CSS classes */
  className?: string;
}

/**
 * A tooltip component that displays explanations for scoring components.
 * Shows the explanation on hover with a smooth transition.
 *
 * Usage:
 * ```tsx
 * // Standalone usage with label and value
 * <ComponentTooltip componentKey="meta" value={0.85} />
 *
 * // Wrapping existing content
 * <ComponentTooltip componentKey="synergy">
 *   <span>Syn: 0.72</span>
 * </ComponentTooltip>
 * ```
 */
export function ComponentTooltip({
  componentKey,
  value,
  label,
  children,
  className = "",
}: ComponentTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState<"top" | "bottom">("top");
  const tooltipRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLSpanElement>(null);

  const explanation = COMPONENT_EXPLANATIONS[componentKey] || `Score component: ${componentKey}`;
  const displayLabel = label || COMPONENT_LABELS[componentKey] || componentKey;

  // Determine tooltip position based on available space
  useEffect(() => {
    if (isVisible && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const spaceAbove = rect.top;
      // If less than 60px above, position below
      setPosition(spaceAbove < 60 ? "bottom" : "top");
    }
  }, [isVisible]);

  const valueColor =
    value !== undefined
      ? value >= 0.7
        ? "text-success/80"
        : value >= 0.5
          ? "text-warning/80"
          : "text-danger/80"
      : "text-text-secondary";

  const handleMouseEnter = () => setIsVisible(true);
  const handleMouseLeave = () => setIsVisible(false);
  const handleFocus = () => setIsVisible(true);
  const handleBlur = () => setIsVisible(false);

  // If children provided, wrap them; otherwise render default label/value display
  const content = children || (
    <span
      className={`
        text-[10px] px-1 py-0.5 rounded bg-lol-dark/50
        ${valueColor}
      `}
    >
      {displayLabel}
      {value !== undefined && `: ${value.toFixed(2)}`}
    </span>
  );

  return (
    <span
      ref={containerRef}
      className={`relative inline-block ${className}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
      tabIndex={0}
      role="button"
      aria-describedby={isVisible ? `tooltip-${componentKey}` : undefined}
    >
      {content}

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        id={`tooltip-${componentKey}`}
        role="tooltip"
        className={`
          absolute left-1/2 -translate-x-1/2 z-50
          px-2 py-1.5 rounded
          bg-lol-darkest border border-gold-dim/40
          text-[11px] text-text-primary leading-tight
          whitespace-normal max-w-[200px] text-center
          shadow-lg shadow-black/50
          transition-all duration-150 ease-out
          pointer-events-none
          ${position === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5"}
          ${isVisible
            ? "opacity-100 translate-y-0"
            : position === "top"
              ? "opacity-0 translate-y-1"
              : "opacity-0 -translate-y-1"
          }
        `}
      >
        {/* Arrow */}
        <div
          className={`
            absolute left-1/2 -translate-x-1/2
            w-0 h-0
            border-l-[5px] border-l-transparent
            border-r-[5px] border-r-transparent
            ${position === "top"
              ? "top-full border-t-[5px] border-t-lol-darkest"
              : "bottom-full border-b-[5px] border-b-lol-darkest"
            }
          `}
        />
        {explanation}
      </div>
    </span>
  );
}

export default ComponentTooltip;
