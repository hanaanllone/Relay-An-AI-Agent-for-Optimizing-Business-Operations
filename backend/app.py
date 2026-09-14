import os, json, time
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from .db import init_db, get_state, entity, update_entity, upsert_entity, add_log, connect, now
from .tasks import build
from .calle import create_call, get_call, DRY_RUN
from .dry_run import simulate

load_dotenv(); init_db()
app=Flask(__name__, static_folder=None); CORS(app)

FEATURE_FOR = {'employee':'employee_operations','customer':'customer_lifecycle','license':'vendor_optimization'}

def public_company():
    s=get_state(); return s.get('company')

@app.post('/api/login')
def login():
    body=request.get_json() or {}; email=body.get('email','').strip().lower(); password=body.get('password','')
    conn=connect(); row=conn.execute('SELECT id,name,email FROM company WHERE lower(email)=? AND password=?',(email,password)).fetchone(); conn.close()
    if not row: return jsonify({'error':'Invalid company email or password'}),401
    return jsonify({'authenticated':True,'company':dict(row)})

@app.post('/api/company')
def create_company():
    body=request.get_json() or {}
    if not body.get('name') or not body.get('email') or not body.get('password'): return jsonify({'error':'name, email and password are required'}),400
    conn=connect()
    try:
        conn.execute('INSERT INTO company(id,name,email,password) VALUES(?,?,?,?)',(f"company_{int(time.time())}",body['name'],body['email'].lower(),body['password']))
        conn.commit()
    except Exception:
        conn.close(); return jsonify({'error':'A company with this email already exists'}),409
    conn.close(); return jsonify({'authenticated':True,'company':public_company()})

@app.get('/api/state')
def state(): return jsonify({'dry_run':DRY_RUN,'server_time':time.strftime('%Y-%m-%d %H:%M:%S'),**get_state()})

@app.get('/api/analytics')
def analytics():
    s=get_state(); employees=s['employees']; customers=s['customers']; licenses=s['licenses'];
    spend=sum(float(x.get('seats_purchased',0))*float(x.get('cost_per_seat',0)) for x in licenses)
    unused=sum(max(0,int(x.get('seats_purchased',0))-int(x.get('seats_active',0)))*float(x.get('cost_per_seat',0)) for x in licenses)
    return jsonify({'employee_status':{k:sum(1 for e in employees if e.get('attendance_status')==k) for k in ['present','absent','late','remote','leave']},'customer_plans':{p:sum(1 for c in customers if c.get('plan')==p) for p in sorted({c.get('plan') for c in customers})},'software':{'monthly_spend':spend,'unused_monthly_spend':unused,'utilization':(sum(int(x.get('seats_active',0)) for x in licenses)/sum(int(x.get('seats_purchased',0)) for x in licenses)*100) if sum(int(x.get('seats_purchased',0)) for x in licenses) else 0},'calls':{'total':len(s['call_logs']),'completed':sum(1 for x in s['call_logs'] if x['status']=='completed'),'by_pillar':{p:sum(1 for x in s['call_logs'] if x['pillar']==p) for p in ['employee','customer','license']}}})

@app.patch('/api/entities/<pillar>/<entity_id>')
def patch_entity(pillar,entity_id):
    data=request.get_json() or {}; updated=update_entity(pillar,entity_id,data)
    if not updated: return jsonify({'error':'entity not found'}),404
    add_log(pillar,f"{updated.get('name') or updated.get('tool')} updated manually")
    return jsonify(updated)

@app.post('/api/entities/<pillar>')
def add_entity(pillar):
    body=request.get_json() or {}
    if not body.get('id'): body['id']=f'{pillar[:2]}_{int(time.time()*1000)}'
    try: out=upsert_entity(pillar,body)
    except Exception as ex: return jsonify({'error':str(ex)}),400
    add_log(pillar,f"{body.get('name') or body.get('tool') or body.get('title')} added")
    return jsonify(out),201

@app.patch('/api/settings')
def settings():
    values=request.get_json() or {}; conn=connect()
    for k,v in values.items(): conn.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,int(bool(v))))
    conn.commit(); conn.close(); return jsonify(get_state()['settings'])

