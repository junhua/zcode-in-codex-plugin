# ZCode in Codex

A local Codex plugin for delegating bounded coding tasks to ZCode CLI while Codex keeps responsibility for review, verification and delivery. The package includes a skill, Python supervisor, durable job registry, isolated Git worktrees, bounded output and macOS write-sandbox controls. It provides setup/doctor, local task routing, delegate, status, result, resume and cancel commands. It excludes inference starts daily from 14:00–18:00 GMT+8 and applies explicit GLM-5.3/Flash effort routing.

**Version 0.3.0 is fixture-tested; real model execution remains blocked by standalone ZCode account setup.** The runtime must expose the exact requested route in a same-process session snapshot before any task text is submitted. The inspected account/host registry did not expose the requested model; no fallback or credential copying was used. No successful real editing, resume or cancellation is claimed. See the [live test status and exact setup steps](plugins/zcode-coordinator/README.md#current-live-readiness-and-setup).

## Install

Requirements: macOS with `sandbox-exec` and `ps`, Python 3.9+, a supported Codex CLI plugin host and an installed/authenticated ZCode CLI. The tested desktop bundle requires Node.js. Development inspected Codex CLI 0.156.1 and ZCode CLI 0.17.0; capability checks inspect the installed interface before execution.

```sh
codex plugin marketplace add junhua/zcode-in-codex-plugin
codex plugin add zcode-coordinator@zcode-local
```

Reload plugins or start a new Codex task if the host requires it. These commands install a user-local plugin; publishing this repository did not globally install anything on the developer's machine.

Ask Codex:

> Use $zcode to implement this bounded task in my authorized repository. Review its diff, run verification yourself and return the job report before integrating.

The [routing matrix and current official research](plugins/zcode-coordinator/ROUTING.md) is a cost-conscious heuristic, not a proven optimum. The daily UTC+08 policy includes weekends and is independent of machine timezone/vendor off-peak plans. Active work is cooperatively stopped with a conservative buffer and partial artifacts retained. See the cancellation limits in the usage guide.

The [usage guide](plugins/zcode-coordinator/README.md) describes exact wrapper commands, job-local model selection, supported setup and known limits. State and artifacts remain local. No cloud server or MCP server is required.

## Validate

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v -s plugins/zcode-coordinator/tests -p 'test_*.py'
python3 scripts/validate_package.py
```

The tests use a fake CLI and disposable synthetic Git repositories; they make no model/provider requests. Actual live-test gaps are recorded separately in [validation](plugins/zcode-coordinator/VALIDATION.md). [Pinned provenance](plugins/zcode-coordinator/PROVENANCE.md) identifies inspected source commits and the installed bundle fingerprint. See [independent review](plugins/zcode-coordinator/validation/independent-review.md).

## Boundaries

ZCode receives an explicit `edit` or `plan` permission mode, never an implicit yolo default. Bash, workflows and external tools are removed; Codex runs tests and records command/result evidence. The child can write only its worktree and runtime, while job/control files and credentials remain unwritable. Global read access and provider networking are not isolated. Use only repositories authorized for the configured provider.

Delegation grants no authority to push, merge, deploy, create credentials, change permissions or contact third parties. Reports consolidate work and preserve partial changes; nothing is automatically merged, committed or rolled back.

Apache-2.0 licensed. Inspired by the reverse workflow of OpenAI's Codex plugin for Claude Code; no upstream runtime or reference implementation source is redistributed.
