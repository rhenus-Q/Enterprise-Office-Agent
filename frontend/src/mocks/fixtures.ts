/**
 * Typed mock responses for the frontend's optional offline mock mode.
 *
 * Every fixture is a real `AgentRunResponse`, so the components are exercised
 * against the exact shape the current adapter returns.
 *
 * Date semantics: all dates below are anchored to the repository's read-only
 * mock data (which centres on 2026-07-01) and are written verbatim into the
 * fixture text. Nothing in this file — or anywhere in the UI — derives "today"
 * from the browser clock.
 *
 * Caveat wording is copied verbatim from `enterprise_rag/graph/formatting.py`
 * (`STOP_REASON_NOTES`) and `office_agent/llm_assist/config.py`, so the demo
 * never invents engine copy.
 */

import type {
  AgentRunResponse,
  HealthResponse,
  RunConstraint,
  RunOptions,
  RunPrivacyMode,
  RunSettings,
} from '../types/api';

/** Verbatim `WEB_SEARCH_DISABLED_NOTE` from enterprise_rag/graph/formatting.py. */
const WEB_SEARCH_DISABLED_NOTE =
  'Note: Web search is disabled, so I could only use the local knowledge base. ' +
  'I may not have enough information to fully answer this question.';

/** Verbatim `LLM_ASSIST_ERROR_NOTE` from office_agent/llm_assist/config.py. */
const LLM_ASSIST_ERROR_NOTE =
  'Note: the LLM-assisted digest was unavailable; showing the standard summary.';

/** Verbatim `UNSUPPORTED_INTENT_NOTE` from office_agent/formatting.py. */
const UNSUPPORTED_INTENT_NOTE =
  "Sorry — the Office Agent can't handle that request. Right now it answers " +
  'enterprise knowledge and policy questions from the internal knowledge base, ' +
  'summarizes your inbox, looks up your calendar, helps with tickets and tasks, ' +
  'gives you a daily briefing, prepares you for a meeting (meeting prep), and ' +
  'handles approval workflows (workflow / approval agent). ' +
  'Try rephrasing toward one of those.';

export const knowledgeSuccess: AgentRunResponse = {
  intent: 'knowledge_qa',
  tool: 'knowledge_qa',
  content: [
    'Employees must connect through the AcmeCorp VPN whenever they access internal',
    'systems from an untrusted network. Split-tunnelling is disabled by default, and',
    'any exception requires security-team approval with a documented expiry date.',
    '',
    'Sources:',
    '- AcmeCorp VPN Access Policy (acmecorp_vpn_policy.md)',
    '- AcmeCorp Onboarding Guide (acmecorp_onboarding_guide.md)',
  ].join('\n'),
  stop_reason: '',
  sources: [
    'AcmeCorp VPN Access Policy (acmecorp_vpn_policy.md)',
    'AcmeCorp Onboarding Guide (acmecorp_onboarding_guide.md)',
  ],
  run_id: '9f2c1a7b4e5d4c8fa1b2c3d4e5f60718',
  duration_ms: 3861.2,
  execution_mode: 'rag_llm',
  observability: {
    run_id: '9f2c1a7b4e5d4c8fa1b2c3d4e5f60718',
    node_path: ['retrieve', 'grade_documents', 'generate'],
    node_timings_ms: [
      { node: 'retrieve', duration_ms: 412.87 },
      { node: 'grade_documents', duration_ms: 1180.44 },
      { node: 'generate', duration_ms: 2260.19 },
    ],
    total_duration_ms: 3853.5,
    retries: 0,
    tracked_llm_calls: 1,
    web_search_count: 0,
    web_result_grading_count: 0,
    web_search_enabled: true,
    web_fallback_policy: 'conservative',
    caveat: '',
  },
  run_settings: null,
};

