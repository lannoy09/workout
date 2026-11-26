/**
 * Workout Tracker — Google Sheets backend for strength-cardio-sites.html
 *
 * SETUP (one time, ~2 minutes):
 *   1. Create a Google Sheet (name it anything, e.g. "Workout Data").
 *   2. In the Sheet, open: Extensions → Apps Script.
 *   3. Replace the default Code.gs contents with this entire file. Save.
 *   4. Deploy → New deployment → Type: Web app.
 *        - Description: anything
 *        - Execute as: Me
 *        - Who has access: Anyone (or "Anyone with the link" — must not require sign-in,
 *          because the Google Sites iframe runs anonymously from the browser).
 *   5. Click Deploy, authorize when prompted, and copy the Web app URL.
 *   6. In strength-cardio-sites.html, set:   const BACKEND_URL = 'PASTE_URL_HERE';
 *   7. Embed strength-cardio-sites.html in Google Sites via Insert → Embed → Embed code.
 *
 * STORAGE MODEL:
 *   Sheet "State" cell A1 holds a single JSON blob of the entire workout log. The app
 *   reads this on load and overwrites it on each save. If you want human-readable rows,
 *   also enable APPEND_HISTORY = true (see below) — it appends one row per saved exercise
 *   to a "History" sheet without affecting the state blob.
 */

const STATE_SHEET = 'State';
const STATE_CELL = 'A1';
const HISTORY_SHEET = 'History';
const APPEND_HISTORY = true; // set to false if you don't want the readable log

function doGet(e) {
  try {
    const sheet = getOrCreateSheet_(STATE_SHEET);
    const raw = sheet.getRange(STATE_CELL).getValue();
    const log = raw ? JSON.parse(raw) : {};
    return jsonResponse_({ ok: true, log: log });
  } catch (err) {
    return jsonResponse_({ ok: false, error: String(err && err.message || err) });
  }
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    const log = body.log || {};
    const sheet = getOrCreateSheet_(STATE_SHEET);
    sheet.getRange(STATE_CELL).setValue(JSON.stringify(log));
    if (APPEND_HISTORY) appendHistory_(log);
    return jsonResponse_({ ok: true });
  } catch (err) {
    return jsonResponse_({ ok: false, error: String(err && err.message || err) });
  }
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getOrCreateSheet_(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  return sheet;
}

/**
 * Appends any logged entries that aren't already in the History sheet.
 * Keyed by (date, session, exercise, setIndex) to prevent duplicates on resave.
 */
function appendHistory_(log) {
  const sheet = getOrCreateSheet_(HISTORY_SHEET);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Date', 'Session', 'Exercise', 'Set', 'Weight', 'Reps', 'Notes', 'LoggedAt']);
    sheet.setFrozenRows(1);
  }
  const existing = new Set();
  const last = sheet.getLastRow();
  if (last > 1) {
    const rows = sheet.getRange(2, 1, last - 1, 4).getValues();
    rows.forEach(r => existing.add([r[0], r[1], r[2], r[3]].join('|')));
  }
  const now = new Date();
  const toAppend = [];
  Object.keys(log).sort().forEach(date => {
    ['am', 'pm'].forEach(session => {
      const sessLog = log[date] && log[date][session];
      if (!sessLog) return;
      Object.keys(sessLog).forEach(ex => {
        const entry = sessLog[ex];
        if (!entry) return;
        if (entry.setLogs && entry.setLogs.length) {
          entry.setLogs.forEach((s, i) => {
            const key = [date, session, ex, i + 1].join('|');
            if (existing.has(key)) return;
            toAppend.push([date, session, ex, i + 1, s.weight || '', s.reps || '', s.notes || entry.notes || '', now]);
          });
        } else if (entry.duration || entry.distance || entry.avgPace || entry.heartRate) {
          const key = [date, session, ex, 'cardio'].join('|');
          if (existing.has(key)) return;
          const parts = [];
          if (entry.duration) parts.push(entry.duration);
          if (entry.distance) parts.push(entry.distance);
          if (entry.avgPace) parts.push(entry.avgPace);
          if (entry.heartRate) parts.push('HR ' + entry.heartRate);
          toAppend.push([date, session, ex, 'cardio', '', parts.join(' / '), entry.notes || '', now]);
        }
      });
    });
  });
  if (toAppend.length) sheet.getRange(sheet.getLastRow() + 1, 1, toAppend.length, 8).setValues(toAppend);
}
