"""
office_agent.run_settings — request-scoped run settings for one Office Agent request.

A caller may ask for a stricter run (`OfficeRunOptions`); this module resolves that
request against the server's own policy and reports, honestly, what actually governed
the run.

Two rules define the whole module:

1. **Server policy always wins.** A request may only ever *restrict* execution. It can
   turn an external service off; it can never turn one on that the server has
   disabled. This mirrors the runtime privacy hierarchy in ADR 019, one level lower:
   `OFFLINE_MODE` > `PRIVACY_MODE` > server flags > **per-request options**.
2. **Nothing here mutates anything.** Resolution is a pure function over frozen
   dataclasses, with the server policy passed in as explicit arguments. No
   environment variable, module global, or process-wide setting is read or written
   during resolution, so two concurrent requests with opposite settings cannot
   interfere.

The resolved result separates four distinct questions, because collapsing them is
what makes observability dishonest:

- `requested` — what the caller asked for.
- `effective` — what actually governed the run.
- `applicability` — whether the setting even applies to the routed capability
  (LLM assist applies to Email Summary / Daily Briefing; web search applies to
  Knowledge Q&A). A setting that does not apply is reported as not applicable
  rather than as "used".
- `constraints` — typed reasons why `requested` and `effective` differ.
"""

from dataclasses import dataclass, field

from office_agent.schemas import (
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
)

# Per-request privacy levels. `strict` is the request-scoped analogue of the server's
# PRIVACY_MODE: it restricts this run only and writes nothing back to the environment.
PRIVACY_STANDARD = "standard"
PRIVACY_STRICT = "strict"
RUN_PRIVACY_MODES = (PRIVACY_STANDARD, PRIVACY_STRICT)

# Typed constraint reasons. Stable identifiers, not prose: the UI maps them to text.
CONSTRAINT_SERVER_OFFLINE_MODE = "server_offline_mode"
CONSTRAINT_SERVER_PRIVACY_MODE = "server_privacy_mode"
CONSTRAINT_REQUEST_PRIVACY_STRICT = "request_privacy_strict"
CONSTRAINT_SERVER_LLM_ASSIST_DISABLED = "server_llm_assist_disabled"
CONSTRAINT_SERVER_WEB_SEARCH_DISABLED = "server_web_search_disabled"
CONSTRAINT_LLM_ASSIST_NOT_APPLICABLE = "llm_assist_not_applicable"
CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE = "web_search_not_applicable"

# Canonical ordering, so the constraint list is deterministic and testable.
# Broadest cause first: a server mode explains more than a per-setting flag.
_CONSTRAINT_ORDER = (
    CONSTRAINT_SERVER_OFFLINE_MODE,
    CONSTRAINT_SERVER_PRIVACY_MODE,
    CONSTRAINT_REQUEST_PRIVACY_STRICT,
    CONSTRAINT_SERVER_LLM_ASSIST_DISABLED,
    CONSTRAINT_SERVER_WEB_SEARCH_DISABLED,
    CONSTRAINT_LLM_ASSIST_NOT_APPLICABLE,
    CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE,
)

# Which capabilities each optional external path can apply to.
LLM_ASSIST_INTENTS = frozenset({INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING})
WEB_SEARCH_INTENTS = frozenset({INTENT_KNOWLEDGE_QA})


@dataclass(frozen=True)
class OfficeRunOptions:
    """What one caller asked for. Frozen: a run's options cannot drift mid-run.

    Defaults are the conservative ones (standard privacy, both external paths
    off), so constructing this type never silently enables anything.
    """

    privacy_mode: str = PRIVACY_STANDARD
    llm_assist: bool = False
    web_search: bool = False


@dataclass(frozen=True)
class RunSettingsValues:
    """One coherent set of settings — used for both `requested` and `effective`."""

    privacy_mode: str
    llm_assist: bool
    web_search: bool


@dataclass(frozen=True)
class RunSettingsApplicability:
    """Whether each optional path applies to the routed capability at all."""

    llm_assist: bool
    web_search: bool


@dataclass(frozen=True)
class ResolvedRunSettings:
    """The full, honest account of one run's settings."""

    requested: RunSettingsValues
    effective: RunSettingsValues
    applicability: RunSettingsApplicability
    constraints: tuple[str, ...] = field(default_factory=tuple)