@app.post('/api/policies/upload')
def upload_policy():
    file=request.files.get('file'); key=request.form.get('key','')
    if key not in ('employee','customer','marketing','vendor') or not file: return jsonify({'error':'Choose a policy and a text/markdown file'}),400
    raw=file.read()
    try: content=raw.decode('utf-8')
    except UnicodeDecodeError: return jsonify({'error':'For this demo, upload UTF-8 .txt or .md policies'}),400
    conn=connect(); conn.execute('INSERT INTO policies(key,content,filename,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET content=excluded.content,filename=excluded.filename,updated_at=excluded.updated_at',(key,content,file.filename,now())); conn.commit(); conn.close(); add_log('policy',f'{key} policy uploaded: {file.filename}'); return jsonify({'key':key,'filename':file.filename,'content':content})

@app.put('/api/policies/<key>')
def policy(key):
    if key not in ('employee','customer','marketing','vendor'): return jsonify({'error':'invalid policy'}),400
    content=(request.get_json() or {}).get('content',''); conn=connect(); conn.execute('INSERT INTO policies(key,content,filename,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET content=excluded.content,updated_at=excluded.updated_at',(key,content,f'{key}-policy.md',now())); conn.commit(); conn.close(); add_log('policy',f'{key} policy updated'); return jsonify({'key':key,'content':content})

