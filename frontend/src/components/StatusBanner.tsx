import { FlaskConical, Globe, Shield, Sparkles, WifiOff, type LucideIcon } from 'lucide-react';

import type { HealthResponse } from '../types/api';

interface StatusBannerProps {
  health: HealthResponse | null;
}

/** Semantic tone for a status chip — drives tint, border, and icon colour. */
type StatusTone = 'privacy' | 'slate' | 'assist' | 'ok' | 'mock';

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

/**
 * Compact runtime status indicators in the product header.
 *
 * `web_search_effective` is the effective, mode-aware value from the engine's own
 * reader — not a raw `WEB_SEARCH_ENABLED` echo — so it already reflects
 * PRIVACY_MODE and OFFLINE_MODE. The wording here is presentation only; no API
 * field name or value changes.
 *
 * The mock-environment chip is deliberately set apart from the runtime-policy
 * chips: it describes where the data came from, not a policy the engine applied.
 */
export function StatusBanner({ health }: StatusBannerProps) {
  if (!health) {
    return (
      <ul className="status" aria-label="Runtime status" aria-live="polite">
        <li className="status-chip status-chip--slate">
          <span className="status-chip__label">Runtime status</span>
          <span className="status-chip__sep" aria-hidden="true">
            ·
          </span>
          <span className="status-chip__value">Loading…</span>
        </li>
      </ul>
    );
  }

  return (
    <ul className="status" aria-label="Runtime status" aria-live="polite">
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

      <li className="status__divider" aria-hidden="true" />

      <StatusChip
        icon={FlaskConical}
        tone="mock"
        label="Mock environment"
        value="Phase 1"
        explanation="Responses come from typed mock fixtures; the Python backend is not connected yet."
      />
    </ul>
  );
}
