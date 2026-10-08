const form = document.getElementById('report-form');
const steps = [...form.querySelectorAll('fieldset')];
const el = id => document.getElementById(id);
let step = 0, config, pinned = true, locationPicker;

function validSection(index) {
  if (index === 2 && (!form.elements.lat.value || !form.elements.lon.value)) {
    el('error').textContent = 'Choose the photo location on the map or use your current location.'; return false;
  }
  el('error').textContent = '';
  for (const input of steps[index].querySelectorAll('input,textarea')) if (!input.reportValidity()) return false;
  return true;
}
function show(index) {
  step = index; steps.forEach((section, i) => section.hidden = i !== index);
  document.querySelectorAll('.steps span').forEach((label, i) => label.classList.toggle('active', i === index));
  if (index === 2) requestAnimationFrame(() => locationPicker?.refresh());
  el('back').hidden = index === 0; el('next').hidden = index === 2; el('submit').hidden = index !== 2;
}
el('next').onclick = () => { if (validSection(step)) show(step + 1); };
el('back').onclick = () => show(step - 1);
form.elements.images.onchange = () => WaterlineUpload.previews(form.elements.images, el('photo-previews'));
el('locate').onclick = () => {
  if (!navigator.geolocation) { el('location-status').textContent = 'Location access is unavailable. Select a location on the map.'; return; }
  el('location-status').textContent = 'Finding your location…';
  navigator.geolocation.getCurrentPosition(position => {
    locationPicker?.setPoint([position.coords.latitude, position.coords.longitude]);
    form.elements.lat.value = position.coords.latitude; form.elements.lon.value = position.coords.longitude;
    form.elements.accuracy.value = position.coords.accuracy; pinned = false;
    el('location-status').textContent = `Location found. Accuracy about ${position.coords.accuracy.toFixed(0)} metres.`;
  }, () => { el('location-status').textContent = 'Could not access location. Check permission or select a location on the map. Phone access requires HTTPS.'; }, { enableHighAccuracy: true, timeout: 10000 });
};
form.onsubmit = async event => {
  event.preventDefault(); if (!validSection(step) || !config) return;
  el('submit').disabled = true; el('progress').hidden = false; el('error').textContent = '';
  try {
    const files = [...form.elements.images.files];
    if (!files.length || files.length > config.thresholds.max_images) throw Error('Choose one to four photos.');
    const data = new FormData();
    for (const key of ['state', 'people_count', 'note', 'lat', 'lon', 'accuracy']) data.append(key, form.elements[key].value);
    data.append('pin', String(pinned)); data.append('token', location.pathname.split('/').pop());
    data.append('vulnerable', [...form.querySelectorAll('input[name=vulnerable]:checked')].map(input => input.value).join(','));
    el('upload-status').textContent = 'Preparing your photos…';
    for (const file of files) data.append('images', await WaterlineUpload.resize(file, config.thresholds), file.name);
    const receipt = await WaterlineUpload.send('/api/reports', data, config.thresholds, progress => el('progress').value = progress, status => el('upload-status').textContent = status);
    form.hidden = true; document.querySelector('.steps').hidden = true; el('receipt').hidden = false;
    const title = document.createElement('h2'); title.textContent = 'Your report has been received';
    const reference = document.createElement('p'); reference.textContent = 'Reference: ' + receipt.report_id;
    const message = document.createElement('p'); message.textContent = receipt.message + ' ' + receipt.simulation_notice;
    const tips = document.createElement('p'); tips.textContent = receipt.tips;
    el('receipt').replaceChildren(title, reference, message, tips);
  } catch (error) { el('error').textContent = error.message; el('submit').disabled = false; }
};
async function start() {
  const token = location.pathname.split('/').pop();
  const [configuration, alertResponse] = await Promise.all([fetch('/api/config'), fetch('/api/report-link/' + token)]);
  if (!configuration.ok || !alertResponse.ok) throw Error('This reporting link could not be loaded. Refresh when connected.');
  config = await configuration.json(); const alert = await alertResponse.json();
  el('safety').textContent = config.templates.safety;
  el('hazard').textContent = alert.hazard.replaceAll('_', ' ') + ' · Conditions in your area';
  el('vision-notice').textContent = config.vision.provider === 'live' ? 'Resized photos are sent to Google for scene analysis. AI failures and unmeasurable scenes are saved for manual review; no simulated measurement is substituted.' : 'Photo processing is in demonstration mode. Actual image contents will not be assessed.';
  locationPicker = WaterlineLocation.create('report-location-map', { status: el('location-status'), onChange: point => {
    form.elements.lat.value = point.lat; form.elements.lon.value = point.lon;
    form.elements.accuracy.value = config.thresholds.accuracy_warn_m; pinned = true;
  } });
  locationPicker?.setPoint([alert.center_lat, alert.center_lon]);
  // Show the alert area, but require an explicit photo location rather than accepting its center.
  form.elements.lat.value = ''; form.elements.lon.value = '';
  locationPicker?.reset();
  el('location-status').textContent = 'Use your current location or tap the map where the photo was taken.';
  el('next').disabled = false;
}
start().catch(error => { el('error').textContent = error.message; });
