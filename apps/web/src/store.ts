import { create } from "zustand";

export type Task = {
  id: string;
  project_id: string;
  agent_id: string;
  title: string;
  description: string;
  status: string;
  depends_on: string[];
  attempts: number;
  acceptance_criteria: string[];
  error?: string;
  result?: {
    summary: string;
    findings?: string[];
    changes?: { path: string; content: string }[];
    test_result?: { exit_code: number; output: string };
  };
};
export type Agent = {
  id: string;
  name: string;
  role: string;
  color: string;
  status: string;
  task?: Task;
  settings?: { model: string | null; reasoning: string | null };
};
export type Project = {
  id: string;
  name: string;
  workspace: string;
  requirement: string;
};
export type OfficeEvent = {
  id: number;
  type: string;
  at: string;
  agent_id?: string;
  project_id?: string;
  task_id?: string;
  message?: string;
  tool?: string;
  diff?: string;
  output?: string;
  [key: string]: unknown;
};
export type Approval = {
  id: string;
  agent_id: string;
  task_id: string;
  project_id: string;
  kind: string;
  status: string;
  payload: Record<string, unknown>;
};
export type Run = {
  model_settings?: { model: string | null; reasoning: string | null };
  id: string;
  task_id: string;
  project_id: string;
  agent_id: string;
  status: string;
  attempt: number;
  result?: { summary: string };
  error?: string;
};
type State = {
  runs: Run[];
  agents: Agent[];
  projects: Project[];
  tasks: Task[];
  events: OfficeEvent[];
  approvals: Approval[];
  busy: boolean;
};
export const roles: Agent[] = [
  {
    id: "planner",
    name: "Planner",
    role: "Plans & architecture",
    color: "#8ca9ff",
    status: "idle",
  },
  {
    id: "frontend",
    name: "Frontend Dev",
    role: "Interfaces & experience",
    color: "#61d6d0",
    status: "idle",
  },
  {
    id: "backend",
    name: "Backend Dev",
    role: "APIs & data systems",
    color: "#d4aeff",
    status: "idle",
  },
  {
    id: "qa",
    name: "QA Engineer",
    role: "Tests & quality",
    color: "#f4c778",
    status: "idle",
  },
  {
    id: "devops",
    name: "DevOps",
    role: "Builds & infrastructure",
    color: "#91bbfc",
    status: "idle",
  },
  {
    id: "reviewer",
    name: "Code Reviewer",
    role: "Review & security",
    color: "#b8db97",
    status: "idle",
  },
];
export const useOffice = create<
  State & {
    online: boolean;
    selected: string | null;
    select: (id: string | null) => void;
    refresh: () => Promise<void>;
    setOnline: (v: boolean) => void;
  }
>((set) => ({
  runs: [],
  agents: roles,
  projects: [],
  tasks: [],
  events: [],
  approvals: [],
  busy: false,
  online: false,
  selected: null,
  select: (selected) => set({ selected }),
  setOnline: (online) => set({ online }),
  refresh: async () => {
    const state = await api<State>("/state");
    set({ ...state, online: true });
  },
}));
export async function api<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      message = JSON.parse(text).detail ?? text;
    } catch {}
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}
export function connectOffice(): () => void {
  let disposed = false,
    socket: WebSocket | undefined,
    timer: ReturnType<typeof setTimeout>,
    cursor = 0;
  async function connect() {
    try {
      await api("/session");
      await useOffice.getState().refresh();
      cursor = useOffice.getState().events.at(-1)?.id ?? 0;
      if (disposed) return;
      socket = new WebSocket(
        (location.protocol === "https:" ? "wss://" : "ws://") +
          location.host +
          "/ws?after=" +
          cursor,
      );
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.events?.length) {
          cursor = payload.events.at(-1).id;
          void useOffice
            .getState()
            .refresh()
            .catch(() => useOffice.getState().setOnline(false));
        }
      };
      socket.onclose = () => {
        useOffice.getState().setOnline(false);
        if (!disposed) timer = setTimeout(connect, 3000);
      };
      socket.onerror = () => socket?.close();
    } catch {
      useOffice.getState().setOnline(false);
      if (!disposed) timer = setTimeout(connect, 3000);
    }
  }
  void connect();
  return () => {
    disposed = true;
    clearTimeout(timer);
    socket?.close();
  };
}
