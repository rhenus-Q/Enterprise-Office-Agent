import { Activity, Gauge, Route, ShieldHalf } from 'lucide-react';

interface ExecutionPreviewProps {
  phase: 'idle' | 'loading' | 'error';
}

const PHASE_NOTE: Record<ExecutionPreviewProps['phase'], string> = {
  idle: 'Run a request to see its intent, tool, duration, and execution mode.',
  loading: 'Waiting for the run to finish…',
  error: 'The request failed before any execution details were returned.',
};

/**
 * The execution panel before a run.
 *
 * Shows the same four groups the real panel uses, so the structure is legible
 * before anything happens and the layout does not jump when a result arrives.
 *
 * Every value is an explicit placeholder — no runtime data is invented, and no
 * RAG timeline is implied for capabilities that do not expose one.
 */
export function ExecutionPreview({ phase }: ExecutionPreviewProps) {
  const isWaiting = phase === 'loading';

  return (
    <div className={isWaiting ? 'panel panel--waiting' : 'panel'}>
      <h2 className="panel__title">Execution details</h2>
      <p className="panel__status">{PHASE_NOTE[phase]}</p>

      <section className="card card--preview card--routing">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <Route size={13} strokeWidth={2.25} />
          </span>
          Routing
        </h3>
        <dl className="fields">
          <div className="field">
            <dt>Intent</dt>
            <dd className="placeholder">—</dd>
          </div>
          <div className="field">
            <dt>Tool</dt>
            <dd className="placeholder">—</dd>
          </div>
        </dl>
      </section>

      <section className="card card--preview card--runtime">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <Gauge size={13} strokeWidth={2.25} />
          </span>
          Runtime
        </h3>
        <dl className="fields">
          <div className="field">
            <dt>Duration</dt>
            <dd className="placeholder">—</dd>
          </div>
          <div className="field">
            <dt>Execution mode</dt>
            <dd className="placeholder">—</dd>
          </div>
        </dl>
      </section>

      <section className="card card--preview card--privacy">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <ShieldHalf size={13} strokeWidth={2.25} />
          </span>
          Privacy and modes
        </h3>
        <p className="empty-note">
          Per-run settings are reported for Knowledge Q&amp;A, the one capability that reaches an
          external service.
        </p>
      </section>

      <section className="card card--preview card--observability">
        <h3 className="card__title">
          <span className="card__icon" aria-hidden="true">
            <Activity size={13} strokeWidth={2.25} />
          </span>
          Observability
        </h3>
        <p className="empty-note">
          Graph steps, timings, and counters are reported by the RAG engine only.
        </p>
      </section>
    </div>
  );
}
