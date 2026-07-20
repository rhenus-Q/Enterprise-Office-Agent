import type { KnowledgeObservability } from '../types/api';
import { formatDurationMs } from '../lib/status';

interface KnowledgeTimelineProps {
  observability: KnowledgeObservability;
}

/**
 * The Knowledge Q&A execution timeline.
 *
 * Every value here is genuine `enterprise_rag` AnswerResult metadata carried
 * through the adapter — nothing is derived, estimated, or invented. Bars are
 * scaled against the slowest step so short steps stay visible; the numbers
 * themselves are the raw per-node timings.
 *
 * Per-run web-search and fallback settings live in the panel's "Privacy and
 * modes" card, so each value appears exactly once.
 */
export function KnowledgeTimeline({ observability }: KnowledgeTimelineProps) {
  const timings = observability.node_timings_ms;
  const slowestMs = timings.reduce((max, timing) => Math.max(max, timing.duration_ms), 0);

  return (
    <div className="timeline">
      <h4 className="timeline__title">Graph execution</h4>

      <ol className="timeline__list">
        {timings.map((timing, index) => (
          <li key={`${timing.node}-${index}`} className="timeline__step">
            <div className="timeline__row">
              <span className="timeline__node">
                <span className="timeline__index">{index + 1}</span>
                <code>{timing.node}</code>
              </span>
              <span className="timeline__duration">{formatDurationMs(timing.duration_ms)}</span>
            </div>
            <div className="timeline__bar">
              <span
                className="timeline__bar-fill"
                style={{
                  width: slowestMs > 0 ? `${(timing.duration_ms / slowestMs) * 100}%` : '0%',
                }}
              />
            </div>
          </li>
        ))}
      </ol>

      <dl className="fields">
        <div className="field">
          <dt>Total graph duration</dt>
          <dd>{formatDurationMs(observability.total_duration_ms)}</dd>
        </div>
        <div className="field">
          <dt>Retries</dt>
          <dd>{observability.retries}</dd>
        </div>
        <div className="field">
          <dt>Tracked LLM calls</dt>
          <dd>
            {observability.tracked_llm_calls}
            <span className="field__note">budgeted counter, not total LLM usage</span>
          </dd>
        </div>
        <div className="field">
          <dt>Web searches</dt>
          <dd>{observability.web_search_count}</dd>
        </div>
        <div className="field">
          <dt>Web results graded</dt>
          <dd>{observability.web_result_grading_count}</dd>
        </div>
      </dl>

      {observability.caveat ? <p className="timeline__caveat">{observability.caveat}</p> : null}
    </div>
  );
}
