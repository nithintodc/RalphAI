# Marketing Breakdown - Go-To-Market Strategy

## What It Does

Marketing Breakdown is a lightweight Node.js + vanilla HTML/CSS analytics app for DoorDash marketing and financial export analysis. Users upload a DoorDash export folder (or use default files), and the app analyzes financial detailed transactions with a clean, branded TODC interface. It is a focused, single-purpose tool for quickly breaking down marketing campaign performance from DoorDash data exports.

**Internal users**: TODC operations team members who need a quick campaign breakdown without spinning up the full DeepDive or VB Dashboard.

---

## Productization Assessment: LOW (standalone) / USEFUL as lightweight module

Marketing Breakdown is too narrow for standalone productization. It handles one platform (DoorDash) with one analysis type (financial transaction breakdown). Its value is speed and simplicity -- it fills the gap when someone needs a quick answer without the overhead of the full analytics stack.

### Role in the Ecosystem
- **Quick analysis tool** for operators or account managers in the field
- **Validation tool** to spot-check numbers before a full DeepDive run
- **Template** for building similar quick-analysis tools for UberEats and GrubHub

---

## Internal Adoption Strategy

### Current Strengths
- Very lightweight (Node.js + static HTML, no Python/Streamlit dependencies)
- Clean branded UI with upload + analyze workflow
- Works offline / locally with no external dependencies
- Fast startup and analysis

### Gaps
1. **DoorDash only** - no UberEats or GrubHub support
2. **No persistence** - results disappear on page refresh
3. **No export** - cannot save or share analysis results
4. **Limited metrics** - financial transactions only, no marketing ROAS view
5. **No deployment** - runs locally only

### Adoption Actions
1. Deploy as a static site with Node backend on a shared server or Netlify
2. Add "Copy to Clipboard" and "Export CSV" buttons for analysis results
3. Create a bookmark/shortcut on team devices for quick access
4. Position as the "5-second answer" tool -- use Marketing Breakdown for quick checks, DeepDive for full analysis
5. Add UberEats export support to increase utility

### Integration Points
- DoorDash CSV exports (direct upload)
- Could feed results into RalphAI for automated recommendations
- Could be embedded as an iframe in RalphAI dashboard for quick analysis

---

## KPIs

### Internal
- Number of analyses run per week
- Time from upload to result (target: < 10 seconds)
- User satisfaction (does the team actually use it vs going straight to DeepDive?)
- Number of issues caught by quick Marketing Breakdown check before full analysis
