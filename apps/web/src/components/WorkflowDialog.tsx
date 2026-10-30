import { useEffect, useState } from "react";
import { Play, X } from "lucide-react";
import { api, useOffice, type Project } from "../store";
export default function WorkflowDialog({
  project,
  close,
}: {
  project: Project;
  close: () => void;
}) {
  const [automatic, setAutomatic] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, close]);
  return (
    <div
      className="modal-backdrop"
      onClick={() => {
        if (!busy) close();
      }}
    >
      <section
        className="modal workflow-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="workflow-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="close"
          aria-label="Close workflow options"
          disabled={busy}
          onClick={close}
        >
          <X size={20} />
        </button>
        <h2 id="workflow-title">Start workflow</h2>
        <p>{project.name}</p>
        <label className="workflow-choice">
          <input
            type="checkbox"
            checked={automatic}
            disabled={busy}
            onChange={(e) => setAutomatic(e.target.checked)}
          />
          <span>
            <strong>Auto workflow</strong>
            <small>
              Approve workspace edits and local install / typecheck / build /
              test commands for this workflow run.
            </small>
          </span>
        </label>
        <p className="workflow-note">
          Agents inspect files, apply changes, verify results and repair
          failures automatically. Local project scripts run on this PC without
          Docker or an OS sandbox. Dependency installation may use the network.
          Run only projects you trust.
        </p>
        <p className="workflow-note">
          Workspace: <code>{project.workspace}</code>
        </p>
        <p className="workflow-note">
          {automatic
            ? "Applies to this run only. Plans still require approval. No push, deployment or file deletion tools. Retry limit: 3 attempts per task."
            : "Review mode: each edit and local command pauses for your approval."}
        </p>
        {error && (
          <p role="alert" className="model-error">
            {error}
          </p>
        )}
        <button
          className="primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await api(`/projects/${project.id}/workflow`, {
                auto_approve: automatic,
              });
              await useOffice.getState().refresh();
              close();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Play size={16} />
          {busy
            ? "Starting…"
            : automatic
              ? "Start auto workflow"
              : "Start with approvals"}
        </button>
      </section>
    </div>
  );
}
