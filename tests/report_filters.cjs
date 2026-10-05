// Exercise the actual report script with a minimal DOM, without browser dependencies.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const element = extra => Object.assign({hidden: false, value: '', attrs: {}, events: {},
  setAttribute(k,v) { this.attrs[k]=v; }, addEventListener(k,fn) { this.events[k]=fn; }}, extra);
const cards = [
  element({dataset:{status:'accepted',errors:'[]'},textContent:'Line 1 search_documents RAG ارزیابی'}),
  element({dataset:{status:'rejected',errors:'["schema_type"]'},textContent:'Line 2 schema_type /arguments/horizon_hours'}),
  element({dataset:{status:'rejected',errors:'["schema_minimum","schema_type"]'},textContent:'Line 3 schema_minimum schema_type /arguments/top_k'})];
const buttons = ['all','accepted','rejected'].map(filter=>element({dataset:{filter}}));
const ids = Object.fromEntries(['search','error-filter','visible-count','empty-state','reset-filters'].map(id=>[id,element({textContent:''})]));
const nav=element({hidden:true}), controls=element({hidden:true});
const html=fs.readFileSync(process.argv[2],'utf8');
vm.runInNewContext(html.split('<script>')[1].split('</script>')[0], {document:{
  querySelectorAll: s => s.startsWith('article')?cards:buttons,
  querySelector: s => s==='nav'?nav:controls, getElementById: id=>ids[id]}});
const visible=()=>cards.map((c,i)=>c.hidden?null:i).filter(i=>i!==null);
assert.deepEqual(visible(),[0,1,2]);
assert.equal(nav.hidden,false); assert.equal(controls.hidden,false);
buttons[2].events.click(); assert.deepEqual(visible(),[1,2]);
ids['error-filter'].value='schema_type'; ids['error-filter'].events.change(); assert.deepEqual(visible(),[1,2]);
ids.search.value='  HORIZON  '; ids.search.events.input(); assert.deepEqual(visible(),[1]);
ids['error-filter'].value='schema_minimum'; ids['error-filter'].events.change();
assert.deepEqual(visible(),[]); assert.equal(ids['empty-state'].hidden,false);
assert.equal(ids['visible-count'].textContent,'Showing 0 of 3 calls');
ids['reset-filters'].events.click(); assert.deepEqual(visible(),[0,1,2]);
assert.equal(ids['empty-state'].hidden,true); assert.equal(buttons[0].attrs['aria-pressed'],'true');
ids.search.value='ارزیابی'; ids.search.events.input(); assert.deepEqual(visible(),[0]);
ids.search.value='ＲＡＧ'; ids.search.events.input(); assert.deepEqual(visible(),[0]);
ids.search.value='.*'; ids.search.events.input(); assert.deepEqual(visible(),[]);
console.log('Report filter tests passed: combined filters, reset, empty state, Unicode and literal search.');
