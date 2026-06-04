# Marketing Breakdown - Task List

## Coding

- [ ] Add UberEats export file support (parse UberEats CSV format)
- [ ] Add GrubHub export file support
- [ ] Implement "Export Results as CSV" button
- [ ] Add "Copy to Clipboard" for key metrics
- [ ] Build marketing ROAS analysis view (not just financial transactions)
- [ ] Add date range filtering to analysis results
- [ ] Implement store-level breakdown within the analysis
- [ ] Add comparison mode (upload two periods, see the diff)
- [ ] Add charts/visualizations (Chart.js or similar lightweight library)
- [ ] Implement local storage to persist recent analyses
- [ ] Add drag-and-drop file upload (in addition to folder select)
- [ ] Make responsive for mobile/tablet use
- [ ] Add loading indicator during analysis

## Operations

- [ ] Deploy to Netlify or shared server for team-wide access
- [ ] Set up CI/CD for automatic deployment on push
- [ ] Add basic error tracking (Sentry or similar)

## Documentation

- [ ] Create README.md with setup instructions and usage guide
- [ ] Document supported file formats and folder structures
- [ ] Add inline help tooltips in the UI explaining each metric

## Integration

- [ ] Build API endpoint that returns analysis results as JSON (for RalphAI consumption)
- [ ] Add "Send to DeepDive" button for deeper analysis of the same data
- [ ] Create webhook to notify Slack when analysis reveals ROAS < 4 campaigns
