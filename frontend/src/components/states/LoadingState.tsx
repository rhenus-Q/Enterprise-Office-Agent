interface LoadingStateProps {
  /**
   * The submitted request, echoed verbatim for continuity while the run is in
   * flight. Never parsed, and never used to guess a capability.
   */
  requestText?: string;
}

/**
 * Loading state for a run whose result has no predecessor on screen — a first
 * run or a new request.
 *
 * Deliberately capability-neutral: no icon, no title, no route. Which tool will
 * answer is decided by the backend router and is unknown until the response
 * arrives, so claiming one here would be a guess.
 */
export function LoadingState({ requestText }: LoadingStateProps) {
  return (
    <div className="state">
      <h2 className="state__title">
        <span className="spinner" aria-hidden="true" />
        Running…
      </h2>
      {requestText ? (
        <p className="state__request">
          <span className="sr-only">Request: </span>
          {requestText}
        </p>
      ) : null}
      <p className="state__body">
        Routing the request — the capability is chosen by the Office Agent router.
      </p>
    </div>
  );
}
