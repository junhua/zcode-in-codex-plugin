# ZCode Coordinator 0.2.0

A local Codex skill and Python supervisor that delegates bounded file-editing tasks to ZCode. No MCP server, cloud hosting, credential installation, or global configuration changes are needed to build it. Codex reviews edits, executes tests and decides subsequent delivery.

## Install when authorized

Install the published marketplace with the supported Codex CLI commands:

```sh
codex plugin marketplace add junhua/zcode-in-codex-plugin
codex plugin add zcode-coordinator@zcode-local
```

For offline delivery, the companion `local-marketplace` directory is also a complete marketplace: use its absolute path instead of the GitHub source above. Keep that directory in a stable location.

Installation changes the user's local Codex plugin configuration; it was not run against the user's global configuration during development. Reload plugins or begin a new Codex task if required by the host. The standalone ZIP contains one plugin, with both portable `plugin.json` and Codex `.codex-plugin/plugin.json` metadata. A skill-only install can copy `skills/zcode` into an authorized Codex skills directory; do not copy only SKILL.md because the script is required.

## Use

In Codex: “Use $zcode to implement the bounded task in /path/to/repo; verify and return the report before integrating.” Codex resolves the script from the installed skill and invokes:

```sh
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/zcode-jobs doctor
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/zcode-jobs delegate --repo '/path/with spaces/repo' --base main --task-id DEMO-1 --prompt-file /absolute/task.txt --timeout 600
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/zcode-jobs status JOB_ID
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/zcode-jobs result JOB_ID
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/zcode-jobs resume JOB_ID --prompt-file /absolute/followup.txt
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/zcode-jobs cancel JOB_ID
```

The state directory is created private (0700); existing public/shared directories are refused. Each job has a random durable ID, detached Git worktree, isolated runtime/HOME, atomic registry, and attempt directories with prompt, redacted stdout/stderr, final result, patch and consolidated JSON report. `record-test` adds a coordinator-attested argv, exit code and copied/redacted evidence with a SHA-256. It never executes agent-supplied commands. Source checkout contents are not changed. Git worktree metadata is created in the source repository; worktrees are retained for review and can later be removed using normal Git worktree management after all processes stop.

## Verified interface and setup

Development used Codex CLI 0.156.1, ZCode's desktop-bundled CLI 0.17.0 and Node 26.5.0 on macOS arm64. The bundled CLI is found at `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs` if `zcode` is absent from PATH. An explicit verified argv is accepted via `--cli-json '["/absolute/node","/absolute/zcode.cjs"]'`. No shell splitting is used. A fixture argv is a test dependency, not a production ZCode identity.

The wrapper probes actual `--version` and parser acceptance of `--help --output-format stream-json --workflow-mode disabled`, checks help for prompt/cwd/mode/resume/disallowed-tools, and records the executable/bundle hash. Parser acceptance is not proof of live event behavior. The pinned upstream source documents NDJSON ending in a `type: result` record, explicit `--resume sess_...`, and signals for headless cancellation. No `--model`, `--max-turns`, `--print` or other guessed flags are used. Unknown events are retained in bounded logs; malformed/missing results fail clearly.

The installed desktop bundle needs its existing resource at `Contents/Resources/config/provider/zcode-builtin.json`, which differs from the standalone source layout. The wrapper supplies the verified `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` and `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` environment paths for that bundle without modifying those files.

## Live test status and model setup

Fixture tests and isolated plugin installation are validated. Real inference, code editing and session resume have not passed: the installed standalone CLI rejected initialization before producing a session/model response. This is explicitly not a successful end-to-end test.

The CLI has no supported `--model` or `--settings` flag. Version 0.2.0 adds wrapper options for a **per-job selection-only profile**:

```sh
python3 /path/to/skills/zcode/scripts/zcode_job.py --state /absolute/private/jobs delegate \
  --repo /absolute/synthetic-repo --task-id SMOKE-1 --prompt-file /absolute/task.txt \
  --provider-id EXISTING_BUILTIN_PROVIDER_ID --model-id EXISTING_ENABLED_MODEL_ID \
  --reasoning-level ADVERTISED_LEVEL
```

These are wrapper options, not ZCode CLI flags. The wrapper checks the installed desktop catalog, creates a job-local provider configuration containing only model selection, and points the documented `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` environment variable there. It copies no user configuration, tokens, keys or endpoints. Existing credentials remain read-only, the global default stays unchanged, and resume uses the same selection. Account entitlement is still enforced by ZCode; catalog presence alone does not establish account readiness. Other CLI layouts currently reject this option rather than guessing resource paths.

