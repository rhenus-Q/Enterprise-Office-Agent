/**
 * Runtime status from `GET /api/health`.
 *
 * Three distinct phases, deliberately not collapsed into "we have data or we
 * don't": `loading` (the first check is in flight), `ready` (the adapter
 * answered), and `unreachable` (it did not). Only `unreachable` may claim the
 * API is down, so a slow first response never shows a false alarm.
 *
 * The hook transports the four flags and interprets none of them — the privacy,
 * offline, assist, and effective-web-search values are already resolved by the
 * Python readers behind the endpoint.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import type { AgentClient } from '../api/client';
import type { HealthResponse } from '../types/api';

export type HealthPhase = 'loading' | 'ready' | 'unreachable';

export interface HealthState {
  phase: HealthPhase;
  health: HealthResponse | null;
  /** A manual refresh is running on top of an already-resolved phase. */
  isRefreshing: boolean;
}

const INITIAL_STATE: HealthState = { phase: 'loading', health: null, isRefreshing: false };

export function useHealth(client: AgentClient) {
  const [state, setState] = useState<HealthState>(INITIAL_STATE);
  // Guards against a slow earlier check overwriting a newer one.
  const latestCheckRef = useRef(0);

  const load = useCallback(
    async (isRefresh: boolean) => {
      const checkId = latestCheckRef.current + 1;
      latestCheckRef.current = checkId;
      // A refresh keeps the current phase on screen while it runs; the first
      // check is already in `loading`.
      setState((current) => ({ ...current, isRefreshing: isRefresh }));

      try {
        const health = await client.health();
        if (latestCheckRef.current === checkId) {
          setState({ phase: 'ready', health, isRefreshing: false });
        }
      } catch {
        if (latestCheckRef.current === checkId) {
          setState({ phase: 'unreachable', health: null, isRefreshing: false });
        }
      }
    },
    [client],
  );

  useEffect(() => {
    setState(INITIAL_STATE);
    void load(false);
  }, [load]);

  const refresh = useCallback(() => {
    void load(true);
  }, [load]);

  return { ...state, refresh };
}
