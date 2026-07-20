import type { StopReason } from '../../types/api';

interface DegradedNoticeProps {
  stopReason: StopReason;
  caveat: string;
}

/**
 * Degraded run: a result was produced, but the engine recorded a stop reason.
 *
 * The stop reason is shown verbatim as a machine-readable code, and any caveat
 * text comes from the engine itself. The UI never writes its own explanation of
 * a stop reason, so the two can never drift apart.
 */
export function DegradedNotice({ stopReason, caveat }: DegradedNoticeProps) {
  return (
    <div className="notice notice--degraded" role="status">
      <p className="notice__title">
        Degraded run — stop reason: <code>{stopReason}</code>
      </p>
      {caveat ? <p className="notice__body">{caveat}</p> : null}
    </div>
  );
}
