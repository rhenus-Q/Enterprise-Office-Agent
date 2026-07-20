import {
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  MessageSquare,
  RefreshCw,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { capabilityFor } from '../../data/capabilities';
import { RUN_STATUS_LABELS } from '../../lib/status';
import type { AgentRunResponse, Intent, RunStatus } from '../../types/api';

interface ResultCardProps {
  response: AgentRunResponse;
  status: RunStatus;
  /** Whether the transcript surface is shown. The header is always visible. */
  expanded: boolean;
  onToggleExpanded: () => void;
  /** Re-runs the request that produced this result, via the shared run machinery. */
  onRetry: () => void;
  /**
   * True while *this* result is being re-run.
   *
   * The card is only mounted during the loading phase when the run is a retry of
   * the result it shows (see `useAgentRun`'s `previous`), so this single flag
   * covers both "a request is in flight" — actions are locked — and "the run
   * targets me" — the refreshing treatment applies. A new request unmounts the
   * card instead, which is why there is no longer a separate retry flag to
   * disagree with.
   */
  isRefreshing: boolean;
  /**
   * Completed-run counter. Used purely as a remount key for the transcript so
   * the entry animation replays on every finished run — including when the
   * response, its content, and its run_id are byte-identical to the last one.
   */
  revision: number;
}

/** How long a transient copy/download confirmation stays on screen. */
const FEEDBACK_DURATION_MS = 2000;
/** How long the "Updated" success chip stays on screen after a retry. */
const UPDATED_DURATION_MS = 1500;
/**
 * Minimum time the refreshing state stays visible.
 *
 * Purely a UI floor: a mock response can return in single-digit milliseconds,
 * which would flash the whole feedback cycle past before it can be read. It
 * delays only the visual transition — never the request, and never any value
 * reported in Execution Details.
 */
const MIN_REFRESH_VISIBLE_MS = 500;

type ContentTypography = 'prose' | 'mono';
/** How the transcript should animate when it next mounts. */
type EntryKind = 'new' | 'updated';

/**
 * Typography is chosen from `response.intent` alone — never by inspecting the
 * content. Most capabilities emit space-aligned columns (ticket ids, calendar
 * times, briefing labels) that only survive in a monospace font; Knowledge Q&A
 * emits prose, which reads far better in the UI sans stack.
 *
 * `unknown` is the unsupported-intent sentence, so it is prose too. Extend this
 * map when a capability is added — the exhaustive Record makes that a type error
 * rather than a silent default.
 */
const CONTENT_TYPOGRAPHY: Record<Intent, ContentTypography> = {
  knowledge_qa: 'prose',
  email_summary: 'mono',
  calendar_lookup: 'mono',
  ticket_assistant: 'mono',
  daily_briefing: 'mono',
  meeting_agent: 'mono',
  workflow_approval: 'mono',
  unknown: 'prose',
};

/**
 * Filename-safe form of an intent, so a download can never build a stray path.
 * Underscores are kept, since intents are snake_case and `_` is safe in a
 * filename; anything else (separators, dots, spaces) collapses to a hyphen.
 */
function safeFileSlug(intent: string): string {
  const slug = intent.toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return slug || 'result';
}

/**
 * One result, framed as a deliberate transcript surface.
 *
 * `response.content` is authoritative engine output: it is rendered verbatim in a
 * `<pre>`, never parsed, never reinterpreted, and never passed through a markdown
 * renderer. The header, typography, and actions frame that text without touching
 * it.
 */
export function ResultCard({
  response,
  status,
  expanded,
  onToggleExpanded,
  onRetry,
  isRefreshing,
  revision,
}: ResultCardProps) {
  const [feedback, setFeedback] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [justUpdated, setJustUpdated] = useState(false);
  const [view, setView] = useState<{ revision: number; entry: EntryKind }>({
    revision,
    entry: 'new',
  });

  const feedbackTimerRef = useRef<number | null>(null);
  const holdTimerRef = useRef<number | null>(null);
  const updatedTimerRef = useRef<number | null>(null);
  const startedAtRef = useRef(0);
  const wasRefreshingRef = useRef(false);
  // A refresh cycle owns the transcript transition until it finishes.
  const holdingRef = useRef(false);
  const revisionRef = useRef(revision);

  revisionRef.current = revision;

  useEffect(() => {
    return () => {
      for (const timer of [feedbackTimerRef, holdTimerRef, updatedTimerRef]) {
        if (timer.current !== null) {
          window.clearTimeout(timer.current);
        }
      }
    };
  }, []);

  function flash(message: string, duration = FEEDBACK_DURATION_MS) {
    if (feedbackTimerRef.current !== null) {
      window.clearTimeout(feedbackTimerRef.current);
    }

    setFeedback(message);
    feedbackTimerRef.current = window.setTimeout(() => {
      setFeedback('');
      feedbackTimerRef.current = null;
    }, duration);
  }

  // Drives the refreshing visual, including the minimum-visible floor. Every
  // cycle this effect sees is a retry of this result — a new request unmounts
  // the card rather than refreshing it — so there is no non-retry branch.
  useEffect(() => {
    function finish() {
      holdTimerRef.current = null;
      holdingRef.current = false;
      setRefreshing(false);
      setView({ revision: revisionRef.current, entry: 'updated' });

      // A finished run is otherwise invisible when the response is identical,
      // so completion is confirmed explicitly rather than by content changing.
      setJustUpdated(true);
      if (updatedTimerRef.current !== null) {
        window.clearTimeout(updatedTimerRef.current);
      }
      updatedTimerRef.current = window.setTimeout(() => {
        setJustUpdated(false);
        updatedTimerRef.current = null;
      }, UPDATED_DURATION_MS);
    }

    if (isRefreshing && !wasRefreshingRef.current) {
      startedAtRef.current = Date.now();
      holdingRef.current = true;
      setJustUpdated(false);
      setRefreshing(true);
    } else if (!isRefreshing && wasRefreshingRef.current) {
      const elapsed = Date.now() - startedAtRef.current;
      const remaining = Math.max(0, MIN_REFRESH_VISIBLE_MS - elapsed);
      holdTimerRef.current = window.setTimeout(finish, remaining);
    }

    wasRefreshingRef.current = isRefreshing;
  }, [isRefreshing]);

  // A revision that arrives outside a refresh cycle is simply a new result.
  useEffect(() => {
    if (holdingRef.current) {
      return;
    }
    setView((current) => (current.revision === revision ? current : { revision, entry: 'new' }));
  }, [revision]);

  async function handleCopy() {
    // Exactly the engine output — no labels, metadata, or sources appended.
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard unavailable');
      }
      await navigator.clipboard.writeText(response.content);
      flash('Copied');
    } catch {
      flash('Copy failed');
    }
  }

  function handleDownload() {
    // Local download only: a UTF-8 text blob built in the browser, never uploaded.
    let url: string | null = null;

    try {
      const blob = new Blob([response.content], { type: 'text/plain;charset=utf-8' });
      url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = `office-agent-${safeFileSlug(response.intent)}-result.txt`;
      link.rel = 'noopener';
      link.click();

      flash('Downloaded');
    } catch {
      flash('Download failed');
    } finally {
      if (url !== null) {
        URL.revokeObjectURL(url);
      }
    }
  }

  const capability = capabilityFor(
    response.intent === 'unknown' ? 'knowledge_qa' : response.intent,
  );
  const isUnknown = response.intent === 'unknown';
  const Icon = isUnknown ? MessageSquare : (capability?.icon ?? MessageSquare);
  const label = isUnknown ? 'Unsupported request' : (capability?.label ?? response.intent);
  const typography = CONTENT_TYPOGRAPHY[response.intent];
  const ToggleIcon = expanded ? ChevronUp : ChevronDown;
  const busy = isRefreshing || refreshing;

  return (
    <article className={`result cap--${response.intent}`}>
      <header className="result__header">
        <div className="result__identity">
          <span className="result__icon" aria-hidden="true">
            <Icon size={15} strokeWidth={2} />
          </span>
          <h3 className="result__label">{label}</h3>
          {/* The pill describes the outcome of the run that produced this
              transcript. While a retry is in flight that outcome is being
              superseded, so it is withheld rather than left asserting a stale
              verdict; the live region says "Refreshing…" in its place. */}
          {refreshing ? null : (
            <span className={`pill pill--${status}`}>{RUN_STATUS_LABELS[status]}</span>
          )}
        </div>

        <div className="result__actions">
          {/* One live region for every transient state, so each is announced. */}
          <span className="result__feedback" role="status" aria-live="polite">
            {justUpdated ? (
              <span className="result__updated">
                <Check size={12} strokeWidth={2.5} aria-hidden="true" />
                Updated
              </span>
            ) : refreshing ? (
              'Refreshing…'
            ) : (
              feedback
            )}
          </span>

          <button
            type="button"
            className="action-button"
            aria-label="Copy result"
            title="Copy result"
            disabled={busy}
            onClick={handleCopy}
          >
            <Copy size={14} strokeWidth={2} aria-hidden="true" />
          </button>

          <button
            type="button"
            className="action-button"
            aria-label="Download result"
            title="Download result"
            disabled={busy}
            onClick={handleDownload}
          >
            <Download size={14} strokeWidth={2} aria-hidden="true" />
          </button>

          <button
            type="button"
            className={busy ? 'action-button is-busy' : 'action-button'}
            aria-label="Retry request"
            title="Retry request"
            disabled={busy}
            onClick={onRetry}
          >
            <RefreshCw size={14} strokeWidth={2} aria-hidden="true" />
          </button>

          <span className="result__divider" aria-hidden="true" />

          <button
            type="button"
            className="action-button"
            aria-label={expanded ? 'Collapse result' : 'Expand result'}
            title={expanded ? 'Collapse result' : 'Expand result'}
            aria-expanded={expanded}
            onClick={onToggleExpanded}
          >
            <ToggleIcon size={15} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
      </header>

      {expanded ? (
        // Keyed by the run counter: a completed run remounts this element, which
        // restarts the entry animation even for a byte-identical response.
        <div
          key={view.revision}
          className={refreshing ? 'result__surface is-refreshing' : 'result__surface'}
          data-revision={view.revision}
          data-entry={view.entry}
        >
          {refreshing ? <span className="result__progress" aria-hidden="true" /> : null}
          <pre
            className={`result__content result__content--${typography}`}
            data-typography={typography}
          >
            {response.content}
          </pre>
        </div>
      ) : null}
    </article>
  );
}
