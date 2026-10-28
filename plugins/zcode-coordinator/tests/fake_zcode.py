"""Synthetic implementation of the inspected app-server compatibility protocol."""
import json,os,pathlib,subprocess,sys,time
if '--version' in sys.argv:print('0.17.0-fixture');sys.exit()
if '--help' in sys.argv:print('--prompt --cwd --mode --resume --disallowed-tools');sys.exit()
if 'app-server' not in sys.argv:sys.exit('fixture requires app-server')
wt=pathlib.Path(sys.argv[sys.argv.index('--cwd')+1]);runtime=pathlib.Path(os.environ['ZCODE_STORAGE_DIR'])
sid='sess_fixture-123';selection=None;mode='edit';waiting=False;input_id=None;pending_prepare=None

def out(value):print(json.dumps(value),flush=True)
def response(q,result):out({'id':q['id'],'result':result})
def event(kind,payload):
 if kind.startswith('turn.'):payload=dict(payload,inputId=input_id)
 out({'method':'session/event','params':{'type':kind,'sessionId':sid,'turnId':'turn-fixture','traceId':'trace-fixture','payload':payload}})
def snapshot():
 current=dict(selection)
 if '--fixture-unknown-route' in sys.argv:current={}
 if '--fixture-mismatch-route' in sys.argv:current['modelId']='UnexpectedModel'
 if '--fixture-unknown-effort' in sys.argv:current['options']={}
 if '--fixture-effort-mismatch' in sys.argv:current['options']={'reasoningLevel':'max'}
 actual_mode='edit' if '--fixture-mode-mismatch' in sys.argv else mode
 return {'session':{'id':sid,'workspace':workspace},'settings':{'model':{'current':current},'thoughtLevel':{'current':None if '--fixture-unknown-effort' in sys.argv else selection.get('options',{}).get('reasoningLevel')},'mode':{'current':actual_mode}}}

