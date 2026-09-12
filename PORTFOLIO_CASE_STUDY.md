# AI Knowledge & Operations Agent — Case Study

## Problem

An internal assistant can answer questions quickly, but an assistant that is
allowed to influence operational work cannot be trusted to make every decision
freely. Company facts change, operational calculations need consistent rules,
and sensitive actions may require a manager's judgment.

The project goal was to build a small internal AI system that is useful to
employees while keeping knowledge, operations, identity, approval, and
execution boundaries explicit.

The public demo uses fictional Northstar Atelier information. It does not
contain real company knowledge, customer records, or external business
integrations.

## Design Goals

- Ground answers in retrieved knowledge rather than model memory.
- Keep operational calculations deterministic.
- Require human approval for sensitive actions.
- Make behavior measurable through traces and cost estimates.
- Keep the high-risk rules testable without a live model.
- Separate private local knowledge from public demo data.
- Preserve a maintainable architecture that is easy to inspect.

## Engineering Approach

The system was developed as a sequence of increasingly constrained
capabilities rather than as one giant one-shot AI generation:

1. semantic vector search;
2. RAG over structured document chunks;
3. document extraction and section-aware chunking;
4. retrieval evaluation utilities;
5. a tool-calling agent;
6. deterministic operational tools;
7. multi-tool flows;
8. human approval requests;
9. protected execution;
10. regression and contract tests;
11. observability and cost tracking;
12. a FastAPI and React web application;
13. employee/approver RBAC;
14. Docker and offline CI.

This progression made it possible to test each boundary before adding the next
one.

## Important Engineering Decisions

### PostgreSQL + pgvector instead of a separate vector database

The demo already needs PostgreSQL for application data. Using pgvector keeps
the knowledge store in one operational system and avoids adding an extra
service before the product needs one.

### No LangChain or LangGraph dependency for core orchestration

The core loop is intentionally implemented in Python. That makes model
messages, tool arguments, validation, and error handling visible to the
maintainer instead of hiding the most important control flow behind a
framework abstraction.

### Manual tool-calling loop for transparency

The model can select from a small allowlist, while Python parses arguments,
executes the function, records the result, and decides what state can change.
The loop is simple enough to reason about and test.

### Python security boundaries instead of trusting the model

The model does not receive authority to approve or execute. Python controls
canonical approval types, authenticated identities, persisted status,
allowlisted actions, and duplicate execution checks.

### Human approval separated from model authority

`request_human_approval` creates a pending request. It does not grant
approval. The decision comes through the approval API from an authenticated
approver, and execution resumes only after backend validation.

### Offline tests separated from live model evaluations

Approval, RBAC, API, observability, and repository-safety tests should be
repeatable and inexpensive. Live retrieval and model evaluation remain
separate because they need runtime credentials and introduce external
variability.

### Private/public knowledge separation

The public repository contains only fictional sample knowledge. Private local
documents, extracted text, runtime approvals, executions, traces, screenshots,
and evaluation artifacts are ignored and excluded from Docker build input.

## Bugs Found Through Integration Testing

These sanitized issues were more instructive than a happy-path demo because
they exposed the difference between component correctness and end-to-end
correctness.

### 1. Preview-platform request interception

During browser testing, a private preview layer intercepted POST requests.
The application process was healthy, but platform shielding caused browser
CORS failures.

The lesson was to distinguish application behavior from preview or deployment
transport behavior before changing API code.

### 2. Approval type contract mismatch

An early model response generated a noncanonical approval type. The human
decision was persisted, but protected execution later failed because the
workflow expected a different internal action contract.

The fix was to:

- make the canonical approval type controlled by Python;
- stop allowing the model to choose internal approval types;
- validate the workflow contract before mutating approval state;
- return an honest `retry_required` or failed execution state instead of
  implying success.

### 3. Requester self-approval

An earlier single-admin flow allowed the person who requested an action to
approve their own request. That was a business-design problem, not a model
quality problem.

The fix was to:

- separate employee and approver roles;
- derive `requested_by` from the authenticated requester session;
- derive `decided_by` from the authenticated approver session;
- reject approval when both identities match in the backend.

These issues demonstrate why integration testing matters. Unit tests can show
that each function works in isolation while a complete user flow still
contains a dangerous contract or authorization gap.

## Testing Strategy

The test strategy separates deterministic safeguards from live AI evaluation:

- offline safety tests for approval and execution invariants;
- agent tool-contract tests;
- API, authentication, and RBAC tests;
- observability and cost-calculation tests;
- production configuration tests;
- public-repository privacy tests;
- regression-threshold contracts.

Current local result:

```text
123 offline tests passing
```

No coverage percentage is claimed. Live model evaluation is intentionally
separate from offline CI and is not required to validate the deterministic
workflow safeguards.

## Security and Privacy

The public candidate applies several practical controls:

- environment variables or a secrets manager for runtime credentials;
- fresh public Git history after a publication audit;
- fictional Northstar Atelier demo data;
- ignored approval, execution, and trace records;
- non-root Docker runtime;
- no secrets baked into the image;
- protected-action allowlists;
- server-session-derived RBAC identities;
- no automatic private-data ingestion during Docker startup.

An early credential-history issue was detected during the publication audit.
The credential was rotated, and the contaminated history was isolated before
preparing the fresh public history. The credential value is not part of this
documentation or repository.

## What I Learned

I learned that LLM quality alone is not enough for an internal operations
system. The useful engineering work is in the boundaries: what the model can
request, what Python must validate, which identity is authoritative, and what
state is allowed to change.

Deterministic tools make operational behavior easier to trust. Observability
and evaluation make failures easier to explain. Integration tests reveal
platform and workflow issues that unit tests cannot see. Product logic matters
as much as technical correctness: requester and approver are different roles,
and "approval requested" is not the same as "action approved."

## Current Limitations

- Authentication is a portfolio-stage demo, not enterprise IAM.
- Approval and execution records use local JSON stores.
- The protected action is simulated and local.
- Conversation history is not persisted.
- There are no production external business integrations.
- The system is not an enterprise deployment.
- Live model evaluation is separate from the offline CI path.

## Next Steps

Realistic next steps would be:

- add persistent conversation history with retention controls;
- replace demo authentication with an enterprise identity provider;
- move users and approval records to managed database tables;
- add carefully scoped external actions behind integration-specific policies;
- expand retrieval evaluation and feedback workflows;
- add production monitoring, deployment controls, and operational runbooks.