def resolve_run_settings(
    intent: str,
    options: OfficeRunOptions,
    *,
    server_privacy_mode: bool,
    server_offline_mode: bool,
    server_llm_assist_available: bool,
    server_web_search_available: bool,
) -> ResolvedRunSettings:
    """Resolve `options` for `intent` against the server's policy.

    Pure: server policy arrives as arguments rather than being read here, which
    keeps the precedence rules testable in isolation and guarantees resolution
    touches no process-wide state.

    The two `server_*_available` flags are expected to be the *effective* server
    values (the existing readers already fold the runtime privacy modes into
    them), so this function only has to add the request-scoped restriction.
    """

    requested = RunSettingsValues(
        privacy_mode=_normalize_privacy(options.privacy_mode),
        llm_assist=options.llm_assist,
        web_search=options.web_search,
    )

    # A server mode forces strict; otherwise the request decides. Either way the
    # result can only be equal to or stricter than what was asked for.
    server_forces_strict = server_privacy_mode or server_offline_mode
    effective_privacy = (
        PRIVACY_STRICT
        if server_forces_strict or requested.privacy_mode == PRIVACY_STRICT
        else PRIVACY_STANDARD
    )

    applicability = RunSettingsApplicability(
        llm_assist=intent in LLM_ASSIST_INTENTS,
        web_search=intent in WEB_SEARCH_INTENTS,
    )

    strict = effective_privacy == PRIVACY_STRICT
    effective_llm_assist = (
        requested.llm_assist
        and applicability.llm_assist
        and server_llm_assist_available
        and not strict
    )
    effective_web_search = (
        requested.web_search
        and applicability.web_search
        and server_web_search_available
        and not strict
    )

    constraints: set[str] = set()

    # Privacy was escalated beyond what the caller asked for.
    if requested.privacy_mode == PRIVACY_STANDARD and effective_privacy == PRIVACY_STRICT:
        constraints.add(_mode_constraint(server_offline_mode))

    if requested.llm_assist and not effective_llm_assist:
        constraints.add(
            _blocked_reason(
                applicable=applicability.llm_assist,
                server_available=server_llm_assist_available,
                server_offline_mode=server_offline_mode,
                server_privacy_mode=server_privacy_mode,
                requested_strict=requested.privacy_mode == PRIVACY_STRICT,
                not_applicable=CONSTRAINT_LLM_ASSIST_NOT_APPLICABLE,
                server_disabled=CONSTRAINT_SERVER_LLM_ASSIST_DISABLED,
            )
        )

    if requested.web_search and not effective_web_search:
        constraints.add(
            _blocked_reason(
                applicable=applicability.web_search,
                server_available=server_web_search_available,
                server_offline_mode=server_offline_mode,
                server_privacy_mode=server_privacy_mode,
                requested_strict=requested.privacy_mode == PRIVACY_STRICT,
                not_applicable=CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE,
                server_disabled=CONSTRAINT_SERVER_WEB_SEARCH_DISABLED,
            )
        )

    return ResolvedRunSettings(
        requested=requested,
        effective=RunSettingsValues(
            privacy_mode=effective_privacy,
            llm_assist=effective_llm_assist,
            web_search=effective_web_search,
        ),
        applicability=applicability,
        constraints=tuple(reason for reason in _CONSTRAINT_ORDER if reason in constraints),
    )


def _normalize_privacy(value: str) -> str:
    """Fall back to the safe level for anything unrecognized.

    The API validates this field, so an unknown value can only arrive from a
    direct Python caller — where defaulting to `standard` (rather than raising)
    keeps the engine's contract total. It never *weakens* anything: standard
    still defers entirely to server policy.
    """

    return value if value in RUN_PRIVACY_MODES else PRIVACY_STANDARD


def _mode_constraint(server_offline_mode: bool) -> str:
    """Name the server mode responsible, offline first (it is the stronger one)."""

    return CONSTRAINT_SERVER_OFFLINE_MODE if server_offline_mode else CONSTRAINT_SERVER_PRIVACY_MODE


def _blocked_reason(
    *,
    applicable: bool,
    server_available: bool,
    server_offline_mode: bool,
    server_privacy_mode: bool,
    requested_strict: bool,
    not_applicable: str,
    server_disabled: str,
) -> str:
    """Pick the single most explanatory reason a requested setting did not apply.

    Order matters: "this capability never had that path" is more informative
    than "policy blocked it", and a server mode is more informative than the
    per-setting flag it already forced off.
    """

    if not applicable:
        return not_applicable
    if server_offline_mode:
        return CONSTRAINT_SERVER_OFFLINE_MODE
    if server_privacy_mode:
        return CONSTRAINT_SERVER_PRIVACY_MODE
    if not server_available:
        return server_disabled
    if requested_strict:
        return CONSTRAINT_REQUEST_PRIVACY_STRICT
    return server_disabled
