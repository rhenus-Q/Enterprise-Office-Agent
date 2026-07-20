import { CornerDownLeft, Sparkles } from 'lucide-react';
import type { FormEvent, KeyboardEvent } from 'react';

import { MAX_REQUEST_TEXT_LENGTH } from '../types/api';

interface RequestComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (text: string) => void;
  isLoading: boolean;
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
export function RequestComposer({ value, onChange, onSubmit, isLoading }: RequestComposerProps) {
  const trimmed = value.trim();
  const canSubmit = trimmed.length > 0 && !isLoading;

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
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />

      <div className="composer__footer">
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
        <button type="submit" className="button button--primary" disabled={!canSubmit}>
          {isLoading ? 'Running…' : 'Run request'}
        </button>
      </div>
    </form>
  );
}
