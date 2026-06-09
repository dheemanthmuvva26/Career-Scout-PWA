const msg = $input.first().json.message || $input.first().json.edited_message || {};
const text = (msg.text || '').trim();
const chatId = msg.chat?.id;

const BASE_URL = 'http://host.docker.internal:8000';
const urg = { hot: '🔴', active: '🟡', aging: '⚪', stale: '💀' };

const HELP_TEXT = [
  '🤖 *Career Scout — Command Reference*',
  '',
  '📋 *Browsing Jobs*',
  '/digest — Today\'s top scored matches',
  '/jobs — List latest new jobs (score ≥ 3.5)',
  '/job <id> — Full detail: score, skills, fit summary',
  '',
  '📩 *Tracking Applications*',
  '/apply <id> — Mark as applied, sets 7-day follow-up reminder',
  '/interview <id> — Mark interview received',
  '/offer <id> — Mark offer received',
  '/rejected <id> [reason] — Mark as rejected',
  '/ghosted <id> — Mark as ghosted (no response after 14 days)',
  '/note <id> <text> — Add a private note to a job',
  '',
  '📄 *Resumes*',
  '/resume <id> — Generate ATS-optimised PDF resume for a job',
  '',
  '🔍 *Scouting*',
  '/scout — Trigger a fresh job scan right now',
  '/stats — Dashboard summary (pipeline counts + interview rate)',
  '/digest — Best jobs of the day',
  '',
  '⚙️ *Manage Watchlists*',
  '/add company <name> [url] — Add company to target watchlist',
  '/add role <title> — Add role keyword to search for',
  '/blacklist <company name> — Never show jobs from this company again',
  '',
  '💡 *Tips*',
  '• Job IDs appear after each listing — tap to copy, then use in commands',
  '• Urgency: 🔴 hot (<24h)  🟡 active  ⚪ aging  💀 stale',
  '• Scores are out of 5 ★',
  '• /start shows this help any time',
].join('\n');

if (!text.startsWith('/')) {
  return [{ json: { chatId, text: 'Send a command. Try /help to see everything available.' } }];
}

const parts = text.split(/\s+/);
const rawCmd = parts[0].replace('/', '').toLowerCase();
const args = parts.slice(1);

async function api(method, path, body) {
  try {
    const opts = { method };
    if (body) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(BASE_URL + path, opts);
    return await res.json();
  } catch(e) {
    return { error: String(e) };
  }
}

let cmd = rawCmd;
let a = args;
if (cmd === 'add' && args[0]) { cmd = 'add_' + args[0].toLowerCase(); a = args.slice(1); }

let reply = '';

