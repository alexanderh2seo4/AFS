import {findPublicPlaces} from './locations.js';

const $=id=>document.getElementById(id);
const root=new URL('../',import.meta.url);
const allowedInterests=new Set(['sending_interviews','hosting','weekend_hosting']);
let config={enabled:false,apiBaseUrl:'',noticeVersion:'',purpose:'',retentionText:'',privacyContact:''};
let selectedPlace=null;
let searchTimer;
let requestId=0;
let submissionId=null;

function setMessage(message){$('page-message').textContent=message}
function setPlace(place){selectedPlace=place;$('page-city').value=place.label||place.city;$('page-city-options').replaceChildren();setMessage('Ort ausgewählt: '+place.city+' · '+place.postalCode)}
function buildEndpoint(){
  const endpoint=new URL(config.apiBaseUrl);
  endpoint.pathname=endpoint.pathname.replace(/\/$/,'')+'/api/contact';
  endpoint.search='';endpoint.hash='';
  return endpoint;
}
function loadConfig(){
  fetch(new URL('assets/contact-config.json',root),{cache:'no-store',referrerPolicy:'no-referrer'}).then(async response=>{
    if(!response.ok)throw Error();
    const value=await response.json(),endpoint=new URL(value.apiBaseUrl||'');
    if(value.enabled===true&&endpoint.protocol==='https:'&&!endpoint.username&&!endpoint.password&&!endpoint.search&&!endpoint.hash&&value.purpose&&value.retentionText&&value.privacyContact&&value.noticeVersion){
      config={...config,...value,apiBaseUrl:endpoint.origin};
      $('page-purpose').textContent='Zweck: '+config.purpose+'.'+(config.privacyContact?' Datenschutzkontakt: '+config.privacyContact+'.':'');
      $('page-retention').textContent=config.retentionText;
    }
  }).catch(()=>{}).finally(()=>{
    if(!config.enabled){$('page-submit').disabled=true;setMessage('Das Kontaktformular ist noch nicht eingerichtet. Du kannst ohne Absenden zur Karte wechseln.')}
  });
}

$('page-city').addEventListener('input',()=>{
  selectedPlace=null;clearTimeout(searchTimer);
  const query=$('page-city').value.trim(),id=++requestId;
  $('page-city-options').replaceChildren();
  if(query.length<2){setMessage('Gib mindestens zwei Buchstaben oder Ziffern ein.');return}
  setMessage('Orte werden gesucht …');
  searchTimer=setTimeout(async()=>{
    try{
      const places=await findPublicPlaces(query);
      if(id!==requestId)return;
      $('page-city-options').replaceChildren(...places.map(place=>{
        const button=document.createElement('button');button.type='button';button.className='city-option';button.textContent=place.label||place.city;
        button.addEventListener('click',()=>setPlace(place));return button;
      }));
      setMessage(places.length?'Bitte einen Ort aus der Vorschlagsliste wählen.':'Kein passender Ort gefunden. Prüfe die Schreibweise.');
    }catch{if(id===requestId)setMessage('Ortsuche gerade nicht verfügbar. Bitte versuche es erneut.')}
  },200);
});

$('contact-page-form').addEventListener('submit',async event=>{
  event.preventDefault();
  if(!config.enabled){setMessage('Das Kontaktformular ist noch nicht eingerichtet. Du kannst ohne Absenden zur Karte wechseln.');return}
  if(!selectedPlace){setMessage('Bitte wähle deinen Ort aus der Vorschlagsliste.');return}
  if(!$('page-consent').checked){setMessage('Bitte bestätige die Datenschutzhinweise.');return}
  const button=$('page-submit');button.disabled=true;
  try{
    submissionId||=crypto.randomUUID();
    const payload={
      submissionId,
      name:$('page-name').value.trim(),
      email:$('page-email').value.trim(),
      phone:$('page-phone').value.trim(),
      postalCode:selectedPlace.postalCode,
      city:selectedPlace.city,
      interests:[...document.querySelectorAll('input[name="interests"]:checked')].map(input=>input.value).filter(value=>allowedInterests.has(value)),
      consent:true,
      consentVersion:config.noticeVersion,
      website:$('page-website').value,
    };
    const response=await fetch(buildEndpoint(),{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!response.ok){setMessage(response.status===429?'Bitte warte kurz und versuche es erneut.':'Das Absenden ist gerade fehlgeschlagen. Bitte versuche es erneut.');return}
    try{localStorage.setItem('afs-contact-submitted-v1',config.noticeVersion)}catch{}
    window.location.assign(root.href);
  }catch{setMessage('Das Absenden ist gerade fehlgeschlagen. Bitte versuche es erneut.')}finally{button.disabled=!config.enabled}
});

loadConfig();
