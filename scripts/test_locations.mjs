import assert from 'node:assert/strict';
import {searchPlaces,searchKey} from '../docs/assets/locations.js';
import data from '../docs/assets/locations-de.js';

const chapters=[['80331','München','MUC',48.13,11.57,'80331']];
for(const query of ['München','Munchen','Muenchen','Munich','80331']){
  const result=searchPlaces(data.rows,query,chapters)[0];
  assert.equal(result.city,'München');
  assert.equal(result.chapterId,'MUC');
}
assert.equal(searchKey('Straße'),'strasse');
assert.deepEqual(searchPlaces(data.rows,'%%'),[]);
assert.equal(new Set(data.rows.map(row=>row[0])).size,data.counts.postcodes);
assert.equal(data.rows.length,data.counts.localities);
const fixture=[
  ['10110','Neustadt','County A',52.4,13.3],
  ['10111','Neustadt','County B',52.6,13.5],
  ['10112','Neustadt','County A',52.8,13.3],
  ['12345','Alpha','County C',52.5,13.4],
  ['12345','Beta','County C',52.5,13.4],
  ['12345','Gamma','County C',52.5,13.4],
];
assert.equal(searchPlaces(fixture,'Neustadt').length,2);
assert.deepEqual(searchPlaces(fixture,'10110')[0].location,{lat:52.4,lon:13.3});
assert.equal(searchPlaces(fixture,'12345').length,3);
assert.equal(searchPlaces(fixture,'Gamma')[0].city,'Gamma');
assert.equal(searchPlaces(data.rows,'Tolz')[0].city,'Bad Tölz');
console.log(`Location checks passed: ${data.counts.localities} localities, ${data.counts.postcodes} postcodes.`);
