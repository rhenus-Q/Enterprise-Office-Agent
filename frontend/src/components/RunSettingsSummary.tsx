import type { RunConstraint, RunOptions, RunSettings } from '../types/api';

/**
 * Human text for each typed backend constraint.
 *
 * The identifiers are the contract; this map is presentation only. An unknown
 * identifier falls back to the raw code rather than being hidden, so a new
 * backend reason can never silently disappear from the UI.
 */
export const CONSTRAINT_LABELS: Record<RunConstraint, string> = {
  server_offline_mode: 'Server offline mode overrode this request.',
  server_privacy_mode: 'Server privacy mode overrode this request.',
  request_privacy_strict: 'This run requested strict privacy.',
  server_llm_assist_disabled: 'The server does not allow Office LLM use.',
  server_web_search_disabled: 'Server web search is unavailable.',
  llm_assist_not_applicable: 'LLM Assist does not apply to this capability.',
  web_search_not_applicable: 'Web Search does not apply to this capability.',
};

function constraintLabel(constraint: RunConstraint): string {
  return CONSTRAINT_LABELS[constraint] ?? constraint;
}

function onOff(value: boolean): string {
  return value ? 'On' : 'Off';
}

interface RunSettingsSummaryProps {
  /**
   * The snapshot taken when the run was submitted. Shown on its own while the
   * run is in flight, and as the `requested` column once a response arrives.
   */
  requested: RunOptions | null;
  /** The backend's authoritative account. Null until a response comes back. */
  settings: RunSettings | null;
  /**
   * The run is still in flight, so the backend has not resolved effective
   * settings yet. Distinguishes "still waiting" from a settled run whose
   * response simply carried no `run_settings` — the two are indistinguishable
   * from `settings === null` alone, so the lifecycle must be passed in.
   */
  active?: boolean;
  /**
   * A frontend-stopped run: the browser stopped waiting, so no completed
   * backend response exists and effective settings are genuinely unknown.
   */
  stopped?: boolean;
}

/**
 * Requested vs. effective run settings.
 *
 * The effective column is rendered strictly from the backend's `run_settings`.
 * Nothing here re-derives it, and nothing is inferred from badge text or other
 * rendered content — when the backend has not reported, this says so.
 */
export function RunSettingsSummary({
  requested,
  settings,
  active,
  stopped,
}: RunSettingsSummaryProps) {
  if (!requested && !settings) {
    return (
      <p className="empty-note">
        No per-run settings were sent with this request, so the run used the server defaults.
      </p>
    );
  }

  // The backend echoes back what it received, which is the more authoritative
  // record of the request; the local snapshot covers the in-flight case.
  const requestedValues = settings?.requested ?? requested;
  const effective = settings?.effective ?? null;
  const applicability = settings?.applicability ?? null;

  return (
    <div className="run-settings-summary">
      <h4 className="run-settings-summary__title">Requested</h4>
      <dl className="fields">
        <div className="field">
          <dt>Privacy</dt>
          <dd>{requestedValues?.privacy_mode === 'strict' ? 'Strict' : 'Standard'}</dd>
        </div>
        <div className="field">
          <dt>LLM Assist</dt>
          <dd>{onOff(Boolean(requestedValues?.llm_assist))}</dd>
        </div>
        <div className="field">
          <dt>Web Search</dt>
          <dd>{onOff(Boolean(requestedValues?.web_search))}</dd>
        </div>
      </dl>

      <h4 className="run-settings-summary__title">Effective</h4>
      {effective ? (
        <>
          <dl className="fields">
            <div className="field">
              <dt>Privacy</dt>
              <dd>{effective.privacy_mode === 'strict' ? 'Strict' : 'Standard'}</dd>
            </div>
            <div className="field">
              <dt>LLM Assist</dt>
              <dd>
                {applicability && !applicability.llm_assist ? (
                  <span className="not-applicable">Not applicable</span>
                ) : (
                  onOff(effective.llm_assist)
                )}
              </dd>
            </div>
            <div className="field">
              <dt>Web Search</dt>
              <dd>
                {applicability && !applicability.web_search ? (
                  <span className="not-applicable">Not applicable</span>
                ) : (
                  onOff(effective.web_search)
                )}
              </dd>
            </div>
          </dl>

          {settings && settings.constraints.length > 0 ? (
            <ul className="run-settings-summary__constraints">
              {settings.constraints.map((constraint) => (
                <li key={constraint}>{constraintLabel(constraint)}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <p className="empty-note">
          {stopped
            ? 'This request was stopped in the browser, so no completed response was received. The effective settings for that run are unavailable.'
            : active
              ? 'Waiting for the backend to report which settings actually govern this run.'
              : 'The backend did not report effective settings for this run.'}
        </p>
      )}
    </div>
  );
}
