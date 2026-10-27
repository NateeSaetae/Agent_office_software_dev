import { useState } from "react";
import { Copy, FolderOpen, Trash2, X } from "lucide-react";
import { api, type Project } from "../store";

function actionError(error: unknown) {
  const message = (error as Error).message;
  return message === "Not Found"
    ? "Restart the Agent Office server to enable project folder actions, then refresh this page."
    : message;
}

export function ProjectFolder({
  project,
  notify,
}: {
  project: Project;
  notify: (message: string) => void;
}) {
  const [opening, setOpening] = useState(false);
  return (
    <div className="project-workspace">
      <span className="workspace-label">WORKSPACE FOLDER</span>
      <code className="workspace-path">{project.workspace}</code>
      <div className="workspace-actions">
        <button
          className="secondary"
          disabled={opening}
          onClick={async () => {
            setOpening(true);
            try {
              const result = await api<{ opened: boolean; workspace: string }>(
                `/projects/${project.id}/open-folder`,
                {},
              );
              notify(
                result.opened
                  ? "Opened project folder in File Explorer."
                  : `Project folder: ${result.workspace}`,
              );
            } catch (e) {
              notify(actionError(e));
            } finally {
              setOpening(false);
            }
          }}
        >
          <FolderOpen size={14} />
          {opening ? "Opening…" : "Open folder"}
        </button>
        <button
          className="secondary"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(project.workspace);
              notify("Full workspace path copied.");
            } catch {
              notify(`Project folder: ${project.workspace}`);
            }
          }}
        >
          <Copy size={14} />
          Copy path
        </button>
      </div>
    </div>
  );
}

export function DeleteProjectModal({
  project,
  busy,
  close,
  deleted,
}: {
  project: Project;
  busy: boolean;
  close: () => void;
  deleted: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  return (
    <div
      className="modal-backdrop"
      onClick={() => {
        if (!deleting) close();
      }}
    >
      <section
        className="modal delete-project-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-project-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="close"
          aria-label="Close delete project"
          disabled={deleting}
          onClick={close}
        >
          <X size={20} />
        </button>
        <span className="modal-symbol delete-symbol">
          <Trash2 size={26} />
        </span>
        <h2 id="delete-project-title">Delete project and folder?</h2>
        <p>
          This permanently deletes <strong>{project.name}</strong>, all files
          and subfolders in its workspace, and its tasks, runs and approvals.
          This cannot be undone.
        </p>
        <code className="workspace-path delete-workspace-path">
          {project.workspace}
        </code>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy || deleting || name !== project.name || !confirmed) return;
            setDeleting(true);
            setError("");
            try {
              await api(`/projects/${project.id}/delete`, {
                confirmation_name: name,
                workspace: project.workspace,
              });
              await deleted();
            } catch (e) {
              setError(actionError(e));
              setDeleting(false);
            }
          }}
        >
          <label>
            Type <strong>{project.name}</strong> to confirm
            <input
              aria-label="Project name to confirm deletion"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="off"
              disabled={deleting}
              autoFocus
            />
          </label>
          <label className="delete-confirmation">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              disabled={deleting}
            />
            I understand the entire workspace folder will be permanently
            deleted.
          </label>
          {busy && (
            <p className="delete-error" role="status">
              Wait for the active run or workflow to stop before deleting.
            </p>
          )}
          {error && (
            <p className="delete-error" role="alert">
              {error}
            </p>
          )}
          <div className="delete-modal-actions">
            <button
              className="secondary"
              type="button"
              disabled={deleting}
              onClick={close}
            >
              Cancel
            </button>
            <button
              className="danger"
              type="submit"
              disabled={busy || deleting || name !== project.name || !confirmed}
            >
              <Trash2 size={15} />
              {deleting ? "Deleting…" : "Permanently delete project"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
