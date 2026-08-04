/**
 * The seven Office Agent capabilities shown in the left rail, the featured
 * prompts surfaced in the workspace, and the demo scenarios that make every UI
 * state reachable in offline mock mode.
 *
 * Every example prompt was verified against the deterministic router's keyword
 * lists and rule order in `office_agent/router.py`
 * (email -> workflow/approval -> ticket -> meeting-prep -> calendar -> briefing
 * -> knowledge -> unknown), so each prompt routes to the capability it is listed
 * under when submitted through the default HTTP client. No routing logic is
 * reimplemented here — this is display copy only.
 *
 * Icons and accents are presentation metadata: each capability gets a distinct
 * mark and a restrained accent hue so routing is legible at a glance.
 */

import {
  BookOpen,
  CalendarDays,
  LayoutDashboard,
  ListChecks,
  Mail,
  ShieldCheck,
  Users,
  type LucideIcon,
} from 'lucide-react';

import type { CapabilityIntent } from '../types/api';

export interface Capability {
  intent: CapabilityIntent;
  label: string;
  blurb: string;
  examples: string[];
  icon: LucideIcon;
}

export const CAPABILITIES: Capability[] = [
  {
    intent: 'knowledge_qa',
    label: 'Knowledge Q&A',
    blurb: 'Answers policy questions from the internal knowledge base (Enterprise RAG).',
    examples: ['What is the VPN policy?', 'How do I escalate a Sev-1 incident?'],
    icon: BookOpen,
  },
  {
    intent: 'email_summary',
    label: 'Email Summary',
    blurb: 'Summarizes the mock inbox — unread, high priority, or response needed.',
    examples: ['Summarize my unread emails'],
    icon: Mail,
  },
  {
    intent: 'calendar_lookup',
    label: 'Calendar Lookup',
    blurb: 'Looks up scheduled events and flags conflicts.',
    examples: ['What meetings do I have today?', 'Do I have any scheduling conflicts?'],
    icon: CalendarDays,
  },
  {
    intent: 'ticket_assistant',
    label: 'Ticket Assistant',
    blurb: 'Reviews open tickets and tasks, including blocked work.',
    examples: ['Show my open tickets', 'What tasks are blocked?'],
    icon: ListChecks,
  },
  {
    intent: 'daily_briefing',
    label: 'Daily Briefing',
    blurb: 'Aggregates inbox, calendar, tickets, and approvals into one briefing.',
    examples: ['Brief me on my day', 'What should I focus on today?'],
    icon: LayoutDashboard,
  },
  {
    intent: 'meeting_agent',
    label: 'Meeting Agent',
    blurb: 'Prepares context and talking points for an upcoming meeting.',
    examples: ['Prepare me for my next meeting', 'What should I bring up in the VPN review?'],
    icon: Users,
  },
  {
    intent: 'workflow_approval',
    label: 'Workflow Approval',
    blurb: 'Reviews pending approvals and simulates approve / reject decisions.',
    examples: ['What approvals are pending?', 'What is the status of APR-001?'],
    icon: ShieldCheck,
  },
];

/** Look up a capability by intent. */
export function capabilityFor(intent: CapabilityIntent): Capability | null {
  return CAPABILITIES.find((capability) => capability.intent === intent) ?? null;
}

export interface FeaturedPrompt {
  intent: CapabilityIntent;
  prompt: string;
  description: string;
}

/**
 * The starter set shown when no capability is selected — a small, curated cross
 * section rather than every example at once. Each `prompt` must also appear in
 * its capability's `examples` (asserted in the fixtures test), so the featured
 * set can never drift from the router-verified prompts.
 */
export const FEATURED_PROMPTS: FeaturedPrompt[] = [
  {
    intent: 'knowledge_qa',
    prompt: 'What is the VPN policy?',
    description: 'Grounded answer from the knowledge base, with sources and a full graph timeline.',
  },
  {
    intent: 'email_summary',
    prompt: 'Summarize my unread emails',
    description: 'Deterministic inbox digest — no LLM call unless assists are switched on.',
  },
  {
    intent: 'ticket_assistant',
    prompt: 'Show my open tickets',
    description: 'Open and blocked work items, read from local mock data.',
  },
  {
    intent: 'daily_briefing',
    prompt: 'Brief me on my day',
    description: 'Inbox, calendar, tickets, and approvals aggregated into one view.',
  },
];

export interface DemoScenario {
  id: string;
  label: string;
  prompt: string;
  description: string;
}

/**
 * Explicit demo triggers so a reviewer can reach the degraded, unsupported, and
 * error states without a backend. They are clearly-labeled demo strings, not
 * real user requests, and they are available only through the optional mock client.
 */
export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: 'degraded-assist',
    label: 'Degraded: LLM assist fell back',
    prompt: 'Demo: degraded email digest',
    description: 'Email summary where the optional LLM digest failed and the tool fell back.',
  },
  {
    id: 'degraded-knowledge',
    label: 'Degraded: web search disabled',
    prompt: 'Demo: knowledge with web search disabled',
    description: 'Knowledge Q&A that stopped early because web search is disabled.',
  },
  {
    id: 'unsupported',
    label: 'Unsupported request',
    prompt: 'Demo: unsupported request',
    description: 'A request the router cannot map to any capability.',
  },
  {
    id: 'error',
    label: 'Simulated API error',
    prompt: 'Demo: simulated API error',
    description: 'The request fails before a response is returned.',
  },
];
