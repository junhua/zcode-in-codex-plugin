#!/usr/bin/env python3
"""One bounded ZCode app-server session; verify route before sending task text."""
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
import selectors
import subprocess
import sys
import time
import uuid
from policy import PolicyError,admit,boundary_due,verify_snapshot,utc_now

MAX_LINE=256*1024

def emit(event):
    print(json.dumps(event),flush=True)

def execute(request):
    # This process and its child share the supervisor-owned process group/sandbox.
    child=None;sid=request.get('session_id') or 'sess_'+str(uuid.uuid4());expected_sid=sid;seq=0;pending={};buffers={};stopping=False
    expires=time.monotonic()+request['timeout_seconds']
    started=False;accepted=False;finished=False;effective=None;terminal=None;turn_id=None;input_id=str(uuid.uuid4())
    def send(method,params,tag):
        nonlocal seq
        seq+=1;pending[seq]=tag
        emit({'type':'protocol.phase','method':method,'inference_bearing':method=='session/send'})
        child.stdin.write((json.dumps({'id':seq,'method':method,'params':params})+'\n').encode());child.stdin.flush()
    def finish_terminal():
        nonlocal finished
        if not accepted or terminal is None:return
        event=terminal;payload=event['payload'];kind=payload.get('resultType','error')
        status='idle' if event['type']=='turn.completed' and kind=='success' and not stopping else 'error'
        emit({'type':'result','sessionId':sid,'inputId':input_id,'turnId':turn_id,'traceId':event.get('traceId'),'response':payload.get('response',''),'projection':{'status':status},'effective':effective,'completion_kind':kind})
        finished=True
    def stop(reason='cancelled'):
        nonlocal stopping
        if stopping:return
        stopping=True
        emit({'type':'policy.stopped','reason':reason,'sessionId':sid})
        if sid:
            try:send('session/stop',{'sessionId':sid},'stop')
            except (OSError,BrokenPipeError):pass
    try:
        admit(request['timeout_seconds'])
        child=subprocess.Popen(request['cli']+['app-server','--stdio','--cwd',request['worktree']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        sel=selectors.DefaultSelector()
        for name,pipe in [('stdout',child.stdout),('stderr',child.stderr)]:
            os.set_blocking(pipe.fileno(),False);sel.register(pipe,selectors.EVENT_READ,name);buffers[name]=b''
        common={'workspace':{'workspacePath':request['worktree'],'workspaceKey':'zcode-coordinator-'+request['id']},'toolAllowlist':['Read','Write','Edit','Glob','Grep'],'toolDenylist':request['disallowed'].split(','),'dynamicWorkflowEnabled':False,'offPeakToolEnabled':False}
        if request.get('session_id'):send('session/resume',dict(common,sessionId=sid),'prepare')
        else:send('session/create',dict(common,mode=request['mode'],model=request['selection'],thoughtLevel=request['selection']['options']['reasoningLevel'],sessionId=expected_sid,titleGenerationEnabled=False,persistence='immediate'),'prepare')
        while not finished:
            if time.monotonic()>=expires or boundary_due(request['stop_deadline']) or Path(request['stop_path']).exists():
                reason='peak_interrupted' if boundary_due(request['stop_deadline']) else ('timed_out' if time.monotonic()>=expires else 'cancelled')
                if Path(request['stop_path']).exists():
                    try:reason=json.loads(Path(request['stop_path']).read_text()).get('reason',reason)
                    except (OSError,ValueError):pass
                stop(reason)
                # The supervisor enforces final bounded group cleanup; do not submit more input.
            if child.poll() is not None:
                emit({'type':'process.exit','exit_status':child.returncode})
                if buffers.get('stdout'):raise PolicyError('malformed truncated protocol')
                raise PolicyError('ZCode process exited before a terminal result')
            for key,_ in sel.select(.1):
                chunk=os.read(key.fileobj.fileno(),65536);name=key.data
                if not chunk:
                    if name=='stdout' and buffers[name]:raise PolicyError('malformed truncated protocol')
                    sel.unregister(key.fileobj);continue
                buffers[name]+=chunk
                if len(buffers[name])>MAX_LINE and b'\n' not in buffers[name]:raise PolicyError('oversized protocol line')
                while b'\n' in buffers[name] and not finished:
                    raw,buffers[name]=buffers[name].split(b'\n',1)
                    if len(raw)>MAX_LINE:raise PolicyError('oversized protocol line')
                    if name=='stderr':sys.stderr.buffer.write(raw+b'\n');sys.stderr.flush();continue
                    try:frame=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    except (ValueError,UnicodeError):raise PolicyError('malformed app-server protocol')
                    if not isinstance(frame,dict):raise PolicyError('non-object protocol frame')
                    if 'id' in frame and 'method' in frame:
                        emit({'type':'protocol.host_request','method':frame.get('method')})
                        params=frame.get('params')
                        if frame.get('method')=='session/requestRuntimePreferences' and isinstance(params,dict) and set(params)=={'sessionId','scope'} and params['sessionId']==expected_sid and isinstance(frame['id'],(int,str)) and not isinstance(frame['id'],bool) and params['scope'] in {'runtime-materialization','user-execution'}:
                            preferences={'additionalDirectories':[],'nativeSearchEnhancementsEnabled':False,'toolSearchMode':'off','subagentRuntimeConfigEnabled':False,'memoryEnabled':False,'askUserQuestionAutoResolutionEnabled':False,'modelContextBudgetStrategy':'preflight-v1'}
                            child.stdin.write((json.dumps({'id':frame['id'],'result':preferences})+'\n').encode());child.stdin.flush();continue
                        state='task input may already have been submitted; partial inference is possible' if started else 'no task was submitted'
                        raise PolicyError('ZCode requires unsupported or mismatched host request '+str(frame.get('method'))+'; '+state+'; use its supported desktop/account connection integration')
                    if 'id' in frame:
                        if not isinstance(frame['id'],(int,str)) or isinstance(frame['id'],bool):raise PolicyError('malformed response ID')
                        tag=pending.pop(frame['id'],None)
                        if tag is None:raise PolicyError('unmatched protocol response')
                        if 'error' in frame:
                            if not isinstance(frame['error'],dict) or not isinstance(frame['error'].get('message'),str):raise PolicyError('malformed error response')
                            raise PolicyError('ZCode protocol '+tag+' refused: '+frame['error']['message'])
                        value=frame.get('result')
                        if tag=='prepare':
                            effective=verify_snapshot(value,request['selection'],request['mode']);verified=True
                            session=value.get('session',{})
                            if not isinstance(session,dict):raise PolicyError('malformed session snapshot')
                            prepared_sid=session.get('id') or session.get('sessionId')
                            if prepared_sid!=expected_sid or not isinstance(prepared_sid,str) or not re.fullmatch(r'sess_[A-Za-z0-9_-]+',prepared_sid):raise PolicyError('authoritative session ID differs from expected scope; no task was submitted')
                            workspace=session.get('workspace')
                            if not isinstance(workspace,dict) or workspace.get('workspaceKey')!='zcode-coordinator-'+request['id'] or workspace.get('remoteSessionId') or workspace.get('workspaceIdentity') or not isinstance(workspace.get('workspacePath'),str) or Path(workspace['workspacePath']).resolve()!=Path(request['worktree']).resolve():raise PolicyError('authoritative workspace differs from requested local worktree; no task was submitted')
                            sid=prepared_sid
                            emit({'type':'route.verified','sessionId':sid,'effective':effective,'snapshot_sha256':hashlib.sha256(raw).hexdigest()})
                            # Recheck AFTER async create/resume and immediately before sending any task text.
                            admit(max(1,expires-time.monotonic()))
                            if stopping or boundary_due(request['stop_deadline']) or Path(request['stop_path']).exists():stop();continue
                            send('session/subscribe',{'sessionId':sid},'subscribe')
                        elif tag=='subscribe':
                            admit(max(1,expires-time.monotonic()))
                            if stopping or boundary_due(request['stop_deadline']) or Path(request['stop_path']).exists():stop();continue
                            # Explicit per-input selection is immutable admission data, never a prompt instruction.
                            started=True
                            send('session/send',{'sessionId':sid,'content':request['prompt'],'modelSelection':request['selection'],'inputId':input_id,'toolDenylist':request['disallowed'].split(',')},'send');started=True
                        elif tag=='read':
                            verify_snapshot(value,request['selection'],request['mode'])
                        elif tag=='send':
                            if not isinstance(value,dict) or value.get('accepted') is not True:raise PolicyError('input was not accepted')
                            accepted=True;finish_terminal()
                    elif frame.get('method')=='session/event':
                        event=frame.get('params',{})
                        if not isinstance(event,dict) or not isinstance(event.get('payload'),dict):raise PolicyError('malformed event payload')
                        if event.get('sessionId')!=sid:raise PolicyError('event session mismatch')
                        payload=event.get('payload',{})
                        if event.get('type')=='turn.started':
                            if not started or payload.get('inputId')!=input_id:raise PolicyError('unexpected autonomous input; stopped without reporting task success')
                            turn_id=event.get('turnId')
                            if not isinstance(turn_id,str) or not turn_id:raise PolicyError('missing correlated turn ID')
                        if event.get('type') in {'turn.completed','turn.failed'}:
                            if payload.get('inputId')!=input_id:continue
                            if not turn_id or event.get('turnId')!=turn_id:raise PolicyError('terminal turn is not correlated to submitted input')
                            terminal=event
                        emit(event)
                        finish_terminal()
                    elif frame.get('method')=='interaction/requestPermission':
                        # Never grant approvals. No user/client broker is provided by this adapter.
                        raise PolicyError('interactive permission request requires user action; no approval was granted')
                    else:emit({'type':'protocol.notification','frame':frame})
            if stopping and not started:raise PolicyError('admission stopped before inference')
    except Exception as error:
        error.task_input_state='accepted' if accepted else ('attempted_unknown' if started else 'not_attempted')
        raise
    finally:
        if child is not None:
            if child.poll() is None:
                try:child.stdin.close();child.wait(timeout=1.8)
                except (OSError,subprocess.TimeoutExpired):
                    child.terminate()
                    try:child.wait(timeout=.5)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=1)

if __name__=='__main__':
    try:execute(json.loads(Path(sys.argv[1]).read_text()))
    except (PolicyError,OSError,ValueError,KeyError,TypeError,AttributeError,subprocess.SubprocessError) as e:
        if isinstance(e,PolicyError) and e.detail:emit({'type':'policy.stopped','reason':'peak_blocked','policy':e.detail})
        emit({'type':'route.refused','reason':str(e),'task_input_state':getattr(e,'task_input_state','not_attempted'),'protocol_error':any(word in str(e) for word in ['malformed','oversized','protocol exited','non-object','unmatched'])});sys.exit(2)
