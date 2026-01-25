# LoL Draft Assistant - UI Style Guide

**Version:** 1.0  
**Date:** January 2026  
**Stack:** React 18+ | Tailwind CSS v4 | shadcn/ui components

---

## 1. Design Philosophy

### 1.1 Core Concept: "Hextech Analyst Station"

Our UI draws from Riot's **Hextech design language** - the idea that the interface itself is a magical-mechanical tool that players use to interact with the game world. For our draft assistant, we're building an "analyst station" that feels like:

- A **high-tech command console** used by pro team coaches
- **Hextech magic** highlighting critical decision points
- **Clean data visualization** layered over atmospheric depth

### 1.2 Key Principles from Riot's Hextech System

| Principle | Description | Our Application |
|-----------|-------------|-----------------|
| **Magic has weight** | Hextech effects feel like a mix of water and smoke | Use subtle glow animations, not harsh neon |
| **Blue = Action** | Hextech magic (bright blue/teal) guides attention to primary interactions | Highlight current pick/ban, active recommendations |
| **Gold = Navigation** | Gold elements for secondary interactions | Frame elements, section dividers, team badges |
| **Darkness = Focus** | Deep blue-black backgrounds create focus | Draft board floats in darkness, drawing eye to content |

### 1.3 Design Differentiation

What makes our UI memorable:
- **Asymmetric layouts** - Blue team left, Red team right with an angled central draft board
- **Animated recommendation cards** that pulse with "magic" when confidence is high
- **AI insight panel** that feels like a mystical oracle providing wisdom
- **Phase transitions** with sweeping hextech effects

---

## 2. Color System

### 2.1 Core Palette

```css
:root {
  /* === BACKGROUNDS === */
  --bg-darkest: #010A13;       /* App background, near-black */
  --bg-dark: #0A1428;          /* Main panel backgrounds */
  --bg-medium: #0A323C;        /* Elevated surfaces */
  --bg-light: #1E2328;         /* Card backgrounds */
  --bg-hover: #1E3A5F;         /* Interactive hover states */
  
  /* === HEXTECH MAGIC (Primary Actions) === */
  --magic-bright: #0AC8B9;     /* Primary buttons, active states */
  --magic-core: #0397AB;       /* Standard interactive elements */
  --magic-dim: #005A82;        /* Disabled/inactive magic elements */
  --magic-glow: rgba(10, 200, 185, 0.4);  /* Glow effects */
  
  /* === GOLD SYSTEM (Secondary/Navigation) === */
  --gold-bright: #F0E6D2;      /* Headers, important text */
  --gold-standard: #C8AA6E;    /* Borders, frames, icons */
  --gold-dim: #785A28;         /* Disabled gold elements */
  --gold-dark: #463714;        /* Gold on dark backgrounds */
  
  /* === TEAM COLORS === */
  --blue-team: #0AC8B9;        /* Blue side accent */
  --blue-team-bg: #0A323C;     /* Blue side panel background */
  --red-team: #E84057;         /* Red side accent */
  --red-team-bg: #3C0A0A;      /* Red side panel background */
  
  /* === SEMANTIC COLORS === */
  --success: #1EAD58;          /* High confidence, wins */
  --warning: #F0B232;          /* Medium confidence, caution */
  --danger: #E84057;           /* Low confidence, errors */
  --info: #5B5A56;             /* Neutral info, metadata */
  
  /* === TEXT HIERARCHY === */
  --text-primary: #F0E6D2;     /* Headers, champion names */
  --text-secondary: #A09B8C;   /* Body text, stats */
  --text-tertiary: #5B5A56;    /* Metadata, timestamps */
  --text-muted: #3C3C41;       /* Disabled text */
}
```

### 2.2 Tailwind v4 Configuration

