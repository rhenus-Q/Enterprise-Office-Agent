import type { RunOptions, RunPrivacyMode } from '../types/api';

interface RunSettingsControlsProps {
  value: RunOptions;
  onChange: (next: RunOptions) => void;
  /** Controls are locked while a run is in flight, then restored. */
  disabled: boolean;
}

/**
 * Per-run settings for the *next* request.
 *
 * Deliberately distinct from the top status badges: those are read-only server
 * policy, these are interactive requests. The visual and semantic separation is
 * the point — badges are static text, these are real form controls with labels,
 * focus states, and keyboard operation.
 *
 * Two honesty rules are encoded here:
 *
 * 1. These are *requests*, not guarantees. Server policy always wins, and the
 *    backend reports what actually governed the run. This component never
 *    predicts the effective outcome — the applicability hints below say where a
 *    setting *can* apply, not whether it did.
 * 2. Settings are snapshotted at submit by the caller, so changing a control
 *    mid-run cannot affect the request already in flight.
 */
export function RunSettingsControls({ value, onChange, disabled }: RunSettingsControlsProps) {
  function setPrivacy(privacy_mode: RunPrivacyMode) {
    onChange({ ...value, privacy_mode });
  }

  return (
    <section
      className="run-settings"
      aria-label="Run settings"
      data-disabled={disabled ? 'true' : 'false'}
    >
      <div className="run-settings__header">
        <h2 className="run-settings__title">Run settings</h2>
        <p className="run-settings__note">
          Applied to the next request only. Server policy always wins — a setting here can
          restrict a run, never loosen it.
        </p>
      </div>

      <fieldset className="run-settings__group" disabled={disabled}>
        <legend className="run-settings__legend">
          Privacy
          <span className="run-settings__applies">external-service-capable runs</span>
        </legend>
        <div className="run-settings__choices" role="radiogroup" aria-label="Privacy">
          {(['standard', 'strict'] as const).map((mode) => (
            <label key={mode} className="choice">
              <input
                type="radio"
                name="run-privacy"
                value={mode}
                checked={value.privacy_mode === mode}
                onChange={() => setPrivacy(mode)}
                disabled={disabled}
              />
              <span>{mode === 'standard' ? 'Standard' : 'Strict'}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="run-settings__group" disabled={disabled}>
        <legend className="run-settings__legend">
          LLM Assist
          <span className="run-settings__applies">Email Summary and Daily Briefing</span>
        </legend>
        <label className="choice choice--switch">
          <input
            type="checkbox"
            checked={value.llm_assist}
            onChange={(event) => onChange({ ...value, llm_assist: event.target.checked })}
            disabled={disabled}
            aria-label="LLM Assist"
          />
          <span>{value.llm_assist ? 'On' : 'Off'}</span>
        </label>
      </fieldset>

      <fieldset className="run-settings__group" disabled={disabled}>
        <legend className="run-settings__legend">
          Web Search
          <span className="run-settings__applies">Knowledge Q&amp;A</span>
        </legend>
        <label className="choice choice--switch">
          <input
            type="checkbox"
            checked={value.web_search}
            onChange={(event) => onChange({ ...value, web_search: event.target.checked })}
            disabled={disabled}
            aria-label="Web Search"
          />
          <span>{value.web_search ? 'On' : 'Off'}</span>
        </label>
      </fieldset>
    </section>
  );
}
