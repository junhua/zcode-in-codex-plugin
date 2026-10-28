# ZCode Coordinator 0.3.0

A local Codex skill, Python supervisor and bounded ZCode protocol adapter. Codex delegates a small coding task, reviews its worktree, executes verification and records evidence. No cloud host, MCP server, scheduled automation or always-on service is created.

## Install when authorized

```sh
codex plugin marketplace add junhua/zcode-in-codex-plugin
codex plugin add zcode-coordinator@zcode-local
```

For offline delivery, use the companion local marketplace's absolute path instead of the GitHub source. Installation changes user-local Codex plugin configuration; development only installed into isolated test configurations. Global installation remains a separate user decision.

Requires macOS `sandbox-exec` and `ps`, Python 3.9+, Node for the verified desktop bundle, Codex's plugin host and a supported installed ZCode runtime/account configuration. The ZIP contains portable and Codex compatibility manifests. Keep all three runtime scripts with the skill.

## Daily no-use policy

Inference-bearing `delegate` and `resume` are excluded **every day, including weekends, from 14:00 inclusive to 18:00 exclusive at fixed UTC+08:00 (GMT+8)**. Machine timezone and daylight-saving changes do not affect this rule. This is the user's policy, independent of vendor peak/off-peak plans.

A conservative 60-second shutdown buffer stops admission at 13:59. A requested timeout that would reach that deadline is rejected before CLI/session work; shorten the bounded task or return after 18:00. Responses include the reason and next allowed time. There is no waiting queue, busy polling until evening, automatic 18:00 resume, provider fallback or scheduled service.

Controller, worker and adapter recheck admission, including after asynchronous preparation and immediately before task submission. Active workers use both wall time and an initial monotonic cutoff. At the buffer boundary they request cooperative `session/stop`, then enforce bounded owned-group cleanup. Status becomes `peak_interrupted` (or `cleanup_required` if cleanup cannot be proven). Partial files, prompt, logs, report, patch and available session identity are retained as a local checkpoint; no code is discarded or rolled back. Resume requires an explicit later command and repeats all guards.

**Precise limit:** the provider may continue an already in-flight request after local cancellation. OS suspension, extreme scheduling delays, clock changes between checks and a write, or descendants outside/left in the owned group prevent a perfect remote billing/processing cutoff guarantee. The buffer reduces exposure; it does not turn local process cancellation into a server-side guarantee. `cleanup_required` demands prompt manual inspection and blocks resume. The adapter disables background work and allows only file tools to reduce this surface.

`doctor`, `status`, `result`, `cancel`, local `route` planning and inspection remain available during the excluded window. Doctor uses non-inference help/version checks; it does not test account access by issuing a model request.

## Choose a task route

See [ROUTING.md](ROUTING.md) for the sourced model facts, full heuristic and limitations. The coordinator classifies task kind, complexity and risk. Default effort is never inherited from the vendor or the user's current model.

```sh
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs route --task-kind mechanical --complexity simple --risk normal
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs doctor
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs delegate --repo /absolute/authorized-repo --task-id STORY-1 --prompt-file /absolute/task.txt --task-kind routine --complexity bounded --risk normal --provider-id account:zai-individual-coding-plan --timeout 600
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs status JOB_ID
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs result JOB_ID
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs resume JOB_ID --prompt-file /absolute/followup.txt --task-kind routine --complexity bounded --risk normal
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs cancel JOB_ID
```

`--task-kind` is required; supported kinds are mechanical, routine, capability, debugging, architecture and ui-state. `visual` is explicitly refused. Complexity is simple/bounded/hard; risk is normal/ambiguous/security/data-loss/cross-service. The provider must be explicit and already authorized. Optional `--model-id` / `--reasoning-level` act as matching assertions against the policy; mismatches fail rather than override it. A follow-up requiring a different route becomes a newly bounded task after reviewing existing work, not a silently switched session. Legacy jobs without routing evidence cannot be resumed.

