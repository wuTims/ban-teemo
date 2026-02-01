// frontend/src/components/SettingsModal/index.tsx
import { useState, useEffect } from "react";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKey: string;
  llmEnabled: boolean;
  onSave: (apiKey: string, llmEnabled: boolean) => void;
}

export function SettingsModal({
  isOpen,
  onClose,
  apiKey: initialApiKey,
  llmEnabled: initialLlmEnabled,
  onSave,
}: SettingsModalProps) {
  const [apiKey, setApiKey] = useState(initialApiKey);
  const [llmEnabled, setLlmEnabled] = useState(initialLlmEnabled);
  const [showKey, setShowKey] = useState(false);

  // Sync local state when modal opens
  useEffect(() => {
    if (isOpen) {
      setApiKey(initialApiKey);
      setLlmEnabled(initialLlmEnabled);
      setShowKey(false);
    }
  }, [isOpen, initialApiKey, initialLlmEnabled]);

  const handleSave = () => {
    onSave(apiKey, llmEnabled);
    onClose();
  };

  const handleCancel = () => {
    setApiKey(initialApiKey);
    setLlmEnabled(initialLlmEnabled);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
      <div className="bg-lol-dark rounded-lg p-6 w-full max-w-md border border-gold-dim/30 shadow-lg">
        <h2 className="text-xl font-bold text-gold-bright mb-6 text-center uppercase tracking-wide">
          Settings
        </h2>

        {/* API Key Input */}
        <div className="mb-6">
          <label className="block text-sm text-text-secondary mb-2">
            Nebius API Key
          </label>
          <div className="relative">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key..."
              className="w-full px-3 py-2 pr-16 bg-lol-light border border-gold-dim/30 rounded text-text-primary focus:outline-none focus:border-magic"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
            >
              {showKey ? "Hide" : "Show"}
            </button>
          </div>
          <p className="mt-1 text-xs text-text-tertiary">
            Required for AI-powered draft analysis. Get a key from{" "}
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

        {/* LLM Enabled Toggle */}
        <div className="mb-8">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={llmEnabled}
              onChange={(e) => setLlmEnabled(e.target.checked)}
              disabled={!apiKey}
              className="w-4 h-4 accent-magic"
            />
            <div>
              <span className="text-text-primary">Enable AI Analysis</span>
              {!apiKey && (
                <span className="text-xs text-text-tertiary ml-2">
                  (requires API key)
                </span>
              )}
            </div>
          </label>
          <p className="mt-1 text-xs text-text-tertiary ml-7">
            Get AI-powered strategic insights during replay
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={handleCancel}
            className="flex-1 px-4 py-2 bg-lol-light border border-gold-dim/30 rounded text-text-secondary hover:bg-lol-hover transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex-1 px-4 py-2 bg-magic text-lol-darkest rounded font-semibold hover:bg-magic-bright transition-colors"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
