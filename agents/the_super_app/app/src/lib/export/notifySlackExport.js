import { formatSlashDateRange } from '../utils/dateUtils';

function slackExportUrl() {
  if (typeof window === 'undefined') return null;
  return `${window.location.origin}/api/slack/super-app-export`;
}

/** Notify Ralph-AI Slack with Doc + Excel links (best-effort). */
export async function notifySlackExport(config, { docUrl, spreadsheetUrl }) {
  const targetUrl = slackExportUrl();
  if (!targetUrl) return;

  const prePeriod = formatSlashDateRange(config.ddPreStart, config.ddPreEnd);
  const postPeriod = formatSlashDateRange(config.ddPostStart, config.ddPostEnd);

  try {
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        operatorName: (config.operatorName || '').trim(),
        prePeriod,
        postPeriod,
        docUrl: docUrl || null,
        spreadsheetUrl: spreadsheetUrl || null,
      }),
    });
    if (!response.ok) {
      console.warn('Slack export notification failed:', response.status);
    }
  } catch (err) {
    console.warn('Slack export notification error:', err);
  }
}
