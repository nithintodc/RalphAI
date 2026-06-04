import { useEffect, useState } from "react";
import {
  Plus,
  Play,
  Trash2,
  Loader2,
  Clock,
  CheckCircle2,
  XCircle,
  Calendar,
} from "lucide-react";

type AgentDef = {
  id: string;
  name: string;
  category: string;
  description: string;
  inputs: { name: string; type: string; required: boolean; description?: string; options?: string[] }[];
};

type Job = {
  id: string;
  name: string;
  agent_id: string;
  variables: Record<string, unknown>;
  schedule: string;
  enabled: boolean;
  created_at: string;
  last_run_at: string | null;
  last_status: string | null;
  run_count: number;
};

const statusBadge: Record<string, string> = {
  success: "bg-brand-100 text-ink-900",
  failed: "bg-red-50 text-red-800",
  error: "bg-red-50 text-red-800",
  running: "bg-amber-50 text-amber-800",
};

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [agents, setAgents] = useState<AgentDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [running, setRunning] = useState<string | null>(null);

  // Create form state
  const [newName, setNewName] = useState("");
  const [newAgent, setNewAgent] = useState("");
  const [newSchedule, setNewSchedule] = useState("");
  const [newVars, setNewVars] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);

  async function loadData() {
    try {
      const [jobsRes, agentsRes] = await Promise.all([
        fetch("/api/jobs"),
        fetch("/api/agents"),
      ]);
      if (jobsRes.ok) setJobs(await jobsRes.json());
      if (agentsRes.ok) setAgents(await agentsRes.json());
    } catch {
      /* API unavailable */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const selectedAgent = agents.find((a) => a.id === newAgent);

  async function handleCreate() {
    if (!newName.trim() || !newAgent) return;
    setCreating(true);
    try {
      const body = new FormData();
      body.append("name", newName.trim());
      body.append("agent_id", newAgent);
      body.append("schedule", newSchedule.trim());
      body.append("variables", JSON.stringify(newVars));
      const res = await fetch("/api/jobs", { method: "POST", body });
      if (res.ok) {
        setShowCreate(false);
        setNewName("");
        setNewAgent("");
        setNewSchedule("");
        setNewVars({});
        await loadData();
      }
    } finally {
      setCreating(false);
    }
  }

  async function handleRun(jobId: string) {
    setRunning(jobId);
    try {
      await fetch(`/api/jobs/${jobId}/run`, { method: "POST" });
      await loadData();
    } finally {
      setRunning(null);
    }
  }

  async function handleDelete(jobId: string) {
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    await loadData();
  }

  function agentName(id: string) {
    return agents.find((a) => a.id === id)?.name ?? id;
  }

  function formatDate(iso: string | null) {
    if (!iso) return "Never";
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-ink-400" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
            Jobs
          </h2>
          <p className="mt-1 text-ink-600 dark:text-white/65">
            Save agent configurations and schedule recurring runs.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className="inline-flex items-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900"
        >
          <Plus className="h-4 w-4" />
          New Job
        </button>
      </div>

      {showCreate && (
        <div className="brand-card rounded-[28px] p-6">
          <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
            Create Job
          </h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-ink-700 dark:text-white/70">
                Job Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Weekly Data Pull"
                className="mt-1 w-full rounded-xl border border-brand-200 bg-white px-3 py-2 text-sm text-ink-900 shadow-sm focus:border-brand-500 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-ink-700 dark:text-white/70">
                Agent
              </label>
              <select
                value={newAgent}
                onChange={(e) => {
                  setNewAgent(e.target.value);
                  setNewVars({});
                }}
                className="mt-1 w-full rounded-xl border border-brand-200 bg-white px-3 py-2 text-sm text-ink-900 shadow-sm focus:border-brand-500 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                <option value="">Select an agent...</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} — {a.category}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-ink-700 dark:text-white/70">
                Schedule (cron expression, optional)
              </label>
              <input
                type="text"
                value={newSchedule}
                onChange={(e) => setNewSchedule(e.target.value)}
                placeholder="e.g. 0 9 * * 1 (every Monday at 9am) — leave empty for manual"
                className="mt-1 w-full rounded-xl border border-brand-200 bg-white px-3 py-2 text-sm text-ink-900 shadow-sm focus:border-brand-500 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </div>
          </div>

          {selectedAgent && selectedAgent.inputs.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-semibold text-ink-600 dark:text-white/60">
                Variables
              </p>
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                {selectedAgent.inputs
                  .filter((inp) => inp.type !== "file" && inp.type !== "file[]")
                  .map((inp) => (
                    <div key={inp.name}>
                      <label className="block text-xs font-medium text-ink-600 dark:text-white/60">
                        {inp.name}
                        {inp.required && (
                          <span className="ml-1 text-red-500">*</span>
                        )}
                        <span className="ml-1 text-ink-400">({inp.type})</span>
                      </label>
                      {inp.type === "select" && inp.options ? (
                        <select
                          value={newVars[inp.name] ?? ""}
                          onChange={(e) =>
                            setNewVars((v) => ({
                              ...v,
                              [inp.name]: e.target.value,
                            }))
                          }
                          className="mt-1 w-full rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm text-ink-900 focus:border-brand-500 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
                        >
                          <option value="">Select...</option>
                          {inp.options.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type={inp.type === "password" ? "password" : "text"}
                          value={newVars[inp.name] ?? ""}
                          onChange={(e) =>
                            setNewVars((v) => ({
                              ...v,
                              [inp.name]: e.target.value,
                            }))
                          }
                          placeholder={inp.description ?? ""}
                          className="mt-1 w-full rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm text-ink-900 focus:border-brand-500 focus:outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
                        />
                      )}
                    </div>
                  ))}
              </div>
              {selectedAgent.inputs.some(
                (i) => i.type === "file" || i.type === "file[]"
              ) && (
                <p className="mt-2 text-xs text-ink-400">
                  File inputs are not supported in jobs — upload files from the agent page.
                </p>
              )}
            </div>
          )}

          <div className="mt-5 flex gap-3">
            <button
              type="button"
              disabled={creating || !newName.trim() || !newAgent}
              onClick={handleCreate}
              className="inline-flex items-center gap-2 rounded-xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900"
            >
              {creating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Create
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-xl border border-brand-200 px-4 py-2 text-sm font-medium text-ink-600 transition hover:bg-brand-50 dark:border-white/10 dark:text-white/60"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="brand-card flex flex-col items-center rounded-[28px] p-12 text-center">
          <Calendar className="h-12 w-12 text-ink-300" />
          <h3 className="mt-4 font-display text-lg font-semibold text-ink-700 dark:text-white">
            No jobs yet
          </h3>
          <p className="mt-1 text-sm text-ink-500 dark:text-white/60">
            Create a job to save agent configurations and run them on demand or on a schedule.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="brand-card flex flex-col gap-4 rounded-[24px] p-5 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                  <h3 className="truncate font-display text-base font-semibold text-ink-900 dark:text-white">
                    {job.name}
                  </h3>
                  {job.last_status && (
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${statusBadge[job.last_status] ?? "bg-ink-100 text-ink-600"}`}
                    >
                      {job.last_status === "success" ? (
                        <CheckCircle2 className="h-3 w-3" />
                      ) : (
                        <XCircle className="h-3 w-3" />
                      )}
                      {job.last_status}
                    </span>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-500 dark:text-white/55">
                  <span>Agent: {agentName(job.agent_id)}</span>
                  {job.schedule && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {job.schedule}
                    </span>
                  )}
                  <span>Runs: {job.run_count}</span>
                  <span>Last: {formatDate(job.last_run_at)}</span>
                </div>
                {Object.keys(job.variables).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(job.variables).map(([k, v]) => (
                      <span
                        key={k}
                        className="rounded-lg bg-brand-50 px-2 py-0.5 text-xs text-ink-600 dark:bg-white/5 dark:text-white/50"
                      >
                        {k}={typeof v === "string" && v.length > 30 ? v.slice(0, 30) + "..." : String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  disabled={running === job.id}
                  onClick={() => handleRun(job.id)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-brand-500 px-3 py-2 text-sm font-semibold text-ink-900 transition hover:bg-brand-400 disabled:opacity-50"
                >
                  {running === job.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Run
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(job.id)}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-red-200 px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-900/30 dark:text-red-400"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
