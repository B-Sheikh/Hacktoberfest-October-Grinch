const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/app.js', 'utf8');
const binding = source.slice(source.indexOf('async function bindReportDeletion'), source.indexOf('function renderQueue'));

test('Delete cancellation makes no request; confirmation deletes and refreshes', async () => {
  const button = { dataset:{deleteReport:'report-123'} }, calls=[];
  let confirm=false, refreshed=0;
  const context = { window:{confirm:()=>confirm}, api:async(...args)=>{calls.push(args);return {};}, notify(){} };
  vm.runInNewContext(binding,context);
  await context.bindReportDeletion({querySelectorAll:()=>[button]},async()=>refreshed++);
  await button.onclick(); assert.equal(calls.length,0); assert.equal(refreshed,0);
  confirm=true; await button.onclick();
  assert.equal(calls.length,1); assert.equal(calls[0][0],'/api/reports/report-123');
  assert.equal(calls[0][2],'DELETE'); assert.equal(refreshed,1);
});

test('Failed deletion keeps button available and displays the failure', async () => {
  const button={dataset:{deleteReport:'report-123'}};let error;
  const context={window:{confirm:()=>true},api:async()=>{throw Error('Admin login required');},notify:(message)=>error=message};
  vm.runInNewContext(binding,context);
  await context.bindReportDeletion({querySelectorAll:()=>[button]},async()=>assert.fail('Must not refresh after failure'));
  await button.onclick(); assert.equal(button.disabled,false); assert.equal(error,'Admin login required');
});
