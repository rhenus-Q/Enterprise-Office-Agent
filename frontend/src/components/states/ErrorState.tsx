interface ErrorStateProps {
  errorType: string;
  onRetry: () => void;
}

/**
 * Error state: the request failed before any response was returned.
 *
 * Only the error *type* is displayed, matching the adapter's 500 contract —
 * exception messages may carry file paths or secrets.
 */
export function ErrorState({ errorType, onRetry }: ErrorStateProps) {
  return (
    <div className="state notice notice--error" role="alert">
      <h2 className="state__title">Request failed</h2>
      <p className="state__body">
        The request did not complete. Error type: <code>{errorType}</code>
      </p>
      <button type="button" className="button" onClick={onRetry}>
        Retry request
      </button>
    </div>
  );
}