```javascript
// tailwind.config.js
export default {
  theme: {
    extend: {
      colors: {
        // Backgrounds
        lol: {
          darkest: '#010A13',
          dark: '#0A1428',
          medium: '#0A323C',
          light: '#1E2328',
          hover: '#1E3A5F',
        },
        // Hextech Magic
        magic: {
          bright: '#0AC8B9',
          DEFAULT: '#0397AB',
          dim: '#005A82',
        },
        // Gold
        gold: {
          bright: '#F0E6D2',
          DEFAULT: '#C8AA6E',
          dim: '#785A28',
          dark: '#463714',
        },
        // Teams
        'blue-team': '#0AC8B9',
        'red-team': '#E84057',
      },
      fontFamily: {
        'beaufort': ['Beaufort for LOL', 'serif'],
        'spiegel': ['Spiegel', 'sans-serif'],
        // Fallbacks for web (see Typography section)
        'display': ['Cinzel', 'Beaufort for LOL', 'serif'],
        'body': ['Inter', 'Spiegel', 'sans-serif'],
      },
      boxShadow: {
        'magic': '0 0 20px rgba(10, 200, 185, 0.4)',
        'magic-lg': '0 0 40px rgba(10, 200, 185, 0.6)',
        'gold': '0 0 10px rgba(200, 170, 110, 0.3)',
        'inner-dark': 'inset 0 2px 10px rgba(0, 0, 0, 0.5)',
      },
      backgroundImage: {
        'hextech-gradient': 'linear-gradient(135deg, #0A1428 0%, #0A323C 50%, #005A82 100%)',
        'gold-gradient': 'linear-gradient(135deg, #463714 0%, #C8AA6E 50%, #F0E6D2 100%)',
        'magic-gradient': 'linear-gradient(180deg, #0AC8B9 0%, #0397AB 100%)',
      },
      animation: {
        'magic-pulse': 'magicPulse 2s ease-in-out infinite',
        'magic-glow': 'magicGlow 1.5s ease-in-out infinite',
        'slide-in-left': 'slideInLeft 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        magicPulse: {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%': { opacity: 0.8, transform: 'scale(1.02)' },
        },
        magicGlow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(10, 200, 185, 0.4)' },
          '50%': { boxShadow: '0 0 40px rgba(10, 200, 185, 0.7)' },
        },
        slideInLeft: {
          from: { transform: 'translateX(-20px)', opacity: 0 },
          to: { transform: 'translateX(0)', opacity: 1 },
        },
        slideInRight: {
          from: { transform: 'translateX(20px)', opacity: 0 },
          to: { transform: 'translateX(0)', opacity: 1 },
        },
        fadeIn: {
          from: { opacity: 0 },
          to: { opacity: 1 },
        },
      },
    },
  },
}
```

---

## 3. Typography

### 3.1 Font Stack

