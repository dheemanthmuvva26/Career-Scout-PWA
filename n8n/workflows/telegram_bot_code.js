// Parse Telegram update → {chatId, cmd, args, callbackQueryId}
// Handles both regular text messages AND inline-keyboard button taps
// (callback_query). All command logic lives in FastAPI POST /bot.
const body = $input.first().json.body || $input.first().json;
const cbq = body.callback_query;
const msg = body.message || body.edited_message || {};

let chatId, cmd, args, callbackQueryId = null;

if (cbq && cbq.id) {
  // Button tap — callback_data format is "action:short_id"
  chatId = (cbq.message && cbq.message.chat && cbq.message.chat.id) || (cbq.from && cbq.from.id);
  callbackQueryId = cbq.id;
  const data = cbq.data || '';
  const sep = data.indexOf(':');
  if (sep > -1) {
    cmd = data.substring(0, sep).toLowerCase();
    args = [data.substring(sep + 1)];
  } else {
    cmd = data.toLowerCase() || 'help';
    args = [];
  }
} else {
  const text = (msg.text || '').trim();
  chatId = msg.chat?.id;
  if (!chatId) return [];

  const parts = text.split(/\s+/);
  const rawCmd = (parts[0] || '').replace(/^\//, '').toLowerCase().split('@')[0];
  args = parts.slice(1);
  cmd = rawCmd || 'help';
  if (cmd === 'add' && args.length > 0) {
    cmd = 'add_' + args[0].toLowerCase();
    args = args.slice(1);
  }
}

return [{ json: { chatId, cmd, args, callbackQueryId } }];
