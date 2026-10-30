import Dropdown from "./components/Dropdown";
import { useEffect, useState, type FormEvent } from "react";
import AgentSettingsDrawer from "./components/AgentSettingsDrawer";
import { useDrawerPresence } from "./useDrawerPresence";
import {
  Activity,
  ArrowDownLeft,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  Cloud,
  Code2,
  Coffee,
  Compass,
  Database,
  ExternalLink,
  FlaskConical,
  FolderGit2,
  Home,
  ListTodo,
  Pause,
  Play,
  Plus,
  Settings,
  Search,
  Users,
  Layers3,
  ShieldCheck,
  Terminal,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import Avatar from "./components/Avatar";
import WorkflowDialog from "./components/WorkflowDialog";
import "./workflow-dialog.css";
import AgentModelSettings from "./components/AgentModelSettings";
import "./agent-model-settings.css";
import AppHeader from "./components/AppHeader";
import NewProjectModal from "./components/NewProjectModal";
import OfficeView from "./components/OfficeView";
import { ProjectFolder, DeleteProjectModal } from "./components/ProjectActions";
import {
  api,
  connectOffice,
  roles,
  useOffice,
  type Approval,
  type Project,
  type Task,
} from "./store";
import "./style.css";
import "./office-theme.css";
import "./workspace-theme.css";
import "./navbar.css";
import "./new-project-modal.css";
import "./light-shell.css";
import "./drawer-motion.css";
import "./planner-dialog.css";

const icons: Record<string, typeof Home> = {
  planner: Compass,
  frontend: Code2,
  backend: Database,
  qa: FlaskConical,
  devops: Cloud,
  reviewer: ShieldCheck,
};
export type Page =
  | "Office"
  | "Projects"
  | "Tasks"
  | "Agents"
  | "Activity"
  | "Settings";
const statusLabel = (s: string) =>
  ({
    idle: "Ready when you are",
    running: "Working",
    queued: "Queued",
    awaiting_approval: "Needs your approval",
    completed: "Completed",
    skipped: "Skipped",
    failed: "Needs attention",
    blocked: "Blocked",
    pending: "To do",
    cancelled: "Cancelled",
    interrupted: "Interrupted",
  })[s] ?? s;
export default function App() {
  const [page, setPage] = useState<Page>("Office"),
    [newProject, setNewProject] = useState(false),
    [deleteProject, setDeleteProject] = useState<Project | null>(null),
    [projectId, setProjectId] = useState(""),
    [plannerProject, setPlannerProject] = useState<Project | null>(null),
    [plannerMessage, setPlannerMessage] = useState(""),
    [plannerSending, setPlannerSending] = useState(false),
    [toast, setToast] = useState(""),
    [taskSearch, setTaskSearch] = useState(""),
    [eventSearch, setEventSearch] = useState(""),
    [account, setAccount] = useState<{
      connected: boolean;
      plan?: string;
      error?: string;
    }>({ connected: false }),
    [effects, setEffects] = useState(
      localStorage.getItem("natee-effects") !== "false",
    ),
    [diagnostics, setDiagnostics] = useState<
      Record<string, { ready: boolean; message?: string }>
    >({}),
    [checking, setChecking] = useState(false),
    [authUrl, setAuthUrl] = useState(""),
    [approval, setApproval] = useState<Approval | null>(null),
    [clock, setClock] = useState(new Date());
  const [workflowProject, setWorkflowProject] = useState<Project | null>(null);
  const [agentSettingsOpen, setAgentSettingsOpen] = useState(false);
  const state = useOffice();
  const project = state.projects.find((p) => p.id === projectId);
  const projectTasks = state.tasks.filter((t) => t.project_id === project?.id);
  const visibleTasks = projectTasks.filter((t) =>
    `${t.title} ${t.description} ${t.agent_id}`
      .toLowerCase()
      .includes(taskSearch.trim().toLowerCase()),
  );
  const visibleEvents = state.events.filter((e) =>
    `${e.type} ${e.message ?? ""} ${e.agent_id ?? ""} ${e.tool ?? ""}`
      .toLowerCase()
      .includes(eventSearch.trim().toLowerCase()),
  );
  const pending = state.approvals.filter((a) => a.status === "pending");
  const agentPanel = useDrawerPresence(state.agents.find((a) => a.id === state.selected));
  const settingsPanel = useDrawerPresence(agentSettingsOpen ? true : null);
  const selected = agentPanel.value;
  useEffect(() => connectOffice(), []);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setNewProject(false);
        setPlannerProject(null);
        setApproval(null);
        useOffice.getState().select(null);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  useEffect(() => {
    if (state.online)
      void api<typeof account>("/account")
        .then(setAccount)
        .catch(() => {});
  }, [state.online]);
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 30000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(""), 7000);
      return () => clearTimeout(t);
    }
  }, [toast]);
  const action = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      await state.refresh();
    } catch (e) {
      setToast((e as Error).message);
    }
  };
  const run = (t: Task) => action(() => api("/tasks/" + t.id + "/run", {}));
  const changePage = (p: Page) => {
    setPage(p);
    state.select(null);
  };
  return (
    <div
      className={
        "app light-shell " +
        (page === "Office" ? "office-mode" : "workspace-mode")
      }
      data-page={page.toLowerCase()}
    >
      <AppHeader
        page={page}
        onPage={changePage}
        online={state.online}
        clock={clock}
        pending={pending.length}
        onApprovals={() =>
          pending[0]
            ? setApproval(pending[0])
            : setToast("You’re all caught up. No approvals waiting.")
        }
        onNewProject={() => setNewProject(true)}
      />
      <main
        key={page}
        className={page === "Office" ? "office-main" : "workspace-main"}
      >
        {page !== "Office" && (
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span /> WORKSPACE <ChevronRight size={13} />{" "}
                {page.toUpperCase()}
              </div>
              <h1>
                {page === "Projects"
                  ? "Projects"
                  : page === "Tasks"
                    ? "Task board"
                    : page === "Agents"
                      ? "Your AI team"
                      : page === "Activity"
                        ? "Activity log"
                        : "Workspace settings"}
              </h1>
              <p>
                {page === "Projects"
                  ? "Everything you’re building, in one place."
                  : page === "Tasks"
                    ? "Plan, follow progress, and keep your next step in focus."
                    : page === "Agents"
                      ? "Six specialists, working together on your next idea."
                      : page === "Activity"
                        ? "Follow agent runs, approvals, and every step along the way."
                        : "Your account, environment, and office preferences."}
              </p>
            </div>
            {page === "Projects" && <div className="heading-actions">
              <button className="primary new-project-button" onClick={() => setNewProject(true)}>
                <Plus size={16} />
                New project
              </button>
            </div>}
            {page === "Agents" && <div className="heading-actions">
              <button className="secondary" onClick={() => { state.select(null); setAgentSettingsOpen(true); }}>
                <Settings size={16} /> Agent settings
              </button>
            </div>}
          </div>
        )}
        {(page === "Tasks" || page === "Projects") && (
          <div className="workspace-summary" aria-label="Workspace overview">
            <div>
              <span className="summary-icon">
                <FolderGit2 size={20} />
              </span>
              <span>
                <small>Projects</small>
                <strong>{state.projects.length}</strong>
              </span>
            </div>
            <div>
              <span className="summary-icon">
                <Layers3 size={20} />
              </span>
              <span>
                <small>
                  {page === "Tasks" ? "Tasks in project" : "Total tasks"}
                </small>
                <strong>
                  {(page === "Tasks" ? projectTasks : state.tasks).length}
                </strong>
              </span>
            </div>
            <div>
              <span className="summary-icon">
                <Activity size={20} />
              </span>
              <span>
                <small>In progress</small>
                <strong>
                  {
                    state.tasks.filter((t) =>
                      ["running", "queued", "awaiting_approval"].includes(
                        t.status,
                      ),
                    ).length
                  }
                </strong>
              </span>
            </div>
            <div>
              <span className="summary-icon">
                <Users size={20} />
              </span>
              <span>
                <small>AI teammates</small>
                <strong>{state.agents.length}</strong>
              </span>
            </div>
          </div>
        )}
        {page === "Office" ? (
          <OfficeView
            effects={effects}
            onEffects={() => {
              setEffects(!effects);
              localStorage.setItem("natee-effects", String(!effects));
            }}
            onPage={changePage}
            onNewProject={() => setNewProject(true)}
          />
        ) : page === "Projects" ? (
          <div className="content-grid">
            {state.projects.map((p) => (
              <article className="project-card" key={p.id}>
                <div className="project-card-top">
                  <span className="project-icon">
                    <FolderGit2 size={24} />
                  </span>
                  <span className="mini-tag">LOCAL</span>
                </div>
                <h2>{p.name}</h2>
                <div className="project-brief">
                  <span className="field-caption">PROJECT BRIEF</span>
                  <p tabIndex={0} aria-label={p.name + " project brief"}>
                    {p.requirement}
                  </p>
                </div>
                <ProjectFolder project={p} notify={setToast} />
                <div className="project-card-actions">
                  <button
                    className="secondary"
                    onClick={() => {
                      setProjectId(p.id);
                      changePage("Tasks");
                    }}
                  >
                    Task board <ArrowRight size={14} />
                  </button>
                  <button
                    className="primary"
                    disabled={state.busy}
                    onClick={() =>
                      action(() => api("/projects/" + p.id + "/plan", {}))
                    }
                  >
                    <Compass size={15} />
                    Ask Planner
                  </button>
                  <button
                    className="secondary"
                    disabled={
                      state.busy ||
                      !state.tasks.some(
                        (t) => t.project_id === p.id && t.status === "pending",
                      )
                    }
                    onClick={() => setWorkflowProject(p)}
                  >
                    <Play size={14} />
                    Run workflow
                  </button>
                  <button
                    className="danger project-delete"
                    disabled={state.busy}
                    onClick={() => setDeleteProject(p)}
                    title={
                      state.busy
                        ? "Wait for the active run to stop"
                        : "Delete project and its workspace folder"
                    }
                  >
                    <Trash2 size={14} />
                    Delete project
                  </button>
                </div>
              </article>
            ))}
            <button
              className={
                "add-project-card " +
                (!state.projects.length ? "project-empty-state" : "")
              }
              onClick={() => setNewProject(true)}
            >
              <Plus size={28} />
              <strong>
                {state.projects.length
                  ? "Start a new project"
                  : "Your next idea starts here"}
              </strong>
              <span>
                Create a project, share your brief, and bring your AI team
                together.
              </span>
              <span className="empty-create-label">
                <Plus size={16} />
                Create project
              </span>
            </button>
          </div>
        ) : page === "Tasks" ? (
          <>
            <div className="board-filter">
              <span>
                <ListTodo size={16} /> Project board
              </span>
              <label className="search-field">
                <Search size={18} />
                <input
                  aria-label="Search tasks"
                  placeholder="Search tasks…"
                  value={taskSearch}
                  onChange={(e) => setTaskSearch(e.target.value)}
                />
              </label>
              <Dropdown
                aria-label="Filter project"
                disabled={!state.projects.length}
                value={project?.id ?? ""}
                onValueChange={setProjectId}
              >
                <option value="">Default — No project selected</option>
                {state.projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Dropdown>
              {project && (
                <button
                  className="secondary"
                  disabled={state.busy}
                  onClick={() =>
                    action(() => api("/projects/" + project.id + "/plan", {}))
                  }
                >
                  <Compass size={14} />
                  Create plan
                </button>
              )}
              {project && (
                <button
                  className="primary"
                  disabled={
                    state.busy ||
                    !projectTasks.some((t) => t.status === "pending")
                  }
                  onClick={() => setWorkflowProject(project)}
                >
                  <Play size={14} /> Run workflow
                </button>
              )}
              {project && (
                <button
                  className="secondary"
                  disabled={state.busy}
                  onClick={() => {
                    setPlannerMessage("");
                    setPlannerProject(project);
                  }}
                >
                  <Compass size={14} /> คุยกับ Planner ต่อ
                </button>
              )}
            </div>
            <div className="kanban">
              {[
                { title: "To do", statuses: ["pending", "queued"] },
                {
                  title: "In progress",
                  statuses: ["running", "awaiting_approval"],
                },
                {
                  title: "Needs attention",
                  statuses: ["failed", "blocked", "cancelled", "interrupted"],
                },
                { title: "Finished", statuses: ["completed", "skipped"] },
              ].map((col) => (
                <section className="kanban-column" key={col.title}>
                  <h3>
                    <i
                      className={
                        "status-dot " +
                        (col.title === "Finished" ? "connected" : "pending")
                      }
                    />
                    {col.title}
                    <span>
                      {
                        visibleTasks.filter((t) =>
                          col.statuses.includes(t.status),
                        ).length
                      }
                    </span>
                  </h3>
                  <div
                    className="kanban-cards"
                    tabIndex={0}
                    aria-label={col.title + " tasks"}
                  >
                    {visibleTasks
                      .filter((t) => col.statuses.includes(t.status))
                      .map((t) => (
                        <article className="task-card" key={t.id}>
                          <div className="task-top">
                            <span>{t.agent_id.toUpperCase()}</span>
                            <span>#{t.id.slice(0, 4)}</span>
                          </div>
                          <div
                            className="task-card-content"
                            tabIndex={0}
                            aria-label={t.title + " details"}
                          >
                            <h4>{t.title}</h4>
                            <p className="task-description" tabIndex={0}>
                              {t.description}
                            </p>
                            <div
                              className="criteria"
                              tabIndex={0}
                              aria-label="Acceptance criteria"
                            >
                              {t.acceptance_criteria.map((c, i) => (
                                <div key={i}>
                                  <Check size={11} />
                                  {c}
                                </div>
                              ))}
                            </div>
                            {t.depends_on.length > 0 && (
                              <small className="dependencies">
                                {t.depends_on.length} prerequisite task(s)
                              </small>
                            )}
                            {t.error && (
                              <div className="task-error">{t.error}</div>
                            )}
                            {t.result && (
                              <details>
                                <summary>Run result</summary>
                                <p>{t.result.summary}</p>
                                {t.result.findings?.map((f, i) => (
                                  <p key={i}>{f}</p>
                                ))}
                                {t.result.test_result && (
                                  <pre>{t.result.test_result.output}</pre>
                                )}
                              </details>
                            )}
                          </div>
                          <div className="task-bottom">
                            <Avatar id={t.agent_id} small />
                            {[
                              "pending",
                              "failed",
                              "blocked",
                              "cancelled",
                              "interrupted",
                            ].includes(t.status) && (
                              <button
                                className="text-link"
                                disabled={state.busy}
                                title="Skip this task and allow dependent tasks to proceed"
                                onClick={() =>
                                  action(() =>
                                    api("/tasks/" + t.id + "/skip", {}),
                                  )
                                }
                              >
                                Skip task
                              </button>
                            )}
                            {[
                              "running",
                              "queued",
                              "awaiting_approval",
                            ].includes(t.status) ? (
                              <button
                                className="text-link danger"
                                onClick={() =>
                                  action(() =>
                                    api("/tasks/" + t.id + "/cancel", {}),
                                  )
                                }
                              >
                                <Pause size={12} />
                                Cancel
                              </button>
                            ) : t.status === "skipped" ? (
                              <span className="skipped-text">Skipped</span>
                            ) : t.status !== "completed" ? (
                              <button
                                className="text-link"
                                disabled={
                                  state.busy ||
                                  t.depends_on.some(
                                    (id) =>
                                      !["completed", "skipped"].includes(
                                        state.tasks.find((d) => d.id === id)
                                          ?.status ?? "",
                                      ),
                                  )
                                }
                                onClick={() => run(t)}
                              >
                                <Play size={12} />
                                {t.attempts ? "Retry" : "Run task"}
                              </button>
                            ) : (
                              <span className="success-text">
                                <Check size={12} />
                                Done
                              </span>
                            )}
                          </div>
                        </article>
                      ))}
                    {!visibleTasks.some((t) =>
                      col.statuses.includes(t.status),
                    ) && (
                      <div className="column-empty">
                        <ListTodo size={25} />
                        <strong>
                          {taskSearch
                            ? "No matching tasks"
                            : "Nothing here yet"}
                        </strong>
                        <span>
                          {taskSearch
                            ? "Try a different search."
                            : "Tasks will appear here as your project moves forward."}
                        </span>
                      </div>
                    )}
                  </div>
                </section>
              ))}
            </div>
          </>
        ) : page === "Agents" ? (
          <div className="content-grid agents-grid">
            {state.agents.map((a) => {
              const Icon = icons[a.id];
              return (
                <button
                  className="agent-card"
                  style={{ "--agent-accent": a.color } as React.CSSProperties}
                  key={a.id}
                  onClick={() => state.select(a.id)}
                >
                  <div className="agent-card-top">
                    <Avatar id={a.id} />
                    <span className={"status-pill " + a.status}>
                      {statusLabel(a.status)}
                    </span>
                  </div>
                  <h2>{a.name}</h2>
                  <p>{a.role}</p>
                  <div className="agent-specialty">
                    <Icon size={18} style={{ color: a.color }} />
                    <span>{a.task?.title ?? "Ready for an assignment"}</span>
                    <ChevronRight size={14} />
                  </div>
                </button>
              );
            })}
          </div>
        ) : page === "Activity" ? (
          <section className="activity-page">
            <div className="section-header">
              <h2>
                <Terminal size={17} />
                Execution journal
              </h2>
              <span className="subtle">
                {visibleEvents.length} events · Stored locally
              </span>
            </div>
            <label className="search-field activity-search">
              <Search size={18} />
              <input
                aria-label="Search activity"
                placeholder="Search events, agents or messages…"
                value={eventSearch}
                onChange={(e) => setEventSearch(e.target.value)}
              />
            </label>
            <div
              className="journal-list"
              tabIndex={0}
              aria-label="Execution events"
            >
              {visibleEvents.length ? (
                visibleEvents
                  .slice()
                  .reverse()
                  .map((e) => (
                    <article className="journal-row" key={e.id}>
                      <span className="journal-id">#{e.id}</span>
                      <i
                        className={
                          "status-dot " +
                          (e.type.includes("failed") ? "failed" : "connected")
                        }
                      />
                      <div>
                        <strong>{e.type}</strong>
                        <p>{e.message ?? e.tool ?? "Runtime event"}</p>
                        {e.diff && (
                          <details>
                            <summary>View diff</summary>
                            <pre>{e.diff}</pre>
                          </details>
                        )}
                        {e.output && (
                          <details>
                            <summary>Execution output</summary>
                            <pre>{e.output}</pre>
                          </details>
                        )}
                      </div>
                      <time>{new Date(e.at).toLocaleString()}</time>
                    </article>
                  ))
              ) : (
                <Empty
                  title={eventSearch ? "No matching events" : "A fresh start"}
                  text={
                    eventSearch
                      ? "Try a different search to find an event."
                      : "Agent runs, results, and decisions will appear here when your team starts working."
                  }
                />
              )}
            </div>
          </section>
        ) : (
          <div className="settings-layout">
            <section className="settings-card">
              <div className="section-header">
                <h2>
                  <Zap size={18} />
                  Codex connection
                </h2>
                <span
                  className={
                    "status-pill " + (account.connected ? "completed" : "idle")
                  }
                >
                  {account.connected ? "Connected" : "Not connected"}
                </span>
              </div>
              <div className="connection-illustration">
                <Zap size={32} />
                <span
                  className={
                    "connection-state " +
                    (account.connected ? "is-connected" : "")
                  }
                >
                  <i />
                  {account.connected
                    ? "You’re connected"
                    : "Let’s get connected"}
                </span>
              </div>
              <h3>Your AI connection</h3>
              <p>
                Use Codex with your eligible ChatGPT subscription. Your
                account’s usage limits apply.
              </p>
              <div className="setting-row">
                <span>Provider</span>
                <strong>Codex Python SDK</strong>
              </div>
              <div className="setting-row">
                <span>Authentication</span>
                <strong>
                  ChatGPT sign-in {account.plan && "· " + account.plan}
                </strong>
              </div>
              {account.error && (
                <div className="task-error">{account.error}</div>
              )}
              <button
                className="primary"
                onClick={() =>
                  action(async () => {
                    if (account.connected) {
                      setAccount(await api("/account"));
                      setToast("Connection checked.");
                    } else {
                      const r = await api<{ auth_url: string }>("/login", {});
                      setAuthUrl(r.auth_url);
                      window.open(r.auth_url, "_blank", "noopener,noreferrer");
                      setToast(
                        "Complete sign-in in the browser, then check the connection.",
                      );
                    }
                  })
                }
              >
                <ExternalLink size={15} />
                {account.connected
                  ? "Check connection"
                  : "Sign in with ChatGPT"}
              </button>
              {authUrl && !account.connected && (
                <a
                  className="text-link check-account"
                  href={authUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Continue sign-in <ExternalLink size={12} />
                </a>
              )}
              <button
                className="text-link check-account"
                onClick={() =>
                  action(async () => {
                    setAccount(await api("/account"));
                  })
                }
              >
                Refresh connection
              </button>
            </section>
            <section className="settings-card">
              <div className="section-header">
                <h2>
                  <ShieldCheck size={18} />
                  Workspace controls
                </h2>
              </div>
              <div className="setting-row">
                <span>Execution</span>
                <strong>Sequential · one run at a time</strong>
              </div>
              <div className="setting-row">
                <span>File changes</span>
                <strong>Per-action review or authorized auto workflow</strong>
              </div>
              <div className="setting-row">
                <span>Tests</span>
                <strong>Local commands · Docker disabled</strong>
              </div>
              <div className="setting-row">
                <span>Retry limit</span>
                <strong>3 attempts per task</strong>
              </div>
              <div className="setting-row">
                <span>Push & deployment</span>
                <strong>Unavailable in this version</strong>
              </div>
              <div className="environment-check">
                <button
                  className="secondary full"
                  disabled={checking}
                  onClick={() => {
                    setChecking(true);
                    void api<
                      Record<string, { ready: boolean; message?: string }>
                    >("/diagnostics")
                      .then(setDiagnostics)
                      .catch((e) => setToast(e.message))
                      .finally(() => setChecking(false));
                  }}
                >
                  <Activity size={14} />
                  {checking
                    ? "Checking local environment…"
                    : "Check environment"}
                </button>
                {Object.entries(diagnostics).map(([key, value]) => (
                  <div className="environment-result" key={key}>
                    <strong>
                      <i
                        className={
                          "status-dot " + (value.ready ? "connected" : "failed")
                        }
                      />
                      {key === "project_tests"
                        ? "Project tests · local mode"
                        : "Codex sandbox"}{" "}
                      ·{" "}
                      {value.ready
                        ? key === "project_tests"
                          ? "Enabled"
                          : "Ready"
                        : "Needs setup"}
                    </strong>
                    {key === "project_tests" && <p>{value.message}</p>}
                    {!value.ready && (
                      <>
                        <p>
                          Launch Start Office.cmd from Windows, outside this
                          chat’s sandbox. Ensure Codex’s Windows sandbox is
                          configured.
                        </p>
                        <details>
                          <summary>Technical details</summary>
                          <pre>{value.message}</pre>
                        </details>
                      </>
                    )}
                  </div>
                ))}
              </div>
              <div className="setting-row">
                <span>Cinematic lighting</span>
                <button
                  className={"toggle " + (effects ? "on" : "")}
                  aria-label="Cinematic lighting"
                  aria-pressed={effects}
                  onClick={() => {
                    setEffects(!effects);
                    localStorage.setItem("natee-effects", String(!effects));
                  }}
                >
                  <span />
                </button>
              </div>
            </section>
          </div>
        )}
        {page !== "Office" && (
          <footer className="page-footer">
            <span>
              <span className="footer-dot" /> A small studio for ambitious
              ideas.
            </span>
            <span>
              LOCAL FIRST <span className="footer-separator">/</span> HUMAN IN
              THE LOOP <span className="footer-separator">/</span> v0.1.0
            </span>
          </footer>
        )}
      </main>
      {pending.length > 0 && (
        <button
          className="approval-banner"
          onClick={() => setApproval(pending[0])}
        >
          <ShieldCheck size={18} />
          {pending.length} decision{pending.length > 1 ? "s" : ""} waiting for
          you
          <ArrowRight size={16} />
        </button>
      )}
      {settingsPanel.value && <AgentSettingsDrawer agents={state.agents} closing={settingsPanel.closing} close={() => setAgentSettingsOpen(false)} />}
      {selected && (
        <>
          <div className="drawer-shade" onClick={() => state.select(null)} />
          <aside className={"agent-drawer" + (agentPanel.closing ? " is-closing" : "")} inert={agentPanel.closing}>
            <button
              className="close"
              aria-label="Close agent details"
              onClick={() => state.select(null)}
            >
              <X size={20} />
            </button>
            <Avatar id={selected.id} />
            <div className="eyebrow">YOUR TEAMMATE</div>
            <h2>{selected.name}</h2>
            <p>{selected.role}</p>
            <span className={"status-pill " + selected.status}>
              {state.online ? statusLabel(selected.status) : "Offline"}
            </span>
            <AgentModelSettings key={selected.id} agent={selected} />
            <h3>Current assignment</h3>
            {selected.task ? (
              <>
                <h4>{selected.task.title}</h4>
                <p>{selected.task.description}</p>
              </>
            ) : (
              <div className="drawer-empty">
                <Coffee size={24} />
                <p>Ready for the next good idea.</p>
              </div>
            )}
            <h3>Execution history</h3>
            {state.runs
              .filter((r) => r.agent_id === selected.id)
              .slice()
              .reverse()
              .map((r) => (
                <div className="history-item" key={r.id}>
                  <strong>
                    {state.tasks.find((t) => t.id === r.task_id)?.title ??
                      r.task_id}{" "}
                    · attempt {r.attempt}
                  </strong>
                  <span>{statusLabel(r.status)}</span>
                  <span>
                    {r.model_settings?.model ?? "Runtime default"} · reasoning:{" "}
                    {r.model_settings?.reasoning ?? "Model default"}
                  </span>
                  {r.result && <p>{r.result.summary}</p>}
                  {r.error && <p>{r.error}</p>}
                </div>
              ))}
            <h3>Recent logs & tool calls</h3>
            {state.events
              .filter((e) => e.agent_id === selected.id)
              .slice(-12)
              .reverse()
              .map((e) => (
                <div className="agent-log" key={e.id}>
                  <small>
                    {new Date(e.at).toLocaleTimeString()} · {e.type}
                  </small>
                  <p>{e.message ?? e.tool ?? "Runtime event"}</p>
                  {e.diff && <pre>{e.diff}</pre>}
                </div>
              ))}
          </aside>
        </>
      )}
      {workflowProject && (
        <WorkflowDialog
          project={workflowProject}
          close={() => setWorkflowProject(null)}
        />
      )}
      {deleteProject && (
        <DeleteProjectModal
          project={deleteProject}
          busy={state.busy}
          close={() => setDeleteProject(null)}
          deleted={async () => {
            const removedId = deleteProject.id;
            setDeleteProject(null);
            if (projectId === removedId) setProjectId("");
            if (approval?.project_id === removedId) setApproval(null);
            state.select(null);
            await state.refresh();
            setToast("Project and workspace folder deleted.");
          }}
        />
      )}
      <NewProjectModal open={newProject} onClose={() => setNewProject(false)}>
        <span className="modal-symbol">
          <FolderGit2 size={26} />
        </span>
        <div className="eyebrow">A NEW BEGINNING</div>
        <h2 id="new-project-title">What shall we build?</h2>
        <p>Give your team a workspace and a clear brief.</p>
        <form
          onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void action(async () => {
              const p = await api<{ id: string }>("/projects", {
                name: f.get("name"),
                workspace: f.get("workspace"),
                requirement: f.get("requirement"),
              });
              setProjectId(p.id);
              setNewProject(false);
              changePage("Projects");
            });
          }}
        >
          <label>
            Project name
            <input
              name="name"
              required
              autoFocus
              maxLength={100}
              placeholder="e.g. My next great app"
            />
          </label>
          <label>
            Workspace path <span>OPTIONAL</span>
            <input
              name="workspace"
              placeholder="Leave empty to create a dedicated workspace"
            />
            <small>
              Use a dedicated folder. Source files are shared with Codex when
              you run an agent.
            </small>
          </label>
          <label>
            Your brief
            <textarea
              name="requirement"
              required
              minLength={5}
              rows={5}
              maxLength={20000}
              placeholder="What would you like to build? Include the features and what a good result looks like."
            />
          </label>
          <div className="form-note">
            <ShieldCheck size={15} />
            You review the plan and approve source changes.
          </div>
          <button className="primary full" type="submit">
            Create project <ArrowRight size={16} />
          </button>
        </form>
      </NewProjectModal>
      {plannerProject && (
        <div className="modal-backdrop">
          <section
            className="modal planner-follow-up"
            role="dialog"
            aria-modal="true"
            aria-labelledby="planner-follow-up-title"
          >
            <button
              className="close"
              aria-label="Close Planner conversation"
              onClick={() => setPlannerProject(null)}
            >
              <X size={20} />
            </button>
            <h2 id="planner-follow-up-title">คุยกับ Planner ต่อ</h2>
            <p>{plannerProject.name} — บอกสิ่งที่ต้องการปรับเพิ่มจากงานเดิม</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (plannerSending || !plannerMessage.trim()) return;
                const target = plannerProject;
                setPlannerSending(true);
                void action(async () => {
                  await api("/projects/" + target.id + "/plan", {
                    message: plannerMessage.trim(),
                  });
                  setProjectId(target.id);
                  setPlannerProject(null);
                  setPlannerMessage("");
                }).finally(() => setPlannerSending(false));
              }}
            >
              <label htmlFor="planner-message">ต้องการปรับอะไรเพิ่มเติม?</label>
              <textarea
                id="planner-message"
                name="planner-message"
                autoFocus
                required
                rows={8}
                maxLength={20000}
                value={plannerMessage}
                onChange={(e) => setPlannerMessage(e.target.value)}
                placeholder="เช่น เพิ่มปุ่มแก้ไขชื่องาน และเปลี่ยนสีหน้าเว็บเป็นโทนเขียว"
              />
              <p>Planner จะดูไฟล์และแผนเดิม แล้วเสนอแผนเพิ่มให้คุณอนุมัติ</p>
              <div className="planner-dialog-actions">
                <button
                  className="secondary"
                  type="button"
                  onClick={() => setPlannerProject(null)}
                >
                  ยกเลิก
                </button>
                <button
                  className="primary"
                  type="submit"
                  disabled={
                    plannerSending || state.busy || !plannerMessage.trim()
                  }
                >
                  {plannerSending ? "กำลังส่ง…" : "ส่งให้ Planner"}{" "}
                  <ArrowRight size={16} />
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
      {approval && (
        <div className="modal-backdrop">
          <section
            className="modal approval-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-title"
          >
            <button
              className="close"
              aria-label="Close"
              onClick={() => setApproval(null)}
            >
              <X size={20} />
            </button>
            <span className="modal-symbol">
              <ShieldCheck size={26} />
            </span>
            <div className="eyebrow">YOUR CALL</div>
            <h2 id="approval-title">Review {approval.kind}</h2>
            <p>
              {roles.find((a) => a.id === approval.agent_id)?.name} is waiting
              for your decision.
            </p>
            <div className="approval-content">
              {approval.kind === "changes" ? (
                (
                  approval.payload.changes as { path: string; diff: string }[]
                ).map((c) => (
                  <div key={c.path}>
                    <h4>{c.path}</h4>
                    <pre>{c.diff || "(No textual difference)"}</pre>
                  </div>
                ))
              ) : (
                <pre>{JSON.stringify(approval.payload, null, 2)}</pre>
              )}
            </div>
            <div className="approval-actions">
              <button
                className="secondary"
                onClick={() =>
                  action(async () => {
                    await api("/approvals/" + approval.id, { approve: false });
                    setApproval(null);
                  })
                }
              >
                <X size={15} />
                Reject
              </button>
              <button
                className="primary"
                onClick={() =>
                  action(async () => {
                    await api("/approvals/" + approval.id, { approve: true });
                    setApproval(null);
                  })
                }
              >
                <Check size={15} />
                Approve {approval.kind}
              </button>
            </div>
          </section>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <CircleHelp size={18} />
          <span>{toast}</span>
          <button aria-label="Dismiss" onClick={() => setToast("")}>
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty-state">
      <ArrowDownLeft size={30} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

