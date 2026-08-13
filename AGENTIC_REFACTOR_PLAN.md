# Job Search Studio — Agentic Refactor Plan

Status: accepted for implementation  
Date: 2026-08-13

## Product outcome

Deliver a private, evidence-first job-search operating system that:

1. maintains a verified, living candidate profile;
2. discovers and normalizes fresh jobs from compliant sources;
3. ranks opportunities with hard gates, decomposed fit signals, citations, gaps, and confidence;
4. guides the user through an explicit application state machine;
5. prepares claim-safe resumes and cover letters after approval;
6. renders versioned PDF artifacts through Gotenberg; and
7. exposes the system through a calm workbench and a conversational concierge.

## Architecture decisions

- PostgreSQL remains the canonical source of truth. Agents never own private state.
- Django domain services expose typed, owner-scoped commands used by both REST APIs and agents.
- Celery/Redis provides durable execution, retries, scheduling, and resumability.
- Agent execution is recorded as runs and steps with typed inputs/outputs, cost metadata, and errors.
- Human approval is mandatory before storing uncertain candidate facts, preparing application materials, or marking an application as applied.
- The OpenAI Responses API is used for structured extraction and bounded specialist judgment. Deterministic fallbacks keep the local application usable without an API key.
- Vector similarity is a retrieval signal, not an authority. Structured records and source spans are authoritative.
- Existing records and endpoints are extended rather than discarded.

## Domain migration

### Candidate intelligence

- Add one `CandidateProfile` per user for headline, goals, location, authorization, compensation, work-mode, and completeness.
- Extend `ProfileFact` with lifecycle, evidence quote, dates, strength, and user notes.
- Add `CandidatePreference` with category, importance, desired/avoided values, and verification.

### Sourcing

- Add `SourceRun` for execution status and metrics.
- Add immutable `JobPostingVersion` snapshots.
- Add structured `JobRequirement` rows for hard/soft requirements.
- Implement manual, RSS, Greenhouse, Lever, and Ashby connector contracts.

### Matching

- Add `MatchSignal` records for eligibility, skills, evidence, direction, domain, and logistics.
- Compute hard-filter status separately from fit.
- Preserve supporting fact citations and confidence.

### Application materials

- Add `CoverLetter` drafts with approval and validation.
- Version artifacts with checksums and MIME type.
- Render resume and cover-letter HTML through Gotenberg; retain an HTML fallback artifact when Gotenberg is unavailable.

### Agent runtime and conversation

- Add `ConversationThread`, `ConversationMessage`, `AgentRun`, `AgentStep`, and `ApprovalRequest`.
- Implement specialist workflows: Profile Steward, Sourcing Scout, Match Analyst, Application Coach, Document Tailor, and Search Concierge.
- Keep every run bounded, owner-scoped, idempotent, observable, and interruptible.

## Experience migration

- Replace the generic dashboard with a daily briefing and prioritized review queue.
- Add a persistent concierge panel with suggested prompts and inline approval cards.
- Turn matches into an opportunity inbox with eligibility, score decomposition, citations, gaps, freshness, and one clear decision.
- Turn the pipeline into an application workspace with stage-specific next actions.
- Turn Resume Lab into a document studio for resume/cover-letter review, claim warnings, approval, and PDF download.
- Keep advanced source, strategy, and artifact views available without dominating the primary loop.

## Delivery sequence

1. Domain models and data migration.
2. Modular domain services and connector contract.
3. Durable agent runtime, approvals, and conversations.
4. REST/realtime surface.
5. Angular experience refactor.
6. Gotenberg and deployment integration.
7. Tests, seeded demo journey, documentation, and final build verification.

## Acceptance criteria

- A new user can create a candidate profile and ingest source material.
- The system extracts facts and makes uncertain facts reviewable.
- A source run imports, versions, deduplicates, normalizes, and scores jobs.
- Every match shows eligibility, fit components, evidence, gaps, and confidence.
- Approving an opportunity can create an application and prepare both document drafts.
- Unsupported document claims are visible and block final approval.
- Approved documents can be rendered and downloaded as PDFs.
- Conversation messages can trigger bounded specialist runs and create approval requests.
- Long-running work is observable over the existing realtime channel.
- All APIs enforce owner isolation.
- Backend tests and the production Angular build pass.