export const knowledgeWebSearchDisabled: AgentRunResponse = {
  intent: 'knowledge_qa',
  tool: 'knowledge_qa',
  content: [
    'The local knowledge base does not cover the third-party VPN vendor advisory',
    'you asked about, so this answer is limited to AcmeCorp internal policy.',
    '',
    WEB_SEARCH_DISABLED_NOTE,
    '',
    'Sources:',
    '- AcmeCorp VPN Access Policy (acmecorp_vpn_policy.md)',
  ].join('\n'),
  stop_reason: 'web_search_disabled',
  sources: ['AcmeCorp VPN Access Policy (acmecorp_vpn_policy.md)'],
  run_id: 'c41d8fe0a7b24f6b9d0e5a3c8b1f2d67',
  duration_ms: 2140.9,
  execution_mode: 'rag_llm',
  observability: {
    run_id: 'c41d8fe0a7b24f6b9d0e5a3c8b1f2d67',
    node_path: ['retrieve', 'grade_documents', 'web_search_disabled_notice', 'generate'],
    node_timings_ms: [
      { node: 'retrieve', duration_ms: 389.12 },
      { node: 'grade_documents', duration_ms: 902.55 },
      { node: 'web_search_disabled_notice', duration_ms: 0.41 },
      { node: 'generate', duration_ms: 842.63 },
    ],
    total_duration_ms: 2134.71,
    retries: 1,
    tracked_llm_calls: 2,
    web_search_count: 0,
    web_result_grading_count: 0,
    web_search_enabled: false,
    web_fallback_policy: 'conservative',
    caveat: WEB_SEARCH_DISABLED_NOTE,
  },
  run_settings: null,
};

export const emailSuccess: AgentRunResponse = {
  intent: 'email_summary',
  tool: 'email_summary',
  content: [
    'Inbox summary — unread (2 messages)',
    '',
    '1. VPN rollout review needed',
    '   From: manager@acmecorp.example',
    '   Received: 2026-07-01T09:00:00 · high priority · response needed',
    '',
    '2. Action required: confirm on-call coverage for Sev-1 rotation',
    '   From: security-team@acmecorp.example',
    '   Received: 2026-07-01T08:15:00 · high priority · response needed',
  ].join('\n'),
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 6.4,
  execution_mode: 'deterministic',
  observability: null,
  run_settings: null,
};

export const emailAssistFallback: AgentRunResponse = {
  intent: 'email_summary',
  tool: 'email_summary',
  content: [emailSuccess.content, '', LLM_ASSIST_ERROR_NOTE].join('\n'),
  stop_reason: 'llm_assist_error',
  sources: [],
  run_id: null,
  duration_ms: 61240.8,
  execution_mode: 'llm_assist_fallback',
  observability: null,
  run_settings: null,
};

export const calendarSuccess: AgentRunResponse = {
  intent: 'calendar_lookup',
  tool: 'calendar_lookup',
  content: [
    'Calendar — 2026-07-01 (3 events)',
    '',
    '09:30–10:00  VPN rollout review · Zoom · high',
    '10:00–10:15  Team standup · Room A',
    '11:00–12:00  Onboarding session for new hires · Room B',
    '',
    'No overlapping events detected.',
  ].join('\n'),
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 4.1,
  execution_mode: 'deterministic',
  observability: null,
  run_settings: null,
};

export const ticketsSuccess: AgentRunResponse = {
  intent: 'ticket_assistant',
  tool: 'ticket_assistant',
  content: [
    'Open tickets (2)',
    '',
    'TICK-001  VPN split-tunnel exception for onboarding cohort',
    '          Status: open · Priority: high · Updated 2026-07-01',
    '',
    'TICK-002  Expense reimbursement portal timeout',
    '          Status: blocked · Priority: normal · Updated 2026-06-30',
  ].join('\n'),
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 5.2,
  execution_mode: 'deterministic',
  observability: null,
  run_settings: null,
};

export const briefingSuccess: AgentRunResponse = {
  intent: 'daily_briefing',
  tool: 'daily_briefing',
  content: [
    'Daily briefing — 2026-07-01',
    '',
    'Inbox      2 unread, both high priority and awaiting a response.',
    'Calendar   3 events, starting 09:30 with the VPN rollout review.',
    'Tickets    2 open (1 blocked).',
    'Approvals  2 pending, earliest due 2026-07-02T17:00:00.',
  ].join('\n'),
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 9.8,
  execution_mode: 'deterministic',
  observability: null,
  run_settings: null,
};

