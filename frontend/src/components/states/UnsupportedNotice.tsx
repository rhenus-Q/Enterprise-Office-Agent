/**
 * Unsupported request: the router matched no capability.
 *
 * This is a normal, successful outcome (empty stop reason), so it is framed as
 * guidance rather than an error. The engine's own explanation is rendered below
 * this notice as the result content.
 */
export function UnsupportedNotice() {
  return (
    <div className="notice notice--unsupported" role="status">
      <p className="notice__title">No matching capability</p>
      <p className="notice__body">
        The request did not route to any of the seven capabilities. The Office Agent&apos;s reply
        is shown below.
      </p>
    </div>
  );
}
