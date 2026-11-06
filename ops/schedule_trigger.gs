// HN Daily: start the GitHub scraper at 8:00 and 18:00 America/Los_Angeles.
// GitHub's own cron is often hours late; this Google Apps Script project calls workflow_dispatch on time.
// Setup: Project Settings -> time zone America/Los_Angeles; Script Properties -> GITHUB_TOKEN
// (fine-grained token, repository chaowang15/hackernews only, Actions: Read and write). Then run setupTriggers once.
const REPO = 'chaowang15/hackernews';
const WORKFLOW = 'hn_top.yml';

function setupTriggers() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('morning').timeBased().everyDays(1).atHour(8).nearMinute(0).create();
  ScriptApp.newTrigger('evening').timeBased().everyDays(1).atHour(18).nearMinute(0).create();
}

function morning() { dispatch_('morning'); }
function evening() { dispatch_('full'); }

function dispatch_(edition) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  const res = UrlFetchApp.fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ ref: 'main', inputs: { edition: edition } }),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 204) throw new Error('GitHub ' + res.getResponseCode() + ': ' + res.getContentText());
}
