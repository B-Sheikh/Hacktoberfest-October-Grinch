const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

test('Map tiles, accuracy bounds and alert previews preserve actual report location', () => {
  const warnings = [], maps = [], layers = [], tiles = [];
  const point = value => Array.isArray(value) ? { lat:value[0], lng:value[1] } : value;
  const container = { insertAdjacentElement(_, value) { warnings.push(value); }, querySelector() { return this.failed ? {} : null; } };
  const document = { getElementById: () => container, createElement: () => ({setAttribute(){}}) };
  function layer(position, options) {
    return { position: point(position), options, events:{}, addTo() { layers.push(this); return this; },
      on(event, callback) { this.events[event] = callback; return this; }, setLatLng(value) { this.position = point(value); return this; },
      getLatLng() { return this.position; }, getBounds() { return { radius:this.options.radius, center:this.position }; }, setRadius() { return this; } };
  }
  const L = { latLng:point, marker:layer, circle:layer, divIcon:value=>value,
    tileLayer(url) { const value=layer([0,0],{}); value.url=url; tiles.push(value); return value; },
    map() { const value={ events:{}, removed:[], setView() {return this;}, getContainer:()=>container, on(event,callback) { this.events[event]=callback; },
      panTo(){}, invalidateSize(){}, removeLayer(layer) {this.removed.push(layer);}, fitBounds(bounds) {this.bounds=bounds;}, distance:()=>1000 }; maps.push(value); return value; }
  };
  const context = { window:{L}, L, document };
  vm.runInNewContext(fs.readFileSync('app/static/location.js','utf8'),context);
  let chosen;
  const picker=context.window.WaterlineLocation.create('map',{ status:{}, onChange:value=>chosen=value });
  assert.equal(tiles[0].url,'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
  tiles[0].events.tileerror(); assert.equal(warnings[0].hidden,false);
  container.failed=true; tiles[0].events.load(); assert.equal(warnings[0].hidden,false);
  container.failed=false; tiles[0].events.load(); assert.equal(warnings[0].hidden,true);
  picker.viewArea([11,77],3000); assert.equal(chosen,undefined); assert.equal(picker.selected(),false);
  picker.setDevicePoint([12,78],250); assert.equal(chosen.lat,12); assert.equal(chosen.lon,78);
  assert.equal(maps[0].bounds.radius,250);
  const accuracy=layers.at(-1);
  picker.setPoint([12.01,78.01]); assert.ok(maps[0].removed.includes(accuracy));
  picker.viewArea([11,77],3000); assert.equal(chosen.lat,12.01); assert.equal(chosen.lon,78.01);
  picker.reset(); assert.equal(picker.selected(),false);
});

async function portal(geo) {
  const elements={}; const el=id=>elements[id] ||= {textContent:'',disabled:false,innerHTML:''};
  const calls=[]; let options;
  const picker={ reset() { options.onChange({lat:'',lon:''}); }, setDevicePoint(point,accuracy) {calls.push({point,accuracy}); options.onChange({lat:point[0],lon:point[1]});}, setPoint(){}, viewArea(){} };
  const context={ document:{getElementById:el,querySelectorAll:()=>[]}, navigator:{geolocation:geo}, window:{isSecureContext:true},
    WaterlineLocation:{create(_,value){options=value;return picker;}}, fetch:async()=>({ok:true,json:async()=>[{id:'a',center_lat:11,center_lon:77,radius_m:1000,hazard:'flash_flood',event_time:'2026-10-08T00:00:00Z',report_url:'/report/token'}]}) };
  vm.runInNewContext(fs.readFileSync('app/static/portal.js','utf8'),context);
  await new Promise(resolve=>setImmediate(resolve)); return {el,calls};
}

test('Device timeout retries approximate location and discloses accuracy', async () => {
  const requests=[];
  const page=await portal({getCurrentPosition(ok,error,options){requests.push(options);if(requests.length===1)error({code:3});else ok({coords:{latitude:11,longitude:77,accuracy:350}});}});
  await page.el('portal-locate').onclick();
  assert.equal(requests.length,2);assert.equal(requests[1].enableHighAccuracy,false);
  assert.equal(page.calls[0].accuracy,350);
  assert.match(page.el('portal-location-status').textContent,/350 metres/);
  assert.match(page.el('portal-count').textContent,/possibly matching/);
  assert.equal(page.el('portal-locate').disabled,false);
});

test('Permission denial does not invent a location or retry', async () => {
  let requests=0;
  const page=await portal({getCurrentPosition(ok,error){requests++;error({code:1});}});
  await page.el('portal-locate').onclick();
  assert.equal(requests,1);assert.equal(page.calls.length,0);
  assert.match(page.el('portal-location-status').textContent,/permission was denied/);
});

test('Late device result cannot override a manual show-all selection', async () => {
  let complete;
  const page=await portal({getCurrentPosition(ok){complete=ok;}});
  const pending=page.el('portal-locate').onclick();
  page.el('show-all').onclick();
  complete({coords:{latitude:11,longitude:77,accuracy:20}});await pending;
  assert.equal(page.calls.length,0);assert.match(page.el('portal-location-status').textContent,/Showing all/);
});
