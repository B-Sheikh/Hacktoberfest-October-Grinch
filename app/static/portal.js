const el = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let alerts = [], point = null, picker, locationRequest = 0, applyingDeviceLocation = false;
function finishLocating() {
  el('portal-locate').disabled = false;
  el('portal-locate').textContent = 'Use my current location';
}
function devicePosition(options) {
  return new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, options));
}
function distance(a, b) {
  const rad = value => value * Math.PI / 180;
  const dlat = rad(b.center_lat - a.lat), dlon = rad(b.center_lon - a.lon);
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.center_lat)) * Math.sin(dlon / 2) ** 2;
  return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}
function render() {
  const rows = point ? alerts.filter(alert => distance(point, alert) <= alert.radius_m + (point.accuracy || 0)) : alerts;
  el('portal-count').textContent = `${rows.length} ${point ? point.accuracy ? 'possibly matching' : 'matching' : 'available'} office alerts. Choose the event you are reporting about.`;
  el('public-alerts').innerHTML = rows.length ? rows.map(alert => `<article class="panel form-panel"><span class="pill">${alert.simulated ? 'Demo event' : 'Office alert'}</span><h2>${esc(alert.hazard.replaceAll('_', ' '))}</h2><p>Event time: ${esc(new Date(alert.event_time).toLocaleString())}<br>Area radius: ${(alert.radius_m / 1000).toFixed(2)} km</p><div class="portal-alert-actions"><button type="button" class="button secondary" data-view-area="${esc(alert.id)}">View alert area</button><a class="button" href="${esc(alert.report_url)}">Make a civilian report →</a></div></article>`).join('') : '<div class="panel empty-state"><h2>No matching office alert</h2><p>Try another locality or show all available alerts. The office must create an alert before reports can be attached to an event.</p></div>';
  for (const button of document.querySelectorAll('[data-view-area]')) button.onclick = () => {
    const alert = alerts.find(a => a.id === button.dataset.viewArea);
    if (!picker || !alert) return;
    ++locationRequest; finishLocating();
    picker.viewArea([alert.center_lat, alert.center_lon], alert.radius_m);
    el('portal-map').scrollIntoView({ behavior: 'smooth', block: 'center' });
  };
}
el('show-all').onclick = () => { ++locationRequest; finishLocating(); point = null; picker?.reset(); el('portal-location-status').textContent = 'Showing all available office alerts. Tap the map to filter by locality.'; render(); };
el('portal-locate').onclick = async () => {
  if (!navigator.geolocation) { el('portal-location-status').textContent = 'Location access unavailable. Tap your locality on the map.'; return; }
  if (!window.isSecureContext) { el('portal-location-status').textContent = 'Device location needs HTTPS or localhost. Open a secure link or select your locality on the map.'; return; }
  const request = ++locationRequest;
  el('portal-locate').disabled = true;
  el('portal-locate').textContent = 'Finding location…';
  el('portal-location-status').textContent = 'Finding your location…';
  try {
    let position;
    try {
      position = await devicePosition({ timeout: 12000, enableHighAccuracy: true, maximumAge: 60000 });
    } catch (error) {
      if (request !== locationRequest) return;
      if (error.code === 1) throw error;
      el('portal-location-status').textContent = 'Precise location unavailable. Trying an approximate device location…';
      position = await devicePosition({ timeout: 15000, enableHighAccuracy: false, maximumAge: 300000 });
    }
    if (request !== locationRequest) return;
    const { latitude, longitude, accuracy } = position.coords;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !Number.isFinite(accuracy)) throw { code: 2 };
    applyingDeviceLocation = true;
    try { picker?.setDevicePoint([latitude, longitude], accuracy); }
    finally { applyingDeviceLocation = false; }
    point = { lat: latitude, lon: longitude, accuracy };
    render();
    const precision = accuracy >= 1000 ? `${(accuracy / 1000).toFixed(1)} km` : `${Math.round(accuracy)} metres`;
    el('portal-location-status').textContent = `Device location found, accurate to about ${precision}. Check the pin and drag it to your locality if needed. Alerts overlapping this accuracy range are included.`;
  } catch (error) {
    if (request !== locationRequest) return;
    el('portal-location-status').textContent = error.code === 1
      ? 'Location permission was denied. Allow location for this site in your browser and enable device Location services, then try again. You can also tap your locality on the map.'
      : error.code === 3
        ? 'The device did not return a location in time. Check device Location services or tap your locality on the map.'
        : 'Your device could not determine its location. Check device Location services and your connection, or tap your locality on the map.';
  } finally { if (request === locationRequest) finishLocating(); }
};
async function start() {
  const response = await fetch('/api/public/alerts');
  if (!response.ok) throw Error('Alerts could not be loaded. Refresh when connected.');
  alerts = await response.json();
  picker = WaterlineLocation.create('portal-map', { status: el('portal-location-status'), onChange: location => {
    if (!applyingDeviceLocation) { ++locationRequest; finishLocating(); }
    point = location.lat === '' ? null : location; render();
  } });
  if (point) {
    const saved = point;
    applyingDeviceLocation = true;
    try { picker?.setPoint([saved.lat, saved.lon]); } finally { applyingDeviceLocation = false; }
    point = saved;
  }
  render();
}
start().catch(error => el('portal-error').textContent = error.message);