export const meetingSuccess: AgentRunResponse = {
  intent: 'meeting_agent',
  tool: 'meeting_agent',
  content: [
    'Meeting prep — VPN rollout review',
    'When: 2026-07-01T09:30:00 – 2026-07-01T10:00:00 · Zoom',
    'Attendees: manager@acmecorp.example, security@acmecorp.example',
    '',
    'Context',
    '- Ticket TICK-001 (VPN split-tunnel exception) is still open.',
    '- Approval APR-001 is pending, due 2026-07-02T17:00:00.',
    '',
    'Suggested talking points',
    '- Confirm the split-tunnel exception scope for the onboarding cohort.',
    '- Agree an owner for the remaining rollout blockers.',
  ].join('\n'),
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 7.6,
  execution_mode: 'deterministic',
  observability: null,
  run_settings: null,
};

export const approvalsSuccess: AgentRunResponse = {
  intent: 'workflow_approval',
  tool: 'workflow_approval',
  content: [
    'Pending approvals (2)',
    '',
    'APR-001  Approve VPN exception for onboarding cohort',
    '         Type: access · Priority: high · Due 2026-07-02T17:00:00',
    '         Requested by manager@acmecorp.example',
    '',
    'APR-002  Approve June expense reimbursement',
    '         Type: expense · Priority: normal · Due 2026-07-03T17:00:00',
    '',
    'Approve / reject actions are simulated — nothing is written back.',
  ].join('\n'),
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 5.9,
  execution_mode: 'deterministic',
  observability: null,
  run_settings: null,
};

export const unsupportedResponse: AgentRunResponse = {
  intent: 'unknown',
  tool: null,
  content: UNSUPPORTED_INTENT_NOTE,
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 0.3,
  execution_mode: 'none',
  observability: null,
  run_settings: null,
};

export const mockHealth: HealthResponse = {
  status: 'ok',
  privacy_mode: false,
  offline_mode: false,
  office_llm_enabled: false,
  web_search_effective: true,
};

/**
 * Server policy the mock resolver applies — exactly the keyword inputs of the
 * Python `resolve_run_settings`. Injectable so tests can exercise other server
 * configurations against the same rules; the mock client uses the default below.
 */
export interface MockServerPolicy {
  server_privacy_mode: boolean;
  server_offline_mode: boolean;
  server_llm_assist_available: boolean;
  server_web_search_available: boolean;
}

/**
 * Default mock server policy, derived from `mockHealth` (assists disabled, web
 * search available). It is the default argument to `resolveMockRunSettings`, so
 * every existing caller keeps its exact previous behavior.
 */
export const MOCK_SERVER_POLICY: MockServerPolicy = {
  server_privacy_mode: mockHealth.privacy_mode,
  server_offline_mode: mockHealth.offline_mode,
  server_llm_assist_available: mockHealth.office_llm_enabled,
  server_web_search_available: mockHealth.web_search_effective,
};

/**
 * Canonical constraint order — a faithful port of `_CONSTRAINT_ORDER` in
 * `office_agent/run_settings.py`. Broadest cause first: a server mode explains
 * more than a per-setting flag. The resolver deduplicates reasons into a set and
 * emits them in this order, exactly as Python does.
 */
const CONSTRAINT_ORDER: RunConstraint[] = [
  'server_offline_mode',
  'server_privacy_mode',
  'request_privacy_strict',
  'server_llm_assist_disabled',
  'server_web_search_disabled',
  'llm_assist_not_applicable',
  'web_search_not_applicable',
];

/**
 * The single most explanatory reason a requested setting did not apply — a
 * faithful port of `_blocked_reason` in `office_agent/run_settings.py`, including
 * its priority: not-applicable first, then the active server mode (offline before
 * privacy — a mode outranks the per-service flag it already forced off), then the
 * per-service server-disabled flag, then a request-level strict, then the
 * per-service flag as the fallback.
 */
function blockedReason(
  server: MockServerPolicy,
  args: {
    applicable: boolean;
    serverAvailable: boolean;
    requestedStrict: boolean;
    notApplicable: RunConstraint;
    serverDisabled: RunConstraint;
  },
): RunConstraint {
  if (!args.applicable) {
    return args.notApplicable;
  }
  if (server.server_offline_mode) {
    return 'server_offline_mode';
  }
  if (server.server_privacy_mode) {
    return 'server_privacy_mode';
  }
  if (!args.serverAvailable) {
    return args.serverDisabled;
  }
  if (args.requestedStrict) {
    return 'request_privacy_strict';
  }
  return args.serverDisabled;
}

