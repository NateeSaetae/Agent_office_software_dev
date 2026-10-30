import { useEffect, useRef, useState } from "react";
import { Cpu, Gauge, Plus, Save, Settings, Trash2, X } from "lucide-react";
import { api, type Agent, useOffice } from "../store";
import Dropdown from "./Dropdown";
import "./AgentSettingsDrawer.css";

type Model = {
  model: string;
  name: string;
  reasoning_efforts: { value: string; description: string }[];
};
type Row = { id: number; value: string; agents: string[] };
let nextId = 0;
function group(agents: Agent[], key: "model" | "reasoning"): Row[] {
  const rows: Row[] = [];
  agents.forEach((a) => {
    const value = a.settings?.[key] ?? "";
    const row = rows.find((r) => r.value === value);
    if (row) row.agents.push(a.id);
    else rows.push({ id: nextId++, value, agents: [a.id] });
  });
  return rows.length ? rows : [{ id: nextId++, value: "", agents: [] }];
}
export default function AgentSettingsDrawer({
  agents,
  close,
  closing = false,
}: {
  agents: Agent[];
  close: () => void;
  closing?: boolean;
}) {
  const [modelRows, setModels] = useState(() => group(agents, "model"));
  const [reasonRows, setReasons] = useState(() => group(agents, "reasoning"));
  const [catalog, setCatalog] = useState<Model[]>([]),
    [loading, setLoading] = useState(true);
  const [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [saved, setSaved] = useState(false);
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    let alive = true;
    api<{ models: Model[] }>("/models")
      .then((d) => {
        if (alive) setCatalog(d.models);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => {
      alive = false;
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  function modelFor(id: string) {
    return modelRows.find((r) => r.agents.includes(id))?.value ?? "";
  }
  function efforts(row: Row) {
    const models = row.agents.map((id) =>
      catalog.find((m) => m.model === modelFor(id)),
    );
    if (!models.length || models.some((m) => !m)) return [];
    return models[0]!.reasoning_efforts.filter((e) =>
      models.every((m) =>
        m!.reasoning_efforts.some((r) => r.value === e.value),
      ),
    );
  }
  const invalid =
    reasonRows.some(
      (r) =>
        r.agents.length > 0 &&
        r.value &&
        !efforts(r).some((e) => e.value === r.value),
    ) ||
    modelRows.some(
      (r) =>
        r.agents.length > 0 &&
        r.value &&
        !catalog.some((m) => m.model === r.value),
    );
  function update(
    kind: "model" | "reasoning",
    id: number,
    change: Partial<Row>,
  ) {
    const setter = kind === "model" ? setModels : setReasons;
    setter((rows) =>
      rows.map((r) =>
        r.id === id
          ? { ...r, ...change }
          : change.agents
            ? {
                ...r,
                agents: r.agents.filter((a) => !change.agents!.includes(a)),
              }
            : r,
      ),
    );
    setSaved(false);
    setError("");
  }
  return (
    <>
      <div
        className="drawer-shade bulk-settings-shade"
        onClick={() => {
          if (!saving) close();
        }}
      />
      <aside
        ref={panel}
        tabIndex={-1}
        className={"bulk-settings-drawer" + (closing ? " is-closing" : "")}
        inert={closing}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bulk-settings-title"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            if (!saving) close();
          }
          if (e.key === "Tab") {
            const elements = panel.current?.querySelectorAll<HTMLElement>(
              'button:not(:disabled), [tabindex="0"]',
            );
            if (!elements?.length) return;
            const first = elements[0],
              last = elements[elements.length - 1];
            if (
              e.shiftKey &&
              (document.activeElement === first ||
                document.activeElement === panel.current)
            ) {
              e.preventDefault();
              last.focus();
            } else if (
              !e.shiftKey &&
              (document.activeElement === last ||
                document.activeElement === panel.current)
            ) {
              e.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <header className="bulk-settings-heading">
          <div>
            <span className="bulk-eyebrow">
              <Settings size={16} /> TEAM PREFERENCES
            </span>
            <h2 id="bulk-settings-title">Agent settings</h2>
          </div>
          <button
            className="bulk-icon-button"
            aria-label="Close agent settings"
            disabled={saving}
            onClick={close}
          >
            <X size={20} />
          </button>
        </header>
        <div className="bulk-settings-body">
          <p className="bulk-intro">
            Choose models and reasoning for your team. Changes apply to the next
            run or retry.
          </p>
          {(["model", "reasoning"] as const).map((kind) => {
            const rows = kind === "model" ? modelRows : reasonRows;
            const setter = kind === "model" ? setModels : setReasons;
            return (
              <section
                className="bulk-settings-section"
                key={kind}
                aria-label={
                  kind === "model"
                    ? "Model assignments"
                    : "Reasoning assignments"
                }
              >
                <h3>
                  {kind === "model" ? <Cpu size={18} /> : <Gauge size={18} />}
                  {kind === "model" ? "Model" : "Reasoning effort"}
                  <span>
                    {rows.length} / {agents.length}
                  </span>
                </h3>
                <p>
                  {kind === "model"
                    ? "Assign a model to one or more agents."
                    : "Choose an effort supported by every selected agent’s model."}
                </p>
                <div className="bulk-column-labels">
                  <span>{kind === "model" ? "Model" : "Reasoning"}</span>
                  <span>Agents</span>
                </div>
                {rows.map((row, index) => {
                  const available = kind === "reasoning" ? efforts(row) : [];
                  const unavailable =
                    Boolean(row.value) &&
                    (kind === "model"
                      ? !catalog.some((m) => m.model === row.value)
                      : !available.some((e) => e.value === row.value));
                  return (
                    <div className="bulk-assignment" key={row.id}>
                      <div className="bulk-value">
                        <Dropdown
                          value={row.value}
                          disabled={loading || saving}
                          aria-label={`${kind} for group ${index + 1}`}
                          onValueChange={(value) =>
                            update(kind, row.id, { value })
                          }
                        >
                          <option value="">
                            {kind === "model"
                              ? "Runtime default"
                              : "Model default"}
                          </option>
                          {unavailable && (
                            <option value={row.value}>
                              {row.value} · unavailable
                            </option>
                          )}
                          {kind === "model"
                            ? catalog.map((m) => (
                                <option key={m.model} value={m.model}>
                                  {m.name}
                                </option>
                              ))
                            : available.map((e) => (
                                <option key={e.value} value={e.value}>
                                  {e.value}
                                </option>
                              ))}
                        </Dropdown>
                      </div>
                    <div className="bulk-agent-field" data-dropdown-anchor>
                        <div className="bulk-agent-tags">
                          {row.agents.map((id) => {
                            const agent = agents.find((a) => a.id === id)!;
                            return (
                              <span
                                className="bulk-agent-tag"
                                key={id}
                                style={
                                  {
                                    "--tag-color": agent.color,
                                  } as React.CSSProperties
                                }
                              >
                                {agent.name}
                                <button
                                  type="button"
                                  disabled={saving}
                                  aria-label={`Remove ${agent.name} from ${kind} group ${index + 1}`}
                                  onClick={() =>
                                    update(kind, row.id, {
                                      agents: row.agents.filter(
                                        (a) => a !== id,
                                      ),
                                    })
                                  }
                                >
                                  <X size={12} />
                                </button>
                              </span>
                            );
                          })}
                        </div>
                        <Dropdown
                          value=""
                          multipleValues={row.agents}
                          onMultipleChange={(values) =>
                            update(kind, row.id, { agents: values })
                          }
                          onValueChange={() => {}}
                          disabled={saving}
                          aria-label={`Agents for ${kind} group ${index + 1}`}
                        >
                          {agents.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </Dropdown>
                      </div>
                      <button
                        className="bulk-icon-button bulk-delete"
                        disabled={saving}
                        aria-label={`Delete ${kind} group ${index + 1}`}
                        onClick={() => {
                          setter((current) =>
                            current.filter((r) => r.id !== row.id),
                          );
                          setSaved(false);
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                      {unavailable && row.agents.length > 0 && (
                        <p className="bulk-row-error">
                          {kind === "model"
                            ? "This model is unavailable. Choose another model."
                            : "This effort is not supported by all selected models. Choose Model default, or split these agents into separate groups."}
                        </p>
                      )}
                    </div>
                  );
                })}
                <button
                  className="bulk-add"
                  disabled={saving || rows.length >= agents.length}
                  onClick={() => {
                    setter((current) => [
                      ...current,
                      { id: nextId++, value: "", agents: [] },
                    ]);
                    setSaved(false);
                  }}
                >
                  <Plus size={16} />
                  Add {kind === "model" ? "model" : "reasoning"} group
                </button>
              </section>
            );
          })}
          <p className="bulk-footnote">
            Selecting an agent moves it from its previous group in the same
            section. Unassigned agents use defaults.
          </p>
          {loading && (
            <p role="status" className="bulk-footnote">
              Loading available models…
            </p>
          )}
          {error && (
            <p role="alert" className="model-error">
              {error}
            </p>
          )}
          {saved && (
            <p role="status" className="model-saved">
              Settings saved for all agents.
            </p>
          )}
        </div>
        <footer className="bulk-settings-footer">
          <button className="bulk-cancel" disabled={saving} onClick={close}>
            Close
          </button>
          <button
            className="bulk-save"
            disabled={loading || saving || invalid}
            onClick={async () => {
              setSaving(true);
              setError("");
              setSaved(false);
              try {
                await api("/agent-settings/bulk", {
                  settings: agents.map((a) => ({
                    agent_id: a.id,
                    model: modelFor(a.id) || null,
                    reasoning:
                      reasonRows.find((r) => r.agents.includes(a.id))?.value ||
                      null,
                  })),
                });
                setSaved(true);
                await useOffice.getState().refresh();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setSaving(false);
              }
            }}
          >
            <Save size={16} />
            {saving ? "Saving…" : "Save settings"}
          </button>
        </footer>
      </aside>
    </>
  );
}
