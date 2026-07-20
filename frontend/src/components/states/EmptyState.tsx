import { AgentFlow } from '../AgentFlow';

/** Idle state: nothing has been run yet. */
export function EmptyState() {
  return (
    <div className="state state--empty">
      <h2 className="state__title">No request yet</h2>
      <p className="state__body">
        Ask a question or describe a task. The Office Agent routes it deterministically to one of
        seven capabilities, then reports exactly how it ran.
      </p>

      <AgentFlow />

      <p className="state__hint">
        Execution details — routing, runtime, privacy, and observability — appear in the right
        panel once a request runs.
      </p>
    </div>
  );
}
