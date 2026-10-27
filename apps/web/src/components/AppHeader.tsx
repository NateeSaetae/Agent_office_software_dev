import {
  Activity,
  Bell,
  ChevronDown,
  FolderGit2,
  House,
  ListTodo,
  Plus,
  Settings,
  Sun,
  Users,
} from "lucide-react";
import type { Page } from "../App";
import Avatar from "./Avatar";
const items: { label: Page; icon: typeof House }[] = [
  { label: "Office", icon: House },
  { label: "Tasks", icon: ListTodo },
  { label: "Agents", icon: Users },
  { label: "Projects", icon: FolderGit2 },
  { label: "Activity", icon: Activity },
  { label: "Settings", icon: Settings },
];
export default function AppHeader({
  page,
  onPage,
  online,
  clock,
  pending,
  onApprovals,
  onNewProject,
}: {
  page: Page;
  onPage: (p: Page) => void;
  online: boolean;
  clock: Date;
  pending: number;
  onApprovals: () => void;
  onNewProject: () => void;
}) {
  return (
    <header className="app-header">
      <button
        className="brand header-brand"
        onClick={() => onPage("Office")}
        aria-label="Natee’s Software House home"
      >
        <span className="brand-mark">
          <House size={29} />
          <span />
        </span>
        <span>
          NATEE’S<small>SOFTWARE HOUSE</small>
        </span>
      </button>
      <nav className="top-navigation" aria-label="Main navigation">
        {items.map(({ label, icon: Icon }) => (
          <button
            className={"top-nav-item " + (page === label ? "active" : "")}
            key={label}
            aria-current={page === label ? "page" : undefined}
            onClick={() => onPage(label)}
          >
            <Icon size={21} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="header-right">
        <button
          className="new-project-shortcut"
          onClick={onNewProject}
          title="New project"
        >
          <Plus size={16} />
          <span>New project</span>
        </button>
        <div className="office-clock">
          <Sun size={22} />
          <span>
            {clock.toLocaleDateString("en-GB", {
              weekday: "short",
              day: "numeric",
              month: "short",
            })}
            <strong>
              {clock.toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </strong>
          </span>
        </div>
        <button
          className="header-notifications"
          aria-label="Open approvals"
          onClick={onApprovals}
        >
          <Bell size={19} />
          {pending > 0 && <span>{pending}</span>}
        </button>
        <div className="header-owner">
          <Avatar id="planner" small />
          <span>
            <i
              className={"connection-dot " + (online ? "online" : "offline")}
            />
            {online ? "Online" : "Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}
