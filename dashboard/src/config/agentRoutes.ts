/** Internal RalphAI routes for agent UIs (no separate localhost embed). */
export const AGENT_RUN_ROUTES: Record<string, string> = {
  marketingreco: "/agents/marketingreco",
  "ralphai-offers": "/agents/offers",
  "ralphai-ads": "/agents/ads",
  review: "/agents/campaign-review",
  "data-run": "/agents/data-run",
  strategist: "/agents/strategist",
  "health-check": "/agents/health-check",
  "campaign-killer": "/agents/campaign-killer",
  the_super_app: "/agents/the-super-app",
  app2_0: "/agents/the-super-app?tab=breakdown",
  app3_0: "/agents/the-super-app",
  markup_app: "/agents/markup-app",
};

export function agentRunRoute(agentId: string): string | undefined {
  return AGENT_RUN_ROUTES[agentId];
}