During the real synthetic test, a catalog-enabled `GLM-5.3` selection with advertised reasoning level `low` for the existing Z.AI coding-plan provider still produced `Select a model before sending a message`. Source inspection established why this can happen: the standalone account runtime requires provider account-link identity metadata before it exposes account models. That metadata was absent, even though the desktop had account credentials. No metadata or credentials were copied, repaired or created. The isolated Codex CLI configuration had no login, while the normal Codex CLI was already logged in. No credentials were copied to make a nested isolated CLI run. A later test can reuse normal auth with `codex exec --ephemeral --ignore-user-config` and an explicit local skill-path instruction; this does not install the plugin persistently. The active Codex coordinator exercised the real wrapper initialization path; full nested CLI execution remains unverified.

The required user-controlled setup is to connect the existing account through the installed ZCode standalone CLI's supported login flow, then use `/model` in its TUI to confirm an available model. For the verified desktop bundle, make its existing resources visible first:

```sh
export ZCODE_BUILTIN_PROVIDER_CONFIG_FILE='/Applications/ZCode.app/Contents/Resources/config/provider/zcode-builtin.json'
export ZCODE_PERSONAL_PROVIDER_CONFIG_FILE="$HOME/.zcode/v2/provider_config.json"
node '/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs' login zai
node '/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs'
```

The login command is shown for Z.AI; use the existing configured family, not a new billing account. It writes account-link/authentication state and therefore was **not run** during validation. In the TUI, `/model` lists/selects a model and persists a normal default; select it only when you want that persistent change. A job-local model selection can avoid changing that default once standalone account access is ready. Afterwards repeat a disposable real task; do not treat mocks or plugin discovery as proof of authentication.

## Scope and limits

- This release requires macOS `sandbox-exec` and `ps` process inspection; other operating systems fail execution clearly. A host denying either capability must authorize normal local process access; the wrapper never requests elevated permissions itself.
- ZCode receives an explicit `edit` or `plan` mode. Headless command approvals cannot be answered, so Bash is removed. File editing is supported; running tests is Codex's job. No approval broker or yolo fallback exists.
- User extensions are disabled in isolated HOME. Project/ancestor `zcode.json`, `.zcode/config.json`, or `.env` files are refused because they can override runtime restrictions. This intentional limit may exclude existing repositories until those settings receive a deliberate integration design.
- The macOS sandbox allows writes only in that job's runtime and worktree, plus `/dev/null`. Registry/reports, selection-only provider profiles, isolated HOME control settings and credentials are unwritable by the child. It does not isolate read access or provider networking. Only delegate repositories authorized for that provider. Prompt text is stored privately, not automatically scrubbed: never include secrets. Output redaction is conservative/best effort; credential-like assignment strings are dropped as a unit, and known token patterns are removed. Do not publish logs without review.
- Captured stdout and stderr are each capped at 1 MiB; individual unterminated lines at 256 KiB. A 16 MiB runtime-storage watchdog checks every 0.5 seconds and stops the job on excess; transient overshoot and CLI-native artifacts are possible. This is not a filesystem quota. Patches are capped at 1 MiB, with truncation marked. Untracked file contents remain in the reviewable worktree.
- Timeout defaults to 600 seconds (maximum 86400). The supervisor owns a fresh process group and validates UID/start time/PGID before SIGTERM and SIGKILL. Cancellation is confirmed only in final status. If descendants outlive the leader, inspection fails or ownership changes, the job becomes `cleanup_required`/`interrupted` and resume is refused; detached processes outside the owned group are not guaranteed to be detected or cancelled. Bash/subagents are disabled and prompts forbid background work, reducing this surface.
- Registry operations use file locks; each job has a supervisor lock and independent worktree/runtime. Worker loss is reported as interrupted rather than running forever. No automatic rollback, commits, merges, push or worktree deletion occurs.
- A valid final result and zero exit code mean CLI completion only. Tool errors, permission denial, turn failure or non-idle final projection require review. Model is recorded only if observed; a job-local selection is recorded as configured, with inference still unverified until a real response arrives. Test attestations identify Codex as their source; ZCode's narrative is not proof of tests.

See PROVENANCE.md and the accompanying validation evidence for exact inspected sources and test results.