/**
 * Mock-server resolution of per-run settings.
 *
 * This is the *fake backend's* job, not the frontend's: it mirrors the rules in
 * `office_agent/run_settings.py` so the offline demo behaves like the real
 * adapter. Production code never derives effective settings — it displays what
 * the backend returned.
 *
 * `server` defaults to `MOCK_SERVER_POLICY` (the frontend's fixed mock health:
 * assists disabled, web search available), so the mock client is unchanged;
 * tests may inject an explicit policy to drive other server configurations.
 */
export function resolveMockRunSettings(
  options: RunOptions,
  intent: AgentRunResponse['intent'],
  server: MockServerPolicy = MOCK_SERVER_POLICY,
): RunSettings {
  const serverPrivacy = server.server_privacy_mode || server.server_offline_mode;
  const effectivePrivacy: RunPrivacyMode =
    serverPrivacy || options.privacy_mode === 'strict' ? 'strict' : 'standard';
  const strict = effectivePrivacy === 'strict';

  const applicability = {
    llm_assist: intent === 'email_summary' || intent === 'daily_briefing',
    web_search: intent === 'knowledge_qa',
  };

  const llmAssist =
    options.llm_assist && applicability.llm_assist && server.server_llm_assist_available && !strict;
  const webSearch =
    options.web_search && applicability.web_search && server.server_web_search_available && !strict;

  // Collect a *set* of typed reasons (deduplicated), then emit them in the one
  // canonical order — exactly as the Python resolver does, so a mode that blocks
  // a requested applicable service is attributed to the mode (not the per-service
  // flag) and folded into a single constraint.
  const reasons = new Set<RunConstraint>();

  // Privacy escalated beyond what the caller asked for.
  if (options.privacy_mode === 'standard' && strict) {
    reasons.add(server.server_offline_mode ? 'server_offline_mode' : 'server_privacy_mode');
  }
  if (options.llm_assist && !llmAssist) {
    reasons.add(
      blockedReason(server, {
        applicable: applicability.llm_assist,
        serverAvailable: server.server_llm_assist_available,
        requestedStrict: options.privacy_mode === 'strict',
        notApplicable: 'llm_assist_not_applicable',
        serverDisabled: 'server_llm_assist_disabled',
      }),
    );
  }
  if (options.web_search && !webSearch) {
    reasons.add(
      blockedReason(server, {
        applicable: applicability.web_search,
        serverAvailable: server.server_web_search_available,
        requestedStrict: options.privacy_mode === 'strict',
        notApplicable: 'web_search_not_applicable',
        serverDisabled: 'server_web_search_disabled',
      }),
    );
  }

  return {
    requested: { ...options },
    effective: { privacy_mode: effectivePrivacy, llm_assist: llmAssist, web_search: webSearch },
    applicability,
    constraints: CONSTRAINT_ORDER.filter((reason) => reasons.has(reason)),
  };
}

/** Prompt that makes the mock client reject, so the error state is reachable. */
export const ERROR_PROMPT = 'Demo: simulated API error';

/**
 * Exact-prompt demo lookup table.
 *
 * This is deliberately NOT intent detection: it is exact string equality over
 * the canned prompts shipped in the sidebar. Real routing is the deterministic
 * Python router's job and stays server-side. Anything not listed here
 * falls back to the unsupported response.
 */
export const RESPONSES_BY_PROMPT: Record<string, AgentRunResponse> = {
  'What is the VPN policy?': knowledgeSuccess,
  'How do I escalate a Sev-1 incident?': knowledgeSuccess,
  'Summarize my unread emails': emailSuccess,
  'What meetings do I have today?': calendarSuccess,
  'Do I have any scheduling conflicts?': calendarSuccess,
  'Show my open tickets': ticketsSuccess,
  'What tasks are blocked?': ticketsSuccess,
  'Brief me on my day': briefingSuccess,
  'What should I focus on today?': briefingSuccess,
  'Prepare me for my next meeting': meetingSuccess,
  'What should I bring up in the VPN review?': meetingSuccess,
  'What approvals are pending?': approvalsSuccess,
  'What is the status of APR-001?': approvalsSuccess,
  'Demo: degraded email digest': emailAssistFallback,
  'Demo: knowledge with web search disabled': knowledgeWebSearchDisabled,
  'Demo: unsupported request': unsupportedResponse,
};
