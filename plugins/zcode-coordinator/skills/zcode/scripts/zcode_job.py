#!/usr/bin/env python3
"""Local ZCode supervisor. Python 3.9+, macOS/Linux, no third-party dependencies."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parent))
from policy import POLICY_VERSION,PolicyError,admit,boundary_due,route,window,utc_now,verify_snapshot

VERSION = '0.3.0'
ACTIVE = {'starting', 'running', 'cancelling'}
MAX_LOG = 1024 * 1024
MAX_LINE = 256 * 1024
MAX_RUNTIME = 16 * 1024 * 1024
BUNDLE = '/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs'
# Bash needs an interactive approval in edit mode; removing it closes the command surface.
DISALLOWED = 'Bash,Agent,Task,ToolSearch,WebSearch,WebFetch,CreateWorkflow,EnterPlanMode,ExitPlanMode,AskUserQuestion'

class JobError(Exception):
    pass

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def redact(text):
    # Drop credential-like assignments as a unit, including quoted/escaped values.
    if re.search(r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)[\\\"'\s]*[:=]", text):
        return '[REDACTED: credential-like assignment]'
    text = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+', r'\1[REDACTED]', text)
    return re.sub(r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{12,})\b', '[REDACTED]', text)

def redacted_value(value):
    if isinstance(value,str): return redact(value)
    if isinstance(value,list): return [redacted_value(v) for v in value]
    if isinstance(value,dict):
        return {k: ('[REDACTED]' if re.search(r'(?i)^(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)$',k) else redacted_value(v)) for k,v in value.items()}
    return value

def save(path, data):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with open(tmp, 'x', encoding='utf-8') as f:
        os.chmod(tmp, 0o600)
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def read(path):
    return json.loads(path.read_text())

def run(argv, cwd=None, timeout=15):
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, check=False,
                          env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')})

def git(repo, *args):
    p = run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args])
    if p.returncode:
        raise JobError('git failed: ' + redact(p.stderr.strip())[:500])
    return p.stdout.strip()

def state_dir(value):
    p = Path(value).expanduser()
    if not p.is_absolute() or p.is_symlink():
        raise JobError('--state must be an absolute, non-symlink directory')
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    p = p.resolve()
    if p.stat().st_uid != os.getuid() or p.stat().st_mode & 0o077:
        raise JobError('state directory must be canonical, owned by you, and mode 0700')
    return p

@contextlib.contextmanager
def lock(root):
    with open(root / '.lock', 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield

def job_path(root, jid):
    if not re.fullmatch(r'[a-f0-9]{32}', jid):
        raise JobError('invalid job ID')
    p = root / jid
    if p.is_symlink() or not p.is_dir():
        raise JobError('job not found')
    return p

def identity(pid):
    p = run(['ps', '-p', str(pid), '-o', 'uid=,lstart='])
    return p.stdout.strip() if p.returncode == 0 else None

def group_live(pgid):
    listing=run(['ps','-axo','uid=,pid=,pgid=,stat='])
    if listing.returncode: return None
    return [int(row.split()[1]) for row in listing.stdout.splitlines() if len(row.split())>=4 and row.split()[2]==str(pgid) and not row.split()[3].startswith('Z')]

def alive(job):
    expected = job.get('worker_identity')
    return bool(expected and identity(job['worker_pid']) == expected)

def reconcile(root, job):
    if job['status'] in ACTIVE and time.time() - job['created_epoch'] > 5 and not alive(job):
        job['status'] = 'interrupted'
        job['blockers'].append('Supervisor is absent or identity changed; no process was signalled. Inspect child evidence before resuming.')
        job['ended_at'] = now()
        save(root / job['id'] / 'job.json', job)
    return job

def resolve_cli(explicit=None):
    if explicit:
        argv = json.loads(explicit)
        if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v for v in argv):
            raise JobError('--cli-json must be a nonempty argv array')
    elif shutil.which('zcode'):
        argv = [shutil.which('zcode')]
    elif Path(BUNDLE).is_file() and shutil.which('node'):
        argv = [shutil.which('node'), BUNDLE]
    else:
        raise JobError('ZCode CLI missing: install the official CLI or supply --cli-json with its verified absolute argv')
    if not Path(argv[0]).is_absolute() or not os.access(argv[0], os.X_OK):
        raise JobError('CLI executable must be an absolute executable path')
    return argv

def capability(argv):
    version = run(argv + ['--version'])
    help_result = run(argv + ['--help', '--output-format', 'stream-json', '--workflow-mode', 'disabled'])
    text = help_result.stdout
    required = ['--prompt', '--cwd', '--mode', '--resume', '--disallowed-tools']
    if version.returncode or help_result.returncode or not all(x in text for x in required):
        raise JobError('CLI lacks the verified prompt/resume/mode/output interface; inspect its help and source')
    model = None
    if BUNDLE in argv:
        personal=Path.home()/'.zcode/v2/provider_config.json'
        try:
            selection=read(personal).get('config',{}).get('defaultModelSelection',{})
            mid=selection.get('modelId');pid=selection.get('providerId')
            if isinstance(mid,str) and isinstance(pid,str) and len(mid)<=256 and len(pid)<=256:
                model={'provider_id':pid,'model_id':mid,'source':'existing personal defaultModelSelection'}
        except (OSError,ValueError,AttributeError): pass
    return {'argv': argv, 'version': version.stdout.strip(),
            'executable_sha256': hashlib.sha256(Path(argv[-1] if len(argv)>1 and Path(argv[-1]).is_file() else argv[0]).read_bytes()).hexdigest(),
            'stream_parser_probe': 'accepted; live event protocol still requires a real run',
            'auth': 'unknown; doctor does not read or validate credentials', 'model': model}

def doctor(args):
    try:
        info = capability(resolve_cli(args.cli_json))
        info.update({'peak_policy':window(),'routing_policy_version':POLICY_VERSION,'route_verification':'same-process app-server session snapshot; unsupported/missing effective route fails before session/send','wrapper_version': VERSION, 'ready_for_probe': True, 'process_inspection': bool(identity(os.getpid())), 'modes': ['edit', 'plan'],
                     'cancel': 'owned process-group SIGTERM then SIGKILL; detached descendants outside group are not guaranteed',
                     'limits': 'macOS write sandbox required. Bash removed; isolated HOME disables user extensions. Read access and provider network are not isolated; use only authorized repositories.'})
        return info
    except (JobError, OSError, subprocess.TimeoutExpired, ValueError) as e:
        return {'wrapper_version': VERSION, 'ready_for_probe': False, 'error': redact(str(e))}

def selected_model(selection):
    if not selection: return None
    return {'provider_id':selection['providerId'],'model_id':selection['modelId'],
            'source':'per-job selection-only provider profile', 'reasoning_level':selection.get('options',{}).get('reasoningLevel')}

def validate_model_selection(selection, catalog):
    if not {'providerId','modelId'} <= set(selection) or set(selection)-{'providerId','modelId','options'} or not all(isinstance(selection[k],str) and 0<len(selection[k])<=256 for k in ['providerId','modelId']):
        raise JobError('model selection requires only nonempty providerId and modelId strings')
    providers=catalog.get('config',{}).get('providerConfigRules',{}).get('providerRules',[])
    provider=next((v for v in providers if v.get('providerId')==selection['providerId']),None)
    if not provider or provider.get('config',{}).get('access',{}).get('type')!='zhipu-account':
        raise JobError('per-job selection is limited to an installed built-in account provider; custom endpoints or credentials are unsupported')
    models=catalog.get('config',{}).get('modelConfigRules',{}).get('builtinProviderModelRules',[])
    if not any(v.get('providerId')==selection['providerId'] and v.get('modelId')==selection['modelId'] and v.get('config',{}).get('enabled') is True for v in models):
        raise JobError('requested model is not enabled in the installed built-in provider catalog')
    if 'options' in selection:
        options=selection['options']
        if not isinstance(options,dict) or set(options)!={'reasoningLevel'} or not isinstance(options['reasoningLevel'],str):
            raise JobError('only reasoningLevel is supported in per-job model options')
        allowed=[]
        for rule in catalog.get('config',{}).get('modelConfigRules',{}).get('modelRules',[]):
            try: match=re.fullmatch(rule.get('modelMatch','a^'),selection['modelId'],re.I)
            except re.error: match=None
            values=rule.get('config',{}).get('optionSpecs',{}).get('reasoningLevel',{}).get('values')
            if match and isinstance(values,list):allowed=values
        if options['reasoningLevel'] not in allowed:
            raise JobError('reasoning level is not advertised by the installed model catalog')
    return dict(selection)

def job_selection(args, cli):
    decision=route(args.task_kind,args.complexity,args.risk)
    if args.model_id and args.model_id!=decision['model_id']:raise JobError('Explicit model differs from task routing policy; revise the classification with evidence, not a blind override')
    if args.reasoning_level and args.reasoning_level!=decision['effort']:raise JobError('Explicit effort differs from task routing policy; revise the classification with evidence')
    args.model_id=decision['model_id'];args.reasoning_level=decision['effort']
    if not args.provider_id:raise JobError('An existing built-in --provider-id is required; no provider/default is selected silently')
    if not args.provider_id and not args.model_id:
        if args.reasoning_level:raise JobError('--reasoning-level requires --provider-id and --model-id')
        return None
    if not args.provider_id or not args.model_id:
        raise JobError('--provider-id and --model-id must be supplied together')
    if not Path(BUNDLE).is_file():
        raise JobError('the verified desktop catalog is unavailable; use the supported ZCode bundle/configuration, no route can be proven')
    catalog=read(Path(BUNDLE).parent.parent/'config/provider/zcode-builtin.json')
    selection={'providerId':args.provider_id,'modelId':args.model_id}
    if args.reasoning_level:selection['options']={'reasoningLevel':args.reasoning_level}
    selected=validate_model_selection(selection,catalog)
    provider=next(v for v in catalog['config']['providerConfigRules']['providerRules'] if v.get('providerId')==selected['providerId'])
    transport=provider.get('config',{}).get('api',{}).get('type')
    mapping=None
    for rule in catalog['config']['modelConfigRules'].get('modelApiRules',[]):
        if re.fullmatch(rule.get('modelMatch','a^'),selected['modelId'],re.I) and re.fullmatch(rule.get('apiTypeMatch','a^'),transport or '',re.I):
            value=rule.get('config',{}).get('optionSpecs',{}).get('reasoningLevel',{}).get('map')
            if value is not None:mapping=value
    for section in ['providerSiteRules','templateModelRules','providerModelRules','manualProviderModelRules','builtinProviderModelRules']:
        for rule in catalog['config']['modelConfigRules'].get(section,[]):
            if rule.get('providerId') not in {None,selected['providerId']}:continue
            if section=='templateModelRules' and rule.get('templateId')!=provider.get('config',{}).get('templateId'):continue
            if rule.get('apiTypeMatch') and not re.fullmatch(rule['apiTypeMatch'],transport or '',re.I):continue
            if rule.get('baseUrlMatch') and not re.fullmatch(rule['baseUrlMatch'],provider.get('config',{}).get('api',{}).get('baseUrl',''),re.I):continue
            override=rule.get('config',{}).get('optionSpecs',{}).get('reasoningLevel')
            if not override:continue
            matches=(rule.get('modelId')==selected['modelId']) if 'modelId' in rule else bool(re.fullmatch(rule.get('modelMatch','.*'),selected['modelId'],re.I))
            if matches:raise JobError('Later catalog reasoning override is unverified; inspect provider configuration before inference')
    expected='{"thinking":{"type":"enabled"},"output_config":{"effort":reasoningLevel}}'
    if transport!='anthropic-messages' or not isinstance(mapping,str) or re.sub(r'\s','',mapping)!=expected:
        raise JobError('Installed provider transport/effort mapping is not verified; no inference will be submitted; inspect supported ZCode provider configuration')
    cli['route_catalog_evidence']={'catalog_sha256':hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest(),'transport':transport,'map_sha256':hashlib.sha256(mapping.encode()).hexdigest(),'mapping':'thinking enabled; output_config.effort explicitly set','api_defaults':'not used; effort always explicit'}
    return selected

def prompt_text(path):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.stat().st_size > 32768:
        raise JobError('prompt must be a UTF-8 file of at most 32768 bytes')
    text = p.read_text()
    if not text.strip() or text.lstrip().startswith('/'):
        raise JobError('use a bounded task specification, not a slash command')
    return p, text

def check_project_inputs(worktree):
    # These can enable plugins, MCP, hooks or inject runtime env above isolated user config.
    for parent in [worktree, *worktree.parents]:
        for relative in ['zcode.json','.zcode/config.json','.env']:
            if (parent / relative).exists() or (parent / relative).is_symlink():
                raise JobError('execution refused: project/ancestor runtime input requires review: ' + str(parent / relative))

def verify_worktree(job):
    control=Path(job['worktree'])/'.git'
    if control.is_symlink() or not control.is_file() or hashlib.sha256(control.read_bytes()).hexdigest()!=job.get('worktree_git_control_sha256'):
        raise JobError('worktree Git control file changed; trusted Git inspection/resume refused')

def launch(root, job, text):
    job['peak_policy']=admit(job['timeout_seconds'])
    job['stop_deadline']=job['peak_policy']['stop_deadline']
    check_project_inputs(Path(job['worktree']))
    attempt = job['attempt']
    directory = root / job['id'] / f'attempt-{attempt}'
    directory.mkdir(mode=0o700)
    (directory / 'prompt.txt').write_text(text)
    os.chmod(directory / 'prompt.txt', 0o600)
    for stale in ['cooperative_stop','peak_block','checkpoint','interruption_reason','interruption_policy']:job.pop(stale,None)
    job.update(status='starting', created_epoch=time.time(), started_at=now(), ended_at=None,
               worker_pid=None, worker_identity=None, child_pid=None, exit_status=None,
               effective_route=None,route_verification=None,inference_submission_state='not_attempted',blockers=[], attempt_path=str(directory), changed_files=[], final_commits=[])
    save(root / job['id'] / 'job.json', job)
    token = uuid.uuid4().hex
    job['worker_token'] = token
    save(root / job['id'] / 'job.json', job)
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--state', str(root),
                          '_worker', job['id'], token], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                         close_fds=True)
    # Worker owns subsequent state writes; never overwrite its fast completion.
    return {'id': job['id'], 'attempt': attempt, 'status': 'starting', 'supervisor_pid': p.pid,
            'worktree': job['worktree'], 'report_path': str(directory / 'report.json')}

def start(args, root):
    admit(args.timeout)
    prompt_path, text = prompt_text(args.prompt_file)
    repo = Path(args.repo).expanduser().resolve(strict=True)
    if git(repo, 'rev-parse', '--show-toplevel') != str(repo):
        raise JobError('--repo must be the repository root')
    sha = git(repo, 'rev-parse', '--verify', '--end-of-options', args.base + '^{commit}')
    if not identity(os.getpid()):
        raise JobError('process inspection unavailable; delegate requires ps UID/start-time ownership checks')
    cli = capability(resolve_cli(args.cli_json))
    selection = job_selection(args, cli)
    jid = uuid.uuid4().hex
    with lock(root):
        directory = root / jid; directory.mkdir(mode=0o700)
        worktrees = root / 'worktrees'; worktrees.mkdir(exist_ok=True, mode=0o700)
        wt = worktrees / jid
        git(repo, 'worktree', 'add', '--detach', str(wt), sha)
        git_control=wt/'.git'
        job = {'worktree_git_control_sha256':hashlib.sha256(git_control.read_bytes()).hexdigest(),'schema': 1, 'id': jid, 'task_id': args.task_id, 'spec_reference': str(prompt_path),
               'spec_sha256': hashlib.sha256(text.encode()).hexdigest(), 'repo': str(repo),
               'worktree': str(wt), 'base_ref': args.base, 'base_sha': sha,
               'source_branch': git(repo, 'branch', '--show-current'), 'cli': cli,
               'mode': args.mode, 'timeout_seconds': args.timeout, 'session_id': None,
               'wrapper_version':VERSION,'routing_policy':route(args.task_kind,args.complexity,args.risk),'requested_route':selected_model(selection),'configured_model': selected_model(selection), 'model_selection':selection, 'attempt': 1, 'tests': [], 'parent_job': None}
        return launch(root, job, text)

def resume(args, root):
    # Admission precedes reconciliation or any session/runtime action.
    admit(1)
    spec_path, text = prompt_text(args.prompt_file)
    with lock(root):
        directory = job_path(root, args.id)
        job = reconcile(root, read(directory / 'job.json'))
        admit(job['timeout_seconds'])
        if not job.get('routing_policy') or not job.get('model_selection'):raise JobError('Legacy job lacks a verified task route; start a new classified task instead of resuming an unknown route')
        if job['status'] in ACTIVE:
            raise JobError('job is active; wait or cancel first')
        if job['status'] in {'interrupted','cleanup_required'}:
            raise JobError('resume blocked: supervisor interruption requires manual process/worktree inspection')
        with open(directory / 'supervisor.lock','a') as finishing:
            try: fcntl.flock(finishing,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise JobError('previous supervisor is finishing; resume was not started, retry shortly')
        if not job.get('session_id'):
            raise JobError('resume unsupported for this job: no valid ZCode session ID was observed')
        verify_worktree(job)
        if not Path(job['worktree']).is_dir():
            raise JobError('original worktree missing')
        decision=route(args.task_kind,args.complexity,args.risk)
        if decision['model_id']!=job['model_selection']['modelId'] or decision['effort']!=job['model_selection']['options']['reasoningLevel']:raise JobError('Follow-up requires a different task route; start a new bounded job, not a silently switched session')
        job['routing_policy']=decision
        job['cli'] = capability(job['cli']['argv'])
        job['configured_model'] = selected_model(job.get('model_selection')) or job['cli'].get('model')
        if job.get('model_selection'):
            validate_model_selection(job['model_selection'],read(Path(BUNDLE).parent.parent/'config/provider/zcode-builtin.json'))
        job['spec_reference'] = str(spec_path)
        job['spec_sha256'] = hashlib.sha256(text.encode()).hexdigest()
        job['attempt'] += 1
        return launch(root, job, text)

class Sink:
    def __init__(self, path):
        self.f = open(path, 'wb'); self.size = 0; self.truncated = False
    def write(self, text):
        data = redact(text).encode()
        remain = MAX_LOG - self.size
        self.f.write(data[:max(0,remain)]); self.size += min(len(data), max(0,remain))
        self.truncated |= len(data)>remain
    def close(self):
        self.f.close()

def child_environment(job, root):
    # Preserve only runtime basics. Do not forward arbitrary API keys, shell hooks or service tokens.
    env = {k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','LANG','LC_ALL','TMPDIR','SSL_CERT_FILE','NODE_EXTRA_CA_CERTS'}}
    runtime = root / job['id'] / 'runtime'; runtime.mkdir(exist_ok=True, mode=0o700)
    original_home = os.environ.get('HOME', str(Path.home()))
    control=root / job['id'] / 'control';control.mkdir(exist_ok=True,mode=0o700)
    home = control / 'home'; config_dir = home / '.zcode' / 'cli'
    config_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    save(config_dir / 'config.json', {'features':{'mcp':False,'subagent':False,'memory':False,'skill':False},'plugins':{'enabled':False},'skills':{'enabled':False},'hooks':{'enabled':False},'memory':{'use':False}})
    if Path(BUNDLE).is_file():
        builtin=Path(BUNDLE).parent.parent/'config/provider/zcode-builtin.json'
        personal=Path(original_home)/'.zcode/v2/provider_config.json'
        if builtin.is_file():env['ZCODE_BUILTIN_PROVIDER_CONFIG_FILE']=str(builtin)
        if personal.is_file():env['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE']=str(personal)
    if job.get('model_selection'):
        # Selection-only profile: no user config or credential bytes are copied.
        profile=control/'selected-provider.json'
        save(profile,{'schemaVersion':1,'config':{'providerConfigRules':{'providerRules':[]},'modelConfigRules':{'providerModelRules':[],'manualProviderModelRules':[]},'defaultModelSelection':job['model_selection']}})
        env['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE']=str(profile)
    env.update(HOME=str(home), ZCODE_DATA_BASE_DIR=original_home, ZCODE_STORAGE_DIR=str(runtime), ZCODE_LOG_DIR=str(runtime / 'log'),
               ZCODE_SESSION_DB_PATH=str(runtime / 'db.sqlite'))
    return env

def terminate_owned(child, birth):
    if child.returncode is not None:return
    members=group_live(child.pid)
    if members is None:raise JobError('process group inspection unavailable; cleanup refused')
    if not members:
        try:child.wait(timeout=0);return
        except subprocess.TimeoutExpired:raise JobError('owned process absent from group inspection')
    if not birth or identity(child.pid)!=birth:raise JobError('child ownership check failed; cancellation refused')
    try:
        if os.getpgid(child.pid)!=child.pid:raise JobError('owned process group changed')
    except ProcessLookupError:
        # Darwin cannot query a zombie leader's PGID. The unreaped Popen PID and
        # matching UID/start identity reserve its original newly-created group ID.
        pass
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:child.wait(timeout=3);return
    time.sleep(.5)
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    except PermissionError:
        if group_live(child.pid):raise JobError('group cleanup not confirmed')
    child.wait(timeout=3)

def worker(args, root):
    directory = job_path(root,args.id)
    with open(directory / 'supervisor.lock', 'a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise JobError('another supervisor owns this job')
        job = read(directory / 'job.json')
        if job.get('worker_token') != args.token or job['status'] != 'starting':
            raise JobError('invalid supervisor launch')
        job.update(worker_pid=os.getpid(), worker_identity=identity(os.getpid()), status='running')
        save(directory / 'job.json', job)
        attempt = Path(job['attempt_path'])
        cancel = attempt / 'cancel.request'
        child = None
        status = 'failed'; result = None; malformed = False; errors = []
        sinks = {name: Sink(attempt / (name + '.log')) for name in ['stdout','stderr']}
        buffers = {name:b'' for name in sinks}
        deadline = time.monotonic() + job['timeout_seconds']
        peak_monotonic=time.monotonic()+max(0,(datetime.datetime.fromisoformat(job['stop_deadline'])-utc_now()).total_seconds())
        def line(name, raw):
            nonlocal result, malformed, status
            text = raw.decode('utf-8', errors='replace')
            sinks[name].write(text+'\n')
            if name != 'stdout' or not text.strip(): return
            try:
                event = json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-finite JSON constant')))
                if not isinstance(event,dict): raise ValueError('event must be an object')
                if result is not None: raise ValueError('event after final result')
                sid = event.get('sessionId')
                if isinstance(sid,str) and re.fullmatch(r'sess_[A-Za-z0-9_-]+',sid):
                    if job.get('session_id') and job['session_id'] != sid: raise ValueError('session ID changed')
                    job['session_id'] = sid
                if event.get('type')=='policy.stopped' and event.get('reason') in {'peak_interrupted','peak_blocked','timed_out','cancelled','output_limit'}:
                    status=event['reason']
                if event.get('type')=='route.verified':
                    effective=event.get('effective')
                    expected=job['requested_route']
                    if not isinstance(effective,dict) or any(effective.get(k)!=expected.get(k if k!='effort' else 'reasoning_level') for k in ['provider_id','model_id','effort']):raise ValueError('effective route mismatch')
                    job['effective_route']=effective
                    job['route_verification']={'snapshot_sha256':event.get('snapshot_sha256'),'policy_version':POLICY_VERSION,'verified_at':now()}
                    save(directory/'job.json',job)
                if event.get('type')=='process.exit':job['backend_exit_status']=event.get('exit_status')
                if event.get('type')=='route.refused':
                    job['inference_submission_state']=event.get('task_input_state','unknown')
                    if event.get('protocol_error'):malformed=True
                    job['blockers'].append(redact(str(event.get('reason','route verification failed')))[:1000])
                if event.get('type') == 'result':
                    if not job.get('effective_route'):raise ValueError('unverified result route')
                    if not isinstance(event.get('response'),str) or not job.get('session_id'):
                        raise ValueError('invalid result')
                    result = event
                payload = event.get('payload') if isinstance(event.get('payload'),dict) else {}
                projection = event.get('projection') if isinstance(event.get('projection'),dict) else {}
                structured_error = (event.get('type') == 'turn.failed' or (event.get('type') == 'tool.updated' and payload.get('kind') == 'error') or (event.get('type') == 'permission.resolved' and payload.get('decision') == 'deny') or projection.get('status') in {'error','failed','cancelled','interrupted'})
                if structured_error or re.search(r'No permission client configured|permission.denied|"isError"\s*:\s*true',text,re.I):
                    if len(errors)<20: errors.append('Tool/permission error observed; inspect redacted stream')
            except (ValueError,TypeError):
                malformed = True
        try:
            text = (attempt / 'prompt.txt').read_text()
            prompt = ('Bounded task delegated by Codex. Work only in this worktree. Do not push, merge, deploy, change permissions, create credentials, contact third parties, or start background processes. Do not use external tools, plugins, MCP, workflows or subagents. Do not commit. Return changed files, tests actually executed with results, and blockers. If approvals block work, report it.\n\n' + text)
            admit(job['timeout_seconds'])
            env=child_environment(job,root)
            control=directory/'control'
            request={'id':job['id'],'cli':job['cli']['argv'],'worktree':job['worktree'],'mode':job['mode'],
                     'selection':job['model_selection'],'session_id':job.get('session_id'),'timeout_seconds':job['timeout_seconds'],
                     'stop_deadline':job['stop_deadline'],'stop_path':str(attempt/'stop.request'),'disallowed':DISALLOWED,'prompt':prompt}
            save(control/'protocol-request.json',request)
            argv=[sys.executable,str(Path(__file__).with_name('protocol_bridge.py')),str(control/'protocol-request.json')]
            if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').exists():
                raise JobError('This release requires macOS sandbox-exec; execution is unsupported on this host')
            # Credential/provider files can be read but cannot be changed; file writes stay in job scope.
            check_project_inputs(Path(job['worktree']))
            profile = '(version 1)(allow default)(deny file-write*)(allow file-write* (subpath ' + json.dumps(str(root / job['id'] / 'runtime')) + ') (subpath ' + json.dumps(job['worktree']) + ') (literal \"/dev/null\"))(deny file-write* (literal '+json.dumps(str(Path(job['worktree'])/'.git'))+'))'
            argv = ['/usr/bin/sandbox-exec','-p',profile] + argv
            admit(job['timeout_seconds'])
            child = subprocess.Popen(argv,cwd=job['worktree'],env=env,
                     stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            birth = identity(child.pid)
            job.update(child_pid=child.pid,child_identity=birth)
            save(directory / 'job.json',job)
            sel = selectors.DefaultSelector()
            for name,pipe in [('stdout',child.stdout),('stderr',child.stderr)]:
                os.set_blocking(pipe.fileno(),False); sel.register(pipe,selectors.EVENT_READ,name)
            eof_deadline = None
            runtime_next_check = 0
            while sel.get_map() or child.poll() is None:
                runtime_exceeded = False
                if time.monotonic() >= runtime_next_check:
                    runtime_next_check = time.monotonic() + .5
                    runtime_root = directory / 'runtime'
                    total = 0
                    for path in runtime_root.rglob('*'):
                        try:
                            if path.is_file() and not path.is_symlink(): total += path.stat().st_size
                        except FileNotFoundError: pass
                        if total > MAX_RUNTIME: runtime_exceeded = True; break
                peak_due=boundary_due(job['stop_deadline']) or time.monotonic()>=peak_monotonic
                reason = 'peak_interrupted' if peak_due else ('cancelled' if cancel.exists() else ('timed_out' if time.monotonic()>=deadline else ('output_limit' if runtime_exceeded else None)))
                if reason:
                    status=reason
                    job['interruption_reason']=reason
                    if reason=='peak_interrupted':job['interruption_policy']=window()
                    if child.returncode is None:
                        save(attempt/'stop.request',{'reason':reason,'at':now()})
                        job['cooperative_stop']={'requested':True,'method':'session/stop','reason':reason,'at':now()}
                        # Keep the owned leader unreaped during cooperative stop, preventing PGID reuse.
                        time.sleep(2)
                    terminate_owned(child,birth); status=reason
                    # Drain only for a bounded time; inherited pipe FDs must not hang the supervisor.
                    eof_deadline = eof_deadline or time.monotonic()+2
                if child.poll() is not None: eof_deadline=eof_deadline or time.monotonic()+2
                if eof_deadline and time.monotonic()>eof_deadline: break
                for key,_ in sel.select(.1):
                    chunk=os.read(key.fileobj.fileno(),65536); name=key.data
                    if not chunk:
                        sel.unregister(key.fileobj); key.fileobj.close(); continue
                    buffers[name] += chunk
                    while b'\n' in buffers[name]:
                        raw,buffers[name]=buffers[name].split(b'\n',1); line(name,raw)
                    if len(buffers[name])>MAX_LINE:
                        sinks[name].write('[oversize line discarded]\n'); buffers[name]=b''; malformed=True
            for name,buf in buffers.items():
                if buf: line(name,buf)
            job['exit_status']=child.wait(timeout=3)
            if status not in {'cancelled','timed_out','output_limit','peak_interrupted','peak_blocked'}:
                if malformed:status='protocol_error'
                elif job['exit_status'] != 0: status='failed'
                elif malformed or result is None: status='protocol_error'
                elif errors: status='needs_review'
                else: status='completed'
            if status in {'failed','protocol_error'}:
                job['blockers'].append('CLI failed or final stream was missing/malformed; inspect stdout/stderr evidence')
            if status in {'timed_out','cancelled','output_limit','peak_interrupted'}:
                job['blockers'].append('Process group terminated. Review partial edits; cancellation is not rollback.')
        except Exception as e:
            if isinstance(e,PolicyError):status='peak_blocked';job['peak_block']=e.detail
            job['blockers'].append(redact(str(e))[:1000])
            if child is not None and child.poll() is None:
                try: terminate_owned(child,job.get('child_identity'))
                except Exception as cancel_error:
                    status='cleanup_required'
                    job['blockers'].append('Child termination NOT confirmed: ' + redact(str(cancel_error)))
        finally:
            for sink in sinks.values(): sink.close()
        if child is not None:
            job['exit_status']=child.poll()
            remaining=group_live(child.pid)
            job['remaining_group_pids']=remaining
            if remaining is None or remaining:
                status='cleanup_required'
                job['blockers'].append('Process-group cleanup not confirmed; live members or inspection unavailable. Manual inspection required before resume.')
        job.update(status=status,ended_at=now(),protocol_malformed=malformed,
                   logs_truncated=any(s.truncated for s in sinks.values()), tool_errors=errors)
        if result:
            safe_result=redacted_value(result)
            save(attempt / 'result.json',safe_result)
            job['trace_id']=result.get('traceId');job['turn_id']=result.get('turnId');job['input_id']=result.get('inputId')
        try:
            verify_worktree(job)
            job['changed_files']=git(job['worktree'],'status','--porcelain=v1','--untracked-files=all').splitlines()
            job['final_commits']=git(job['worktree'],'log','--format=%H',job['base_sha']+'..HEAD').splitlines()
            job['final_sha']=git(job['worktree'],'rev-parse','HEAD')
            patch=run(['git','-c','core.hooksPath=/dev/null','-C',job['worktree'],'diff','--no-ext-diff','--no-textconv',job['base_sha'],'--']).stdout
            (attempt / 'changes.patch').write_text(redact(patch)[:MAX_LOG])
            job['patch_truncated']=len(patch)>MAX_LOG
        except Exception as e:
            job['blockers'].append(redact(str(e)))
            job['review_required']=True
            if 'Git control file changed' in str(e):job['status']='cleanup_required'
            elif job['status']=='completed':job['status']='needs_review'
        if child is not None and child.poll() is None:
            status='cleanup_required'
            job['status']=status
            job['blockers'].append('Child may still be alive. Do not resume until manually inspected.')
        job['tests']=[{'source':'agent response','status':'unverified; read result.json; coordinator must run approved tests separately'}]
        job['report_path']=str(attempt / 'report.json')
        if job['status'] in {'peak_interrupted','cancelled','timed_out'}:
            job['checkpoint']={'kind':'retained local artifacts; vendor session persistence is not a transactional checkpoint','at':now(),'report_path':job['report_path'],'patch_path':str(attempt/'changes.patch'),'worktree':job['worktree'],'session_id':job.get('session_id'),'automatic_resume':False}
        save(attempt / 'report.json',job)
        save(directory / 'job.json',job)

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',required=True,help='Absolute private directory (0700) for jobs/worktrees')
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('doctor',aliases=['setup']);d.add_argument('--cli-json')
    s=sub.add_parser('delegate');s.add_argument('--repo',required=True);s.add_argument('--base',default='HEAD')
    s.add_argument('--task-id',required=True);s.add_argument('--prompt-file',required=True)
    s.add_argument('--timeout',type=int,default=600);s.add_argument('--mode',choices=['edit','plan'],default='edit');s.add_argument('--cli-json');s.add_argument('--provider-id');s.add_argument('--model-id');s.add_argument('--reasoning-level')
    s.add_argument('--task-kind',required=True,choices=['mechanical','routine','capability','debugging','architecture','ui-state','visual']);s.add_argument('--complexity',choices=['simple','bounded','hard'],default='bounded');s.add_argument('--risk',choices=['normal','ambiguous','security','data-loss','cross-service'],default='normal')
    plan=sub.add_parser('route');plan.add_argument('--task-kind',required=True);plan.add_argument('--complexity',default='bounded');plan.add_argument('--risk',default='normal')
    for command in ['status','result','cancel']:
        t=sub.add_parser(command);t.add_argument('id')
    r=sub.add_parser('resume');r.add_argument('id');r.add_argument('--prompt-file',required=True);r.add_argument('--task-kind',required=True);r.add_argument('--complexity',default='bounded');r.add_argument('--risk',default='normal')
    t=sub.add_parser('record-test');t.add_argument('id');t.add_argument('--argv-json',required=True);t.add_argument('--exit-code',type=int,required=True);t.add_argument('--evidence-file',required=True)
    w=sub.add_parser('_worker');w.add_argument('id');w.add_argument('token')
    args=p.parse_args()
    try:
        root=state_dir(args.state)
        if args.command=='route':output=route(args.task_kind,args.complexity,args.risk)
        elif args.command in {'doctor','setup'}: output=doctor(args)
        elif args.command=='delegate':
            if not 1<=args.timeout<=86400: raise JobError('timeout must be 1..86400 seconds')
            output=start(args,root)
        elif args.command=='resume': output=resume(args,root)
        elif args.command=='_worker': worker(args,root);return
        else:
            with lock(root):
                directory=job_path(root,args.id);job=reconcile(root,read(directory / 'job.json'))
                if args.command=='record-test':
                    if job['status'] in ACTIVE or not job.get('report_path'): raise JobError('record verification only after a final job report exists')
                    argv=json.loads(args.argv_json)
                    if not isinstance(argv,list) or not argv or not all(isinstance(v,str) for v in argv): raise JobError('test argv must be a nonempty string array')
                    evidence=Path(args.evidence_file).resolve(strict=True)
                    if not evidence.is_file() or evidence.stat().st_size>MAX_LOG: raise JobError('test evidence must be a file of at most 1 MiB')
                    target=Path(job['attempt_path'])/('verification-'+str(len(job['tests']))+'.log')
                    target.write_text(redact(evidence.read_text()))
                    job['tests'].append({'source':'coordinator attestation','argv':redacted_value(argv),'cwd':job['worktree'],'exit_code':args.exit_code,'recorded_at':now(),'evidence_path':str(target),'evidence_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
                    save(directory/'job.json',job)
                    save(Path(job['report_path']),job)
                    output=job
                elif args.command=='cancel':
                    if job['status'] not in ACTIVE: raise JobError('job is not active; nothing was cancelled')
                    if not alive(job): raise JobError('supervisor identity unavailable; cancellation not delivered')
                    (Path(job['attempt_path'])/'cancel.request').touch(exist_ok=True)
                    output={'id':args.id,'status':'cancellation_requested','confirmed':False}
                elif args.command=='result':
                    if job['status'] in ACTIVE: raise JobError('result pending; job is active')
                    output=job
                    rp=Path(job['attempt_path'])/'result.json'
                    if rp.exists(): output={**job,'result':read(rp)}
                else: output=job
        print(json.dumps(output,indent=2))
        if args.command in {'doctor','setup'} and not output['ready_for_probe']: sys.exit(2)
    except PolicyError as e:
        print(json.dumps({'error':str(e),'policy':e.detail,'status':'peak_blocked' if e.detail else 'route_refused'}),file=sys.stderr);sys.exit(3)
    except (JobError,OSError,ValueError,subprocess.SubprocessError) as e:
        print(json.dumps({'error':redact(str(e))}),file=sys.stderr);sys.exit(2)

if __name__=='__main__': main()
