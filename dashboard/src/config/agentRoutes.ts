import { REPORTING_BROWSER_USE_FORKS, reportingBrowserUseRoute } from "./reportingBrowserUseForks";

/** Internal RalphAI routes for agent UIs (no separate localhost embed). */
export const AGENT_RUN_ROUTES: Record<string, string> = {
  "ralphai-offers": "/agents/offers",
  "ralphai-ads": "/agents/ads",
  review: "/agents/health-check#campaign-review",
  "data-run": "/agents/data-run",
  strategist: "/agents/strategist",
  "health-check": "/agents/health-check",
  the_super_app: "/agents/the-super-app",
  app2_0: "/agents/the-super-app",
  markup_app: "/agents/markup-app",
  ...Object.fromEntries(
    REPORTING_BROWSER_USE_FORKS.map((f) => [f.id, reportingBrowserUseRoute(f.id)])
  ),
};

export function agentRunRoute(agentId: string): string | undefined {
  return AGENT_RUN_ROUTES[agentId];
}
