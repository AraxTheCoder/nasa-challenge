"""Crosshair-to-analysis regression with real controllers and deterministic map/API adapters."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


MAP = '''
let api, ready=false, camera={ra:150,dec:2.2,fov:.5}; const changes=[],hooks=[];
const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=900;
canvas.style='width:100%;height:100%;display:block';const ctx=canvas.getContext('2d');
const rect=()=>canvas.getBoundingClientRect();
const proj={fromScreen:(x,y)=>[camera.ra+(x/rect().width-.5)*camera.fov,camera.dec+(y/rect().height-.5)*camera.fov],
 toScreen:(ra,dec)=>({x:(ra-camera.ra)/camera.fov*rect().width+rect().width/2,y:(dec-camera.dec)/camera.fov*rect().height+rect().height/2,front:true}),
 view:()=>({width:rect().width,height:rect().height})};
const sky={base:{depth:1,slice:0,props:{}},proj,on:(e,fn)=>changes.push(fn),view:()=>({...camera,width:rect().width,height:rect().height,roll:0}),
 addDrawHook:fn=>{hooks.push(fn);fn(ctx,proj)},redraw:()=>hooks.forEach(fn=>fn(ctx,proj))};
export const DEFAULT_SURVEY='spherex-live',SURVEYS=[{id:'spherex-live',label:'Test map'}];
export const initExplore=async(box,opts)=>{api=opts.api;box.append(canvas);ready=true;document.dispatchEvent(new CustomEvent('explore:ready'));return sky};
export const getSky=()=>ready?sky:null,getApiBase=()=>api;
export const view=()=>({ra:camera.ra,dec:camera.dec,fovArcmin:camera.fov*60,heightArcmin:camera.fov*60*rect().height/rect().width});
export const on=(e,fn)=>changes.push(fn),onTiles=()=>{},addDrawHook=fn=>sky.addDrawHook(fn),redraw=()=>sky.redraw();
export const skyAt=(x,y)=>proj.fromScreen(x,y),screenAt=(ra,dec)=>{const p=proj.toScreen(ra,dec);return[p.x,p.y]};
export const wantedOrder=()=>5,detector=()=>1,bandWavelengths=()=>[],surveyPasses=()=>[];
export const setSurvey=async()=>sky.base,setBand=()=>{},setDebug=()=>{},northUp=()=>{};
export const setFieldLayers=async layers=>layers,setEpochLayers=async layers=>layers,setPassLayers=async()=>[];
export const hideEpochs=()=>{},hideOverlay=()=>{},showOverlay=()=>{},showEpoch=()=>{},showLayer=async()=>true;
export const setBaseCap=()=>{},overlayProgress=()=>null,currentLayer=()=>null;
export const markField=(ra,dec,size)=>window.markedField={ra,dec,size},markRegion=()=>{},viewRegion=()=>[];
export const goTo=(ra,dec,fov)=>{window.cameraMoves=(window.cameraMoves||0)+1;camera={ra,dec,fov:fov||camera.fov};changes.forEach(fn=>fn())};
export const placeAt=goTo,fovForOrder=()=>.25;
window.testProject=(x,y)=>proj.fromScreen(x,y);
window.testMove=()=>{camera.ra+=2;changes.forEach(fn=>fn());sky.redraw()};
'''


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix='selection-test-'))
    out.mkdir(parents=True, exist_ok=True)
    web = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=web.serve_forever, daemon=True).start()
    fixture = json.loads((ROOT / 'fixtures/targets/demo-synthetic/target.json').read_text())
    image = next((ROOT / 'fixtures/targets/demo-synthetic/frames').glob('*.png')).read_bytes()
    fields, points, field_photometry, targets, pending = [], [], [], {}, []
    hold_points = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width':1200,'height':900})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/web/explore.js',lambda r:r.fulfill(content_type='text/javascript',body=MAP))
            def api(route):
                nonlocal hold_points
                u=urlsplit(route.request.url);q=parse_qs(u.query);path=u.path
                data={}
                if path=='/api/health':data={'ok':True,'mode':'live'}
                elif path=='/api/target':
                    fields.append({k:v[0] for k,v in q.items()});tid=f'selected-{len(fields)}'
                    t={**fixture,'id':tid,'synthetic':False,'name':tid,'center':{'ra_deg':float(q['ra'][0]),'dec_deg':float(q['dec'][0])},
                       'size_arcmin':int(q['size'][0]),'labels':[],'labels_requested':True}
                    targets[tid]=t;data={'status':'ready','id':tid,'target_url':f'/api/targets/{tid}/target.json'}
                elif path.endswith('/target.json'):data=targets[path.split('/')[-2]]
                elif path=='/api/photometry':
                    points.append({k:v[0] for k,v in q.items()})
                    data={'status':'ready','ra_deg':float(q['ra'][0]),'dec_deg':float(q['dec'][0]),'frames':[],
                          'all_exposures':True,'note':'Synthetic API adapter for selection testing'}
                    if hold_points:pending.append((route,data));return
                elif path.endswith('/photometry'):
                    field_photometry.append(path);data={'status':'no_data'}
                elif path.endswith('/spectral-outliers'):data={'status':'not_started'}
                elif '/api/hips/' in path:data={'layers':[]}
                elif path.endswith('/objects'):data={'status':'ready','objects':[],'known_objects':[],'detections':[]}
                elif path.endswith('/updates'):data={'status':'ready','new_exposures':0}
                elif path.endswith('/motion'):route.fulfill(status=404,content_type='application/json',body='{"status":"none"}');return
                elif path=='/api/chemistry/features':data={'features':[],'presets':[]}
                elif path.endswith('/redshift'):data={'status':'ready','galaxies':[]}
                elif path.endswith('.png'):route.fulfill(content_type='image/png',body=image);return
                elif path.startswith('/api/community'):data={'tiles':[],'threads':[],'comments':[],'status':'ready'}
                route.fulfill(content_type='application/json',body=json.dumps(data))
            page.route('**/api/**',api)
            origin=f'http://127.0.0.1:{web.server_port}'
            page.goto(origin+'/web/?api='+origin)
            page.wait_for_selector('#sky canvas')
            canvas=page.locator('#sky canvas')
            bounds=canvas.bounding_box();x,y=bounds['width']*.75,bounds['height']*.65
            expected=page.evaluate('([x,y])=>window.testProject(x,y)',[x,y])
            canvas.click(position={'x':x,'y':y})
            page.wait_for_function("document.querySelector('.ph-where')?.textContent.includes('exposures measured')")
            page.wait_for_function("window.markedField?.ra===Number(document.querySelector('[name=ra]').value)")
            assert len(fields)==1,fields
            assert abs(float(fields[0]['ra'])-expected[0])<1e-5 and abs(float(fields[0]['dec'])-expected[1])<1e-5
            assert fields[0]['size']=='15' and 'detector' not in fields[0],fields
            assert abs(float(points[-1]['ra'])-expected[0])<1e-5
            assert page.evaluate('window.cameraMoves||0')==0,'selection must not recenter the camera'
            assert field_photometry==[],'new field must not reset the selected spectrum to its centre'
            page.locator('#ol-scope').wait_for(state='visible')
            assert f'{expected[0]:.4f}' in page.locator('#ol-scope').inner_text(), 'region tools report the selected centre'
            # Labels/target refresh and panning keep the point and region selected.
            page.evaluate("async()=>{const{currentTarget}=await import('/web/viewer.js');document.dispatchEvent(new CustomEvent('viewer:target',{detail:{target:currentTarget()}}));window.testMove()}")
            page.wait_for_timeout(400)
            assert len(fields)==1 and len(points)==1 and field_photometry==[]
            assert str(round(expected[0],4)) in page.locator('.ph-where').inner_text()
            # New point wins even if the older spectrum completes last.
            hold_points=True
            page.evaluate("void window.spherexSpectrumAt(151.1,2.3)")
            page.wait_for_function("document.querySelector('[name=ra]').value==='151.10000'")
            page.evaluate("void window.spherexSpectrumAt(151.2,2.4)")
            page.wait_for_function("document.querySelector('[name=ra]').value==='151.20000'")
            page.wait_for_timeout(200)
            assert len(pending)==2,pending
            hold_points=False
            for route,data in reversed(pending):route.fulfill(content_type='application/json',body=json.dumps(data))
            page.wait_for_function("document.querySelector('.ph-where')?.textContent.includes('151.2000')")
            assert page.evaluate('window.markedField.ra')==151.2
            # A pin pick is handled once and uses the same region path.
            page.evaluate('window.scrollTo(0,0)')
            page.locator('#pin-btn').click()
            old_count=len(fields);old_points=len(points)
            canvas.click(position={'x':bounds['width']*.55,'y':bounds['height']*.8})
            page.wait_for_function("document.querySelector('.ph-where')?.textContent.includes('exposures measured')")
            page.wait_for_timeout(400)
            assert len(fields)==old_count+1 and len(points)==old_points+1,(fields,points)
            # Drag and double-click do not select an analysis position.
            page.evaluate('window.scrollTo(0,0)');old_count=len(fields);old_points=len(points)
            b=canvas.bounding_box();page.mouse.move(b['x']+500,b['y']+600);page.mouse.down();page.mouse.move(b['x']+560,b['y']+620);page.mouse.up()
            canvas.dblclick(position={'x':600,'y':650});page.wait_for_timeout(400)
            assert len(fields)==old_count and len(points)==old_points
            # Go places a marker too and must use the same selection path.
            page.locator('[name=ra]').fill('153.25')
            page.locator('[name=dec]').fill('3.5')
            page.locator('#go-btn').click()
            page.wait_for_function("document.querySelector('.ph-where')?.textContent.includes('153.2500')")
            assert fields[-1]['ra']=='153.25000' and points[-1]['ra']=='153.25000'
            assert parse_qs(urlsplit(page.url).query)['size']==['15']
            assert not errors,errors
            page.screenshot(path=str(out/'analysis-selection.png'))
            browser.close()
        print('PASS selection: click/pin/Go centre region and spectrum, refresh/pan retention, newest response wins, drag/double-click ignored')
    finally:
        web.shutdown();web.server_close()


if __name__=='__main__':main()