for raw in sys.stdin:
 q=json.loads(raw)
 if 'method' not in q and pending_prepare is not None:
  assert q['id']=='host-pref' and q['result']['memoryEnabled'] is False and q['result']['askUserQuestionAutoResolutionEnabled'] is False
  response(pending_prepare,snapshot());pending_prepare=None;continue
 method=q['method'];p=q['params']
 if method in ['session/create','session/resume']:
  if method=='session/create':
   sid=p['sessionId'];workspace=p['workspace'];selection=p['model'];mode=p['mode'];(runtime/'fixture-selection.json').write_text(json.dumps({'selection':selection,'mode':mode,'sessionId':sid,'workspace':workspace}))
  else:
   data=json.loads((runtime/'fixture-selection.json').read_text());selection=data['selection'];mode=data['mode'];sid=data['sessionId'];workspace=data['workspace']
   if '--fixture-resume-id-mismatch' in sys.argv:sid='sess_wrong'
  if '--fixture-workspace-mismatch' in sys.argv:workspace=dict(workspace,workspacePath='/missing/other-worktree')
  if '--fixture-slow-prepare' in sys.argv:(runtime/'prepare-marker').write_text('ready');time.sleep(1)
  if '--fixture-host-preferences' in sys.argv:
   pending_prepare=q;out({'id':'host-pref','method':'session/requestRuntimePreferences','params':{'sessionId':'sess_wrong' if '--fixture-host-id-mismatch' in sys.argv else sid,'scope':'runtime-materialization'}});continue
  if '--fixture-host-unsupported' in sys.argv:out({'id':'host-secret','method':'provider/requestCredentials','params':{}});continue
  if '--fixture-malformed-frame' in sys.argv:out({'id':[],'result':{}});continue
  response(q,snapshot())
 elif method=='session/subscribe':
  if '--fixture-slow-subscribe' in sys.argv:(runtime/'subscribe-marker').write_text('ready');time.sleep(1)
  response(q,{'sessionId':sid})
 elif method=='session/read':response(q,snapshot())
 elif method=='session/stop':
  response(q,{})
  event('turn.completed',{'response':'Stopped; partial artifacts retained.','resultType':'cancelled'});break
 elif method=='session/send':
  prompt=p['content'];input_id=p['inputId'];marker=runtime/'fixture-send-marker';marker.write_text(str(int(marker.read_text())+1) if marker.exists() else '1')
  if '--fixture-terminal-before-rejected-ack' in sys.argv:
   event('turn.started',{'input':prompt,'turnNumber':1});event('turn.completed',{'response':'must not be accepted','resultType':'success'});response(q,{'accepted':False});continue
  if '--fixture-terminal-before-accepted-ack' in sys.argv:
   event('turn.started',{'input':prompt,'turnNumber':1});event('turn.completed',{'response':'correlated success','resultType':'success'});response(q,{'sessionId':sid,'accepted':True,'stateRevision':1});continue
  if '--fixture-stale-terminal' in sys.argv:out({'method':'session/event','params':{'type':'turn.completed','sessionId':sid,'turnId':'old-turn','payload':{'inputId':'old-input','response':'stale','resultType':'success'}}})
  response(q,{'sessionId':sid,'accepted':True,'stateRevision':1})
  event('turn.started',{'input':prompt,'turnNumber':1})
  if 'CASE_AUTH' in prompt:print('Authentication required: api_key=sk-fake-secret-123456789',file=sys.stderr);sys.exit(1)
  if 'CASE_FAIL' in prompt:sys.exit(9)
  if 'CASE_RUNTIME_LIMIT' in prompt:(runtime/'huge.log').write_bytes(b'x'*(17*1024*1024));waiting=True;continue
  if 'CASE_EXEC' in prompt:os.execv('/bin/sleep',['sleep','300'])
  if 'CASE_TREE' in prompt or 'CASE_ORPHAN' in prompt:
   c=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(300)']);(wt/'descendant.pid').write_text(str(c.pid))
   if 'CASE_ORPHAN' in prompt:event('turn.completed',{'response':'leader exits first','resultType':'success'});sys.exit()
  if 'CASE_SLEEP' in prompt or 'CASE_TREE' in prompt:(wt/'partial.txt').write_text('partial work retained');waiting=True;continue
  if 'CASE_MALFORMED' in prompt:print('{broken',flush=True)
  if 'CASE_TRUNCATED' in prompt:print('{"type":"res',end='',flush=True);sys.exit()
  if 'CASE_OVERSIZE' in prompt:print('x'*400000,flush=True)
  if 'CASE_PERMISSION' in prompt or 'CASE_DENIED' in prompt:event('permission.resolved',{'decision':'deny'})
  if 'CASE_TOOL_ERROR' in prompt:event('tool.updated',{'kind':'error'})
  if 'CASE_TURN_ERROR' in prompt:event('turn.failed',{'message':'fixture failure'});continue
  if 'CASE_ESCAPE' in prompt:
   registry=wt.parents[1]/wt.name/'job.json';gitdir=pathlib.Path((wt/'.git').read_text().split('gitdir: ',1)[1].strip())
   for target in [wt/'.git',registry,gitdir.parents[2]/'escaped.txt',pathlib.Path(os.environ['HOME'])/'.zcode/cli/config.json',pathlib.Path(os.environ['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE'])]:
    try:target.write_text('must be blocked');raise RuntimeError('write sandbox escaped')
    except PermissionError:pass
  if 'CASE_QUOTED_SECRET' in prompt:event('turn.completed',{'response':'api_key="ABCDEF12345"','resultType':'success'});continue
  if 'CASE_AFTER' in prompt:
   event('turn.completed',{'response':'done','resultType':'success'});print('{broken',flush=True);sys.exit()
  name='resumed.txt' if method=='session/send' and (wt/'answer.txt').exists() else 'answer.txt'
  (wt/name).write_text(sid if name=='resumed.txt' else '42\n')
  event('unknown.future.event',{'kept':True})
  event('turn.completed',{'response':'Edited answer.txt. Tests: not run. Blockers: none.','resultType':'success'})
 else:out({'id':q['id'],'error':{'code':-32601,'message':'unknown fixture method'}})
