import Dropdown from "./Dropdown";
import { useEffect, useState } from "react";
import { Cpu, RefreshCw, RotateCcw, Save } from "lucide-react";
import { api, useOffice, type Agent } from "../store";

type ModelInfo = {
  model: string;
  name: string;
  description: string;
  is_default: boolean;
  default_reasoning: string;
  reasoning_efforts: { value: string; description: string }[];
};

export default function AgentModelSettings({ agent }: { agent: Agent }) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  const [model, setModel] = useState(agent.settings?.model ?? "");
  const [reasoning, setReasoning] = useState(agent.settings?.reasoning ?? "");
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setLoadError("");
    api<{ models: ModelInfo[] }>("/models")
      .then((data) => {
        if (alive) setModels(data.models);
      })
      .catch((error) => {
        if (alive)
          setLoadError(
            error.message === "Not Found"
              ? "Restart the Office backend to enable model selection, then refresh."
              : error.message,
          );
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [revision]);
  const selected = models.find((m) => m.model === model);
  const dirty =
    model !== (agent.settings?.model ?? "") ||
    reasoning !== (agent.settings?.reasoning ?? "");
  return (
    <section className="agent-model-settings" aria-label="Agent model settings">
      <div className="agent-model-title">
        <Cpu size={18} />
        <h3>Model & reasoning</h3>
        <button
          type="button"
          className="model-refresh"
          aria-label="Refresh available models"
          title="Refresh available models"
          disabled={loading || saving}
          onClick={() => setRevision((v) => v + 1)}
        >
          <RefreshCw size={15} />
        </button>
      </div>
      <p className="model-help">
        Choose how {agent.name} handles future tasks.
      </p>
      <label htmlFor={`model-${agent.id}`}>Model</label>
      <Dropdown
        id={`model-${agent.id}`}
        value={model}
        disabled={loading || saving}
        onValueChange={(value) => {
          setModel(value);
          setReasoning("");
          setMessage("");
        }}
      >
        <option value="">Runtime default</option>
        {model && !selected && (
          <option value={model}>
            {model} · {loading ? "loading" : "unavailable"}
          </option>
        )}
        {models.map((m) => (
          <option key={m.model} value={m.model}>
            {m.name}
            {m.is_default ? " · default" : ""}
          </option>
        ))}
      </Dropdown>
      <label htmlFor={`reasoning-${agent.id}`}>Reasoning effort</label>
      <Dropdown
        id={`reasoning-${agent.id}`}
        value={reasoning}
        disabled={!selected || loading || saving}
        onValueChange={(value) => {
          setReasoning(value);
          setMessage("");
        }}
      >
        <option value="">
          {selected
            ? `Model default · ${selected.default_reasoning}`
            : "Model default"}
        </option>
        {reasoning &&
          !selected?.reasoning_efforts.some((r) => r.value === reasoning) && (
            <option value={reasoning}>{reasoning} · unavailable</option>
          )}
        {selected?.reasoning_efforts.map((r) => (
          <option key={r.value} value={r.value}>
            {r.value}
          </option>
        ))}
      </Dropdown>
      {loading && (
        <p className="model-help" role="status">
          Loading models from your Codex account…
        </p>
      )}
      {loadError && (
        <p className="model-error" role="alert">
          {loadError}
        </p>
      )}
      {selected && (
        <p className="model-help">
          {selected.reasoning_efforts.find((r) => r.value === reasoning)
            ?.description ?? selected.description}
        </p>
      )}
      <p className="model-help">
        Applies to the next run or retry. Higher reasoning can take longer and
        use more of your allowance.
      </p>
      <div className="model-actions">
        <button
          type="button"
          className="model-save"
          disabled={
            !dirty || saving || (Boolean(model) && (!selected || loading))
          }
          onClick={async () => {
            setSaving(true);
            setMessage("");
            setFailed(false);
            try {
              await api(`/agents/${encodeURIComponent(agent.id)}/settings`, {
                model: model || null,
                reasoning: reasoning || null,
              });
              await useOffice.getState().refresh();
              setMessage("Saved. Applies to the next run or retry.");
            } catch (error) {
              setFailed(true);
              setMessage((error as Error).message);
            } finally {
              setSaving(false);
            }
          }}
        >
          <Save size={15} />
          {saving ? "Saving…" : "Save preferences"}
        </button>
        <button
          type="button"
          className="model-reset"
          disabled={saving}
          onClick={() => {
            setModel("");
            setReasoning("");
            setMessage("");
          }}
        >
          <RotateCcw size={15} />
          Use defaults
        </button>
      </div>
      {message && (
        <p className={failed ? "model-error" : "model-saved"} role="status">
          {message}
        </p>
      )}
    </section>
  );
}
