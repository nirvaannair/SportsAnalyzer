chrome.storage.local.get('status', ({ status }) => {
  const out = document.getElementById('out');
  if (!status) return;
  const flags = status.flags || {};
  const inr = status.balances && status.balances.available ? status.balances.available.inr : undefined;
  const row = (k, v, cls = '') => `<div class="row"><span class="muted">${k}</span><span class="${cls}">${v}</span></div>`;
  out.innerHTML =
    row('Local app', status.appConnected ? 'connected' : 'not reachable', status.appConnected ? 'ok' : 'bad') +
    row('Stake balance', inr === undefined ? '—' : `₹${inr}`) +
    row('Learn mode', flags.learn_mode ? 'on' : 'off') +
    row('Execution', flags.execution_enabled ? 'ON' : 'off', flags.execution_enabled ? 'ok' : '') +
    (status.lastOrder ? row('Last bet', `#${status.lastOrder.id} ${status.lastOrder.status}`) : '') +
    (status.error ? `<p class="bad">${String(status.error).slice(0, 160)}</p>` : '') +
    `<p class="muted">Updated ${new Date(status.at).toLocaleTimeString()}</p>`;
});
