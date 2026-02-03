# AI Insights Discoverability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make it obvious that AI insights exist and how to enable them, via a dismissible global banner and improved simulator setup UX.

**Architecture:** Three small changes — a dismissible banner component in App.tsx, an enhanced API key section in SimulatorSetupModal, and wiring so the simulator setup auto-saves the key to global settings and enables AI.

**Tech Stack:** React, Tailwind CSS, localStorage

---

### Task 1: Add dismissible AI insights banner to App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Context:** The banner should appear below the header, above `<main>`. It shows when: (1) no API key is configured globally, AND (2) the user hasn't dismissed it. It has two actions: "Open Settings" (opens settings modal) and a dismiss X button.

**Step 1: Add banner dismiss state**

Add to App.tsx, inside `App()`, after the existing `useState` calls:

```tsx
const [bannerDismissed, setBannerDismissed] = useState(() => {
  try {
    return localStorage.getItem("ban_teemo_ai_banner_dismissed") === "true";
  } catch {
    return false;
  }
});

const dismissBanner = () => {
  setBannerDismissed(true);
  try {
    localStorage.setItem("ban_teemo_ai_banner_dismissed", "true");
  } catch {}
};

const showAiBanner = !settings.hasApiKey && !bannerDismissed;
```

**Step 2: Add banner JSX**

Insert between `</header>` and `<main>` in App.tsx:

```tsx
{showAiBanner && (
  <div className="bg-magic/10 border-b border-magic/30 px-3 sm:px-6 py-2.5 flex items-center justify-between gap-3">
    <div className="flex items-center gap-2 min-w-0">
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-magic shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      <p className="text-sm text-text-secondary">
        <span className="text-magic font-medium">AI-powered draft insights</span>
        {" "}are available. Add your Nebius API key in{" "}
        <button
          onClick={() => setShowSettings(true)}
          className="text-magic hover:underline font-medium"
        >
          Settings
        </button>
        {" "}to enable.
      </p>
    </div>
    <button
      onClick={dismissBanner}
      className="p-1 text-text-tertiary hover:text-text-secondary transition-colors shrink-0"
      title="Dismiss"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
)}
```

**Step 3: Verify visually**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run dev`

- Verify banner appears when no API key is set
- Click "Settings" link — settings modal opens
- Click X — banner disappears and does not return on refresh
- Set an API key in settings, remove the localStorage dismiss flag — banner should not appear (key is set)

**Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(ui): add dismissible banner for AI insights discoverability"
```

---

### Task 2: Improve SimulatorSetupModal API key section

**Files:**
- Modify: `frontend/src/components/SimulatorSetupModal/index.tsx`

**Context:** The current API key input in SimulatorSetupModal just says "optional" with no guidance on where to get a key. We need to:
1. Add a link to Nebius AI Studio (matching the SettingsModal pattern)
2. Add helper text explaining what it enables
3. Accept a new prop to persist the key to global settings and auto-enable AI

**Step 1: Update the SimulatorSetupModalProps interface**

Add a new optional prop for persisting to global settings:

```tsx
interface SimulatorSetupModalProps {
  isOpen: boolean;
  onStart: (config: SimulatorConfig) => void;
  onClose: () => void;
  onSetLlmApiKey?: (key: string | null) => void;
  onSaveGlobalApiKey?: (apiKey: string, llmEnabled: boolean) => void;
}
```

**Step 2: Destructure the new prop**

Update the function signature:

```tsx
export function SimulatorSetupModal({ isOpen, onStart, onClose, onSetLlmApiKey, onSaveGlobalApiKey }: SimulatorSetupModalProps) {
```

**Step 3: Update handleStart to persist globally**

In the `handleStart` function, after the existing `onSetLlmApiKey` call, add:

```tsx
if (onSaveGlobalApiKey && llmApiKey.trim()) {
  onSaveGlobalApiKey(llmApiKey.trim(), true);
}
```

This saves the key to global settings AND auto-enables AI when a key is entered through the simulator setup.

**Step 4: Update the API key input section JSX**

Replace the existing AI Insights API Key section (lines 177-192) with:

```tsx
{/* AI Insights API Key */}
<div className="mb-8 space-y-2">
  <label className="block text-sm text-text-secondary">
    AI Insights API Key
    <span className="text-text-tertiary ml-1">(optional)</span>
  </label>
  <input
    type="password"
    placeholder="Enter your API key..."
    value={llmApiKey}
    onChange={(e) => setLlmApiKey(e.target.value)}
    className="w-full px-3 py-2 bg-lol-light border border-magic/30 rounded text-text-primary placeholder-text-tertiary focus:outline-none focus:border-magic"
  />
  <p className="text-xs text-text-tertiary">
    Enables AI-powered strategic analysis during your draft. Get a free key from{" "}
    <a
      href="https://studio.nebius.ai/"
      target="_blank"
      rel="noopener noreferrer"
      className="text-magic hover:underline"
    >
      Nebius AI Studio
    </a>
  </p>
</div>
```

**Step 5: Commit**

```bash
git add frontend/src/components/SimulatorSetupModal/index.tsx
git commit -m "feat(ui): improve simulator setup AI key section with link and auto-enable"
```

---

### Task 3: Wire the new prop in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Context:** Pass the `onSaveGlobalApiKey` callback from App.tsx to SimulatorSetupModal so that entering a key in the simulator setup persists it to global settings and auto-enables AI.

**Step 1: Add the prop to SimulatorSetupModal usage**

In App.tsx, update the `<SimulatorSetupModal>` JSX (around line 288) to add the new prop:

```tsx
<SimulatorSetupModal
  isOpen={showSetup}
  onStart={handleStartSimulator}
  onClose={() => setShowSetup(false)}
  onSetLlmApiKey={simulator.setLlmApiKey}
  onSaveGlobalApiKey={handleSaveSettings}
/>
```

`handleSaveSettings` already exists (line 30-33) and accepts `(apiKey: string, llmEnabled: boolean)` — it calls `settings.setApiKey` and `settings.setLlmEnabled`, which is exactly what we need.

**Step 2: Verify end-to-end**

Run: `cd /workspaces/web-dev-playground/ban-teemo/frontend && npm run dev`

- Open simulator setup, enter an API key, start a draft
- After starting, verify: Settings modal shows the key saved, AI Analysis is enabled
- Verify the banner disappears (key is now set globally)
- Clear localStorage, reload — banner should reappear

**Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(ui): wire simulator setup to persist API key to global settings"
```
