Plan/Requirements: Textual-based TUI for AAP/AWX 2.5 (User-Facing Features Only)

1) Goals & Scope

Goal: A fast, keyboard-first terminal app (built with Textual) that lets a logged-in AAP/AWX user do their daily work: browse resources, launch jobs/workflows, view/stream logs, manage personal schedules, and inspect results — without platform administration (no system settings, org/user admin, SSO/LDAP, licensing).

Explicitly out of scope (v1): Platform-wide admin (Users/Teams/Orgs CRUD, RBAC editing, Credentials type definitions, System settings, SSO, LDAP, Execution Environment builds, Controller config), content signing, Pulp/AH admin, instance groups admin.

Assumptions:
	•	Connects to an existing AAP Controller/AWX 2.5 via REST API.
	•	Uses user-scoped auth (personal token or OAuth2 token).
	•	Respects server-side RBAC (read-only where needed).

⸻

2) Core User Journeys
	1.	Login & Connect
	•	Configure multiple controller profiles; quick switch.
	•	Token-based auth; secure local storage.
	2.	Discover Resources
	•	Browse/search: Projects, Inventories, Hosts, Groups, Credentials (view only), Job Templates, Workflow Job Templates, Schedules, Recent Jobs/Workflows.
	3.	Run Jobs/Workflows
	•	Launch with survey prompts, limit, tags/skip-tags, verbosity, EE selection, diff mode, credential override (if allowed).
	•	Track live status and stream ANSI logs; follow/unfollow.
	4.	Inspect Results
	•	Job summary, host/task breakdown, changed/failed stats, artifacts, resurface failed task traceback.
	•	Re-run with same params; relaunch-on-fail.
	5.	Schedules (User Scope)
	•	View existing schedules; enable/disable; create personal schedules where permitted by RBAC.
	6.	Ad-hoc Commands
	•	Module + args, inventory/limit, become/verbosity, EE; stream output.
	7.	Notifications & Activity
	•	Read notifications tied to the user; view activity stream per object.
	8.	Optional (toggleable) EDA
	•	If EDA Controller is present: list rulebooks/rule sets, activations, logs, enable/disable activations (no global admin).

⸻

3) Functional Requirements

3.1 Authentication & Profiles
	•	Multiple controller profiles: {name, base_url, verify_ssl, token_kind, token, timeout}.
	•	Login flow to exchange username/password ⇢ token (stored securely).
	•	Token refresh and expiry handling.
	•	Secret storage: OS keyring first; fallback to an encrypted file (age/fernet).

3.2 Navigation & Search
	•	Global search (⌘/Ctrl+K) across resource types with fuzzy matching.
	•	Left sidebar: resource tree and saved views (filters).
	•	Tabs/workspaces: open multiple resources (e.g., job run + inventory page).

3.3 Resources (Read)
	•	Projects: list/sync + last update status, branch, SCM.
	•	Inventories: list, vars preview, hosts/groups, smart inventories.
	•	Hosts: facts, recent job outcomes, enable/disable.
	•	Credentials: view (metadata only), not secrets.
	•	Job Templates: parameters, defaults, survey; launch permissions.
	•	Workflow Job Templates: graph view (ASCII/compact), node details.
	•	Schedules: list/detail; enable/disable.
	•	Jobs/Workflow Jobs: status, timings, artifacts, stdout, events, host/task stats.
	•	Notification Templates: list + recent sends (read-only).

3.4 Actions (Write, user-scoped)
	•	Launch Job Template and Workflow Job Template.
	•	Survey prompts UI with validation.
	•	Extra vars editor (YAML/JSON) with linting and preview.
	•	Tags/skip-tags pickers; limit; verbosity; diff; EE picker.
	•	Ad-hoc command runner.
	•	Schedule create/update if RBAC allows (otherwise read-only).
	•	Project sync; inventory source update (if permitted).
	•	Host enable/disable; relaunch job; re-run on failed.

3.5 Job Output
	•	Live log streaming with pause, search, filter by host/status/task.
	•	Colorized ANSI, soft-wrap toggle, copy/export (txt/ansi).
	•	Event/host panels with failure drill-down; quick “open failing task” jump.

3.6 Security & Compliance
	•	Never prints secrets; credentials masked.
	•	All actions gated by server-side RBAC; app mirrors permission errors cleanly.
	•	Audit trail: local action log (optional) with redaction.

3.7 Configuration
	•	~/.config/aap-tui/config.toml (profiles, UI prefs).
	•	~/.local/state/aap-tui/ cache (ETag-aware) + logs.
	•	Proxy, CA bundle, timeout, retries.

3.8 Extensibility
	•	Provider plugin system (entry points): controller, eda, future “other controllers”.
	•	Command palette extensions per plugin.
	•	Custom renderers for artifacts (e.g., JSON/YAML viewers, diff viewer).

⸻

