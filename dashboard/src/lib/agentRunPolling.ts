export type AgentRunAgent = "offers" | "ads" | "strategist";

/** Rolling window of log lines shown in agent run panels. */
export const AGENT_LOG_VISIBLE_LINES = 12;

export function appendAgentLogLines(
  prev: string[],
  incoming: string[],
  max = AGENT_LOG_VISIBLE_LINES
): string[] {
  if (!incoming.length) return prev;
  return [...prev, ...incoming].slice(-max);
}

export type AgentRunPayload = Record<string, unknown>;

export type LogTailPayload = {
  lines?: string[];
  line_count?: number;
  status?: string;
  queue_position?: number;
};

function parseApiError(body: string, status: number): string {
  const trimmed = body.trim();
  if (!trimmed) return `Request failed (HTTP ${status})`;
  try {
    const parsed = JSON.parse(trimmed) as {
      detail?: string | Array<{ msg?: string }>;
      error?: string;
    };
    if (typeof parsed.error === "string" && parsed.error.trim()) {
      return parsed.error.trim();
    }
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
  } catch {
    // not JSON
  }
  return trimmed;
}

export async function pollAgentRun(
  agent: AgentRunAgent,
  runId: string,
  callbacks?: {
    onStatus?: (status: string, payload: AgentRunPayload) => void;
    onLogLines?: (lines: string[], lineCount: number) => void;
  }
): Promise<AgentRunPayload> {
  let afterLine = 0;

  for (;;) {
    const [statusRes, logsRes] = await Promise.all([
      fetch(`/api/runs/${agent}/${encodeURIComponent(runId)}`),
      fetch(`/api/runs/${agent}/${encodeURIComponent(runId)}/logs?after=${afterLine}`),
    ]);

    if (!statusRes.ok) {
      const text = await statusRes.text();
      throw new Error(parseApiError(text, statusRes.status));
    }

    const data = (await statusRes.json()) as AgentRunPayload;
    const status = String(data.status || "").toLowerCase();
    callbacks?.onStatus?.(status, data);

    if (logsRes.ok) {
      const logs = (await logsRes.json()) as LogTailPayload;
      const lines = Array.isArray(logs.lines) ? logs.lines : [];
      const lineCount = typeof logs.line_count === "number" ? logs.line_count : afterLine + lines.length;
      if (lines.length > 0) {
        callbacks?.onLogLines?.(lines, lineCount);
        afterLine = lineCount;
      }
    }

    if (status && status !== "running" && status !== "queued") {
      if (status === "interrupted" || status === "error") {
        throw new Error(String(data.error || data.detail || `${agent} run did not complete.`));
      }
      return data;
    }

    await new Promise((r) => setTimeout(r, 2000));
  }
}