The adapter uses the inspected `app-server --stdio` interface. It verifies the same-process session's effective model, effort and mode before sending task text, then sends explicit model selection. Only accepted input/turn-correlated results can complete. Unknown/mismatched routes, unsupported transport mappings and unknown host callbacks fail closed. The only host preference callback returns a fixed restrictive, nonsecret configuration. It never returns credentials or grants approvals. A temporary selection profile and control settings are child-unwritable; global defaults and account linkage are unchanged.

## Current live readiness and setup

**Real inference is not validated.** On the inspected ZCode 0.17.0 installation, the latest non-inference preflight reached `session/create` and was refused because the requested `account:zai-individual-coding-plan/GLM-5.3-Flash` model was absent from that process's registry. No `session/send`, effective route, model response or edits followed. Earlier standalone headless tests also lacked required account-link identity/auth-source metadata, even though desktop OAuth credentials existed. No credential metadata was created or copied.

The supported user-side account setup uses the existing account through ZCode's CLI/TUI, with the installed bundle's resource paths:

```sh
export ZCODE_BUILTIN_PROVIDER_CONFIG_FILE='/Applications/ZCode.app/Contents/Resources/config/provider/zcode-builtin.json'
export ZCODE_PERSONAL_PROVIDER_CONFIG_FILE="$HOME/.zcode/v2/provider_config.json"
node '/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs' login zai
node '/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs'
```

Use the already configured family rather than a new billing account. Login writes account-link/authentication state and was not run during validation. `/model` and `/effort` in the TUI persist normal defaults; use them only when you intend that change. A job-local selection avoids global model-default edits once a supported registry is available. **CLI account setup alone is not proof that the separate app-server host/account registry is ready**: the app-server source expects host-managed account configuration. A supported host/account integration must expose the exact route in its snapshot. Until that is available and tested, this wrapper refuses before inference; it does not copy credentials or fake a successful route.

Normal Codex CLI authentication was available. Isolated test Codex configurations lacked login, which does not imply normal Codex is unavailable. A later test can reuse normal auth with `codex exec --ephemeral --ignore-user-config` and an explicit local skill-path instruction, after the downstream route prerequisite is resolved. That full live flow is not claimed as passed.

## Registry, review and safety

The private 0700 state directory holds durable random IDs, detached worktrees, immutable control files, isolated writable runtime and attempt artifacts. Locks prevent duplicate supervisors. Source checkouts are not edited, though Git creates worktree metadata in their repositories. The `.git` pointer is protected by the child sandbox and fingerprinted before trusted Git inspection/resume; hooks and external diff/textconv helpers are disabled. Worktrees remain for review.

Bash, workflows, subagents and external tools are removed; `Read/Write/Edit/Glob/Grep` are the protocol allowlist. Modes are explicit `edit`/`plan`; no yolo fallback or approval broker exists. Codex runs approved tests and records `record-test JOB_ID --argv-json '["python3","-m","unittest"]' --exit-code 0 --evidence-file /absolute/test-output.txt`. This records an attestation, not an executed command. Agent claims remain unverified. Reports include requested/effective route, rationale/version/evidence, task/prompt hash, base/final SHA, session/input/turn/trace IDs, changed files, tests, blockers and exit status. Untracked files require direct inspection; Git diff does not include their contents.

The write sandbox permits only job runtime/worktree writes, excluding `.git`; it does not isolate global reads or provider networking. Delegate only authorized repositories. Project/ancestor `zcode.json`, `.zcode/config.json` and `.env` are refused. Never put secrets in prompts. Output redaction is conservative/best effort; credential-like assignment strings can be dropped as a unit. Captured stdout/stderr are each capped at 1 MiB, lines at 256 KiB; a 16 MiB runtime watchdog can overshoot transiently. Patches are capped at 1 MiB with truncation marked.

Cancellation is a request until final status confirms it; partial work remains. Ownership mismatches, surviving groups or unavailable inspection require manual cleanup, never blind PID signalling. No commits, merges, pushes, deployments, permission changes, credential creation or rollback occur automatically.
