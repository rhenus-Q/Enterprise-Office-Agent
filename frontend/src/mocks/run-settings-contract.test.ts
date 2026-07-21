/**
 * Cross-language contract test for request-scoped Run Settings resolution.
 *
 * This Vitest test and the Python test in
 * `tests/office_agent/test_run_settings_contract.py` consume the SAME fixture,
 * `tests/contracts/run-settings-resolution.json`, so the frontend mock resolver
 * (`resolveMockRunSettings`) and the Python resolver
 * (`office_agent.run_settings.resolve_run_settings`) cannot silently drift apart.
 *
 * Every case runs in BOTH resolvers with no filtering: each case carries its own
 * server policy, which is injected into the mock resolver (the DI parameter that
 * defaults to the mock health for the mock client). An `afterAll` assertion pins
 * the number of executed cases to the total fixture count, so no case can be
 * skipped or filtered out unnoticed.
 *
 * The fixture is imported statically (`resolveJsonModule`); the repo root holds
 * the `.git` marker, so Vite's workspace-root search puts it inside the fs-allow
 * list. No Node filesystem API is used, so no `@types/node` is required.
 */

import { afterAll, describe, expect, it } from 'vitest';

import rawContract from '../../../tests/contracts/run-settings-resolution.json';
import { resolveMockRunSettings, type MockServerPolicy } from './fixtures';
import type { Intent, RunOptions, RunSettings } from '../types/api';

interface ContractCase {
  name: string;
  intent: Intent;
  options: RunOptions;
  server: MockServerPolicy;
  expected: RunSettings;
}

interface Contract {
  schema_version: number;
  cases: ContractCase[];
}

const contract = rawContract as unknown as Contract;
const cases = contract.cases;

describe('run settings resolution contract (shared with the Python resolver)', () => {
  it('declares the expected schema version', () => {
    expect(contract.schema_version).toBe(1);
  });

  const executed: string[] = [];

  it.each(cases.map((testCase) => [testCase.name, testCase] as [string, ContractCase]))(
    'mock resolver matches the contract for %s',
    (_name, testCase) => {
      executed.push(testCase.name);
      expect(resolveMockRunSettings(testCase.options, testCase.intent, testCase.server)).toEqual(
        testCase.expected,
      );
    },
  );

  afterAll(() => {
    // Every fixture case ran — the shared-subset filtering is gone, so the
    // TypeScript executed count must equal the total fixture case count.
    expect(cases.length).toBeGreaterThan(0);
    expect(executed).toHaveLength(cases.length);
  });
});
