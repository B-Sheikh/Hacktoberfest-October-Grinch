const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const human = value => String(value).replaceAll('_', ' ');
const scale = () => Number($('scale').value);
let config, sites = [], selected = null, map, markers, fieldSite;

async function api(url, body) {
  const response = await fetch(url, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Waterline-Request': '1' }, body: JSON.stringify(body) });
  if (response.status === 401) { location.assign('/admin/login'); throw Error('Your admin session has ended. Sign in again.'); }
  const value = await response.json();
  if (!response.ok) throw Error(typeof value.detail === 'string' ? value.detail : 'Check the supplied information.');
  return value;
}
function notify(text, error = false) {
  $('message').textContent = text; $('message').hidden = false; $('message').classList.toggle('error', error);
}
function sourceLabel(site) {
  return site.extraction_status === 'failed' ? 'Model unavailable · simulated fallback' : site.simulated ? 'Demo data · simulated' : 'Photo estimate · verify on scene';
}
function summary(site) {
  return site.family === 'flood' ? `${site.depth.lo.toFixed(2)}–${site.depth.hi.toFixed(2)} m observed range` : `${site.zones.length} visible zones · ${human(site.crew)}`;
}
function chart(site) {
  if (!site.projections) return '';
  const width = 600, height = 240, padding = 45, cap = config.thresholds.depth_cap_m, end = config.thresholds.horizon_min;
  const x = t => padding + t / end * (width - padding * 2);
  const y = d => height - padding - d / cap * (height - padding * 2);
  let drawing = config.thresholds.depths_m.map(d => `<line x1="${padding}" x2="${width - padding}" y1="${y(d)}" y2="${y(d)}" stroke="#dbe4d4"/><text x="4" y="${y(d) + 5}" font-size="12" fill="#87977a">${d} m</text>`).join('');
  for (const [key, color] of [['best', '#72966a'], ['expected', '#285b51'], ['worst', '#b06a50']]) {
    drawing += `<polyline fill="none" stroke="${color}" stroke-width="2.5" points="${site.projections.map(p => `${x(p.t)},${y(p[key])}`).join(' ')}"/>`;
  }
  drawing += `<line x1="${x(site.eta_min)}" x2="${x(site.eta_min)}" y1="10" y2="${height - padding}" stroke="#5d7050" stroke-dasharray="5 5"/><text x="${x(site.eta_min) + 5}" y="22" font-size="12">Arrival</text><text x="${padding}" y="${height - 8}" font-size="12">Now</text><text x="${width - padding - 60}" y="${height - 8}" font-size="12">${end} min</text>`;
  return `<svg class="projection" viewBox="0 0 ${width} ${height}" role="img" aria-label="Best, expected and worst depth scenarios">${drawing}</svg><p>Light green: best · Dark green: expected · Rust: worst. Assumptions, not forecasts.</p><p>${esc(config.templates.projection)}</p>`;
}
function card(site, field = false) {
  const flood = site.family === 'flood';
  const metrics = flood ? `<div class="metrics"><div class="metric">CURRENT DEPTH<strong>${site.depth.lo.toFixed(2)}–${site.depth.hi.toFixed(2)} m</strong><small>Estimated range</small></div><div class="metric">AT ARRIVAL<strong>${site.depth_arrival_m.toFixed(2)} m</strong><small>If current rise continues</small></div><div class="metric">FLOW<strong>${esc(human(site.flow_class))}</strong><small>Classification is an assumption</small></div></div>` : `<div class="metrics"><div class="metric">VISIBLE ZONES<strong>${site.zones.length}</strong><small>Interior conditions unknown</small></div><div class="metric">SLAB MASS<strong>${site.mass_kg[1].toFixed(0)} kg</strong><small>Estimated upper bound</small></div><div class="metric">CREW CLASS<strong>${esc(human(site.crew))}</strong><small>Confirm on scene</small></div></div>`;
  const details = flood ? `<details><summary>Water projections and uncertainty</summary>${chart(site)}<p>Rise rate ${(site.rate_m_min * 100).toFixed(2)} ± ${(site.rate_sigma * 100).toFixed(2)} cm/min (assumption).</p><table><tr><th>Threshold</th><th>Time from now</th></tr>${site.threshold_times.map(t => `<tr><td>${t.depth_m} m</td><td>${t.minutes === null ? 'Not reached' : t.minutes.toFixed(1) + ' min'}</td></tr>`).join('')}</table></details>` : `<details open><summary>Visible zones and search order</summary><p>A visible aperture is an upper bound on interior height. It cannot establish a person's condition.</p>${site.zones.map(z => `<div class="report-entry"><strong>Zone ${esc(z.zone_id)} · ${esc(z.plausibility)} plausibility</strong><p>${z.height_m[0].toFixed(2)}–${z.height_m[1].toFixed(2)} m · ${esc(human(z.pattern))}<br>${esc(z.entry)}</p></div>`).join('')}<p>Mass range ${site.mass_kg[0]}–${site.mass_kg[1]} kg. Crew class uses upper bound (assumptions).</p></details>`;
  const navigation = `<div class="links">${Object.entries(site.navigation).map(([name, link]) => `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(name)} ↗</a>`).join('')}</div>`;
  return `<div class="detail-header"><span class="tier ${esc(site.tier)}">${esc(site.tier)} PRIORITY</span><span class="source-label">${esc(sourceLabel(site))}</span></div><h2>${esc(site.name)}</h2><p class="subtle">${esc(human(site.scene_type))} · ${site.n_reports} reports · ${esc(human(site.status))}</p>${metrics}${site.flags.length ? `<div class="flags">${site.flags.map(f => `<span class="flag">${esc(human(f))}</span>`).join('')}</div>` : ''}<h3>Response</h3><p class="subtle">${site.assignment ? `${esc(site.assignment.team_id)} · ${site.assignment.eta_min.toFixed(1)} min estimated travel` : 'Awaiting team assignment'}${site.time_to_critical_min !== null ? ` · ${site.time_to_critical_min.toFixed(1)} min to context threshold (assumption)` : ''}</p>${!field && site.assignment ? `<p><a class="button secondary" href="/field/${encodeURIComponent(site.assignment.team_id)}">Open team workspace ↗</a></p>` : ''}${navigation}<p class="subtle">${site.lat.toFixed(6)}, ${site.lon.toFixed(6)} · Verify approach conditions.</p>${details}<details ${field ? 'open' : ''}><summary>Responder briefing</summary><div class="briefing">${Object.entries(site.briefing).map(([key, value]) => `<p><strong>${esc(key)}</strong>${esc(value)}</p>`).join('')}</div></details><details><summary>Assumptions and supporting information</summary><p>Relative planning index: ${site.priority_index.toFixed(2)}.</p><p>${site.assumptions.map(esc).join(' · ')}</p></details><h3>Photos &amp; field reports</h3><div id="report-history"><p class="subtle">Loading reports…</p></div><p class="subtle">${esc(site.footer)}</p>`;
}
async function history(id) {
  const rows = await api(`/api/incidents/${encodeURIComponent(id)}/reports`);
  if (!$('report-history')) return;
  $('report-history').innerHTML = rows.length ? rows.map(r => `<div class="report-entry"><strong>${r.team_id ? esc(r.team_id) + ' · Field report' : 'Resident report'}</strong><p>${esc(r.note || 'No additional observation supplied.')}</p>${r.kind === 'field_update' ? `<p>${r.status ? esc(human(r.status)) : ''}${r.depth_cm != null ? ' · Measured depth ' + r.depth_cm + ' cm' : ''}${r.rescued_count != null ? ' · ' + r.rescued_count + ' rescued (reported)' : ''}</p>` : ''}<div class="photo-grid">${r.photos.map(url => `<a href="${esc(url)}" target="_blank" rel="noopener"><img src="${esc(url)}" alt="Submitted scene photo" loading="lazy"></a>`).join('')}</div><small>${esc(new Date(r.created_at).toLocaleString())} · ${esc(human(r.extraction_status))}</small></div>`).join('') : '<p class="subtle">No uploaded photos yet. Demo estimates use simulated observations.</p>';
}
function renderQueue() {
  const term = $('search').value.trim().toLowerCase();
  const visible = sites.filter(s => `${s.name} ${s.scene_type} ${s.tier}`.toLowerCase().includes(term));
  $('sites').innerHTML = visible.length ? visible.map(s => `<button class="site ${s.id === selected ? 'selected' : ''}" data-site="${esc(s.id)}"><span class="site-top"><span class="tier ${esc(s.tier)}">${esc(s.tier)}</span><span>${esc(human(s.scene_type))}</span></span><strong>${esc(s.name)}</strong><small>${esc(summary(s))}</small><span class="site-bottom"><span>${s.assignment ? 'Crew assigned' : 'Awaiting assignment'}</span><span>View details →</span></span></button>`).join('') : '<div class="empty-state"><h2>No matching sites</h2><p>Load the demo or create an alert to receive reports.</p></div>';
  document.querySelectorAll('[data-site]').forEach(button => button.onclick = () => select(button.dataset.site).catch(e => notify(e.message, true)));
}
async function refresh() {
  const alert = $('alert').value;
  sites = await api(`/api/incidents?eta_scale=${scale()}${alert ? '&alert_id=' + encodeURIComponent(alert) : ''}`);
  $('count').textContent = sites.length;
  $('priority-count').textContent = sites.filter(s => s.tier === 'P1' && s.status !== 'resolved').length;
  $('assigned-count').textContent = sites.filter(s => s.assignment).length;
  $('waiting-count').textContent = sites.filter(s => !s.assignment && s.status !== 'resolved').length;
  renderQueue();
  if (markers) {
    markers.clearLayers();
    sites.forEach(s => {
      const marker = L.circleMarker([s.lat, s.lon], { radius: 8, color: { P1: '#b54039', P2: '#bf7133', P3: '#a38a36', P4: '#87958e' }[s.tier], fillOpacity: .8 }).addTo(markers);
      const tip = document.createElement('span'); tip.textContent = s.name; marker.bindTooltip(tip);
      marker.on('click', () => select(s.id).catch(e => notify(e.message, true)));
    });
  }
  if (selected && !sites.some(s => s.id === selected)) selected = null;
  if (selected) { $('card').innerHTML = card(sites.find(s => s.id === selected)); await history(selected); }
}
async function select(id) {
  selected = id; const site = sites.find(s => s.id === id);
  if (!site) return;
  $('card').innerHTML = card(site); renderQueue();
  if (map) map.panTo([site.lat, site.lon]); await history(id);
}
async function loadAlerts() {
  const current = $('alert').value, alerts = await api('/api/alerts');
  $('alert').innerHTML = '<option value="">All alerts</option>' + alerts.map(a => `<option value="${esc(a.id)}">${esc(human(a.hazard))} · ${esc(a.id.slice(0, 10))}</option>`).join('');
  if (alerts.some(a => a.id === current)) $('alert').value = current;
}
function createMap(id) {
  if (!window.L) return null;
  const value = L.map(id).setView([11.0168, 76.9558], 12);
  WaterlineLocation.addTiles(value);
  return value;
}
async function outbox() {
  const rows = await api('/api/outbox');
  $('outbox').innerHTML = rows.length ? rows.map(r => `<div class="outbox-row"><div><strong>${esc(r.phone)}</strong><p>${esc(r.message)}</p><span class="pill">Simulated delivery</span></div><a href="/report/${encodeURIComponent(r.token)}">Open reporting link →</a></div>`).join('') : '<p class="subtle">Create an alert with recipients to generate reporting links.</p>';
}
async function authority() {
  const form = $('alert-form'), now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  form.elements.event_time.value = now.toISOString().slice(0, 16);
  let previewVersion = 0, previewTimer;
  const preview = async () => {
    const version = ++previewVersion;
    if (!form.elements.radius_m.value) { $('recipient-preview').textContent = 'Select an area to find registered residents who opted into SMS.'; return; }
    try {
      const result = await api('/api/office/preview', { center_lat: Number(form.elements.center_lat.value), center_lon: Number(form.elements.center_lon.value), radius_m: Number(form.elements.radius_m.value) });
      if (version === previewVersion) $('recipient-preview').textContent = `${result.count} registered residents in this area have opted into SMS alerts.`;
    } catch (error) { if (version === previewVersion) $('recipient-preview').textContent = error.message; }
  };
  const area = WaterlineLocation.create('authority-map', { area: true, status: $('area-status'), onChange: point => {
    form.elements.center_lat.value = point.lat; form.elements.center_lon.value = point.lon;
    form.elements.radius_m.value = point.radius ?? '';
    ++previewVersion; clearTimeout(previewTimer); previewTimer = setTimeout(preview, 250);
  } });
  $('area-reset').onclick = () => area?.reset();
  async function refreshOffice() {
    const data = await api('/api/office');
    $('office-residents').textContent = data.residents.length;
    $('office-consented').textContent = data.residents.filter(r => r.consent).length;
    $('office-messages').textContent = data.campaigns.reduce((n, c) => n + c.simulated, 0);
    $('office-reports').textContent = data.campaigns.reduce((n, c) => n + c.reports, 0);
    $('resident-directory').innerHTML = data.residents.length ? `<div class="directory-list">${data.residents.map(r => `<div class="outbox-row"><div><strong>${esc(r.name)}</strong><p>${esc(r.phone)}</p></div><span class="pill">${r.consent ? 'SMS opted in' : 'SMS opted out'}</span></div>`).join('')}</div>` : '<p class="subtle">No residents yet. Add demo residents or register a resident above.</p>';
    $('office-campaigns').innerHTML = data.campaigns.length ? data.campaigns.map(c => `<article class="campaign"><div class="outbox-row"><div><strong>${esc(human(c.hazard))}</strong><p>${esc(new Date(c.event_time).toLocaleString())} · ${(c.radius_m / 1000).toFixed(2)} km area radius</p><p>${c.recipients} recipients · ${c.pending} pending · ${c.simulated} simulated messages · <span data-report-count="${esc(c.id)}">${c.reports}</span> reports</p><p>${esc(c.message || 'Default hazard safety message and individual reporting link')}</p></div><div class="campaign-actions"><a href="${esc(c.report_url)}" class="button secondary">Open civilian report</a>${c.pending ? `<button type="button" class="button" data-send="${esc(c.id)}">Simulate sending ${c.pending} SMS</button>` : '<span class="pill">No pending messages</span>'}</div></div><details><summary>Review recipients and SMS preview</summary><div data-recipients="${esc(c.id)}">Loading recipients…</div></details></article>`).join('') : '<p class="subtle">Create an alert to prepare a locality SMS campaign.</p>';
    for (const button of document.querySelectorAll('[data-send]')) button.onclick = async () => {
      button.disabled = true;
      try { const result = await api(`/api/alerts/${button.dataset.send}/send`, {}); notify(`${result.count} SMS messages simulated. No actual text messages were sent.`); await refreshOffice(); }
      catch (error) { notify(error.message, true); button.disabled = false; }
    };
    const recipients = await api('/api/office/recipients');
    for (const container of document.querySelectorAll('[data-recipients]')) {
      const rows = recipients.filter(r => r.alert_id === container.dataset.recipients);
      container.innerHTML = rows.length ? rows.map(r => `<div class="report-entry"><strong>${esc(r.phone)}</strong><span class="pill">${esc(r.status)}</span><p>${esc(r.message)}</p><a href="/report/${encodeURIComponent(r.token)}">Open personal reporting link →</a></div>`).join('') : '<p>No recipients matched this area when the alert was created.</p>';
    }
    await outbox(); await preview();
  }
  const residentForm = $('resident-form');
  const residentMap = WaterlineLocation.create('resident-map', { status: $('resident-location-status'), onChange: point => { residentForm.elements.lat.value = point.lat; residentForm.elements.lon.value = point.lon; } });
  residentForm.onsubmit = async event => {
    event.preventDefault();
    if (!residentMap?.selected()) { notify('Select the resident registration location on the map.', true); return; }
    const button = residentForm.querySelector('button[type=submit]'); button.disabled = true;
    try { await api('/api/residents', { name: residentForm.elements.name.value.trim(), phone: residentForm.elements.phone.value.trim(), lat: Number(residentForm.elements.lat.value), lon: Number(residentForm.elements.lon.value), consent: residentForm.elements.consent.checked }); notify('Resident registration saved.'); await refreshOffice(); }
    catch (error) { notify(error.message, true); } finally { button.disabled = false; }
  };
  $('residents-demo').onclick = async () => { $('residents-demo').disabled = true; try { await api('/api/residents/demo', {}); await refreshOffice(); notify('Synthetic residents added. Demo labels cannot receive real SMS.'); } catch (error) { notify(error.message, true); } finally { $('residents-demo').disabled = false; } };
  $('office-refresh').onclick = async () => { $('office-refresh').disabled = true; try { await refreshOffice(); notify('Dashboard refreshed.'); } catch (error) { notify(error.message, true); } finally { $('office-refresh').disabled = false; } };
  await refreshOffice();
  setInterval(async () => {
    try {
      const data = await api('/api/office');
      $('office-reports').textContent = data.campaigns.reduce((n, c) => n + c.reports, 0);
      for (const value of document.querySelectorAll('[data-report-count]')) {
        const campaign = data.campaigns.find(c => c.id === value.dataset.reportCount);
        if (campaign) value.textContent = campaign.reports;
      }
    } catch (_) { /* Keep the last received count; full refresh reports network errors. */ }
  }, 10000);
  form.onsubmit = async event => {
    event.preventDefault();
    if (!area?.selected()) { notify('Select the affected area on the map: tap its center, then its outer edge.', true); $('authority-map').scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    const button = form.querySelector('button[type=submit]'); button.disabled = true;
    try {
      const payload = Object.fromEntries(new FormData(form));
      for (const key of ['center_lat', 'center_lon', 'radius_m']) payload[key] = Number(payload[key]);
      payload.magnitude = payload.magnitude ? Number(payload.magnitude) : null;
      payload.event_time = new Date(payload.event_time).toISOString(); payload.phones = []; payload.recipient_source = 'locality';
      const alert = await api('/api/alerts', payload);
      notify(`Alert created for ${alert.recipients.length} registered recipients. Review the campaign below, then simulate SMS sending.`); await refreshOffice(); $('office-campaigns').scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (error) { notify(error.message, true); } finally { button.disabled = false; }
  };
}
async function responders() {
  const [teams, all] = await Promise.all([api('/api/teams'), api('/api/incidents')]);
  $('team-list').innerHTML = teams.length ? teams.map(team => {
    const site = all.find(s => s.assignment?.team_id === team.id);
    return `<article class="panel team-card"><span class="pill">${esc(human(team.type))}</span><span class="team-icon" aria-hidden="true">↗</span><h2>${esc(team.name)}</h2><p>${site ? esc(site.name) : 'No site assigned yet. A coordinator can assign this team from Overview.'}</p>${site ? `<a class="button" href="/field/${encodeURIComponent(team.id)}">Open team workspace →</a>` : '<p class="subtle">Awaiting assignment</p>'}</article>`;
  }).join('') : '<div class="panel empty-state"><h2>No teams added yet</h2><p>Load the demo in Overview to explore team assignments.</p><a href="/command">Go to Overview →</a></div>';
}
async function field(team) {
  const [teams, all] = await Promise.all([api('/api/teams'), api('/api/incidents')]);
  const crew = teams.find(t => t.id === team); fieldSite = all.find(s => s.assignment?.team_id === team);
  $('field-team-name').textContent = crew?.name || 'FIELD OPERATIONS';
  $('field-card').innerHTML = fieldSite ? card(fieldSite, true) : '<div class="empty-state"><h2>No active assignment</h2><p>Ask your coordinator to assign a site before sending a field report.</p><a href="/responders">Back to teams →</a></div>';
  $('field-form').hidden = !fieldSite; if (!fieldSite) return;
  await history(fieldSite.id); const form = $('field-form');
  const photoLocation = WaterlineLocation.create('field-location-map', { initial: [fieldSite.lat, fieldSite.lon], status: $('field-location-status'), onChange: point => {
    form.elements.lat.value = point.lat; form.elements.lon.value = point.lon; delete form.dataset.accuracy;
  } });
  // Keep the assigned site available even if map assets fail to load.
  form.elements.lat.value = fieldSite.lat; form.elements.lon.value = fieldSite.lon;
  form.elements.status.value = ['en_route', 'on_scene', 'escalate', 'resolved'].includes(fieldSite.status) ? fieldSite.status : 'en_route';
  $('field-vision-notice').textContent = config.vision.provider === 'live' ? 'Photos are sent to Google for scene extraction. AI failures are saved for manual review without simulated measurements.' : 'Photo analysis is using demo data. Uploads and observations are still saved.';
  form.elements.images.onchange = () => WaterlineUpload.previews(form.elements.images, $('field-previews'));
  $('field-locate').onclick = () => {
    if (!navigator.geolocation) { $('field-location-status').textContent = 'Location unavailable. Tap the map to select your photo location.'; return; }
    navigator.geolocation.getCurrentPosition(position => {
      photoLocation?.setPoint([position.coords.latitude, position.coords.longitude]);
      form.elements.lat.value = position.coords.latitude; form.elements.lon.value = position.coords.longitude;
      form.dataset.accuracy = position.coords.accuracy;
      $('field-location-status').textContent = `Device location captured. Accuracy ${position.coords.accuracy.toFixed(0)} m.`;
    }, () => { $('field-location-status').textContent = 'Could not get device location. Check permission or select a location on the map.'; }, { enableHighAccuracy: true, timeout: 10000 });
  };
  form.onsubmit = async event => {
    event.preventDefault(); $('field-submit').disabled = true; $('field-receipt').hidden = true;
    let uploaded = false, receipt;
    try {
      const files = [...form.elements.images.files];
      if (files.length > config.thresholds.max_images) throw Error('Choose up to four photos.');
      if (files.length) {
        const data = new FormData(); data.append('team_id', team); data.append('incident_id', fieldSite.id);
        for (const key of ['lat', 'lon', 'note']) data.append(key, form.elements[key].value);
        data.append('state', 'third_party'); data.append('accuracy', form.dataset.accuracy || config.thresholds.accuracy_warn_m);
        data.append('pin', form.dataset.accuracy ? 'false' : 'true'); $('field-progress').hidden = false;
        $('field-upload-status').textContent = 'Preparing photos…';
        for (const file of files) data.append('images', await WaterlineUpload.resize(file, config.thresholds), file.name);
        receipt = await WaterlineUpload.send('/api/field/reports', data, config.thresholds, value => $('field-progress').value = value, text => $('field-upload-status').textContent = text);
        uploaded = true;
      }
      const update = { team_id: team, status: form.elements.status.value, note: form.elements.note.value };
      for (const key of ['depth_cm', 'count']) update[key] = form.elements[key].value === '' ? null : Number(form.elements[key].value);
      await api(`/api/incidents/${fieldSite.id}/field_update`, update);
      $('field-upload-status').textContent = '';
      $('field-receipt').textContent = `Report saved. Your coordinator can review this update.${receipt ? ' ' + receipt.simulation_notice : ''}`;
      $('field-receipt').hidden = false; form.elements.images.value = ''; WaterlineUpload.previews(form.elements.images, $('field-previews'));
      fieldSite = await api(`/api/incidents/${fieldSite.id}`); $('field-card').innerHTML = card(fieldSite, true); await history(fieldSite.id);
    } catch (error) { notify((uploaded ? 'Photos were saved, but the status update needs retrying. ' : '') + error.message, true); }
    finally { $('field-submit').disabled = false; }
  };
}
async function start() {
  const admin = await api('/api/auth/me');
  $('admin-username').textContent = admin.username;
  $('admin-logout').onclick = async () => { try { await api('/api/auth/logout', {}); location.assign('/admin/login'); } catch (error) { notify(error.message, true); } };
  config = await api('/api/config');
  $('provider-badge').textContent = config.vision.provider === 'live' ? 'Photo extraction configured' : 'Demo extraction mode';
  const path = location.pathname;
  const section = ['/authority', '/office'].includes(path) ? 'authority' : path === '/responders' ? 'responders' : path.startsWith('/field/') ? 'field' : 'command';
  $(section).hidden = false;
  document.querySelector(`[data-nav="${section === 'field' ? 'responders' : section}"]`).classList.add('active');
  $('page-path').textContent = 'Operations / ' + ({ authority: 'Main office', responders: 'Field teams', field: 'Team workspace', command: 'Overview' })[section];
  document.title = $('page-path').textContent.split(' / ')[1] + ' · Waterline';
  if (section === 'authority') return authority();
  if (section === 'responders') return responders();
  if (section === 'field') return field(decodeURIComponent(path.split('/').pop()));
  map = createMap('map'); if (map) markers = L.layerGroup().addTo(map);
  await loadAlerts(); await refresh();
  $('search').oninput = renderQueue;
  $('alert').onchange = () => refresh().catch(e => notify(e.message, true));
  let sliderTimer;
  $('scale').oninput = () => { $('scale-value').textContent = scale().toFixed(1) + '×'; clearTimeout(sliderTimer); sliderTimer = setTimeout(() => refresh().catch(e => notify(e.message, true)), 150); };
  $('seed').onclick = async () => { $('seed').disabled = true; try { await api('/api/seed', {}); await loadAlerts(); await refresh(); notify('Demo loaded: eleven simulated sites and seven teams.'); } catch (e) { notify(e.message, true); } finally { $('seed').disabled = false; } };
  $('dispatch').onclick = async () => {
    $('dispatch').disabled = true;
    try { const rows = await api('/api/dispatch/run', { eta_scale: scale() }); notify(`${rows.filter(r => r.team_id).length} teams assigned. Open Field teams to view assignments and send reports.`); await refresh(); }
    catch (e) { notify(e.message, true); } finally { $('dispatch').disabled = false; }
  };
  setInterval(() => refresh().catch(e => notify(e.message, true)), config.thresholds.poll_seconds * 1000);
}
start().catch(error => notify(error.message, true));
