interface StoppedStateProps {
  /** The request that was abandoned, echoed verbatim. */
  requestText: string;
  /** Runs the same request again. */
  onRetry: () => void;
}

/**
 * Shown when a new request was stopped before any result arrived.
 *
 * The wording is deliberately narrow. Stopping aborts the browser's `fetch`; the
 * adapter's run handler is synchronous, so a request already accepted by the
 * server finishes there regardless. Calling this "cancelled" would imply the
 * engine was interrupted, which is not something this frontend can do.
 */
export function StoppedState({ requestText, onRetry }: StoppedStateProps) {
  return (
    <div className="state state--stopped">
      <h2 className="state__title">Stopped waiting</h2>
      <p className="state__request">
        <span className="sr-only">Request: </span>
        {requestText}
      </p>
      <p className="state__body">
        The browser stopped waiting for this request, so no result was received. Work that had
        already started on the server is not interrupted and will finish there.
      </p>
      <button type="button" className="button" onClick={onRetry}>
        Run it again
      </button>
    </div>
  );
}
