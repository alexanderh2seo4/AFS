import assert from 'node:assert/strict';
import {test} from 'node:test';
import {visibleRecords,hasOpenInterview} from '../../docs/assets/record-filters.js';
const now=new Date('2026-10-05T14:00:00Z');
const sending=[{id:'open',status:'open'}, {id:'part',status:'assigned',hasOpenRoles:true,pickedAt:'2026-10-01'}, {id:'full',status:'assigned',hasOpenRoles:false,pickedAt:'2026-09-20'}, {id:'old',status:'assigned',hasOpenRoles:false,pickedAt:'2026-08-01'}, {id:'unknown',status:'assigned',hasOpenRoles:false}];
test('open slots and picked interviews remain distinct, with honest recent dates',()=>{
  assert.equal(hasOpenInterview(sending[1]),true);
  assert.deepEqual(visibleRecords(sending,'sending','open',now).map(r=>r.id),['open','part']);
  assert.deepEqual(visibleRecords(sending,'sending','recent',now).map(r=>r.id),['part','full']);
  assert.equal(visibleRecords(sending,'sending','all',now).length,5);
  assert.equal(visibleRecords(sending,'sending','assigned',now).length,4);
});
test('sendees default to abroad, with selectable preparation and combined views',()=>{
  const sendees=[{status:'active'},{status:'pending'}];
  assert.deepEqual(visibleRecords(sendees,'awayees','active'),[sendees[0]]);
  assert.deepEqual(visibleRecords(sendees,'awayees','pending'),[sendees[1]]);
  assert.equal(visibleRecords(sendees,'awayees','all').length,2);
});
