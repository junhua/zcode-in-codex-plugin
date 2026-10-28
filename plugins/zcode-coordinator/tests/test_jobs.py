import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import datetime as dt
from unittest.mock import patch
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
WRAPPER=ROOT/'skills/zcode/scripts/zcode_job.py'
if not WRAPPER.exists():WRAPPER=ROOT/'plugins/zcode-coordinator/skills/zcode/scripts/zcode_job.py'
FAKE=ROOT/'tests/fake_zcode.py'
spec=importlib.util.spec_from_file_location('jobs',WRAPPER);jobs=importlib.util.module_from_spec(spec);spec.loader.exec_module(jobs)

class JobsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='zcode jobs ')
        self.root=Path(self.temp.name).resolve();self.state=self.root/'state';self.repo=self.root/'repo with spaces'
        self.repo.mkdir();self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@invalid')
        (self.repo/'seed.txt').write_text('synthetic only\n');self.git('add','.');self.git('commit','-qm','seed')
        self.prompt=self.root/'bounded prompt.txt';self.prompt.write_text('Make one synthetic edit. CASE_OK')
        self.started=[]
        self.scripts=self.root/'test-runtime';shutil.copytree(WRAPPER.parent,self.scripts,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        self.clock=self.scripts/'clock.txt';self.clock.write_text('2026-01-01T00:00:00+00:00')
        policy=self.scripts/'policy.py';body=policy.read_text();body=body.replace('return dt.datetime.now(dt.timezone.utc)',"return dt.datetime.fromisoformat(__import__('pathlib').Path(__file__).with_name('clock.txt').read_text())");policy.write_text(body)
        bundle=self.root/'fake-app/Contents/Resources/glm/zcode.cjs';bundle.parent.mkdir(parents=True);bundle.write_text('synthetic bundle marker')
        catalog={'config':{'providerConfigRules':{'providerRules':[{'providerId':'account:zai-individual-coding-plan','config':{'access':{'type':'zhipu-account'},'api':{'type':'anthropic-messages'}}}]},'modelConfigRules':{'builtinProviderModelRules':[{'providerId':'account:zai-individual-coding-plan','modelId':m,'config':{'enabled':True}} for m in ['GLM-5.3','GLM-5.3-Flash']],'modelRules':[{'modelMatch':'.*','config':{'optionSpecs':{'reasoningLevel':{'values':['low','high','max']}}}}],'modelApiRules':[{'modelMatch':'.*','apiTypeMatch':'anthropic-messages','config':{'optionSpecs':{'reasoningLevel':{'map':'{"thinking":{"type":"enabled"},"output_config":{"effort":reasoningLevel}}'}}}}]}}}
        cp=bundle.parent.parent/'config/provider/zcode-builtin.json';cp.parent.mkdir(parents=True);cp.write_text(json.dumps(catalog))
        self.wrapper=self.scripts/'zcode_job.py';self.wrapper.write_text(self.wrapper.read_text().replace(jobs.BUNDLE,str(bundle)))
    def tearDown(self):
        for jid in self.started:
            try:
                j=self.call('status',jid)
                if j['status'] in jobs.ACTIVE:
                    self.call('cancel',jid);self.wait(jid)
            except Exception: pass
        self.temp.cleanup()
    def git(self,*args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).stdout
    def call(self,*args,ok=True):
        args=list(args)
        if args and args[0] in {'delegate','resume'}:
            args+=['--task-kind','routine','--complexity','bounded','--risk','normal']
            if args[0]=='delegate':args+=['--provider-id','account:zai-individual-coding-plan']
        p=subprocess.run([sys.executable,str(self.wrapper),'--state',str(self.state),*map(str,args)],capture_output=True,text=True)
        if ok and p.returncode: self.fail(p.stderr)
        return json.loads(p.stdout if p.stdout else p.stderr)
    def start(self,case='CASE_OK',timeout=10,extra_cli=(),mode='edit'):
        p=self.root/(case+str(time.time_ns())+'.txt');p.write_text('Change a synthetic file. '+case)
        j=self.call('delegate','--repo',self.repo,'--task-id','fixture-'+case,'--prompt-file',p,'--timeout',timeout,'--cli-json',json.dumps([sys.executable,str(FAKE),*extra_cli]),'--mode',mode)
        self.started.append(j['id']);return j['id']
    def wait(self,jid,seconds=15):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            j=self.call('status',jid)
            if j['status'] not in jobs.ACTIVE:return j
            time.sleep(.05)
        self.fail('job did not settle: '+jid)
    def running(self,jid):
        end=time.monotonic()+8
        while time.monotonic()<end:
            j=self.call('status',jid)
            if j.get('child_identity'):return j
            time.sleep(.05)
        self.fail('job did not start')
    def wait_path(self,path,seconds=5):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if path.exists():return
            time.sleep(.02)
        self.fail('fixture marker did not appear')
    def test_peak_blocks_before_repo_or_cli(self):
        self.clock.write_text('2026-01-01T06:00:00+00:00')
        r=self.call('delegate','--repo','/missing','--task-id','peak','--prompt-file','/missing','--timeout','1',ok=False)
        self.assertEqual(r['status'],'peak_blocked');self.assertEqual(r['policy']['reason'],'peak_window')
        self.assertFalse((self.state/'worktrees').exists())
    def test_status_doctor_result_route_allowed_in_peak(self):
        jid=self.start();self.wait(jid);self.clock.write_text('2026-01-01T06:00:00+00:00')
        self.assertEqual(self.call('status',jid)['status'],'completed')
        self.assertEqual(self.call('result',jid)['id'],jid)
        self.assertTrue(self.call('doctor','--cli-json',json.dumps([sys.executable,str(FAKE)]))['peak_policy']['excluded'])
        self.assertEqual(self.call('route','--task-kind','mechanical','--complexity','simple')['effort'],'low')
        self.assertNotIn('policy',self.call('cancel',jid,ok=False))
    def test_resume_peak_block_then_eighteen_allowed(self):
        jid=self.start();self.wait(jid);self.clock.write_text('2026-01-01T09:59:59+00:00')
        self.assertEqual(self.call('resume',jid,'--prompt-file',self.prompt,ok=False)['status'],'peak_blocked')
        self.assertEqual(self.call('status',jid)['attempt'],1)
        self.clock.write_text('2026-01-01T10:00:00+00:00')
        self.call('resume',jid,'--prompt-file',self.prompt);self.assertEqual(self.wait(jid)['attempt'],2)
    def test_active_boundary_stops_and_retains_work(self):
        self.clock.write_text('2026-01-01T05:58:00+00:00')
        jid=self.start('CASE_SLEEP',20);j=self.running(jid)
        partial=Path(j['worktree'])/'partial.txt';self.wait_path(partial)
        self.clock.write_text('2026-01-01T05:59:00+00:00')
        j=self.wait(jid);self.assertEqual(j['status'],'peak_interrupted',j)
        self.assertTrue(partial.exists());self.assertFalse(j['checkpoint']['automatic_resume'])
        self.assertTrue(j['cooperative_stop']['requested']);self.assertEqual(j['remaining_group_pids'],[])
    def test_async_admission_races_never_send(self):
        for flag,marker in [('--fixture-slow-prepare','prepare-marker'),('--fixture-slow-subscribe','subscribe-marker')]:
            self.clock.write_text('2026-01-01T05:58:00+00:00')
            jid=self.start(extra_cli=[flag]);j=self.running(jid);runtime=self.state/jid/'runtime'
            self.wait_path(runtime/marker);self.clock.write_text('2026-01-01T06:00:00+00:00')
            j=self.wait(jid);self.assertIn(j['status'],['peak_interrupted','peak_blocked'])
            self.assertFalse((runtime/'fixture-send-marker').exists())
    def test_unknown_or_mismatched_effective_route_never_sends(self):
        for flag in ['--fixture-unknown-route','--fixture-unknown-effort','--fixture-mismatch-route','--fixture-effort-mismatch','--fixture-mode-mismatch']:
            jid=self.start(extra_cli=[flag],mode='plan');j=self.wait(jid)
            self.assertEqual(j['status'],'failed',j);self.assertIsNone(j['effective_route'])
            self.assertFalse((self.state/jid/'runtime/fixture-send-marker').exists())
    def test_session_and_workspace_scope_refused_before_send(self):
        for flag in ['--fixture-workspace-mismatch','--fixture-host-id-mismatch']:
            flags=[flag]+(['--fixture-host-preferences'] if flag=='--fixture-host-id-mismatch' else [])
            jid=self.start(extra_cli=flags);j=self.wait(jid)
            self.assertEqual(j['status'],'failed');self.assertFalse((self.state/jid/'runtime/fixture-send-marker').exists())
        jid=self.start(extra_cli=['--fixture-resume-id-mismatch']);j=self.wait(jid)
        self.assertEqual(j['status'],'completed');self.call('resume',jid,'--prompt-file',self.prompt);j=self.wait(jid)
        self.assertEqual(j['status'],'failed');self.assertEqual((self.state/jid/'runtime/fixture-send-marker').read_text(),'1')
    def test_known_host_preferences_are_restricted_and_unknown_requests_refused(self):
        jid=self.start(extra_cli=['--fixture-host-preferences']);self.assertEqual(self.wait(jid)['status'],'completed')
        jid=self.start(extra_cli=['--fixture-host-unsupported']);j=self.wait(jid)
        self.assertEqual(j['status'],'failed');self.assertFalse((self.state/jid/'runtime/fixture-send-marker').exists())
    def test_terminal_requires_correlated_accepted_input(self):
        jid=self.start(extra_cli=['--fixture-terminal-before-rejected-ack']);j=self.wait(jid)
        self.assertEqual(j['status'],'failed');self.assertFalse((Path(j['attempt_path'])/'result.json').exists())
        jid=self.start(extra_cli=['--fixture-terminal-before-accepted-ack']);j=self.wait(jid)
        self.assertEqual(j['status'],'completed');self.assertTrue(j['input_id']);self.assertEqual(j['turn_id'],'turn-fixture')
        jid=self.start(extra_cli=['--fixture-stale-terminal']);j=self.wait(jid)
        self.assertEqual(j['status'],'completed');self.assertNotEqual(self.call('result',jid)['result']['response'],'stale')
    def test_malformed_protocol_field_types(self):
        j=self.wait(self.start(extra_cli=['--fixture-malformed-frame']));self.assertEqual(j['status'],'protocol_error')
    def test_success_result_traceability_spaces(self):
        jid=self.start();j=self.wait(jid);self.assertEqual(j['status'],'completed',j)
        r=self.call('result',jid);self.assertTrue(r['session_id'].startswith('sess_'));self.assertEqual(r['exit_status'],0)
        self.assertIn('?? answer.txt',r['changed_files']);self.assertEqual((self.repo/'seed.txt').read_text(),'synthetic only\n')
        self.assertFalse((self.repo/'answer.txt').exists());self.assertTrue(Path(j['report_path']).exists())
        self.assertIn('unknown.future.event',(Path(j['attempt_path'])/'stdout.log').read_text())
    def test_failure(self):
        j=self.wait(self.start('CASE_FAIL'));self.assertEqual(j['status'],'failed');self.assertEqual(j['exit_status'],2)
    def test_auth_failure_redaction(self):
        j=self.wait(self.start('CASE_AUTH'));self.assertEqual(j['status'],'failed')
        log=(Path(j['attempt_path'])/'stderr.log').read_text();self.assertIn('REDACTED',log);self.assertNotIn('fake-secret',log)
    def test_timeout(self):
        j=self.wait(self.start('CASE_SLEEP',1));self.assertEqual(j['status'],'timed_out');self.assertIsNotNone(j['exit_status'])
    def test_selection_catalog_validation(self):
        catalog={'config':{'providerConfigRules':{'providerRules':[{'providerId':'account:fixture','config':{'access':{'type':'zhipu-account'}}}]},'modelConfigRules':{'builtinProviderModelRules':[{'providerId':'account:fixture','modelId':'FixtureModel','config':{'enabled':True}}],'modelRules':[{'modelMatch':'.*','config':{'optionSpecs':{'reasoningLevel':{'values':['low','high']}}}}]}}}
        selection={'providerId':'account:fixture','modelId':'FixtureModel','options':{'reasoningLevel':'low'}}
        self.assertEqual(jobs.validate_model_selection(selection,catalog),selection)
        for bad in [dict(selection,api_key='must-not-copy'),dict(selection,providerId='new-provider'),dict(selection,modelId='unknown'),dict(selection,options={'reasoningLevel':'invented'}),dict(selection,options={'apiKey':'must-not-copy'})]:
            with self.assertRaises(jobs.JobError):jobs.validate_model_selection(bad,catalog)
    def test_selection_profile_is_secret_free_and_scoped(self):
        job={'id':'e'*32,'cli':{'argv':[sys.executable,str(FAKE)]},'model_selection':{'providerId':'account:fixture','modelId':'FixtureModel','options':{'reasoningLevel':'low'}}}
        (self.state/job['id']).mkdir(parents=True)
        env=jobs.child_environment(job,self.state)
        profile=Path(env['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE'])
        self.assertTrue(profile.is_relative_to(self.state/job['id']/'control'))
        data=json.loads(profile.read_text())
        self.assertEqual(data['config']['defaultModelSelection'],job['model_selection'])
        self.assertEqual(data['config']['providerConfigRules'],{'providerRules':[]})
        self.assertNotIn('apiKey',profile.read_text())
        self.assertNotIn('baseUrl',profile.read_text())
        self.assertTrue(Path(env['HOME']).is_relative_to(self.state/job['id']/'control'))
    def test_selection_pair_required_and_bundle_verified(self):
        import argparse
        cli={'argv':[sys.executable,str(FAKE)]}
        for args in [argparse.Namespace(provider_id='provider',model_id=None,reasoning_level=None,task_kind='routine',complexity='bounded',risk='normal'),argparse.Namespace(provider_id=None,model_id=None,reasoning_level='low',task_kind='routine',complexity='bounded',risk='normal'),argparse.Namespace(provider_id='provider',model_id='model',reasoning_level=None,task_kind='routine',complexity='bounded',risk='normal')]:
            with self.assertRaises(jobs.JobError):jobs.job_selection(args,cli)
    def test_runtime_log_watchdog(self):
        self.assertEqual(self.wait(self.start('CASE_RUNTIME_LIMIT'))['status'],'output_limit')
    def test_exec_process_identity_timeout(self):
        self.assertEqual(self.wait(self.start('CASE_EXEC',1))['status'],'timed_out')
    def test_cancel(self):
        jid=self.start('CASE_SLEEP');self.running(jid)
        r=self.call('cancel',jid);self.assertFalse(r['confirmed']);self.assertEqual(self.wait(jid)['status'],'cancelled')
    def test_cancel_tree(self):
        jid=self.start('CASE_TREE');j=self.running(jid);pid_file=Path(j['worktree'])/'descendant.pid'
        end=time.monotonic()+3
        while not pid_file.exists() and time.monotonic()<end:time.sleep(.05)
        pid=int(pid_file.read_text());self.call('cancel',jid);self.assertEqual(self.wait(jid)['status'],'cancelled')
        stat=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
        self.assertTrue(not stat or stat.startswith('Z'),stat)
    def test_resume(self):
        jid=self.start();j=self.wait(jid);self.call('resume',jid,'--prompt-file',self.prompt)
        j=self.wait(jid);self.assertEqual(j['status'],'completed');self.assertEqual(j['attempt'],2);self.assertEqual(j['spec_reference'],str(self.prompt))
        self.assertEqual((Path(j['worktree'])/'resumed.txt').read_text(),j['session_id'])
        self.assertTrue((self.state/jid/'attempt-1/report.json').exists())
    def test_resume_active_rejected(self):
        jid=self.start('CASE_SLEEP');self.running(jid)
        self.assertIn('active',self.call('resume',jid,'--prompt-file',self.prompt,ok=False)['error'])
    def test_no_session_resume_rejected(self):
        jid=self.start();self.wait(jid);p=self.state/jid/'job.json';j=json.loads(p.read_text());j['session_id']=None;p.write_text(json.dumps(j))
        self.assertIn('no valid',self.call('resume',jid,'--prompt-file',self.prompt,ok=False)['error'])
    def test_protocol_errors(self):
        for case in ['CASE_MALFORMED','CASE_TRUNCATED','CASE_OVERSIZE']:
            with self.subTest(case=case):self.assertEqual(self.wait(self.start(case))['status'],'protocol_error')
    def test_tool_permission(self):
        self.assertEqual(self.wait(self.start('CASE_PERMISSION'))['status'],'needs_review')
    def test_quoted_secret_result(self):
        jid=self.start('CASE_QUOTED_SECRET');j=self.wait(jid);self.assertEqual(j['status'],'completed')
        r=self.call('result',jid);self.assertNotIn('ABCDEF12345',json.dumps(r))
        self.assertNotIn('ABCDEF12345',(Path(j['attempt_path'])/'stdout.log').read_text())
    def test_leader_exits_first_cleanup_required(self):
        jid=self.start('CASE_ORPHAN');j=self.wait(jid)
        try:
            self.assertEqual(j['status'],'cleanup_required');self.assertTrue(j['remaining_group_pids'])
            self.assertIn('manual',self.call('resume',jid,'--prompt-file',self.prompt,ok=False)['error'])
        finally:
            for pid in j.get('remaining_group_pids') or []:
                try:os.kill(pid,9)
                except ProcessLookupError:pass
    def test_structured_error_events(self):
        for case in ['CASE_TOOL_ERROR','CASE_DENIED','CASE_TURN_ERROR']:
            self.assertEqual(self.wait(self.start(case))['status'],'needs_review')
    def test_git_pointer_tampering_blocks_resume_before_git_inspection(self):
        jid=self.start();j=self.wait(jid);pointer=Path(j['worktree'])/'.git';original=pointer.read_text()
        try:
            pointer.write_text('gitdir: /missing/gitdir\n')
            self.assertIn('Git control file changed',self.call('resume',jid,'--prompt-file',self.prompt,ok=False)['error'])
        finally:pointer.write_text(original)
    def test_write_sandbox_scope(self):
        j=self.wait(self.start('CASE_ESCAPE'));self.assertEqual(j['status'],'completed',j)
        self.assertFalse((self.repo/'escaped.txt').exists())
    def test_project_and_ancestor_config_refused(self):
        (self.repo/'zcode.json').write_text('{}');self.git('add','zcode.json');self.git('commit','-qm','config')
        p=self.call('delegate','--repo',self.repo,'--task-id','unsafe-config','--prompt-file',self.prompt,'--cli-json',json.dumps([sys.executable,str(FAKE)]),ok=False)
        self.assertIn('requires review',p['error'])
        (self.root/'.env').write_text('KEY=fixture')
        with self.assertRaises(jobs.JobError):jobs.check_project_inputs(self.root/'new')
    def test_record_test_attestation(self):
        jid=self.start();self.wait(jid);e=self.root/'tests.log';e.write_text('3 tests passed')
        j=self.call('record-test',jid,'--argv-json','["python3","-m","unittest"]','--exit-code','0','--evidence-file',e)
        self.assertEqual(j['tests'][-1]['exit_code'],0);self.assertTrue(Path(j['tests'][-1]['evidence_path']).exists())
    def test_concurrent_jobs(self):
        with concurrent.futures.ThreadPoolExecutor(3) as e:ids=list(e.map(lambda _:self.start(),range(3)))
        results=[self.wait(jid) for jid in ids];self.assertEqual(len({r['worktree'] for r in results}),3)
        self.assertTrue(all(r['status']=='completed' for r in results))
    def test_missing_cli(self):
        r=self.call('doctor','--cli-json','["/missing/zcode"]',ok=False);self.assertFalse(r['ready_for_probe'])
    def test_invalid_job_id_and_state(self):
        self.assertIn('invalid job',self.call('status','../../bad',ok=False)['error'])
        self.state.chmod(0o755);self.assertIn('0700',self.call('status','a'*32,ok=False)['error']);self.state.chmod(0o700)
    def test_interrupted_not_running_forever(self):
        jid=self.start();self.wait(jid);p=self.state/jid/'job.json';j=json.loads(p.read_text());j.update(status='running',created_epoch=0,worker_identity='wrong');p.write_text(json.dumps(j))
        self.assertEqual(self.call('status',jid)['status'],'interrupted')
        self.assertIn('manual',self.call('resume',jid,'--prompt-file',self.prompt,ok=False)['error'])
    def test_ownership_refuses_foreign_process(self):
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        try:
            with self.assertRaises(jobs.JobError):jobs.terminate_owned(child,'not its identity')
            self.assertIsNone(child.poll())
        finally:child.terminate();child.wait()
    def test_bounded_logs_and_redaction(self):
        p=self.root/'bounded.log';sink=jobs.Sink(p)
        sink.write('api_key=sk-12345678901234567890\n')
        for _ in range(40):sink.write('x'*50000)
        sink.close();self.assertLessEqual(p.stat().st_size,jobs.MAX_LOG);self.assertTrue(sink.truncated)
        self.assertNotIn('12345678901234567890',p.read_text())
    def test_scope_environment(self):
        os.environ['SYNTHETIC_SECRET']='must-not-forward'
        j={'id':'f'*32,'cli':{'argv':[sys.executable,str(FAKE)]}};(self.state/j['id']).mkdir(parents=True)
        env=jobs.child_environment(j,self.state)
        self.assertNotIn('SYNTHETIC_SECRET',env);self.assertNotEqual(env['HOME'],os.environ['HOME'])

if __name__=='__main__':unittest.main(verbosity=2)
