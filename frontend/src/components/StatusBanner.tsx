import {
  FlaskConical,
  Globe,
  RefreshCw,
  Server,
  Shield,
  Sparkles,
  Unplug,
  WifiOff,
  type LucideIcon,
} from 'lucide-react';

import type { ApiMode } from '../api/client';
import type { HealthPhase } from '../hooks/useHealth';
import type { HealthResponse } from '../types/api';

interface StatusBannerProps {
  health: HealthResponse | null;
  phase: HealthPhase;
  /** The probe ran out of time rather than being refused. */
  timedOut: boolean;
  apiMode: ApiMode;
  isRefreshing: boolean;
  onRefresh: () => void;
}

/** Semantic tone for a status chip — drives tint, border, and icon colour. */
type StatusTone = 'privacy' | 'slate' | 'assist' | 'ok' | 'mock' | 'warn';

interface StatusChipProps {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: StatusTone;
  explanation: string;
}

/**
 * One runtime status chip.
 *
 * Informational only: no click handler, no toggle, no pointer cursor. The
 * explanation is exposed to assistive technology as text inside the item and to
 * pointer users as a tooltip, so the meaning never depends on colour alone.
 */
function StatusChip({ icon: Icon, label, value, tone, explanation }: StatusChipProps) {
  return (
    <li className={`status-chip status-chip--${tone}`} title={explanation}>
      <span className="status-chip__icon" aria-hidden="true">
        <Icon size={13} strokeWidth={2.25} />
      </span>
      <span className="status-chip__label">{label}</span>
      <span className="status-chip__sep" aria-hidden="true">
        ·
      </span>
      <span className="status-chip__value">{value}</span>
      <span className="sr-only">{explanation}</span>
    </li>
  );
}

/** The exact command that starts the adapter, shown when it is not answering. */
const START_API_COMMAND =
  'uv run uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000';

/**
 * Where the workspace's data comes from.
 *
 * Kept separate from the runtime-policy chips because it describes the
 * transport, not a policy the engine applied — and because a demo must never
 * be able to pass fixtures off as live engine output.
 */
function EnvironmentChip({ apiMode }: { apiMode: ApiMode }) {
  if (apiMode === 'mock') {
    return (
      <StatusChip
        icon={FlaskConical}
        tone="mock"
        label="Mock environment"
        value="Fixtures"
        explanation="Responses come from typed mock fixtures; the Python backend is not connected."
      />
    );
  }

  return (
    <StatusChip
      icon={Server}
      tone="ok"
      label="Data source"
      value="Live API"
      explanation="Responses come from the local Office Agent API via POST /api/agent/run."
    />
  );
}

/**
 * Compact runtime status indicators in the product header.
 *
 * `web_search_effective` is the effective, mode-aware value from the engine's own
 * reader — not a raw `WEB_SEARCH_ENABLED` echo — so it already reflects
 * PRIVACY_MODE and OFFLINE_MODE. The wording here is presentation only; no API
 * field name or value changes.
 *
 * The refresh control sits outside the list on purpose: the chips themselves
 * stay strictly informational, never controls.
 */
export function StatusBanner({
  health,
  phase,
  timedOut,
  apiMode,
  isRefreshing,
  onRefresh,
}: StatusBannerProps) {
  return (
    <div className="status-bar">
      <ul className="status" aria-label="Runtime status" aria-live="polite">
        {phase === 'loading' ? (
          <li className="status-chip status-chip--slate">
            <span className="status-chip__label">Runtime status</span>
            <span className="status-chip__sep" aria-hidden="true">
              ·
            </span>
            <span className="status-chip__value">Loading…</span>
          </li>
        ) : null}

        {phase === 'unreachable' ? (
          <StatusChip
            icon={Unplug}
            tone="warn"
            label="Office Agent API"
            // A stalled adapter and an absent one both leave the status blank,
            // but they are different problems, so the chip says which occurred.
            value={timedOut ? 'Timed out' : 'Unreachable'}
            explanation={
              timedOut
                ? `The API accepted the connection but did not answer the health check in time, so no runtime status is available. It may be starting up or stalled. Use Refresh to re-check, or run the frontend with VITE_API_MODE=mock to use the typed mock fixtures instead.`
                : `The API did not respond, so no runtime status is available. Start it with: ${START_API_COMMAND} — or run the frontend with VITE_API_MODE=mock to use the typed mock fixtures instead.`
            }
          />
        ) : null}

        {phase === 'ready' && health ? (
          <>
            <StatusChip
              icon={Shield}
              tone="privacy"
              label="Privacy"
              value={health.privacy_mode ? 'Restricted' : 'Standard'}
              explanation={
                health.privacy_mode
                  ? 'PRIVACY_MODE is active: external services other than OpenAI are blocked.'
                  : 'PRIVACY_MODE is off: the standard external-service policy applies.'
              }
            />
            <StatusChip
              icon={WifiOff}
              tone="slate"
              label="Offline restrictions"
              value={health.offline_mode ? 'On' : 'Off'}
              explanation={
                health.offline_mode
                  ? 'OFFLINE_MODE is active: every external service, including OpenAI, is disabled.'
                  : 'OFFLINE_MODE is off: external services are reachable subject to other policies.'
              }
            />
            <StatusChip
              icon={Sparkles}
              tone="assist"
              label="LLM assist"
              value={health.office_llm_enabled ? 'On' : 'Off'}
              explanation={
                health.office_llm_enabled
                  ? 'Optional LLM assists are enabled for the email digest and daily briefing.'
                  : 'Optional LLM assists are off, so those tools stay fully deterministic.'
              }
            />
            <StatusChip
              icon={Globe}
              tone={health.web_search_effective ? 'ok' : 'slate'}
              label="Web search"
              value={health.web_search_effective ? 'Available' : 'Blocked'}
              explanation={
                health.web_search_effective
                  ? 'Effective web-search state: web fallback is available to the RAG engine.'
                  : 'Effective web-search state: web fallback is blocked for this runtime.'
              }
            />
          </>
        ) : null}

        <li className="status__divider" aria-hidden="true" />

        <EnvironmentChip apiMode={apiMode} />
      </ul>

      <button
        type="button"
        className="status__refresh"
        onClick={onRefresh}
        disabled={isRefreshing || phase === 'loading'}
        aria-label="Refresh runtime status"
        title="Re-check the Office Agent API and its runtime flags"
      >
        <span className={isRefreshing ? 'status__refresh-icon is-spinning' : 'status__refresh-icon'} aria-hidden="true">
          <RefreshCw size={13} strokeWidth={2.25} />
        </span>
        <span className="status__refresh-text">{isRefreshing ? 'Checking…' : 'Refresh'}</span>
      </button>
    </div>
  );
}
