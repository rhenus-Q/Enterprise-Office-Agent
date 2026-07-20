import { useEffect, useMemo, useState } from 'react';

import { createClientFromEnv, type AgentClient } from './api/client';
import { AppShell } from './components/AppShell';
import { CapabilitySidebar } from './components/CapabilitySidebar';
import { ExamplePrompts, type PanelView } from './components/ExamplePrompts';
import { ExecutionPanel } from './components/ExecutionPanel';
import { ExecutionPreview } from './components/ExecutionPreview';
import { RequestComposer } from './components/RequestComposer';
import { StatusBanner } from './components/StatusBanner';
import { ResultCard } from './components/results/ResultCard';
import { DegradedNotice } from './components/states/DegradedNotice';
import { EmptyState } from './components/states/EmptyState';
import { ErrorState } from './components/states/ErrorState';
import { LoadingState } from './components/states/LoadingState';
import { StoppedState } from './components/states/StoppedState';
import { UnsupportedNotice } from './components/states/UnsupportedNotice';
import { useAgentRun } from './hooks/useAgentRun';
import { useHealth } from './hooks/useHealth';
import { classifyRunStatus } from './lib/status';
import type { CapabilityIntent } from './types/api';

interface AppProps {
  /**
   * Injectable for tests; defaults to the environment-selected client, which is
   * the live HTTP adapter unless `VITE_API_MODE=mock` is set.
   */
  client?: AgentClient;
}

/**
 * Return to the top of the page after a reset.
 *
 * Skipped when already at the top, which also keeps it inert under jsdom. Honors
 * `prefers-reduced-motion` by jumping instead of animating.
 */
function scrollToTop() {
  if (typeof window === 'undefined' || window.scrollY === 0) {
    return;
  }

  const prefersReducedMotion =
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
}

