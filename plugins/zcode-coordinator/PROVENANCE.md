# Source provenance

Inspected 2026-10-28 on the user's connected macOS arm64 host. Both upstream repositories were cloned into this isolated task workspace and pinned before implementation.

| Source | Pinned commit / artifact | Inspection |
| --- | --- | --- |
| [ZCode](https://github.com/zai-org/ZCode/tree/3c5b227649371507ddc4eb46ac5133afe6db1cab) | `3c5b227649371507ddc4eb46ac5133afe6db1cab` | README; `apps/zcode-cli/docs/usage/{02-cli-reference,03-config,05-permissions,06-sessions,13-automation}.md`; CLI parser, prompt-command, model handler, model persistence, config precedence, session-mapper and provider-runtime-env source |
| [Reference plugin](https://github.com/openai/codex-plugin-cc/tree/db52e28f4d9ded852ab3942cea316258ae4ef346) | `db52e28f4d9ded852ab3942cea316258ae4ef346` | README, delegation commands, process/job registry handling and license/NOTICE; workflow inspiration only; no implementation source copied |
| Installed ZCode desktop CLI | version `0.17.0`; bundle SHA-256 `97490d0f06a7a225d54d47817acf4b4859cdb268b59f2490caaeda982bef063a` | Actual `--version`, `--help`, `doctor --json`, parser acceptance and two bounded real initialization attempts |
| Installed Codex CLI | `0.156.1` | Actual help for CLI, plugin add and marketplace add; isolated CODEX_HOME install validation |
| Installed ForthAI Harness | `2.14.0` cached Codex manifest and marketplace | Read-only schema/convention comparison; no files copied or changed |
| Local authoring guides | Codex local plugin-authoring guide and manifest reference; current skill-creator; portable/local package requirements | Codex compatibility manifest plus portable root schema, skill layout and validation rules |

A repository commit does not establish the build commit of an installed desktop bundle. This package records both independently and does not claim they are identical. Installed CLI lacks `--output-format` in its printed help although its parser accepts it, illustrating why runtime probes and source inspection are both required.

The ZCode CLI exposes no direct `--model` or `--settings` flag. Its documented `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` environment variable supports a separate provider configuration, so wrapper version 0.2.0 provides a validated per-job selection-only profile for installed built-in account providers. It never copies credentials or user provider rules/endpoints. Reasoning choices are checked against advertised model rules; profile/control files sit outside the delegated child's writable runtime. Original global defaults are unchanged.

Real validation initially found the desktop provider-resource layout mismatch; using the existing resource path fixed that. A subsequent disposable `GLM-5.3` / reasoning `low` selection still stopped before inference with `Select a model before sending a message`. Inspection of the pinned and installed standalone runtime showed it requires account-provider identity/auth-source metadata in addition to desktop OAuth credentials. That link metadata was absent. No account-link metadata was created and no secrets were copied. Account connection through the supported `login zai` flow and model confirmation in the CLI TUI remain user-controlled prerequisites. No successful real edit/session/resume/cancel is claimed.

The normal Codex CLI reported logged in using ChatGPT. The isolated test CODEX_HOME did not have login state; that does not imply the normal CLI is unavailable. A later supported route can reuse normal authentication with `codex exec --ephemeral --ignore-user-config` and an instruction to load the local skill file, without persistent plugin registration or copying credentials. It has not been exercised here because the downstream ZCode account prerequisite remains blocked.

The original package is Apache-2.0 licensed. The Apache-2.0 license text is reproduced from the reference repository; no other reference implementation code or upstream runtime is redistributed. The separate installed ZCode runtime retains its upstream notices and license.

## Version 0.3.0 policy and verified protocol surface

The user-required daily policy is fixed UTC+08 [14:00,18:00), including weekends, with a local 60-second shutdown buffer. It is not inferred from a vendor subscription policy. Task routing policy 2026-10-28.1 is our cost-conscious heuristic; current official model/configuration references and the transport-specific evidence are linked in ROUTING.md.

The same pinned ZCode source was inspected for app-server --stdio framing, session/create/resume/send/stop/subscribe schemas, snapshot settings and workspace scope, canonical per-input modelSelection, runtime-preferences callbacks, and input/turn correlation. Version 0.3.0 uses one bounded protocol process so effective model/effort/mode is checked before task text is sent; it no longer treats a standalone headless profile as effective-route proof. It answers only the documented nonsecret runtime-preferences callback with restrictive capabilities. Unknown host methods, missing registry models or mismatched session/workspace values are refused.

A real non-inference preflight reached session/create but the current account/host registry did not expose the requested Flash model. No session/send occurred. This does not prove real model execution, effort semantics or a perfect remote cancellation cutoff. Account/global settings were not changed. Historical GLM-5.2 reasoning-depth guidance was not used; current provider configuration/mapping source governs this release.
