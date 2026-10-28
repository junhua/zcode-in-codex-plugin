import json, os, pathlib, signal, subprocess, sys, time
if '--version' in sys.argv:
    print('0.17.0-fixture');sys.exit()
if '--help' in sys.argv:
    print('--prompt --cwd --mode --resume --disallowed-tools');sys.exit()
prompt=sys.argv[sys.argv.index('--prompt')+1]
wt=pathlib.Path(sys.argv[sys.argv.index('--cwd')+1])
def event(e): print(json.dumps(e),flush=True)
event({'type':'session.started','sessionId':'sess_fixture-123'})
if 'CASE_AUTH' in prompt:
    print('Authentication required: api_key=sk-fake-secret-123456789',file=sys.stderr);sys.exit(1)
if 'CASE_RUNTIME_LIMIT' in prompt:
    root=pathlib.Path(os.environ['ZCODE_STORAGE_DIR']);(root/'huge.log').write_bytes(b'x'*(17*1024*1024));time.sleep(300)
if 'CASE_EXEC' in prompt:os.execv('/bin/sleep',['sleep','300'])
if 'CASE_FAIL' in prompt: sys.exit(9)
if 'CASE_SLEEP' in prompt or 'CASE_TREE' in prompt:
    if 'CASE_TREE' in prompt:
        p=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(300)'])
        (wt/'descendant.pid').write_text(str(p.pid))
    time.sleep(300)
if 'CASE_TOOL_ERROR' in prompt: event({'type':'tool.updated','payload':{'kind':'error','message':'fixture error'}})
if 'CASE_DENIED' in prompt: event({'type':'permission.resolved','payload':{'decision':'deny'}})
if 'CASE_TURN_ERROR' in prompt: event({'type':'turn.failed','payload':{'message':'fixture failure'}})
if 'CASE_QUOTED_SECRET' in prompt:
    event({'type':'result','sessionId':'sess_fixture-123','response':'api_key=\"ABCDEF12345\"','payload':{'access_token':'ABCDEF12345'}});sys.exit()
if 'CASE_ORPHAN' in prompt:
    p=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(300)'])
    (wt/'descendant.pid').write_text(str(p.pid))
    event({'type':'result','sessionId':'sess_fixture-123','response':'leader exits first'});sys.exit()
if 'CASE_ESCAPE' in prompt:
    registry=wt.parents[1]/wt.name/'job.json'
    gitdir=pathlib.Path((wt/'.git').read_text().split('gitdir: ',1)[1].strip())
    for target in [registry,gitdir.parents[2]/'escaped.txt',pathlib.Path(os.environ['HOME'])/'.zcode/cli/config.json']:
        try: target.write_text('must be blocked');raise RuntimeError('write sandbox escaped')
        except PermissionError: pass
if 'CASE_MALFORMED' in prompt: print('{broken',flush=True)
if 'CASE_TRUNCATED' in prompt:
    print('{"type":"res',end='',flush=True);sys.exit()
if 'CASE_OVERSIZE' in prompt: print('x'*400000,flush=True)
if 'CASE_SECRET' in prompt: print('access_token=abc123456789',file=sys.stderr,flush=True)
if 'CASE_AFTER' in prompt:
    event({'type':'result','sessionId':'sess_fixture-123','response':'done'})
    event({'type':'unknown'});sys.exit()
if 'CASE_PERMISSION' in prompt: event({'type':'tool.result','isError':True,'message':'No permission client configured'})
if '--resume' in sys.argv:
    (wt/'resumed.txt').write_text(sys.argv[sys.argv.index('--resume')+1])
else: (wt/'answer.txt').write_text('42\n')
event({'type':'unknown.future.event','payload':{'kept':True}})
event({'type':'result','sessionId':'sess_fixture-123','traceId':'trace-fixture','turnId':'turn-1','response':'Edited answer.txt. Tests: not run. Blockers: none.'})