Riot uses two proprietary fonts: **Beaufort for LoL** (display/headers) and **Spiegel** (body). These are available from the [Riot Brand Portal](https://brand.riotgames.com/en-us/league-of-legends/color).

For web deployment, we use close substitutes:

| Purpose | Riot Font | Web Fallback | Google Font |
|---------|-----------|--------------|-------------|
| Display/Headers | Beaufort for LoL | Cinzel | [Cinzel](https://fonts.google.com/specimen/Cinzel) |
| Body Text | Spiegel | Inter | [Inter](https://fonts.google.com/specimen/Inter) |

**Note:** If distributing publicly, use web fallbacks. For internal/hackathon demo, you can use the official fonts from Riot's brand assets.

### 3.2 Type Scale

```css
/* Typography Scale - using Tailwind classes */
.text-display-1    { @apply font-display text-5xl font-bold tracking-wide uppercase; }  /* 48px - Page titles */
.text-display-2    { @apply font-display text-3xl font-bold tracking-wide uppercase; }  /* 30px - Section titles */
.text-display-3    { @apply font-display text-xl font-semibold tracking-wide uppercase; } /* 20px - Card titles */
.text-heading-1    { @apply font-body text-lg font-semibold; }        /* 18px - Panel headers */
.text-heading-2    { @apply font-body text-base font-semibold; }      /* 16px - Subheadings */
.text-body         { @apply font-body text-sm font-normal; }          /* 14px - Main body */
.text-caption      { @apply font-body text-xs font-normal; }          /* 12px - Metadata */
.text-micro        { @apply font-body text-[10px] font-medium uppercase tracking-widest; } /* 10px - Labels */
```

### 3.3 Usage Guidelines

```jsx
// Champion names - display font, gold color
<h2 className="font-display text-xl font-bold uppercase tracking-wide text-gold-bright">
  Renekton
</h2>

// Stats - body font, secondary text
<p className="font-body text-sm text-lol-secondary">
  23 games • 67% WR
</p>

// Phase indicator - display font, magic color when active
<span className="font-display text-sm uppercase tracking-widest text-magic-bright">
  Ban Phase 1
</span>

// AI Insight - body font, with magic accent
<p className="font-body text-sm text-gold-bright leading-relaxed">
  "G2 has banned 3 ADCs - they're targeting Hans Sama's pool..."
</p>
```

---

## 4. Layout System

### 4.1 Main Application Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HEADER (Tournament info, Series selector, Replay controls)         H: 64px │
├────────────────────┬────────────────────────────┬───────────────────────────┤
│                    │                            │                           │
│   BLUE TEAM        │     DRAFT BOARD            │     RED TEAM              │
│   PANEL            │     (Central)              │     PANEL                 │
│                    │                            │                           │
│   - Team logo      │   ┌────────────────────┐   │   - Team logo             │
│   - Player list    │   │   Ban Track        │   │   - Player list           │
│   - Picks display  │   │   (10 bans)        │   │   - Picks display         │
│                    │   ├────────────────────┤   │                           │
│   W: 280px         │   │   Phase Indicator  │   │   W: 280px                │
│                    │   ├────────────────────┤   │                           │
│                    │   │   Timer            │   │                           │
│                    │   └────────────────────┘   │                           │
│                    │                            │                           │
├────────────────────┴────────────────────────────┴───────────────────────────┤
│                     RECOMMENDATION PANEL                            H: 320px │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────────┐   │
│  │  TOP PICK (78%)     │  │  SURPRISE (55%)     │  │  AI INSIGHT        │   │
│  │  Renekton           │  │  Aurora             │  │  "G2 is..."        │   │
│  └─────────────────────┘  └─────────────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Responsive Breakpoints

```javascript
// Tailwind screens
screens: {
  'sm': '640px',    // Mobile landscape
  'md': '768px',    // Tablet
  'lg': '1024px',   // Laptop
  'xl': '1280px',   // Desktop (primary target)
  '2xl': '1536px',  // Large desktop
}
```

**Primary Target:** 1920×1080 (Full HD desktop) - this is the standard esports viewing experience.

### 4.3 Grid System

```jsx
// Main layout grid
<div className="grid grid-cols-[280px_1fr_280px] gap-4 h-[calc(100vh-64px)]">
  <aside className="bg-lol-dark">Blue Team Panel</aside>
  <main className="bg-lol-darkest">Draft Board</main>
  <aside className="bg-lol-dark">Red Team Panel</aside>
</div>

// Recommendation panel (below)
<div className="grid grid-cols-3 gap-4 p-4">
  <RecommendationCard />
  <RecommendationCard />
  <InsightPanel />
</div>
```

---

## 5. Component Library

### 5.1 Champion Portrait

The champion portrait is the core visual element. Three sizes are needed:

```jsx
// Size variants
const SIZES = {
  sm: 'w-10 h-10',   // 40px - Inline lists, ban bar
  md: 'w-14 h-14',   // 56px - Team panels
  lg: 'w-20 h-20',   // 80px - Current picker, featured
  xl: 'w-32 h-32',   // 128px - Modal detail view
};

// ChampionPortrait component
function ChampionPortrait({ 
  champion, 
  size = 'md', 
  state = 'default', // 'default' | 'picking' | 'picked' | 'banned' | 'unavailable'
  team = null,       // 'blue' | 'red' | null
}) {
  const baseClasses = `
    relative rounded-sm overflow-hidden
    ${SIZES[size]}
    transition-all duration-200
  `;
  
  const stateClasses = {
    default: 'border-2 border-gold-dim',
    picking: 'border-2 border-magic-bright shadow-magic animate-magic-pulse',
    picked: team === 'blue' 
      ? 'border-2 border-blue-team' 
      : 'border-2 border-red-team',
    banned: 'grayscale opacity-50 border-2 border-red-team',
    unavailable: 'grayscale opacity-30',
  };
  
  return (
    <div className={`${baseClasses} ${stateClasses[state]}`}>
      <img 
        src={getChampionIcon(champion)} 
        alt={champion}
        className="w-full h-full object-cover"
      />
      {state === 'banned' && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-red-team text-2xl font-bold">✕</span>
        </div>
      )}
    </div>
  );
}
```

**Data Dragon Icons:**
```javascript
// Use Riot's Data Dragon CDN for champion icons
const DDRAGON_VERSION = '14.24.1'; // Update to latest
const getChampionIcon = (championKey) => 
  `https://ddragon.leagueoflegends.com/cdn/${DDRAGON_VERSION}/img/champion/${championKey}.png`;
```

### 5.2 Recommendation Card

```jsx
function RecommendationCard({ 
  champion, 
  confidence, 
  flag,        // null | 'SURPRISE_PICK' | 'LOW_CONFIDENCE'
  reasons,
  isTopPick = false 
}) {
  const confidenceColor = 
    confidence >= 0.7 ? 'text-success' :
    confidence >= 0.5 ? 'text-warning' : 'text-danger';
  
  const cardBorder = isTopPick 
    ? 'border-magic-bright shadow-magic' 
    : 'border-gold-dim';
  
  return (
    <div className={`
      bg-lol-light rounded-lg p-4 border-2 ${cardBorder}
      transition-all duration-300 hover:border-magic hover:shadow-magic
    `}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <ChampionPortrait champion={champion} size="lg" state="default" />
        <div>
          <div className="flex items-center gap-2">
            {isTopPick && <span className="text-lg">🎯</span>}
            {flag === 'SURPRISE_PICK' && <span className="text-lg">🎲</span>}
            {flag === 'LOW_CONFIDENCE' && <span className="text-lg">⚠️</span>}
            <h3 className="font-display text-xl uppercase text-gold-bright">
              {champion}
            </h3>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`font-body text-sm font-semibold ${confidenceColor}`}>
              {Math.round(confidence * 100)}%
            </span>
            <ConfidenceBar confidence={confidence} />
          </div>
        </div>
      </div>
      
      {/* Flag banner */}
      {flag && (
        <div className={`
          text-xs uppercase tracking-widest font-semibold mb-3 py-1 px-2 rounded
          ${flag === 'SURPRISE_PICK' ? 'bg-warning/20 text-warning' : 'bg-danger/20 text-danger'}
        `}>
          {flag === 'SURPRISE_PICK' ? 'Surprise Pick - Limited Data' : 'Low Confidence'}
        </div>
      )}
      
      {/* Reasons */}
      <ul className="space-y-1.5">
        {reasons.map((reason, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-lol-secondary">
            <span className="text-gold mt-0.5">•</span>
            <span>{reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConfidenceBar({ confidence }) {
  const fillColor = 
    confidence >= 0.7 ? 'bg-success' :
    confidence >= 0.5 ? 'bg-warning' : 'bg-danger';
  
  return (
    <div className="w-24 h-2 bg-lol-darkest rounded-full overflow-hidden">
      <div 
        className={`h-full ${fillColor} transition-all duration-500`}
        style={{ width: `${confidence * 100}%` }}
      />
    </div>
  );
}
```

### 5.3 Draft Phase Indicator

```jsx
const PHASES = [
  { id: 'BAN_1', label: 'Ban 1', actions: 6 },
  { id: 'PICK_1', label: 'Pick 1', actions: 6 },
  { id: 'BAN_2', label: 'Ban 2', actions: 4 },
  { id: 'PICK_2', label: 'Pick 2', actions: 4 },
];

function PhaseIndicator({ currentPhase, currentAction }) {
  return (
    <div className="flex items-center justify-center gap-2">
      {PHASES.map((phase, i) => {
        const isActive = phase.id === currentPhase;
        const isPast = PHASES.findIndex(p => p.id === currentPhase) > i;
        
        return (
          <div 
            key={phase.id}
            className={`
              px-3 py-1.5 rounded-sm text-xs uppercase tracking-widest font-semibold
              transition-all duration-300
              ${isActive 
                ? 'bg-magic text-lol-darkest shadow-magic' 
                : isPast 
                  ? 'bg-gold-dark text-gold-dim' 
                  : 'bg-lol-light text-lol-secondary'
              }
            `}
          >
            {phase.label}
          </div>
        );
      })}
    </div>
  );
}
```

### 5.4 Timer Component

The timer is a key visual element with an ornate frame.

```jsx
function DraftTimer({ seconds, isActive }) {
  const urgentThreshold = 10;
  const isUrgent = seconds <= urgentThreshold && isActive;
  
  return (
    <div className={`
      relative w-24 h-24 flex items-center justify-center
      ${isActive ? 'animate-magic-pulse' : ''}
    `}>
      {/* Ornate frame (SVG or image asset needed - see Assets section) */}
      <div className="absolute inset-0 timer-frame" />
      
      {/* Timer value */}
      <span className={`
        font-display text-4xl font-bold
        ${isUrgent ? 'text-red-team animate-pulse' : 'text-gold-bright'}
      `}>
        {seconds}
      </span>
      
      {/* Glow effect */}
      {isActive && (
        <div className="absolute inset-0 rounded-full bg-magic/20 blur-xl -z-10" />
      )}
    </div>
  );
}
```

### 5.5 Team Panel

```jsx
function TeamPanel({ team, side, players, picks, isActive }) {
  const sideColors = side === 'blue' 
    ? { bg: 'bg-blue-team-bg', accent: 'border-blue-team', text: 'text-blue-team' }
    : { bg: 'bg-red-team-bg', accent: 'border-red-team', text: 'text-red-team' };
  
  return (
    <div className={`
      ${sideColors.bg} rounded-lg p-4 border-l-4 ${sideColors.accent}
      ${isActive ? 'shadow-magic-lg' : ''}
    `}>
      {/* Team header */}
      <div className="flex items-center gap-3 mb-4">
        <img 
          src={team.logo} 
          alt={team.name}
          className="w-10 h-10 rounded"
        />
        <h2 className={`font-display text-lg uppercase ${sideColors.text}`}>
          {team.name}
        </h2>
      </div>
      
      {/* Player list with picks */}
      <div className="space-y-3">
        {players.map((player, i) => (
          <div key={player.id} className="flex items-center gap-3">
            <span className="w-12 text-xs uppercase text-lol-secondary">
              {player.role}
            </span>
            <span className="flex-1 text-sm text-gold-bright">
              {player.name}
            </span>
            {picks[i] ? (
              <ChampionPortrait 
                champion={picks[i]} 
                size="sm" 
                state="picked"
                team={side}
              />
            ) : (
              <div className="w-10 h-10 border border-gold-dim rounded-sm bg-lol-darkest" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 5.6 AI Insight Panel

```jsx
function InsightPanel({ insight, isLoading }) {
  return (
    <div className="
      bg-gradient-to-br from-lol-dark to-lol-medium
      rounded-lg p-4 border border-magic/30
      relative overflow-hidden
    ">
      {/* Ambient glow background */}
      <div className="absolute inset-0 bg-magic/5" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-32 bg-magic/10 rounded-full blur-3xl" />
      
      {/* Header */}
      <div className="relative flex items-center gap-2 mb-3">
        <span className="text-2xl">💡</span>
        <h3 className="font-display text-sm uppercase tracking-widest text-magic">
          AI Insight
        </h3>
      </div>
      
      {/* Content */}
      <div className="relative">
        {isLoading ? (
          <div className="flex items-center gap-2 text-lol-secondary">
            <div className="w-4 h-4 border-2 border-magic border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Analyzing draft...</span>
          </div>
        ) : (
          <p className="font-body text-sm text-gold-bright leading-relaxed">
            "{insight}"
          </p>
        )}
      </div>
    </div>
  );
}
```

### 5.7 Ban Track

```jsx
function BanTrack({ blueBans, redBans }) {
  const allBans = [
    // Ban order: B1, R1, R2, B2, B3, R3, R4, B4, B5, R5
    { champ: blueBans[0], team: 'blue' },
    { champ: redBans[0], team: 'red' },
    { champ: redBans[1], team: 'red' },
    { champ: blueBans[1], team: 'blue' },
    { champ: blueBans[2], team: 'blue' },
    { champ: redBans[2], team: 'red' },
    // Ban phase 2
    { champ: redBans[3], team: 'red' },
    { champ: blueBans[3], team: 'blue' },
    { champ: blueBans[4], team: 'blue' },
    { champ: redBans[4], team: 'red' },
  ];
  
  return (
    <div className="flex justify-center gap-1">
      {/* Phase 1 bans */}
      <div className="flex gap-1">
        {allBans.slice(0, 6).map((ban, i) => (
          <div 
            key={i}
            className={`
              relative w-8 h-8 rounded-sm overflow-hidden
              border ${ban.team === 'blue' ? 'border-blue-team/50' : 'border-red-team/50'}
            `}
          >
            {ban.champ ? (
              <>
                <img 
                  src={getChampionIcon(ban.champ)} 
                  alt={ban.champ}
                  className="w-full h-full object-cover grayscale"
                />
                <div className="absolute inset-0 bg-lol-darkest/60" />
                <span className="absolute inset-0 flex items-center justify-center text-red-team text-lg">
                  ✕
                </span>
              </>
            ) : (
              <div className="w-full h-full bg-lol-darkest" />
            )}
          </div>
        ))}
      </div>
      
      {/* Separator */}
      <div className="w-px bg-gold-dim mx-2" />
      
      {/* Phase 2 bans */}
      <div className="flex gap-1">
        {allBans.slice(6).map((ban, i) => (
          <div 
            key={i + 6}
            className={`
              relative w-8 h-8 rounded-sm overflow-hidden
              border ${ban.team === 'blue' ? 'border-blue-team/50' : 'border-red-team/50'}
            `}
          >
            {ban.champ ? (
              <>
                <img 
                  src={getChampionIcon(ban.champ)} 
                  alt={ban.champ}
                  className="w-full h-full object-cover grayscale"
                />
                <div className="absolute inset-0 bg-lol-darkest/60" />
                <span className="absolute inset-0 flex items-center justify-center text-red-team text-lg">
                  ✕
                </span>
              </>
            ) : (
              <div className="w-full h-full bg-lol-darkest" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 6. Effects & Animations

### 6.1 CSS Animations

```css
/* Magic glow keyframes */
@keyframes magicPulse {
  0%, 100% { 
    box-shadow: 0 0 20px rgba(10, 200, 185, 0.4);
    transform: scale(1);
  }
  50% { 
    box-shadow: 0 0 40px rgba(10, 200, 185, 0.7);
    transform: scale(1.02);
  }
}

/* Shimmer effect for loading states */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.shimmer {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(10, 200, 185, 0.1) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

/* Phase transition sweep */
@keyframes phaseSweep {
  0% { 
    transform: scaleX(0);
    transform-origin: left;
  }
  50% { 
    transform: scaleX(1);
    transform-origin: left;
  }
  50.01% { 
    transform-origin: right;
  }
  100% { 
    transform: scaleX(0);
    transform-origin: right;
  }
}

/* Stagger reveal for recommendation cards */
.recommendation-card:nth-child(1) { animation-delay: 0ms; }
.recommendation-card:nth-child(2) { animation-delay: 100ms; }
.recommendation-card:nth-child(3) { animation-delay: 200ms; }
```

### 6.2 Framer Motion Variants (Optional Enhancement)

```jsx
// If using framer-motion for more complex animations
const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: i * 0.1,
      duration: 0.3,
      ease: 'easeOut',
    },
  }),
};

const pulseVariants = {
  idle: { scale: 1, boxShadow: '0 0 20px rgba(10, 200, 185, 0.4)' },
  active: {
    scale: [1, 1.02, 1],
    boxShadow: [
      '0 0 20px rgba(10, 200, 185, 0.4)',
      '0 0 40px rgba(10, 200, 185, 0.7)',
      '0 0 20px rgba(10, 200, 185, 0.4)',
    ],
    transition: { duration: 2, repeat: Infinity },
  },
};
```

---

## 7. Assets Required

These elements cannot be effectively replicated with CSS alone and should be created as assets:

### 7.1 Image Assets Needed

| Asset | Description | Format | Notes |
|-------|-------------|--------|-------|
| **Timer Frame** | Ornate hextech-style circular frame around timer | SVG or PNG | See reference in Image 1 - gold metallic frame with corner decorations |
| **Panel Corners** | Decorative corner pieces for major panels | SVG | Gold/bronze metallic corners (4 variants for each corner) |
| **Team Badge Frames** | Hexagonal or shield-shaped frames for team logos | SVG | Blue and Red variants |
| **Phase Divider** | Decorative horizontal divider between sections | SVG | Central ornament with extending lines |
| **Background Texture** | Subtle hextech pattern for backgrounds | PNG (tileable) | Low-opacity metallic/circuit pattern |
| **Magic Particles** | Floating particle effect for active states | PNG sprite or Lottie | Cyan/teal colored particles |

### 7.2 Asset Generation Prompts

For AI image generation (Midjourney, DALL-E, etc.):

**Timer Frame:**
```
Hextech UI frame, circular timer border, gold and bronze metallic, 
fantasy technology aesthetic, dark blue glow, ornate corners, 
game UI element, transparent background, League of Legends style --v 6
```

**Panel Corners:**
```
UI corner decoration, gold metallic frame corner, hextech design,
fantasy technology, angular geometric patterns, game interface element,
isolated on transparent background, League of Legends client style --v 6
```

**Background Texture:**
```
Seamless tileable pattern, hextech circuit board, dark blue #0A1428,
subtle gold lines, fantasy technology aesthetic, game UI background,
low contrast, elegant geometric --tile --v 6
```

### 7.3 Alternative: CSS-Only Approximations

If assets aren't available, here are CSS approximations:

```css
/* Timer frame using gradients and borders */
.timer-frame-css {
  position: relative;
  border: 3px solid var(--gold-standard);
  border-radius: 50%;
  background: 
    linear-gradient(135deg, transparent 45%, var(--gold-dim) 50%, transparent 55%),
    var(--bg-dark);
  box-shadow:
    inset 0 0 20px rgba(0, 0, 0, 0.5),
    0 0 10px rgba(200, 170, 110, 0.3);
}

.timer-frame-css::before,
.timer-frame-css::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 8px;
  background: var(--gold-bright);
  border-radius: 50%;
}

.timer-frame-css::before { top: -4px; left: 50%; transform: translateX(-50%); }
.timer-frame-css::after { bottom: -4px; left: 50%; transform: translateX(-50%); }

/* Panel corner using CSS */
.panel-corner {
  position: absolute;
  width: 20px;
  height: 20px;
  border-color: var(--gold-standard);
  border-style: solid;
}

.panel-corner.top-left {
  top: 0; left: 0;
  border-width: 2px 0 0 2px;
}

.panel-corner.top-right {
  top: 0; right: 0;
  border-width: 2px 2px 0 0;
}

/* etc. for other corners */
```

---

## 8. shadcn/ui Integration

### 8.1 Theme Configuration

Create a custom theme for shadcn components:

```javascript
// lib/theme.ts
export const lolTheme = {
  radius: '0.25rem',  // Slightly angular, not fully rounded
  
  colors: {
    background: 'hsl(210 80% 4%)',      // --bg-darkest
    foreground: 'hsl(44 35% 91%)',       // --gold-bright
    card: 'hsl(210 50% 10%)',            // --bg-light
    cardForeground: 'hsl(44 35% 91%)',
    popover: 'hsl(210 50% 10%)',
    popoverForeground: 'hsl(44 35% 91%)',
    primary: 'hsl(175 92% 41%)',         // --magic-bright
    primaryForeground: 'hsl(210 80% 4%)',
    secondary: 'hsl(44 45% 60%)',        // --gold-standard
    secondaryForeground: 'hsl(210 80% 4%)',
    muted: 'hsl(210 20% 20%)',
    mutedForeground: 'hsl(40 10% 50%)',
    accent: 'hsl(175 60% 33%)',          // --magic
    accentForeground: 'hsl(44 35% 91%)',
    destructive: 'hsl(350 70% 50%)',     // --red-team
    destructiveForeground: 'hsl(44 35% 91%)',
    border: 'hsl(44 30% 30%)',           // --gold-dim
    input: 'hsl(210 30% 15%)',
    ring: 'hsl(175 92% 41%)',            // --magic-bright
  },
};
```

### 8.2 Component Overrides

```jsx
// Override shadcn Button for LoL style
import { Button } from '@/components/ui/button';

// Primary "Hextech Magic" button
<Button 
  className="
    bg-magic hover:bg-magic-bright 
    text-lol-darkest font-display uppercase tracking-wider
    border-2 border-magic-bright
    shadow-magic hover:shadow-magic-lg
    transition-all duration-200
  "
>
  Lock In
</Button>

// Secondary "Gold" button
<Button 
  variant="outline"
  className="
    bg-transparent hover:bg-gold-dark
    text-gold border-gold hover:border-gold-bright
    font-display uppercase tracking-wider
  "
>
  View Details
</Button>
```

---

## 9. Implementation Checklist

### Phase 1: Foundation
- [ ] Set up Tailwind v4 with custom theme
- [ ] Import/configure fonts (Cinzel + Inter)
- [ ] Create color system CSS variables
- [ ] Set up basic layout grid

### Phase 2: Core Components
- [ ] ChampionPortrait (all size/state variants)
- [ ] Timer with basic CSS frame
- [ ] PhaseIndicator
- [ ] BanTrack
- [ ] TeamPanel

### Phase 3: Recommendation UI
- [ ] RecommendationCard with confidence bar
- [ ] InsightPanel
- [ ] Recommendation grid layout

### Phase 4: Polish
- [ ] Add animations (pulse, reveal, transitions)
- [ ] Create/integrate image assets
- [ ] Loading states and skeletons
- [ ] Responsive adjustments

### Phase 5: Integration
- [ ] WebSocket connection for live updates
- [ ] Real champion data from Data Dragon
- [ ] Hook up recommendation API

---

## 10. Reference Links

- [Riot Brand Portal](https://brand.riotgames.com/en-us/league-of-legends)
- [Data Dragon](https://developer.riotgames.com/docs/lol#data-dragon)
- [Hextech Visual Language Article](https://nexus.leagueoflegends.com/en-us/2016/12/the-visual-language-of-hextech/)
- [Beaufort Font (from Brand Portal)](https://cmsassets.rgpub.io/sanity/files/dsfx7636/news/bc7839c2f650eec7fda9141d22ff3c83f7e0cb81.zip)
- [Spiegel Font (from Brand Portal)](https://cmsassets.rgpub.io/sanity/files/dsfx7636/news/5997e78145e4c250ffed3cd3d76bb96d82f22553.zip)

---

*Style Guide Version 1.0 | January 2026*
