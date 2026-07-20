/** Loading state while a request is in flight. */
export function LoadingState() {
  return (
    <div className="state">
      <h2 className="state__title">
        <span className="spinner" aria-hidden="true" />
        Running request…
      </h2>
      <p className="state__body">Routing the request and running the selected capability.</p>
    </div>
  );
}
