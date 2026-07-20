import { CornerDownLeft, Sparkles, Square } from 'lucide-react';
import type { FormEvent, KeyboardEvent } from 'react';

import { MAX_REQUEST_TEXT_LENGTH } from '../types/api';

interface RequestComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string) => void;
  isLoading: boolean;
  /**
   * Whether this composer owns the in-flight run.
   *
   * False during a retry: that run is owned by the result card it is
   * refreshing, and its Stop control lives there. Exactly one Stop button is on
   * screen at a time, next to the thing it will stop.
   */
  canStop: boolean;
  /** Stops the browser waiting for the in-flight run. */
  onStop: () => void;
  /**
   * True immediately after this composer's Stop was pressed.
   *
   * Stop and Run deliberately share one position, which means the click that
   * stops a run lands on an armed Run button a frame later. While disarmed the
   * submit is inert, so a second click — the other half of a double-click, or an
   * impatient "did that register?" — cannot restart the request.
   */
  disarmed: boolean;
  /** Reports a deliberate new gesture, which re-arms the submit. */
  onRearm: () => void;
}

/**
 * The one universal composer for all seven capabilities — there is no per-intent
 * form, because intent selection is the router's job, not the user's.
 *
 * The visible heading carries the visual hierarchy while the form label stays in
 * the accessibility tree (visually hidden), so the field keeps its accessible
 * name. The `maxLength` mirrors the API's exact `max_length=4000` bound, so the
 * UI cannot submit input the adapter would reject with a 422.
 */
export function RequestComposer({
  value,
  onChange,
  onSubmit,
  isLoading,
  canStop,
  onStop,
  disarmed,
  onRearm,
}: RequestComposerProps) {
  const trimmed = value.trim();
  const canSubmit = trimmed.length > 0 && !isLoading && !disarmed;

  function submit() {
    if (canSubmit) {
      onSubmit(trimmed);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter submits; Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer__head">
        <span className="composer__badge" aria-hidden="true">
          <Sparkles size={14} strokeWidth={2.25} />
        </span>
        <div>
          <h2 className="composer__title">Ask the Office Agent</h2>
          <p className="composer__lede">
            One composer for all seven capabilities — routing happens automatically.
          </p>
        </div>
      </div>

      <label className="sr-only" htmlFor="request-text">
        Request
      </label>
      <textarea
        id="request-text"
        className="composer__input"
        name="request-text"
        rows={3}
        value={value}
        maxLength={MAX_REQUEST_TEXT_LENGTH}
        placeholder="Ask anything — for example, summarize my unread emails"
        // Editing or reaching for the field is unambiguous new intent.
        onChange={(event) => {
          onRearm();
          onChange(event.target.value);
        }}
        onFocus={onRearm}
        onKeyDown={handleKeyDown}
      />

      {/* Moving the pointer away from the action area, or releasing the key
          that pressed Stop, both mean the stopping gesture is over — so the
          guard lifts on a real gesture rather than on a timer. The handlers sit
          on the container because a disabled button dispatches no pointer
          events of its own. */}
      <div className="composer__footer" onPointerLeave={onRearm} onKeyUp={onRearm}>
        <p className="composer__hint">
          <kbd className="composer__kbd">
            <CornerDownLeft size={11} strokeWidth={2.25} aria-hidden="true" />
            Enter
          </kbd>
          <span>to send</span>
          <kbd className="composer__kbd">Shift + Enter</kbd>
          <span>for a new line</span>
          <span className="composer__count">
            {value.length} / {MAX_REQUEST_TEXT_LENGTH}
          </span>
        </p>
        {/* Start and stop share one position, so the control you reach for is
            always the one that applies. The label is deliberately "Stop
            waiting": it ends the browser's wait, and does not terminate work
            already running on the server. */}
        {isLoading && canStop ? (
          <button
            type="button"
            className="button button--stop"
            aria-label="Stop waiting for this request"
            title="Stop waiting — work already started on the server will still finish"
            onClick={onStop}
          >
            <Square size={11} strokeWidth={3} fill="currentColor" aria-hidden="true" />
            Stop
          </button>
        ) : (
          <button type="submit" className="button button--primary" disabled={!canSubmit}>
            Run request
          </button>
        )}
      </div>
    </form>
  );
}