def save_call(call_id,pillar,entity_id,act,result,status,created,completed,dry):
    conn=connect(); conn.execute('INSERT OR REPLACE INTO call_logs(id,pillar,entity_id,act,status,summary,structured_result,transcript,dry_run,created_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(call_id,pillar,entity_id,act,status,result.get('summary'),json.dumps(result.get('structured_result')),json.dumps(result.get('transcript',[])),int(dry),created,completed)); conn.commit(); conn.close()

def apply_result(pillar,act,e,result):
    r=result.get('structured_result') or {}; updates={}
    if pillar=='employee' and act=='checkin':
        s=r.get('checkin_status'); mapping={'remote_today':'remote','on_leave':'leave','running_late':'late','forgot_to_checkin':'present','escalate':'absent'}
        updates={'checkin_status':s,'attendance_status':mapping.get(s,e.get('attendance_status')),'last_call_outcome':r.get('reason',''),'flag':None if s in ('remote_today','on_leave','forgot_to_checkin') else ('Escalation required' if s=='escalate' else e.get('flag'))}
    elif pillar=='employee' and act=='offboard':
        updates={'offboarding_status':r.get('handoff_status'),'equipment_return':r.get('equipment_return'),'tool_access_confirmed':r.get('tool_access_confirmed'),'flag':None if r.get('handoff_status')=='confirmed' else 'Follow-up needed'}
    elif pillar=='customer' and act=='renewal':
        updates={'renewal_status':r.get('decision'),'last_call_reason':r.get('reason',''),'flag':None if r.get('decision') in ('renewed','downgraded','cancelled') else e.get('flag')}
        if r.get('plan_after_call'): updates['plan']=r['plan_after_call']
    elif pillar=='customer' and act=='issue': updates={'recent_issue_status':'resolved' if r.get('severity')=='low' else 'follow_up','last_issue_call':r.get('resolution'),'flag':None if r.get('escalated')=='no' else 'Escalated'}
    elif pillar=='customer' and act=='feedback': updates={'last_feedback':r.get('feedback'),'feedback_sentiment':r.get('sentiment'),'flag':None}
    elif pillar=='license':
        try: seats=int(r.get('seats_after_call',''))
        except: seats=None
        if seats is not None and seats>=0: updates['seats_purchased']=seats
        updates['last_call_decision']=r.get('decision'); updates['monthly_cost_after_call']=float(r.get('monthly_cost_after_call',0) or 0); updates['flag']=None if r.get('decision') in ('renew_as_is','downgrade','cancel') else e.get('flag')
    updated=update_entity(pillar,e['id'],updates) if updates else e
    if pillar=='employee' and act=='offboard' and r.get('handoff_status')=='confirmed':
        for lic in get_state()['licenses']:
            assigned=e.get('assigned_software',e.get('tools',[]))
            if lic['tool'] in assigned and lic['dept']==e['dept']:
                new=max(0,lic['seats_purchased']-1); update_entity('license',lic['id'],{'seats_purchased':new,'flag':'Seat reclaimed','_reclaim_reason':e['name']+' offboarding'}); add_log('license',f"{lic['tool']} seat reclaimed after {e['name']} offboarding",True); break
    return updated

@app.post('/api/trigger-call')
def trigger():
    body=request.get_json() or {}; pillar,entity_id,act=body.get('pillar'),body.get('entityId'),body.get('act'); e=entity(pillar,entity_id)
    if not e: return jsonify({'error':'entity not found'}),404
    settings=get_state()['settings']; feature=FEATURE_FOR.get(pillar)
    if feature and not settings.get(feature,True): return jsonify({'error':f'{feature.replace("_"," ").title()} is disabled in Settings'}),403
    target_phone=e.get('phone') or e.get('owner_phone')
    if not target_phone: return jsonify({'error':'entity has no phone number'}),400
    # CALL-E receives the actual target number, while Relay provides policy/context.
    call_entity=dict(e); call_entity['phone']=target_phone
    state=get_state(); task,schema=build(pillar,act,e,state['policies']); metadata={'pillar':pillar,'entityId':entity_id,'act':act}
    try:
        created=create_call(task,call_entity,schema,metadata); call_id=created['id']
        if DRY_RUN:
            result=simulate(pillar,act,e); save_call(call_id,pillar,entity_id,act,result,result['status'],result['created_at'],result['completed_at'],True); apply_result(pillar,act,e,result); add_log(pillar,f"{e.get('name') or e.get('tool')} — {result['summary']}"); return jsonify({'callId':call_id,'dryRun':True,'call':result})
        save_call(call_id,pillar,entity_id,act,{'summary':'Call started','structured_result':None,'transcript':[]},created.get('status','queued'),now(),None,False); add_log(pillar,f"{e.get('name') or e.get('tool')} — call placed via CALL-E"); return jsonify({'callId':call_id,'dryRun':False})
    except Exception as ex: return jsonify({'error':str(ex)}),500

@app.get('/api/calls/<call_id>')
def call_status(call_id):
    conn=connect(); row=conn.execute('SELECT * FROM call_logs WHERE id=?',(call_id,)).fetchone(); conn.close()
    if not row: return jsonify({'error':'unknown call'}),404
    if row['dry_run']: return jsonify({'id':call_id,'status':row['status'],'summary':row['summary'],'structured_result':json.loads(row['structured_result']) if row['structured_result'] else None,'transcript':json.loads(row['transcript']) if row['transcript'] else []})
    try:
        raw=get_call(call_id); status=raw.get('status'); result={'summary':raw.get('summary'),'structured_result':raw.get('structured_result'),'transcript':sum([a.get('transcript_turns',[]) for r in raw.get('recipients',[]) for a in r.get('attempts',[])],[])}
        if status in ('completed','failed','canceled'):
            e=entity(row['pillar'],row['entity_id']); save_call(call_id,row['pillar'],row['entity_id'],row['act'],result,status,row['created_at'],raw.get('completed_at'),False)
            if status=='completed' and e: apply_result(row['pillar'],row['act'],e,result); add_log(row['pillar'],f"{e.get('name') or e.get('tool')} — {result.get('summary') or status}")
        return jsonify(raw)
    except Exception as ex: return jsonify({'error':str(ex)}),500

@app.post('/calle/webhook')
def webhook():
    event=request.get_json() or {}; event_id=request.headers.get('CALL-E-Event-Id')
    if not event_id or event_id != event.get('id'): return jsonify({'error':'invalid event id'}),400
    if event.get('type') not in ('call.completed','call.failed','call.result_validation_failed'): return jsonify({'ok':True})
    data=event.get('data') or {}; call_id=data.get('id'); conn=connect(); row=conn.execute('SELECT * FROM call_logs WHERE id=?',(call_id,)).fetchone(); conn.close()
    if row:
        result={'summary':data.get('summary'),'structured_result':data.get('structured_result') or data.get('structuredResult'),'transcript':sum([a.get('transcript_turns',a.get('transcriptTurns',[])) for r in data.get('recipients',[]) for a in r.get('attempts',[])],[])}
        e=entity(row['pillar'],row['entity_id']); save_call(call_id,row['pillar'],row['entity_id'],row['act'],result,data.get('status','completed'),row['created_at'],data.get('completed_at'),False)
        if data.get('status')=='completed' and e: apply_result(row['pillar'],row['act'],e,result); add_log(row['pillar'],f"{e.get('name') or e.get('tool')} — {result.get('summary') or 'call completed'}")
    return jsonify({'ok':True})

FRONT=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'frontend','dist')
@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def frontend(path):
    if os.path.isdir(FRONT):
        target=os.path.join(FRONT,path)
        if path and os.path.isfile(target): return send_from_directory(FRONT,path)
        return send_from_directory(FRONT,'index.html')
    return jsonify({'message':'Relay API is running. Start the React frontend with npm run dev.'})

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('FLASK_PORT','5000')),debug=True)
