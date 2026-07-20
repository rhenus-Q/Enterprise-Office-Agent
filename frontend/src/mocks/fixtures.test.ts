import { describe, expect, it } from 'vitest';

import {
  ERROR_PROMPT,
  RESPONSES_BY_PROMPT,
  approvalsSuccess,
  briefingSuccess,
  calendarSuccess,
  emailAssistFallback,
  emailSuccess,
  knowledgeSuccess,
  meetingSuccess,
  ticketsSuccess,
  unsupportedResponse,
} from './fixtures';
import { CAPABILITIES, DEMO_SCENARIOS, FEATURED_PROMPTS, capabilityFor } from '../data/capabilities';
import type { AgentRunResponse, CapabilityIntent } from '../types/api';

describe('capability coverage', () => {
  it('ships a fixture for all seven capabilities', () => {
    const byIntent: Record<CapabilityIntent, AgentRunResponse> = {
      knowledge_qa: knowledgeSuccess,
      email_summary: emailSuccess,
      calendar_lookup: calendarSuccess,
      ticket_assistant: ticketsSuccess,
      daily_briefing: briefingSuccess,
      meeting_agent: meetingSuccess,
      workflow_approval: approvalsSuccess,
    };

    expect(CAPABILITIES).toHaveLength(7);
    for (const capability of CAPABILITIES) {
      expect(byIntent[capability.intent].intent).toBe(capability.intent);
    }
  });

  it('resolves every sidebar example prompt (guards against drift)', () => {
    for (const capability of CAPABILITIES) {
      for (const example of capability.examples) {
        const response = RESPONSES_BY_PROMPT[example];
        expect(response, `missing fixture for "${example}"`).toBeDefined();
        expect(response.intent).toBe(capability.intent);
      }
    }
  });

  it('keeps every featured prompt router-safe and resolvable', () => {
    // Featured prompts are a curated subset shown by default. Each one must also
    // be one of its capability's router-verified examples, so the shortlist can
    // never drift into a prompt that would route somewhere else.
    expect(FEATURED_PROMPTS.length).toBeGreaterThan(0);

    for (const featured of FEATURED_PROMPTS) {
      const capability = capabilityFor(featured.intent);
      expect(capability, featured.intent).not.toBeNull();
      expect(capability?.examples).toContain(featured.prompt);

      const response = RESPONSES_BY_PROMPT[featured.prompt];
      expect(response, `missing fixture for "${featured.prompt}"`).toBeDefined();
      expect(response.intent).toBe(featured.intent);
      expect(featured.description.length).toBeGreaterThan(0);
    }
  });

  it('resolves every demo scenario prompt', () => {
    for (const scenario of DEMO_SCENARIOS) {
      if (scenario.prompt === ERROR_PROMPT) {
        expect(RESPONSES_BY_PROMPT[scenario.prompt]).toBeUndefined();
        continue;
      }
      expect(RESPONSES_BY_PROMPT[scenario.prompt], scenario.prompt).toBeDefined();
    }
  });
});

describe('observability honesty', () => {
  it('populates observability only for Knowledge Q&A', () => {
    expect(knowledgeSuccess.observability).not.toBeNull();

    const deterministic = [
      emailSuccess,
      emailAssistFallback,
      calendarSuccess,
      ticketsSuccess,
      briefingSuccess,
      meetingSuccess,
      approvalsSuccess,
      unsupportedResponse,
    ];
    for (const response of deterministic) {
      expect(response.observability, response.intent).toBeNull();
    }
  });

  it('uses strongly typed node timings aligned with node_path', () => {
    const observability = knowledgeSuccess.observability;
    expect(observability).not.toBeNull();
    if (!observability) {
      return;
    }

    expect(observability.node_timings_ms).toHaveLength(observability.node_path.length);
    for (const timing of observability.node_timings_ms) {
      expect(typeof timing.node).toBe('string');
      expect(typeof timing.duration_ms).toBe('number');
    }
  });
});

describe('date semantics', () => {
  it('anchors fixture dates to the mock data, never the browser clock', () => {
    // 2026-07-01 is the anchor day in office_agent/mock_data/. These strings are
    // literals in the fixture text, so the rendered output cannot drift with the
    // system clock.
    expect(emailSuccess.content).toContain('2026-07-01T09:00:00');
    expect(calendarSuccess.content).toContain('Calendar — 2026-07-01');
    expect(briefingSuccess.content).toContain('Daily briefing — 2026-07-01');
    expect(approvalsSuccess.content).toContain('2026-07-02T17:00:00');
  });
});

describe('unsupported fixture', () => {
  it('carries the unknown intent with no tool', () => {
    expect(unsupportedResponse.intent).toBe('unknown');
    expect(unsupportedResponse.tool).toBeNull();
    expect(unsupportedResponse.execution_mode).toBe('none');
  });
});
