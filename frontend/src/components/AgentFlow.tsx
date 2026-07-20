import { ArrowRight, BadgeCheck, GitBranch, MessageSquare, Wrench } from 'lucide-react';

interface FlowStep {
  id: string;
  label: string;
  caption: string;
  icon: typeof MessageSquare;
}

const STEPS: FlowStep[] = [
  { id: 'request', label: 'Request', caption: 'Plain language', icon: MessageSquare },
  { id: 'router', label: 'Intent router', caption: 'Deterministic', icon: GitBranch },
  { id: 'tool', label: 'Office tool / Enterprise RAG', caption: 'One of seven', icon: Wrench },
  { id: 'result', label: 'Verified result', caption: 'With provenance', icon: BadgeCheck },
];

/**
 * A static diagram of how a request travels through the agent.
 *
 * Pure CSS and icons — no image asset, and no runtime data of any kind. It
 * explains the pipeline before anything has run; the real per-run values only
 * ever come from an actual response.
 *
 * Every node is visually independent: hover feedback is a local CSS `:hover`
 * rule on the node itself, with no chain-level behavior. The component holds no
 * hover state, no timers, and no pointer handlers, so nothing in JavaScript can
 * link one node to another or animate the container. Arrows are inert.
 */
export function AgentFlow() {
  return (
    <ol className="flow" aria-label="How a request is processed">
      {STEPS.map((step, index) => {
        const Icon = step.icon;

        return (
          <li key={step.id} className={`flow__step flow__step--${step.id}`}>
            <div className="flow__node">
              <span className="flow__icon" aria-hidden="true">
                <Icon size={16} strokeWidth={2} />
              </span>
              <span className="flow__label">{step.label}</span>
              <span className="flow__caption">{step.caption}</span>
            </div>
            {index < STEPS.length - 1 ? (
              <span className="flow__arrow" aria-hidden="true">
                <ArrowRight size={14} strokeWidth={2} />
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
