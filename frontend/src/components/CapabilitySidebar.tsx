import { CAPABILITIES } from '../data/capabilities';
import type { CapabilityIntent } from '../types/api';

interface CapabilitySidebarProps {
  /** The capability in focus. After a run this is whatever the router chose. */
  selectedIntent: CapabilityIntent | null;
  /**
   * Reports the clicked capability. The rail does not decide between focusing
   * and dismissing — that depends on the panel's browsing mode, which the
   * workspace owns.
   */
  onSelectCapability: (intent: CapabilityIntent) => void;
}

/**
 * The compact capability rail.
 *
 * Deliberately low-density: an icon and a name. Descriptions and example prompts
 * live in the main workspace, shown contextually for the selected capability, so
 * the rail stays scannable.
 *
 * Each capability carries its own restrained accent, and the active item is
 * marked four ways — accent rail, background tint, saturated icon, and stronger
 * text — so selection never depends on colour alone.
 *
 * Selecting a capability filters the examples shown in the workspace; it does not
 * choose a tool. Routing stays the deterministic Python router's job.
 *
 * Each item follows the WAI pattern of a heading wrapping its control, so the
 * capability is both a landmark heading and an operable button.
 */
export function CapabilitySidebar({ selectedIntent, onSelectCapability }: CapabilitySidebarProps) {
  return (
    <div className="nav">
      <h2 className="nav__section-title">Capabilities</h2>

      <ul className="nav__list">
        {CAPABILITIES.map((capability) => {
          const isActive = capability.intent === selectedIntent;
          const Icon = capability.icon;

          return (
            <li key={capability.intent} className={`nav__row cap--${capability.intent}`}>
              <h3 className="nav__item-heading">
                <button
                  type="button"
                  className={isActive ? 'nav__item is-active' : 'nav__item'}
                  aria-pressed={isActive}
                  onClick={() => onSelectCapability(capability.intent)}
                >
                  <span className="nav__icon" aria-hidden="true">
                    <Icon size={15} strokeWidth={2} />
                  </span>
                  <span className="nav__label">{capability.label}</span>
                </button>
              </h3>
            </li>
          );
        })}
      </ul>

      <p className="nav__footer">Requests are routed automatically — you never pick the tool.</p>
    </div>
  );
}