4) Non-Functional Requirements
	•	Performance: First list view ≤ 1.5s on typical corp networks; paging for big resources; lazy-load details.
	•	Resilience: Retries with backoff; offline read from cache (stale banner).
	•	Accessibility: Full keyboard control; high-contrast theme; screen-reader friendly labels.
	•	Portability: Linux/macOS/WSL; Python ≥3.10.
	•	Observability: Structured debug logs; --verbose increases detail.

⸻

5) Architecture

5.1 High-Level
	•	TUI Layer (Textual): screens, widgets, routing, keybinds, command palette.
	•	Domain Layer: Resource models (Projects, JTs, Jobs…) and use-cases (launch, sync, stream).
	•	API Client Layer: httpx for REST, optional websockets/SSE for logs; pagination helpers; type-safe DTOs via pydantic.
	•	Storage: Config (toml), cache (sqlite or diskcache), keyring.
	•	Plugins: pluggy or entry points for optional providers.

5.2 API Surfaces (Controller)
	•	REST endpoints for: projects, inventories, hosts, credentials (read), job_templates, workflow_job_templates, schedules, jobs, job_events, notifications.
	•	Stdout endpoints with ?format=txt|ansi for streaming; fall back to poll events.
	•	Respect page_size, next, results patterns.

⸻

6) Textual UX Design

Layout:
	•	Header: profile, cluster health, context breadcrumbs, quick actions.
	•	Left Sidebar: resource tree + saved filters.
	•	Main: list/detail split view; press Enter to drill-in; Tab cycles panes.
	•	Bottom Bar: key hints (e.g., L=Launch, F=Filter, /=Search, g g=Top).

Keybinds (core):
	•	Global: Ctrl+K (command palette), / (search), ? (help), q (back/quit), : (action prompt).
	•	List: ↑/↓ select, Enter open, f filter, r refresh.
	•	Job detail: L relaunch, s follow logs, S stop follow, =/- change verbosity filter, e export.

Widgets:
	•	Smart table (virtualized rows), pill statuses, progress bars for running jobs, popover forms (surveys), YAML/JSON editors, log viewer with incremental append.

⸻

7) Data & Caching
	•	ETag/Last-Modified for lists; per-object TTLs (e.g., 30s running, 5m completed).
	•	SQLite cache for large tables (hosts/events).
	•	Offline read-only mode.

⸻

8) Security Details
	•	Use system keyring for tokens (keyring lib). If unavailable, encrypt with libsodium/fernet; protect with file perms.
	•	Mask values in logs/UI.
	•	Optional enterprise CA bundle per profile.

⸻

9) Packaging & DX
	•	pipx install aap-tui.
	•	Tooling: ruff, mypy, pytest (+ pytest-httpx), textual-dev for live preview.
	•	CI: pre-commit hooks, wheels for platforms, reproducible builds.
	•	Telemetry opt-in (anonymous) if desired; documented.

⸻

10) Testing Strategy
	•	Unit: API client (happy-path + error codes), parsers, cache, formatters.
	•	TUI: snapshot tests with textual test helpers.
	•	Integration: Against a local AWX container (docker) with seeded data; golden outputs for common screens.
	•	E2E scripts: scripted journeys (launch JT, stream logs, re-run failed).

⸻

11) Milestones (Execution Order)
	1.	Bootstrap & Auth
	•	Config, profiles, keyring, base API client, health check.
	2.	Core Read Views
	•	Projects, Inventories, Job Templates, Jobs (lists + details).
	3.	Launch Flow
	•	Surveys, extra vars editor, run tracking, live log viewer.
	4.	Workflows
	•	WJT list/detail, graph view, launch & follow.
	5.	Ad-hoc & Schedules
	•	Ad-hoc runner; read/enable/disable schedules; create if permitted.
	6.	Search & Filters
	•	Global search, saved views, quick filters.
	7.	Polish & Perf
	•	Virtualized tables, caching, error toasts, accessibility.
	8.	Optional EDA Module
	•	Activations list/detail, enable/disable, logs.
	9.	Docs & Release
	•	--help, quickstart, config reference, troubleshooting.

⸻

12) Acceptance Criteria (v1)
	•	Can add a controller profile, authenticate, and persist token securely.
	•	Can browse Projects, Inventories, JTs, WJTs, Jobs with pagination.
	•	Can launch a JT and WJT with surveys, watch logs live, and export stdout.
	•	Can run ad-hoc commands and view results.
	•	Can view schedules and enable/disable when permitted.
	•	All sensitive values are masked; RBAC errors are surfaced clearly.
	•	Works on macOS/Linux terminals; no crashes under slow network conditions.

⸻

13) Risks & Mitigations
	•	Large datasets (hosts/events): virtualized lists + server-side filters.
	•	Log streaming variants: support both streaming (if available) and polling fallback.
	•	RBAC variability: treat 403/401 distinctly; degrade gracefully with read-only states.
	•	Token storage on headless servers: provide env-var token mode.