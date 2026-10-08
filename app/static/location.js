/* Shared point and circular-area selection. Coordinates remain an API detail. */
window.WaterlineLocation = {
  addTiles(map) {
    const container = map.getContainer();
    const warning = document.createElement('p');
    warning.className = 'map-load-warning'; warning.setAttribute('role', 'status'); warning.hidden = true;
    container.insertAdjacentElement('afterend', warning);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    tiles.on('tileerror', () => {
      warning.hidden = false;
      warning.textContent = 'Map tiles could not load. Check your connection and refresh before selecting a location.';
    });
    tiles.on('load', () => {
      // Keep the warning if any visible tile remains in an error state.
      warning.hidden = !container.querySelector('.leaflet-tile:not(.leaflet-tile-loaded)');
    });
    tiles.addTo(map); return tiles;
  },
  create(id, { area = false, initial = null, onChange, status }) {
    const container = document.getElementById(id);
    if (!window.L) {
      container.textContent = 'Map could not load. Reconnect and refresh to select a location.';
      return null;
    }
    const map = L.map(id).setView(initial || [11.0168, 76.9558], initial ? 15 : 12);
    this.addTiles(map);
    let center, marker, edge, circle, edgePosition, accuracyCircle, previewCircle, radius = null;
    function publish() {
      onChange({ lat: center.lat, lon: center.lng, radius });
      status.textContent = area
        ? radius === null ? 'Center selected. Tap the outer edge of the affected area.' : `Area selected · ${(radius / 1000).toFixed(2)} km radius. Drag either handle to adjust.`
        : 'Location selected. Drag the pin or tap the map to adjust.';
    }
    function redraw() {
      if (!area || radius === null) return;
      if (!circle) circle = L.circle(center, { radius, color: '#245b50', weight: 2, fillOpacity: .16 }).addTo(map);
      else circle.setLatLng(center).setRadius(radius);
    }
    function setPoint(point, pan = true) {
      if (accuracyCircle) { map.removeLayer(accuracyCircle); accuracyCircle = null; }
      if (previewCircle) { map.removeLayer(previewCircle); previewCircle = null; }
      const next = L.latLng(point);
      if (center && edge) {
        const end = edge.getLatLng();
        edge.setLatLng([next.lat + end.lat - center.lat, next.lng + end.lng - center.lng]);
        edgePosition = edge.getLatLng();
        radius = Math.min(100000, Math.max(1, Math.round(map.distance(next, edge.getLatLng()))));
      }
      center = next;
      if (!marker) {
        marker = L.marker(center, { draggable: true, title: area ? 'Area center — drag to move' : 'Report location — drag to move' }).addTo(map);
        marker.on('drag', () => setPoint(marker.getLatLng(), false));
      } else marker.setLatLng(center);
      redraw(); publish();
      if (pan) map.panTo(center);
    }
    function setEdge(point) {
      const distance = Math.round(map.distance(center, point));
      if (distance > 100000 || distance < 1) { status.textContent = 'Choose an edge between 1 metre and 100 km from the center.'; if (edge) edge.setLatLng(edgePosition); return; }
      radius = distance;
      if (!edge) {
        edge = L.marker(point, { draggable: true, title: 'Area edge — drag to resize', icon: L.divIcon({ className: 'area-handle', html: '<span></span>', iconSize: [24, 24], iconAnchor: [12, 12] }) }).addTo(map);
        edge.on('dragend', () => setEdge(edge.getLatLng()));
      } else edge.setLatLng(point);
      edgePosition = edge.getLatLng();
      redraw(); publish();
    }
    map.on('click', event => {
      if (area && center) setEdge(event.latlng);
      else setPoint(event.latlng, false);
    });
    if (initial) setPoint(initial, false);
    // Maps in wizard steps need their size recalculated when revealed.
    return { setPoint, setDevicePoint(point, accuracy) {
      setPoint(point, false);
      if (Number.isFinite(accuracy) && accuracy > 0 && !area) {
        accuracyCircle = L.circle(center, { radius: accuracy, color: '#377a9c', weight: 1, fillOpacity: .10, interactive: false }).addTo(map);
        map.fitBounds(accuracyCircle.getBounds(), { padding: [24,24], maxZoom: 16 });
      } else map.setView(center, 16);
    }, viewArea(point, radius) {
      if (previewCircle) map.removeLayer(previewCircle);
      previewCircle = L.circle(point, { radius, color: '#245b50', weight: 2, fillOpacity: .08, interactive: false }).addTo(map);
      map.fitBounds(previewCircle.getBounds(), { padding: [24,24], maxZoom: 15 });
      status.textContent = 'Showing the office alert area. Tap the map at your actual location; the area center is not a detected device location.';
    }, refresh: () => map.invalidateSize(), selected: () => !!center && (!area || radius !== null), reset() {
      [marker, edge, circle, accuracyCircle, previewCircle].filter(Boolean).forEach(layer => map.removeLayer(layer));
      accuracyCircle = previewCircle = null;
      center = marker = edge = circle = undefined; radius = null; onChange({ lat: '', lon: '', radius: '' });
      status.textContent = 'Tap the center, then tap the outer edge to select the affected area.';
    } };
  }
};