export function App({ client }: AppProps) {
  const agentClient = useMemo(() => client ?? createClientFromEnv(), [client]);
  const { state, run, stop, reset, completedRuns } = useAgentRun(agentClient);
  const {
    phase: healthPhase,
    health,
    isRefreshing: healthRefreshing,
    timedOut: healthTimedOut,
    refresh: refreshHealth,
  } = useHealth(agentClient);
  const [text, setText] = useState('');
  // Three independent concerns, deliberately not inferred from one another:
  //   selectedIntent — the capability in focus (rail highlight); after a run
  //                    this is whatever the backend router returned.
  //   panelView      — which prompts are being browsed. User-controlled: a run
  //                    never changes it, so the panel's identity stays put.
  //   panelOpen      — whether the panel is shown at all. Dismissing is sticky;
  //                    a run must not reopen it.
  const [selectedIntent, setSelectedIntent] = useState<CapabilityIntent | null>(null);
  const [panelView, setPanelView] = useState<PanelView>('all');
  const [panelOpen, setPanelOpen] = useState(true);
  // Controls only whether the transcript is shown. The response, the execution
  // details, and every navigation concern above are untouched by it.
  const [resultExpanded, setResultExpanded] = useState(true);
  // Which control was showing Stop when the run was stopped. Stop and the
  // control it replaced share one position, so that control's replacement stays
  // disarmed until a deliberate new gesture. Only the control that actually
  // swapped is guarded — the other one never moved under the pointer.
  const [disarmed, setDisarmed] = useState<'composer' | 'result' | null>(null);

  /**
   * After a run, the routed capability takes focus.
   *
   * `selectedIntent` represents the capability currently in focus, not just a
   * filter the user picked — so a completed run deliberately overwrites any
   * prior selection. The response is the single source of truth: the active
   * capability is never derived from the clicked prompt card, the previous
   * selection, or the frontend's own prompt metadata, because only the backend
   * router decides where a request goes.
   */
  useEffect(() => {
    if (state.phase !== 'success') {
      return;
    }

    const routed = state.response.intent === 'unknown' ? null : state.response.intent;

    setSelectedIntent(routed);

    // Nothing was routed, so there is no capability to browse.
    if (routed === null) {
      setPanelOpen(false);
    }

    // `panelView` and an open panel are left untouched on purpose: the run
    // reports where it went, it does not navigate the panel for the user.
  }, [state]);

  // The result stays on screen while a retry is in flight, so the card is driven
  // by "the result currently being shown" rather than strictly by the phase.
  // `previous` is non-null only for a retry, so a card that survives into the
  // loading phase is by construction being re-run — never displaced by an
  // unrelated new request.
  // A stopped retry keeps the same held result, so the card simply stays put.
  const shownResult =
    state.phase === 'success'
      ? state.response
      : state.phase === 'loading' || state.phase === 'stopped'
        ? state.previous
        : null;
  const shownStatus = shownResult ? classifyRunStatus(shownResult) : null;

  // Density follows whether the transcript actually occupies space, not the run
  // phase — a collapsed result frees the column, so the discovery view returns.
  const resultContentVisible = shownResult !== null && resultExpanded;
  const denseExamples =
    resultContentVisible ||
    state.phase === 'loading' ||
    state.phase === 'error' ||
    state.phase === 'stopped';

  /** Every new run reveals its answer, so a collapsed result expands first. */
  function handleRun(text: string) {
    setResultExpanded(true);
    setDisarmed(null);
    void run(text);
  }

  /** Re-runs the request behind the visible result through the shared machinery. */
  function handleRetry() {
    if (state.phase === 'loading' || state.phase === 'idle') {
      return;
    }
    setResultExpanded(true);
    setDisarmed(null);
    void run(state.text, { isRetry: true });
  }

  /**
   * Stop the in-flight run and disarm the control that was showing Stop.
   *
   * Which control that is follows the same rule as everything else here: a run
   * holding a previous result is a retry owned by the card, anything else is
   * owned by the composer.
   */
  function handleStop() {
    if (state.phase === 'loading') {
      setDisarmed(state.previous === null ? 'composer' : 'result');
    }
    stop();
  }

  /** A deliberate new gesture — pointer moved away, key released, field touched. */
  function handleRearm() {
    setDisarmed(null);
  }

  /**
   * Return the workspace to its initial state: empty composer, no result, no
   * error, no capability filter, execution details back to placeholders.
   *
   * Runtime status is deliberately preserved — it describes the environment, not
   * the request, so a reset must not discard it.
   */
  function handleReset() {
    setText('');
    setSelectedIntent(null);
    setPanelView('all');
    setPanelOpen(true);
    setResultExpanded(true);
    setDisarmed(null);
    reset();
    scrollToTop();
  }

  /**
   * Clicking a rail capability focuses it. Clicking the one already being
   * browsed dismisses the panel — the toggle applies to the view you are in, so
   * a capability merely highlighted by the last run still focuses on first click.
   */
  function handleSelectCapability(intent: CapabilityIntent) {
    const alreadyBrowsing = panelOpen && panelView === 'capability' && selectedIntent === intent;

    if (alreadyBrowsing) {
      setPanelOpen(false);
      return;
    }

    setSelectedIntent(intent);
    setPanelView('capability');
    setPanelOpen(true);
  }

  /** "Show all" changes the browsing mode only; the rail highlight stays put. */
  function handleShowAllExamples() {
    setPanelView('all');
    setPanelOpen(true);
  }

  // Visibility is now explicit state rather than something inferred from the
  // phase or the selection.
  const showExamples = panelOpen;

  const main = (
    <>
      <RequestComposer
        value={text}
        onChange={setText}
        onSubmit={handleRun}
        isLoading={state.phase === 'loading'}
        // A retry is owned by its result card, which carries its own Stop.
        canStop={state.phase === 'loading' && state.previous === null}
        onStop={handleStop}
        disarmed={disarmed === 'composer'}
        onRearm={handleRearm}
      />

      {showExamples ? (
        <ExamplePrompts
          view={panelView}
          selectedIntent={selectedIntent}
          dense={denseExamples}
          onSelectPrompt={setText}
          onShowAll={handleShowAllExamples}
        />
      ) : null}

      <section
        className="results"
        aria-live="polite"
        aria-busy={state.phase === 'loading'}
        aria-label="Result"
      >
        {state.phase === 'idle' ? <EmptyState /> : null}
        {/* A retry keeps the previous result on screen, so the neutral loading
            card covers every run that has nothing to preserve — a first run and
            a new request alike, which is exactly the set whose capability is not
            yet known. */}
        {state.phase === 'loading' && state.previous === null ? (
          <LoadingState requestText={state.text} />
        ) : null}
        {/* Only a stopped run with nothing held gets its own card; a stopped
            retry falls through to the result it was refreshing. */}
        {state.phase === 'stopped' && state.previous === null ? (
          <StoppedState requestText={state.text} onRetry={handleRetry} />
        ) : null}
        {state.phase === 'error' ? (
          <ErrorState errorType={state.errorType} onRetry={handleRetry} />
        ) : null}
        {shownResult && shownStatus ? (
          <>
            {shownStatus === 'degraded' ? (
              <DegradedNotice
                stopReason={shownResult.stop_reason}
                caveat={shownResult.observability?.caveat ?? ''}
              />
            ) : null}
            {shownStatus === 'unsupported' ? <UnsupportedNotice /> : null}
            <ResultCard
              response={shownResult}
              status={shownStatus}
              expanded={resultExpanded}
              onToggleExpanded={() => setResultExpanded((open) => !open)}
              // A mounted card during the loading phase can only be a retry of
              // this very result, so one flag says everything the card needs.
              isRefreshing={state.phase === 'loading'}
              onStop={handleStop}
              disarmed={disarmed === 'result'}
              onRearm={handleRearm}
              wasStopped={state.phase === 'stopped'}
              onRetry={handleRetry}
              revision={completedRuns}
            />
          </>
        ) : null}
      </section>
    </>
  );

  // Total mapping: the preview covers every phase that is not a rendered result.
  const previewPhase =
    state.phase === 'loading' ? 'loading' : state.phase === 'error' ? 'error' : 'idle';

  // Details describe a settled result, so they follow the card that is on
  // screen — including the one restored after a stopped retry — but stay as
  // placeholders while a run is actually in flight.
  const detailResult = state.phase === 'loading' ? null : shownResult;
  const detailStatus = detailResult ? classifyRunStatus(detailResult) : null;

  const aside =
    detailResult && detailStatus ? (
      <ExecutionPanel response={detailResult} status={detailStatus} />
    ) : (
      <ExecutionPreview phase={previewPhase} />
    );

  return (
    <AppShell
      banner={
        <StatusBanner
          health={health}
          phase={healthPhase}
          timedOut={healthTimedOut}
          apiMode={agentClient.mode}
          isRefreshing={healthRefreshing}
          onRefresh={refreshHealth}
        />
      }
      sidebar={
        <CapabilitySidebar
          selectedIntent={selectedIntent}
          onSelectCapability={handleSelectCapability}
        />
      }
      main={main}
      aside={aside}
      onReset={handleReset}
    />
  );
}
