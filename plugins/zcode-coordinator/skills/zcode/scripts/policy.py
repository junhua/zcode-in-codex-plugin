"""Deterministic local admission and task routing. No CLI/network access."""
import datetime as dt

POLICY_VERSION='2026-10-28.1'
ZONE=dt.timezone(dt.timedelta(hours=8),'UTC+08:00')
STOP_BUFFER_SECONDS=60
KINDS=('mechanical','routine','capability','debugging','architecture','ui-state','visual')
COMPLEXITIES=('simple','bounded','hard')
RISKS=('normal','ambiguous','security','data-loss','cross-service')

class PolicyError(ValueError):
    def __init__(self,message,detail=None):
        super().__init__(message);self.detail=detail or {}

def utc_now():
    return dt.datetime.now(dt.timezone.utc)

def window(instant=None):
    instant=instant or utc_now()
    if instant.tzinfo is None:raise PolicyError('an aware clock is required')
    local=instant.astimezone(ZONE)
    start=local.replace(hour=14,minute=0,second=0,microsecond=0)
    end=start.replace(hour=18)
    excluded=start<=local<end
    next_start=start if local<end else start+dt.timedelta(days=1)
    if local>=end:next_end=end+dt.timedelta(days=1)
    else:next_end=end
    cutoff=next_start-dt.timedelta(seconds=STOP_BUFFER_SECONDS)
    return {'policy_version':POLICY_VERSION,'timezone':'UTC+08:00','local_time':local.isoformat(),
            'excluded':excluded,'next_allowed':next_end.isoformat() if excluded or local>=cutoff else local.isoformat(),
            'peak_start':next_start.isoformat(),'stop_deadline':cutoff.isoformat(),
            'buffer_seconds':STOP_BUFFER_SECONDS}

def admit(seconds,instant=None):
    instant=instant or utc_now();state=window(instant)
    cutoff=dt.datetime.fromisoformat(state['stop_deadline'])
    if state['excluded'] or instant.astimezone(ZONE)>=cutoff:
        raise PolicyError('ZCode starts are blocked by the daily 14:00–18:00 UTC+08 policy and its 60-second shutdown buffer',dict(state,reason='peak_window' if state['excluded'] else 'shutdown_buffer'))
    if instant+dt.timedelta(seconds=seconds)>=cutoff:
        state['next_allowed']=dt.datetime.fromisoformat(state['peak_start']).replace(hour=18).isoformat()
        raise PolicyError('Requested timeout would reach the pre-peak shutdown deadline; shorten the bounded task or start after 18:00 UTC+08',dict(state,reason='would_cross_peak'))
    return state

def boundary_due(stop_deadline,instant=None):
    instant=instant or utc_now()
    state=window(instant)
    return state['excluded'] or instant>=dt.datetime.fromisoformat(stop_deadline) or instant>=dt.datetime.fromisoformat(state['stop_deadline'])

def route(kind,complexity,risk):
    if kind not in KINDS or complexity not in COMPLEXITIES or risk not in RISKS:raise PolicyError('unknown task classification; classify task kind, complexity and risk explicitly')
    if kind=='visual':raise PolicyError('Visual inputs are unsupported by this text-only wrapper; a text prompt does not pass images/video/files')
    if risk in {'security','data-loss'}:
        model,effort='GLM-5.3',('max' if complexity=='hard' else 'high')
        why='High cost of error requires flagship reasoning plus independent review; model choice does not establish safety.'
    elif complexity=='hard' and kind!='ui-state':
        model,effort='GLM-5.3','max';why='Difficult invariants or long-horizon failure analysis justify highest effort; verify the added cost against outcomes.'
    elif risk in {'ambiguous','cross-service'} or kind in {'debugging','architecture'}:
        model,effort='GLM-5.3','high';why='Ambiguity, cross-file or integration reasoning warrants flagship high; escalate on diagnostic evidence.'
    elif kind=='capability':
        model,effort='GLM-5.3',('low' if complexity=='simple' else 'high');why='Task is clear but requires flagship capability; keep effort below max when adequate.'
    elif kind=='ui-state' and complexity=='hard':
        model,effort='GLM-5.3-Flash','max';why='Difficult fully specified textual UI-state reasoning can justify Flash max; this is not a required escalation step.'
    elif kind=='mechanical' and complexity=='simple':
        model,effort='GLM-5.3-Flash','low';why='Mechanical, narrow and explicit work favors the least costly adequate route.'
    else:
        model,effort='GLM-5.3-Flash','high';why='Bounded routine coding/test writing uses a cost-conscious high default; this is our heuristic, not a proven optimum.'
    return {'policy_version':POLICY_VERSION,'task_kind':kind,'complexity':complexity,'risk':risk,
            'model_id':model,'official_model_id':model.lower(),'effort':effort,'rationale':why,
            'independent_review_required':risk in {'security','data-loss'},'basis':'heuristic; minimize total verified outcome cost, not token price alone'}

def verify_snapshot(snapshot,requested,expected_mode):
    try:
        current=snapshot['settings']['model']['current']
        effort=current.get('options',{}).get('reasoningLevel')
        thought=snapshot['settings']['thoughtLevel'].get('current')
        if effort is None:effort=thought
        if thought is not None and thought!=effort:raise KeyError('conflicting effort')
        expected=requested['options']['reasoningLevel']
        if current['providerId']!=requested['providerId'] or current['modelId']!=requested['modelId'] or effort!=expected:raise KeyError('route mismatch')
        if expected_mode not in {'edit','plan'} or snapshot['settings']['mode']['current']!=expected_mode:raise KeyError('unsafe mode')
        return {'provider_id':current['providerId'],'model_id':current['modelId'],'effort':effort,'mode':expected_mode,'evidence':'same-process session snapshot before session/send'}
    except (KeyError,TypeError,AttributeError) as e:
        raise PolicyError('Effective model/effort is unavailable or differs from requested route; no inference was submitted') from e
