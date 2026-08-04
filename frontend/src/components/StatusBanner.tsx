import {
  ChevronDown,
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
import { useEffect, useId, useState } from 'react';

import type { ApiMode } from '../api/client';
import type { HealthPhase } from '../hooks/useHealth';
import { useMediaQuery } from '../hooks/useMediaQuery';
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

/** Semantic tone for a status chip - drives tint, border, and icon colour. */
type StatusTone = 'privacy' | 'slate' | 'assist' | 'ok' | 'mock' | 'warn';

interface StatusItem {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: StatusTone;
  explanation: string;
}

const MOBILE_LAYOUT_QUERY = '(max-width: 860px)';

/** What the chips are, stated outright. */
const SERVER_POLICY_NOTE = 'Read-only server policy configured by the API runtime.';

/** The exact command that starts the adapter, shown when it is not answering. */
const START_API_COMMAND =
  'uv run uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000';

function policyItems(health: HealthResponse): StatusItem[] {
  return [
    {
      icon: Shield,
      tone: 'privacy',
      label: 'Privacy',
      value: health.privacy_mode ? 'Restricted' : 'Standard',
      explanation: health.privacy_mode
        ? 'PRIVACY_MODE is active: external services other than OpenAI are blocked.'
        : 'PRIVACY_MODE is off: the standard external-service policy applies.',
    },
    {
      icon: WifiOff,
      tone: 'slate',
      label: 'Offline restrictions',
      value: health.offline_mode ? 'On' : 'Off',
      explanation: health.offline_mode
        ? 'OFFLINE_MODE is active: every external service, including OpenAI, is disabled.'
        : 'OFFLINE_MODE is off: external services are reachable subject to other policies.',
    },
    {
      icon: Sparkles,
      tone: 'assist',
      label: 'LLM assist',
      value: health.office_llm_enabled ? 'On' : 'Off',
      explanation: health.office_llm_enabled
        ? 'Optional LLM assists are enabled for the email digest and daily briefing.'
        : 'Optional LLM assists are off, so those tools stay fully deterministic.',
    },
    {
      icon: Globe,
      tone: health.web_search_effective ? 'ok' : 'slate',
      label: 'Web search',
      value: health.web_search_effective ? 'Available' : 'Blocked',
      explanation: health.web_search_effective
        ? 'Effective web-search state: web fallback is available to the RAG engine.'
        : 'Effective web-search state: web fallback is blocked for this runtime.',
    },
  ];
}

function environmentItem(apiMode: ApiMode): StatusItem {
  if (apiMode === 'mock') {
    return {
      icon: FlaskConical,
      tone: 'mock',
      label: 'Mock environment',
      value: 'Fixtures',
      explanation:
        'Responses come from typed mock fixtures; the Python backend is not connected.',
    };
  }

  return {
    icon: Server,
    tone: 'ok',
    label: 'Data source',
    value: 'Live API',
    explanation: 'Responses come from the local Office Agent API via POST /api/agent/run.',
  };
}

function unavailableItem(timedOut: boolean): StatusItem {
  return {
    icon: Unplug,
    tone: 'warn',
    label: 'Office Agent API',
    value: timedOut ? 'Timed out' : 'Unreachable',
    explanation: timedOut
      ? 'The API accepted the connection but did not answer the health check in time, so no runtime status is available. It may be starting up or stalled. Use Refresh to re-check, or run the frontend with VITE_API_MODE=mock to use the typed mock fixtures instead.'
      : `The API did not respond, so no runtime status is available. Start it with: ${START_API_COMMAND} — or run the frontend with VITE_API_MODE=mock to use the typed mock fixtures instead.`,
  };
}

/**
 * One desktop runtime status chip. It is informational, with its explanation
 * available both as a tooltip and as screen-reader text.
 */
function StatusChip({ icon: Icon, label, value, tone, explanation }: StatusItem) {
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

function RefreshButton({
  phase,
  isRefreshing,
  onRefresh,
  mobile = false,
}: Pick<StatusBannerProps, 'phase' | 'isRefreshing' | 'onRefresh'> & { mobile?: boolean }) {
  return (
    <button
      type="button"
      className={mobile ? 'status__refresh status__refresh--mobile' : 'status__refresh'}
      onClick={onRefresh}
      disabled={isRefreshing || phase === 'loading'}
      aria-label="Refresh runtime status"
      title="Re-check the Office Agent API and its runtime flags"
    >
      <span
        className={isRefreshing ? 'status__refresh-icon is-spinning' : 'status__refresh-icon'}
        aria-hidden="true"
      >
        <RefreshCw size={13} strokeWidth={2.25} />
      </span>
      <span className="status__refresh-text">{isRefreshing ? 'Checking…' : 'Refresh'}</span>
    </button>
  );
}

function DesktopStatusBanner({
  health,
  phase,
  timedOut,
  apiMode,
  isRefreshing,
  onRefresh,
}: StatusBannerProps) {
  const environment = environmentItem(apiMode);

  return (
    <div className="status-bar">
      <ul className="status" aria-label="Runtime status" aria-live="polite">
        <li className="status__policy" title={SERVER_POLICY_NOTE}>
          <span className="status__policy-text" aria-hidden="true">
            Server policy
          </span>
          <span className="sr-only">{SERVER_POLICY_NOTE}</span>
        </li>

        {phase === 'loading' ? (
          <li className="status-chip status-chip--slate">
            <span className="status-chip__label">Runtime status</span>
            <span className="status-chip__sep" aria-hidden="true">
              ·
            </span>
            <span className="status-chip__value">Loading…</span>
          </li>
        ) : null}

        {phase === 'unreachable' ? <StatusChip {...unavailableItem(timedOut)} /> : null}

        {phase === 'ready' && health
          ? policyItems(health).map((item) => <StatusChip key={item.label} {...item} />)
          : null}

        <li className="status__divider" aria-hidden="true" />
        <StatusChip {...environment} />
      </ul>

      <RefreshButton phase={phase} isRefreshing={isRefreshing} onRefresh={onRefresh} />
    </div>
  );
}

function MobileStatusRow({ item, label }: { item: StatusItem; label?: string }) {
  return (
    <div className="status-mobile__row" title={item.explanation}>
      <dt>{label ?? item.label}</dt>
      <dd>
        {item.value}
        <span className="sr-only">. {item.explanation}</span>
      </dd>
    </div>
  );
}

function formatLastChecked(lastCheckedAt: number | null, now: number) {
  if (lastCheckedAt === null) {
    return 'just now';
  }

  const minutes = Math.max(0, Math.floor((now - lastCheckedAt) / 60_000));
  if (minutes < 1) {
    return 'just now';
  }
  if (minutes === 1) {
    return '1 minute ago';
  }
  return `${minutes} minutes ago`;
}

/**
 * Compact mobile summary and its normal-flow policy disclosure. The summary is
 * presentation-only: all wording is derived from the same health and data-mode
 * values as the desktop chips.
 */
function MobileStatusBanner({
  health,
  phase,
  timedOut,
  apiMode,
  isRefreshing,
  onRefresh,
}: StatusBannerProps) {
  const [open, setOpen] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const panelId = useId();
  const toggleId = useId();
  const environment = environmentItem(apiMode);

  useEffect(() => {
    if (phase === 'loading' || isRefreshing) {
      return;
    }
    const checkedAt = Date.now();
    setLastCheckedAt(checkedAt);
    setNow(checkedAt);
  }, [health, isRefreshing, phase, timedOut]);

  useEffect(() => {
    if (lastCheckedAt === null) {
      return undefined;
    }
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, [lastCheckedAt]);

  let summary = 'Checking';
  let summaryState = 'checking';
  let SummaryIcon: LucideIcon = Server;
  let statusDescription =
    apiMode === 'mock'
      ? 'Server policy status checking. Mock runtime status checking.'
      : 'Server policy status checking. API status checking.';

  if (phase === 'unreachable') {
    summary = 'API unavailable';
    summaryState = 'unavailable';
    SummaryIcon = Unplug;
    statusDescription = 'Server policy unavailable. API unavailable.';
  } else if (phase === 'ready' && health?.offline_mode) {
    summary = 'Offline';
    summaryState = 'offline';
    SummaryIcon = WifiOff;
    statusDescription =
      `Server policy: ${health.privacy_mode ? 'Strict' : 'Standard'}. ` +
      `Offline restrictions enabled. ${apiMode === 'mock' ? 'Mock runtime available.' : 'API online.'}`;
  } else if (phase === 'ready' && health?.privacy_mode) {
    summary = 'Strict';
    summaryState = 'strict';
    SummaryIcon = Shield;
    statusDescription =
      `Server policy: Strict. ${apiMode === 'mock' ? 'Mock runtime available.' : 'API online.'}`;
  } else if (phase === 'ready' && health) {
    summary = 'Standard';
    summaryState = 'standard';
    SummaryIcon = Shield;
    statusDescription =
      `Server policy: Standard. ${apiMode === 'mock' ? 'Mock runtime available.' : 'API online.'}`;
  }

  const items = phase === 'ready' && health ? policyItems(health) : [];
  const lastChecked =
    phase === 'loading' || isRefreshing
      ? 'checking…'
      : formatLastChecked(lastCheckedAt, now);

  return (
    <div className="status-mobile">
      <button
        id={toggleId}
        type="button"
        className="status-mobile__toggle"
        data-state={summaryState}
        aria-label={`${statusDescription} ${open ? 'Collapse details.' : 'Expand details.'}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="status-mobile__summary-icon" aria-hidden="true">
          <SummaryIcon size={14} strokeWidth={2.25} />
        </span>
        <span className="status-mobile__summary">{summary}</span>
        <ChevronDown
          className={open ? 'status-mobile__chevron is-open' : 'status-mobile__chevron'}
          size={15}
          strokeWidth={2.25}
          aria-hidden="true"
        />
      </button>
      <span className="sr-only" aria-live="polite">
        {statusDescription}
      </span>

      <section
        id={panelId}
        className="status-mobile__panel"
        aria-labelledby={toggleId}
        hidden={!open}
      >
        <div className="status-mobile__panel-head">
          <h2>Server policy</h2>
          <p>{SERVER_POLICY_NOTE}</p>
        </div>

        <dl className="status-mobile__details">
          {phase === 'loading' ? (
            <MobileStatusRow
              item={{
                icon: Server,
                tone: 'slate',
                label: 'Runtime status',
                value: 'Loading…',
                explanation: 'The first Office Agent API health check is in progress.',
              }}
            />
          ) : null}
          {phase === 'unreachable' ? (
            <MobileStatusRow item={unavailableItem(timedOut)} />
          ) : null}
          {items.map((item) => (
            <MobileStatusRow key={item.label} item={item} />
          ))}
          <MobileStatusRow item={environment} label="Data source" />
        </dl>

        <div className="status-mobile__footer">
          <span>
            Last checked: <span>{lastChecked}</span>
          </span>
          <RefreshButton
            phase={phase}
            isRefreshing={isRefreshing}
            onRefresh={onRefresh}
            mobile
          />
        </div>
      </section>
    </div>
  );
}

/**
 * Runtime status in the product header. Desktop retains the complete chip strip;
 * mobile uses one compact summary with an inline details panel.
 */
export function StatusBanner(props: StatusBannerProps) {
  const isMobile = useMediaQuery(MOBILE_LAYOUT_QUERY);
  return isMobile ? <MobileStatusBanner {...props} /> : <DesktopStatusBanner {...props} />;
}
