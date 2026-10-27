import { lazy, Suspense, useState } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronRight,
  Coffee,
  Eye,
  FolderGit2,
  Pause,
  Play,
  Plus,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useOffice } from "../store";
import type { Page } from "../App";
import Avatar from "./Avatar";
const Office = lazy(() => import("../Office"));
const labels: Record<string, string> = {
  idle: "Idle · taking a break",
  running: "Working",
  queued: "Queued",
  awaiting_approval: "Waiting for approval",
  failed: "Needs attention",
  blocked: "Blocked",
  completed: "Completed",
};
export default function OfficeView({
  effects,
  onEffects,
  onPage,
  onNewProject,
}: {
  effects: boolean;
  onEffects: () => void;
  onPage: (p: Page) => void;
  onNewProject: () => void;
}) {
  const state = useOffice();
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth > 680),
    [roaming, setRoaming] = useState(
      () => localStorage.getItem("natee-roaming") !== "false",
    );
  const [projectId, setProjectId] = useState("");
  const project =
    state.projects.find((p) => p.id === projectId) ?? state.projects[0];
  const active = state.tasks.find((t) =>
    ["running", "queued", "awaiting_approval"].includes(t.status),
  );
  const projectTasks = state.tasks.filter((t) => t.project_id === project?.id);
  const complete = projectTasks.filter((t) => t.status === "completed").length;
  const toggleRoaming = () => {
    setRoaming(!roaming);
    localStorage.setItem("natee-roaming", String(!roaming));
  };
  return (
    <section
      className="office-experience"
      aria-label="Interactive pixel art office"
    >
      <div className="office-world">
        <Suspense
          fallback={
            <div className="pixel-office-loading">
              <span />
              <strong>Opening the office</strong>
              <small>Getting everyone’s desk ready…</small>
            </div>
          }
        >
          <Office effects={effects} roaming={roaming} />
        </Suspense>
      </div>
      {panelOpen ? (
        <aside
          className="agent-status-panel office-hud"
          role="dialog"
          aria-label="Agent status"
          aria-modal={false}
        >
          <div className="hud-heading">
            <h2>
              <Users size={15} /> AI AGENTS
            </h2>
            <button
              aria-label="Close agent status"
              onClick={() => setPanelOpen(false)}
            >
              <X size={15} />
            </button>
          </div>
          <div className="office-team-list">
            {state.agents.map((a) => (
              <button
                className={
                  "office-agent-card " +
                  (state.selected === a.id ? "selected" : "")
                }
                key={a.id}
                onClick={() => state.select(a.id)}
                style={{ "--agent-accent": a.color } as React.CSSProperties}
              >
                <Avatar id={a.id} />
                <span>
                  <strong>{a.name}</strong>
                  <small>
                    <i className={state.online ? a.status : "offline"} />
                    {state.online
                      ? (labels[a.status] ?? a.status)
                      : "Not connected"}
                  </small>
                </span>
                <ChevronRight size={13} />
              </button>
            ))}
          </div>
          <div className="panel-connection">
            <i
              className={
                "connection-dot " + (state.online ? "online" : "offline")
              }
            />
            {state.online
              ? "Live backend connection"
              : "Reconnecting to backend"}
          </div>
          {active && (
            <button
              className="current-task-compact"
              onClick={() => onPage("Tasks")}
            >
              <span>CURRENT TASK</span>
              <strong>{active.title}</strong>
              <small>
                View task <ArrowRight size={11} />
              </small>
            </button>
          )}
        </aside>
      ) : (
        <button
          className="open-agent-status office-hud"
          onClick={() => setPanelOpen(true)}
        >
          <Users size={17} />
          Agent status<span>6</span>
        </button>
      )}
      <div className="office-controls office-hud">
        <span className="office-live">
          <i
            className={
              "connection-dot " + (state.online ? "online" : "offline")
            }
          />
          {state.online ? "LIVE OFFICE" : "OFFLINE"}
        </span>
        <span className="office-controls-separator" />
        <button
          aria-label={roaming ? "Pause idle roaming" : "Enable idle roaming"}
          aria-pressed={roaming}
          onClick={toggleRoaming}
        >
          {roaming ? <Pause size={14} /> : <Play size={14} />}
          <span>Idle roaming</span>
        </button>
        <button
          onClick={onEffects}
          aria-label="Toggle cinematic lighting"
          aria-pressed={effects}
        >
          <Sparkles size={15} />
        </button>
        <button
          aria-label="Show agent status"
          aria-pressed={panelOpen}
          onClick={() => setPanelOpen(!panelOpen)}
        >
          <Eye size={16} />
        </button>
      </div>
      <aside className="office-recent office-hud">
        <div className="hud-heading">
          <h2>
            <Activity size={13} />
            RECENT ACTIVITY
          </h2>
          <button
            aria-label="View all activity"
            onClick={() => onPage("Activity")}
          >
            <ArrowRight size={13} />
          </button>
        </div>
        {state.events.length ? (
          state.events
            .slice(-3)
            .reverse()
            .map((e) => (
              <div className="office-event" key={e.id}>
                <time>
                  {new Date(e.at).toLocaleTimeString("en-GB", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
                <i
                  className={e.type.includes("failed") ? "error" : "success"}
                />
                <span title={e.message ?? e.type}>
                  {e.message ?? e.type.replaceAll(".", " · ")}
                </span>
              </div>
            ))
        ) : (
          <p className="office-no-events">
            A quiet moment in the studio.
            <br />
            Real agent activity will appear here.
          </p>
        )}
      </aside>
      <div className="office-ambient-caption">
        <Coffee size={14} />
        <span>
          {roaming
            ? "A little coffee. A little wandering. Ready for the next idea."
            : "Idle movement paused. Agent tasks continue as usual."}
        </span>
      </div>
      <aside className="active-project-hud office-hud">
        <div className="hud-heading">
          <h2>
            <FolderGit2 size={14} />
            ACTIVE PROJECT
          </h2>
          {project && (
            <span>
              {complete}/{projectTasks.length}
              <Check size={10} />
            </span>
          )}
        </div>
        {project ? (
          <>
            <select
              aria-label="Active project"
              value={project.id}
              onChange={(e) => setProjectId(e.target.value)}
            >
              {state.projects.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => onPage("Tasks")}
              className="hud-project-link"
            >
              View task board <ArrowRight size={13} />
            </button>
          </>
        ) : (
          <button className="hud-create-project" onClick={onNewProject}>
            <Plus size={18} />
            <span>
              Bring your next idea to life<small>Create a project</small>
            </span>
            <ChevronRight size={14} />
          </button>
        )}
      </aside>
    </section>
  );
}
