# Validation — 0.2.0

**Fixture-tested; real inference remains blocked by standalone account setup.**

- All **29 synthetic fixture tests passed**. They cover success/result traceability, failure/auth-like failure, timeout, owned-group cancellation, resume, concurrency, malformed/truncated/oversize streams, quoted-secret redaction, runtime watchdog, process ownership, orphan detection, write-sandbox boundaries, rejected runtime configuration, coordinator test attestations and per-job selection validation.
- An independent reviewer reran all 29 tests and separately checked the actual macOS sandbox: runtime/worktree writes are permitted; job/control files, the selection-only profile, isolated HOME configuration and outside files are protected.
- Portable manifest was validated against its declared agent-plugins.org 1.0.0 JSON schema; the skill passed skill-creator validation. The repository includes offline structural checks for manifests, marketplace, skill, license and absence of personal machine paths.
- Codex's supported marketplace/plugin commands installed and discovered the package in an isolated test configuration. No global plugin install or configuration changes were performed. Package installation is independent of model authentication.

## Real CLI attempts

Installed versions inspected: **Codex CLI 0.156.1**, **ZCode CLI 0.17.0**, Node.js 26.5.0, macOS arm64.

A real disposable task used the installed desktop CLI and a selection-only profile for catalog-enabled **GLM-5.3**, reasoning **low**, on the already configured Z.AI coding-plan provider. It exited **1 before inference** with `Select a model before sending a message`. No ZCode session ID, model response or code edits were produced. Base and final synthetic repository SHA were equal. Real delegation, resume and cancellation are therefore **not passed**; repeated guaranteed-failing retries were stopped.

This is more than an ordinary model-picker issue: the standalone account runtime requires provider identity/auth-source link metadata. Those records were absent even though desktop OAuth credentials existed. No credentials, metadata, keys, account access or endpoints were copied, created or changed. The supported user-side prerequisite is the standalone CLI's existing-account connection flow, followed by model confirmation. See the usage guide's exact commands.

The normal Codex CLI reported already logged in using ChatGPT. The isolated test Codex configuration was not logged in; no secret copying was used to make it so. A later test can reuse normal auth via `codex exec --ephemeral --ignore-user-config` with an explicit local skill-path instruction. That route is recorded for later testing, not claimed as executed end to end.

## Reproduce fixture validation

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v -s plugins/zcode-coordinator/tests -p 'test_*.py'
python3 scripts/validate_package.py
```

The test CLI is fake and uses synthetic Git repositories; these tests make no model requests and do not prove real provider authentication or model quality. Private runtime logs, session databases, machine-specific installation receipts and user account data are excluded from the public package.
