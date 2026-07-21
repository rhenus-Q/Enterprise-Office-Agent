import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

import { CAPABILITIES, DEMO_SCENARIOS, FEATURED_PROMPTS, capabilityFor } from '../data/capabilities';
import type { CapabilityIntent } from '../types/api';

/**
 * Which prompts the panel is browsing. Held explicitly rather than inferred from
 * `selectedIntent`: the rail highlight follows the router, while the browsing
 * mode belongs to the user, so a run must never change it.
 */
export type PanelView = 'all' | 'capability';

interface ExamplePromptsProps {
  view: PanelView;
  /** The capability in focus — drives the capability view and the rail highlight. */
  selectedIntent: CapabilityIntent | null;
  /**
   * True once the results area is occupied. The discovery view is tall by
   * design, which is fine on an empty workspace but pushes a result off screen —
   * so with a result present it collapses to compact chips and drops the
   * descriptions and the demo-states section.
   */
  dense: boolean;
  onSelectPrompt: (prompt: string) => void;
  onShowAll: () => void;
}

interface PromptCardProps {
  intent: CapabilityIntent;
  prompt: string;
  description?: string;
  onSelect: (prompt: string) => void;
}

/**
 * One example request.
 *
 * The button's accessible name is always exactly the prompt text, with the
 * supporting description attached via `aria-describedby` rather than folded into
 * the name — so the control announces what it will insert, not a paragraph.
 */
function PromptCard({ intent, prompt, description, onSelect }: PromptCardProps) {
  const capability = capabilityFor(intent);
  const Icon = capability?.icon;
  const descriptionId = description ? `prompt-desc-${intent}-${prompt.length}` : undefined;

  return (
    <li className={`cap--${intent}`}>
      <button
        type="button"
        className={description ? 'prompt-card' : 'prompt-card prompt-card--compact'}
        aria-label={prompt}
        aria-describedby={descriptionId}
        onClick={() => onSelect(prompt)}
      >
        <span className="prompt-card__head">
          {Icon ? (
            <span className="prompt-card__icon" aria-hidden="true">
              <Icon size={15} strokeWidth={2} />
            </span>
          ) : null}
          <span className="prompt-card__title">{prompt}</span>
        </span>
        {description ? (
          <span className="prompt-card__desc" id={descriptionId}>
            {description}
          </span>
        ) : null}
      </button>
    </li>
  );
}

/**
 * Example requests, shown contextually in the workspace rather than stacked in
 * the rail.
 *
 * With no capability selected this is a small curated set of featured prompt
 * cards spanning both the RAG path and the deterministic tools; selecting a
 * capability in the rail narrows it to that capability's own prompts. Every
 * prompt was verified against the deterministic router's keyword order.
 *
 * Selecting a prompt fills the composer instead of submitting, so nothing runs
 * without an explicit action.
 *
 * The panel is a disclosure (default open): collapsing hides only the prompt
 * grid, leaving the header so it is re-expandable in place. This is independent
 * of whether the panel is shown at all — the workspace owns that, driven by the
 * capability selection.
 */
export function ExamplePrompts({
  view,
  selectedIntent,
  dense,
  onSelectPrompt,
  onShowAll,
}: ExamplePromptsProps) {
  // The capability view needs both the mode and a capability to show; anything
  // else falls back to the multi-capability view.
  const selected = view === 'capability' && selectedIntent ? capabilityFor(selectedIntent) : null;

  const [open, setOpen] = useState(true);
  const ChevronIcon = open ? ChevronUp : ChevronDown;
  const toggle = (
    <button
      type="button"
      className="action-button examples__toggle"
      aria-expanded={open}
      aria-label={open ? 'Collapse examples' : 'Expand examples'}
      title={open ? 'Collapse examples' : 'Expand examples'}
      onClick={() => setOpen((prev) => !prev)}
    >
      <ChevronIcon size={15} strokeWidth={2.25} aria-hidden="true" />
    </button>
  );

  if (selected) {
    return (
      <section
        className="examples"
        aria-label="Example requests"
        data-collapsed={open ? 'false' : 'true'}
      >
        <div className="examples__head">
          <h2 className={`examples__title cap--${selected.intent}`}>
            <span className="examples__title-icon" aria-hidden="true">
              <selected.icon size={14} strokeWidth={2.25} />
            </span>
            {selected.label}
          </h2>
          <div className="examples__head-actions">
            <button type="button" className="button button--ghost" onClick={onShowAll}>
              Show all
            </button>
            {toggle}
          </div>
        </div>

        {open ? (
          <>
            <p className="examples__desc">{selected.blurb}</p>

            <ul className="examples__grid examples__grid--compact">
              {selected.examples.map((prompt) => (
                <PromptCard
                  key={prompt}
                  intent={selected.intent}
                  prompt={prompt}
                  onSelect={onSelectPrompt}
                />
              ))}
            </ul>
          </>
        ) : null}
      </section>
    );
  }

  return (
    <section
      className="examples"
      aria-label="Example requests"
      data-collapsed={open ? 'false' : 'true'}
    >
      <div className="examples__head">
        <h2 className="examples__title">Start with an example</h2>
        <div className="examples__head-actions">
          <span className="examples__hint">
            {CAPABILITIES.length} capabilities · select one to see all of its prompts
          </span>
          {toggle}
        </div>
      </div>

      {open ? (
        <>
          <ul className={dense ? 'examples__grid examples__grid--compact' : 'examples__grid'}>
            {FEATURED_PROMPTS.map((featured) => (
              <PromptCard
                key={featured.prompt}
                intent={featured.intent}
                prompt={featured.prompt}
                description={dense ? undefined : featured.description}
                onSelect={onSelectPrompt}
              />
            ))}
          </ul>

          {dense ? null : (
            <div className="examples__demo">
              <h3 className="examples__demo-title">Demo states</h3>
              <ul className="examples__chips">
                {DEMO_SCENARIOS.map((scenario) => (
                  <li key={scenario.id}>
                    <button
                      type="button"
                      className="chip chip--demo"
                      title={scenario.description}
                      onClick={() => onSelectPrompt(scenario.prompt)}
                    >
                      {scenario.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
