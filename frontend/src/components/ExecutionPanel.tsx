import { Activity, Gauge, Route, ShieldHalf } from 'lucide-react';

import type { AgentRunResponse, RunOptions, RunStatus } from '../types/api';
import { EXECUTION_MODE_LABELS, RUN_STATUS_LABELS, formatDurationMs } from '../lib/status';
import { KnowledgeTimeline } from './KnowledgeTimeline';
import { RunSettingsSummary } from './RunSettingsSummary';

interface ExecutionPanelProps {
  response: AgentRunResponse;
  status: RunStatus;
  /** The snapshot submitted with this run, if any. */
  requestedSettings?: RunOptions | null;
  /** True when the browser stopped waiting for this run. */
  stopped?: boolean;
}

/**
 * Execution details, grouped into scannable cards: how the request was routed,
 * how it ran, which per-run privacy and fallback settings applied, and what
 * observability the capability actually exposes.
 *
 * Only genuinely available fields are shown. `duration_ms` is labeled
 * adapter-measured and `execution_mode` adapter-derived, because neither is
 * engine telemetry. Capabilities that expose no timeline say so explicitly
 * instead of showing a fabricated one.
 */
export function ExecutionPanel({
  response,
  status,
  requestedSettings = null,
  stopped = false,
}: ExecutionPanelProps) {
  const observability = response.observability;

  return (
    <div className="panel">
      <h2 className="panel__title">Execution details</h2>

      <section className="card card--routing">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <Route size={13} strokeWidth={2.25} />
          </span>
          Routing
        </h3>
        <dl className="fields">
          <div className="field">
            <dt>Status</dt>
            <dd>
              <span className={`pill pill--${status}`}>{RUN_STATUS_LABELS[status]}</span>
            </dd>
          </div>
          <div className="field">
            <dt>Intent</dt>
            <dd>
              <code>{response.intent}</code>
            </dd>
          </div>
          <div className="field">
            <dt>Tool</dt>
            <dd>
              {response.tool ? <code>{response.tool}</code> : <span>— no tool invoked</span>}
            </dd>
          </div>
        </dl>
      </section>

      <section className="card card--runtime">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <Gauge size={13} strokeWidth={2.25} />
          </span>
          Runtime
        </h3>
        <dl className="fields">
          <div className="field">
            <dt>Duration</dt>
            <dd>
              {formatDurationMs(response.duration_ms)}
              <span className="field__note">adapter-measured</span>
            </dd>
          </div>
          <div className="field">
            <dt>Execution mode</dt>
            <dd>
              {EXECUTION_MODE_LABELS[response.execution_mode]}
              <span className="field__note">adapter-derived</span>
            </dd>
          </div>
          <div className="field">
            <dt>Stop reason</dt>
            <dd>{response.stop_reason ? <code>{response.stop_reason}</code> : <span>none</span>}</dd>
          </div>
          <div className="field">
            <dt>Run id</dt>
            <dd>{response.run_id ? <code>{response.run_id}</code> : <span>—</span>}</dd>
          </div>
        </dl>
      </section>

      <section className="card card--privacy">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <ShieldHalf size={13} strokeWidth={2.25} />
          </span>
          Privacy and modes
        </h3>

        <RunSettingsSummary
          requested={requestedSettings}
          settings={response.run_settings}
          stopped={stopped}
        />

        {observability ? (
          <dl className="fields">
            <div className="field">
              <dt>Web search</dt>
              <dd>{observability.web_search_enabled ? 'enabled for this run' : 'disabled'}</dd>
            </div>
            <div className="field">
              <dt>Fallback policy</dt>
              <dd>
                <code>{observability.web_fallback_policy}</code>
              </dd>
            </div>
          </dl>
        ) : (
          <p className="empty-note">
            Per-run privacy and fallback settings are reported only for Knowledge Q&amp;A, which is
            the one capability that reaches an external service.
          </p>
        )}
      </section>

      <section className="card card--observability">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <Activity size={13} strokeWidth={2.25} />
          </span>
          Observability
        </h3>

        {response.sources.length > 0 ? (
          <ul className="sources">
            {response.sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        ) : null}

        {observability ? (
          <KnowledgeTimeline observability={observability} />
        ) : (
          <p className="empty-note">
            This capability does not expose an execution timeline. Only the fields above are
            available.
          </p>
        )}
      </section>
    </div>
  );
}
