# Per-agent model and reasoning preferences

Open Agents, select a teammate, then use Model & reasoning in its details drawer. Choose Model, choose a supported Reasoning effort, and Save preferences. Runtime default / Model default preserve Codex defaults. Use defaults resets the form; Save commits it.

The model list comes from the authenticated Codex SDK catalog (`client.models()`), not a hard-coded list. A missing sign-in/runtime or old backend displays an error with a refresh control; it never substitutes a made-up catalog. The backend checks model availability and supported reasoning before saving. Preferences persist separately per agent in SQLite `agent_settings` records. Both Office and Agents use the same details drawer.

Preferences are captured when a run/retry is queued. Saving during a run affects subsequent runs only. Explicit model selection goes to `thread_start(model=...)`; explicit reasoning goes to `thread.turn(effort=...)`. Run history and runtime-start events retain the requested settings. Default means runtime-selected; it does not assert a resolved model name. This change does not enable tools or change workspace permissions.

API: `GET /api/models`; `POST /api/agents/{id}/settings` with `{ "model": "catalog-model-id", "reasoning": "supported-value" }`, or null/null for defaults. Existing session/origin protection applies.

Validation: frontend production build, five isolated backend contract tests covering invalid pairs, independent persistence, SDK parameter forwarding, queue-time capture, API validation/reset/state. No paid inference used. Browser visual verification was unavailable because local browser use is disabled in Work settings.

## Current capability limitations

The snapshot-only design is application policy, not an OpenAI model requirement. It blocks native tools and supplies a bounded file index/snapshot. Agents cannot search omitted files, inspect a real process or execute a build. Snapshot selection is not task-relevance-based; oversized/missing files can omit needed context. Each task starts a fresh ephemeral thread and receives summaries of previous completed work. Docker-free mode uses manual project test verification. Higher reasoning alone cannot replace missing workspace access or real verification.

A later capability upgrade should add workspace-scoped read/list/search tools, controlled approved edits, approved local build/test commands with logs/timeouts, task-relevant context and end-to-end acceptance checks. Do not simply enable unrestricted host shell access.

Official protocol reference: https://learn.chatgpt.com/docs/app-server (Models and thread/turn configuration).