if (cmd === 'start') {
  reply = '👋 Welcome to *Career Scout*!\n\nI scan job boards every 6 hours and send you the best Data \/ AI \/ BI roles in India — scored and ranked for your profile.\n\n' + HELP_TEXT;

} else if (cmd === 'help') {
  reply = HELP_TEXT;

} else if (cmd === 'jobs') {
  const jobs = await api('GET', '/jobs?status=new&min_score=3.5&limit=5');
  const list = Array.isArray(jobs) ? jobs : [];
  if (!list.length) {
    reply = 'No new jobs right now. Try /scout to run a fresh scan.';
  } else {
    const lines = list.map(j =>
      `${urg[j.urgency] || '⚪'} *${j.title}* @ ${j.company} (${(j.score||0).toFixed(1)}★)\n  ${j.location||'N/A'} — /job ${j.id}`
    );
    reply = '🗂 *Top new jobs:*\n\n' + lines.join('\n\n');
  }

} else if (cmd === 'job') {
  const j = await api('GET', `/jobs/${a[0]}`);
  if (!j || !j.id) {
    reply = 'Job not found. Use /jobs to get valid IDs.';
  } else {
    let d = {};
    try { d = typeof j.score_detail === 'string' ? JSON.parse(j.score_detail) : (j.score_detail || {}); } catch(e) {}
    const matched = (d.matched_skills || []).join(', ') || 'N/A';
    const missing = (d.missing_skills || []).join(', ') || 'None';
    reply = `${urg[j.urgency]||'⚪'} *${j.title}* @ ${j.company}\n${j.location||'N/A'} — Score: ${(j.score||0).toFixed(1)}★ — _${j.status}_\n\n💡 ${d.fit_summary||'No summary.'}\n\n✅ *Matched:* ${matched}\n❌ *Missing:* ${missing}\n\n🔗 ${j.url||'N/A'}\n\n/apply ${j.id}`;
  }

} else if (cmd === 'apply') {
  const r = await api('POST', `/jobs/${a[0]}/apply`);
  reply = r.ok
    ? `✅ Applied to *${r.title}* @ ${r.company}\nFollow-up reminder set for ${r.follow_up_due}.`
    : `❌ ${r.detail || 'Error applying. Check the job ID.'}`;

} else if (cmd === 'interview') {
  if (!a[0]) { reply = 'Usage: /interview <job_id>'; }
  else {
    await api('POST', `/jobs/${a[0]}/outcome`, { outcome: 'interview' });
    reply = '🎉 *Interview scheduled!* Marked. Go prep — you got this!';
  }

} else if (cmd === 'offer') {
  if (!a[0]) { reply = 'Usage: /offer <job_id>'; }
  else {
    await api('POST', `/jobs/${a[0]}/outcome`, { outcome: 'offer' });
    reply = '🎊 *OFFER received! Congratulations!* 🍳';
  }

} else if (cmd === 'rejected') {
  if (!a[0]) { reply = 'Usage: /rejected <job_id> [optional reason]'; }
  else {
    await api('POST', `/jobs/${a[0]}/outcome`, { outcome: 'rejected', rejection_reason: a.slice(1).join(' ') || null });
    reply = '👎 Marked as rejected. Every no gets you closer to a yes.';
  }

} else if (cmd === 'ghosted') {
  if (!a[0]) { reply = 'Usage: /ghosted <job_id>'; }
  else {
    await api('POST', `/jobs/${a[0]}/outcome`, { outcome: 'ghosted' });
    reply = '👻 Marked as ghosted. Auto-ghost runs after 14 days anyway.';
  }

} else if (cmd === 'note') {
  if (!a[0] || !a[1]) { reply = 'Usage: /note <job_id> <your note text>'; }
  else {
    await api('POST', `/jobs/${a[0]}/note`, { text: a.slice(1).join(' ') });
    reply = '📝 Note saved.';
  }

} else if (cmd === 'blacklist') {
  if (!a.length) { reply = 'Usage: /blacklist <company name>'; }
  else {
    const name = a.join(' ');
    await api('POST', `/companies/blacklist?name=${encodeURIComponent(name)}`);
    reply = '🚫 *' + name + '* blacklisted. No more jobs from them.';
  }

} else if (cmd === 'add_company') {
  if (!a[0]) { reply = 'Usage: /add company <name> [careers_url] [linkedin_slug]'; }
  else {
    await api('POST', '/companies', { name: a[0], careers_url: a[1] || '', linkedin_slug: a[2] || '' });
    reply = '🏢 *' + a[0] + '* added to watchlist.';
  }

} else if (cmd === 'add_role') {
  if (!a.length) { reply = 'Usage: /add role <job title>'; }
  else {
    await api('POST', '/roles', { title: a.join(' ') });
    reply = '🎯 Role *' + a.join(' ') + '* added to watchlist.';
  }

} else if (cmd === 'stats') {
  const s = await api('GET', '/stats');
  if (s.error) {
    reply = '❌ Could not reach API. Is the server running?';
  } else {
    const pct = s.applied > 0 ? ((s.interviews / s.applied) * 100).toFixed(0) : 0;
    reply = `📊 *Career Scout Stats*\n\n💼 Total tracked: ${s.total}\n🆕 New \/ unreviewed: ${s.new}\n📨 Applied: ${s.applied}\n🤝 Interviews: ${s.interviews}\n🎊 Offers: ${s.offers}\n⏳ Unscored: ${s.unscored}\n\n📈 Interview rate: ${pct}%`;
  }

} else if (cmd === 'scout') {
  await api('POST', '/scout');
  reply = '🔍 Scout started! New jobs will appear in your next digest. Check back with /jobs in a few minutes.';

} else if (cmd === 'resume') {
  if (!a[0]) {
    reply = 'Usage: /resume <job_id>\n\nGenerates an ATS-optimised PDF resume tailored to that specific job.';
  } else {
    const r = await api('POST', `/forge/${a[0]}`);
    reply = r.telegram_message || r.error || '❌ Resume generation failed.';
  }

} else if (cmd === 'digest') {
  const jobs = await api('GET', '/jobs/digest?limit=5');
  const list = Array.isArray(jobs) ? jobs : [];
  if (!list.length) {
    reply = 'No high-scoring jobs today. Try /scout to fetch fresh listings.';
  } else {
    const lines = list.map(j =>
      `${urg[j.urgency]||'⚪'} *${j.title}* @ ${j.company} (${(j.score||0).toFixed(1)}★)\n  ${j.location||'N/A'} — /job ${j.id}`
    );
    reply = '☀️ *Today\'s top matches:*\n\n' + lines.join('\n\n') + '\n\n_Use /job <id> for full details or /apply <id> to track._';
  }

} else {
  reply = '❓ Unknown command: */' + rawCmd + '*\n\nSend /help to see all available commands.';
}

return [{ json: { chatId, text: reply } }];
