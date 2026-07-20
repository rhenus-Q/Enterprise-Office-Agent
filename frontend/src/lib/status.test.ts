import { describe, expect, it } from 'vitest';

import {
  EXECUTION_MODE_LABELS,
  RUN_STATUS_LABELS,
  classifyRunStatus,
  formatDurationMs,
} from './status';
import { emailSuccess, knowledgeWebSearchDisabled, unsupportedResponse } from '../mocks/fixtures';
import type { ExecutionMode, RunStatus, StopReason } from '../types/api';

/** Every non-empty StopReason in the union — a degraded run by definition. */
const NON_EMPTY_STOP_REASONS: StopReason[] = [
  'web_search_disabled',
  'web_fallback_disabled',
  'max_retries_not_grounded',
  'max_retries_not_useful',
  'budget_exhausted',
  'offline_mode',
  'retrieval_error',
  'web_search_error',
  'generation_error',
  'tool_error',
  'llm_assist_error',
];

const ALL_EXECUTION_MODES: ExecutionMode[] = [
  'none',
  'deterministic',
  'llm_assisted',
  'llm_assist_fallback',
  'rag_llm',
  'rag_blocked_offline',
];

const ALL_RUN_STATUSES: RunStatus[] = ['success', 'degraded', 'unsupported', 'error'];

describe('classifyRunStatus', () => {
  it('treats an empty stop reason as success', () => {
    expect(classifyRunStatus(emailSuccess)).toBe('success');
  });

  it('treats any non-empty stop reason as degraded', () => {
    for (const stopReason of NON_EMPTY_STOP_REASONS) {
      expect(classifyRunStatus({ ...emailSuccess, stop_reason: stopReason })).toBe('degraded');
    }
  });

  it('classifies the unknown intent as unsupported, not success', () => {
    // An unsupported request finishes normally, so the intent check must win.
    expect(unsupportedResponse.stop_reason).toBe('');
    expect(classifyRunStatus(unsupportedResponse)).toBe('unsupported');
  });

  it('classifies a real degraded knowledge fixture as degraded', () => {
    expect(classifyRunStatus(knowledgeWebSearchDisabled)).toBe('degraded');
  });
});

describe('labels', () => {
  it('has a label for every execution mode', () => {
    for (const mode of ALL_EXECUTION_MODES) {
      expect(EXECUTION_MODE_LABELS[mode]).toBeTruthy();
    }
  });

  it('has a label for every run status', () => {
    for (const status of ALL_RUN_STATUSES) {
      expect(RUN_STATUS_LABELS[status]).toBeTruthy();
    }
  });
});

describe('formatDurationMs', () => {
  it('renders sub-second durations in milliseconds', () => {
    expect(formatDurationMs(6.4)).toBe('6.4 ms');
  });

  it('renders longer durations in seconds', () => {
    expect(formatDurationMs(3861.2)).toBe('3.86 s');
  });
});
