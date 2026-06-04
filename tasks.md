# RalphAI Pending Next Tasks

This is the immediate pending task list for shipping the current RalphAI iteration.

## P0 - Finish In-Progress Features

- [x] Finalize DeepDive metric hierarchy integration across analyzer, reporter, and API response formatting.
- [x] Complete MarketingReco Ads Planner flow (planner logic + Excel export contract + API wiring).
- [x] Validate and expose new pages (`AdsPage`, `OffersPage`, `MarketingRecoPage`) in dashboard navigation and routes.
- [x] Ensure `orchestrator/event_router.py`, `triggers.py`, and `todc_flow.py` use the updated DeepDive + MarketingReco flows consistently.
- [x] Confirm `shared/config/settings.py` and `shared/config/__init__.py` include all new feature flags and defaults.

## P1 - Stabilize API and Slack Surfaces

- [ ] Harden `api/main.py` endpoints with input validation, consistent error payloads, and agent timeout handling.
- [ ] Complete Slack command behavior for DeepDive and MarketingReco with clear success/failure user messages.
- [ ] Add end-to-end test coverage for API + orchestrator handoff on the updated agent paths.

## P1 - Test and Quality Gates

- [ ] Expand `tests/test_deepdive.py` for new metric hierarchy and edge cases.
- [ ] Expand `tests/test_marketingreco.py` for ads planner outputs and fallback behavior.
- [ ] Finalize `tests/test_ralph_ads_upload_rows.py` and make upload parsing deterministic.
- [ ] Run and fix full pytest suite (`PYTHONPATH=. python3 -m pytest tests/ -q`) until green.

## P2 - Dashboard UX Completion

- [ ] Add loading, empty, and error states on DeepDive and MarketingReco pages.
- [ ] Surface agent run status/progress in UI (queued/running/success/failed).
- [ ] Ensure page-level forms match API contracts for Ads and Offers workflows.

## P2 - Documentation and Release Readiness

- [ ] Update `README.md` quick-start to include new pages and agent workflows.
- [ ] Keep `README.md` in sync with architecture changes (DeepDive metrics + Ads planner).
- [ ] Decide whether to keep both `tasks.md` and `tasks.MD`; consolidate to one canonical task file.
- [ ] Prepare release checklist: env vars, run commands, smoke tests, and rollback notes.
# RalphAI - Task List

## Coding

- [ ] Harden agent error handling -- add retries, timeouts, and structured error responses for all agents
- [ ] Complete Slack bot wiring -- ensure all command stubs in slack_bot/ actually invoke the correct agents
- [ ] Add UberEats and GrubHub support to browser automation agents
- [ ] Build operator onboarding flow in the dashboard (guided setup wizard)
- [ ] Implement user authentication and role-based access in the dashboard
- [ ] Add real-time agent run status/progress tracking in the dashboard UI
- [ ] Create API endpoint layer (FastAPI) for all agent capabilities -- needed for SaaS
- [ ] Add webhook support for Slack notifications on agent completion
- [ ] Build automated test suite for each agent pipeline (unit + integration)
- [ ] Implement rate limiting and queue management for concurrent agent runs
- [ ] Add data validation layer for CSV/Excel uploads
- [ ] Create agent performance monitoring dashboard (success rates, latency, errors)
- [ ] Implement multi-tenant data isolation for SaaS mode
- [ ] Add SSO/OAuth support for enterprise customers
- [ ] Build campaign performance alerting system (ROAS drops below threshold)

## Operations

- [ ] Set up CI/CD pipeline (GitHub Actions) for automated testing and deployment
- [ ] Configure Docker Compose for full-stack local development
- [ ] Set up staging environment on GCP for pre-production testing
- [ ] Create runbook for common failure modes and recovery procedures
- [ ] Set up monitoring and alerting (Datadog/New Relic or Prometheus+Grafana)
- [ ] Implement automated backups for operator data
- [ ] Create operator data migration scripts (for onboarding new restaurants)
- [ ] Set up Redis properly for production queue management
- [ ] Configure log aggregation and search

## Documentation

- [ ] Write API documentation for all agent endpoints
- [ ] Create operator user guide with screenshots
- [ ] Document agent contract JSON schema with examples
- [ ] Write architecture decision records (ADRs) for key design choices
- [ ] Create troubleshooting guide for common agent failures
- [ ] Build internal wiki page for TODC team onboarding
- [ ] Record Loom video walkthroughs for each major feature
- [ ] Document environment variables and configuration options

## Productization

- [ ] Design and implement SaaS pricing/billing system (Stripe integration)
- [ ] Build self-service signup flow with email verification
- [ ] Create marketing landing page for RalphAI
- [ ] Collect 3-5 case studies from TODC operators (ROAS improvement, time saved)
- [ ] Apply to DoorDash partner directory
- [ ] Create demo environment with sample data for prospects
- [ ] Design referral program mechanics and tracking
- [ ] Write 3 SEO-optimized blog posts: "Delivery Marketing ROAS Benchmarks", "DoorDash Campaign Optimization Guide", "Multi-Platform Delivery Marketing Automation"
- [ ] Set up product analytics (Mixpanel/PostHog) to track user behavior
- [ ] Create investor pitch deck if seeking funding
- [ ] Register domain and set up branded email
- [ ] Build comparison pages vs manual process and vs competitors
