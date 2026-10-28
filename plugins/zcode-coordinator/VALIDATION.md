# Validation — 0.3.0

**Deterministic fixtures validate policy and supervisor behavior. Real model execution is not passed.**

## Automated and independent checks

All **46 regression tests passed** on the release candidate. The fixture suite covers daily 13:59:59/14:00/17:59:59/18:00 boundaries, weekends, UTC+08 conversion across DST offsets, timeout/cutoff equality, current-day clock rewinds, resume exclusion and asynchronous create/subscribe races. It covers all six model/effort choices, visual-input refusal, unsupported/mismatched effective route/effort/mode/session/workspace, strict request/ACK/input/turn correlation, stale/early terminal messages and restricted host preferences.

Existing success/failure/auth-like failure, bounded logs/redaction, malformed/truncated protocol, timeout/cancel/group ownership, orphan detection, runtime watchdog, concurrency, paths with spaces, scope controls, Git-pointer tampering, environment filtering and coordinator test attestations remain covered. Tests copy the runtime into disposable fixture directories and inject a clock/catalog there; no production time-policy bypass exists. They use a fake stdio server, not a model.

Independent review checks runtime modules and staged public content, including actual macOS sandbox boundaries. The public review report records exact fingerprints and independent results. Portable and Codex manifests, marketplace, skill, licenses and archive layout are validated; installation is tested only in isolated Codex configurations, never globally.

## Real installed-interface check

Inspected Codex CLI 0.156.1 and ZCode CLI 0.17.0 on macOS arm64, with the pinned source and bundle fingerprint in PROVENANCE.md. The installed catalog enables both requested models and advertises low/high/max. Its inspected Z.AI account Anthropic transport maps explicit effort to output_config.effort with thinking enabled. Other transport mappings/relevant overrides are rejected unless proven; expressions are not evaluated as arbitrary code.

A bounded real preflight outside the excluded window requested Flash/low in a disposable synthetic repository. It exercised app-server session/create and the source-documented nonsecret runtime-preferences callback with all optional capabilities disabled. The server refused because account:zai-individual-coding-plan/GLM-5.3-Flash was absent from that process's provider registry. **No session/send or model request followed, no effective route was claimed, and no edits occurred.**

The earlier standalone account-link metadata blocker remains. The separate app-server source expects host-managed account configuration, so CLI login/model selection alone is not proof this adapter can verify a route. Unsupported account/host integration fails before inference. No credential copying, account-link changes, global defaults, provider endpoints or permissions were changed. Real inference, resumed inference, provider effort behavior and real boundary cancellation remain unverified. Cancellation of an in-flight remote request cannot guarantee immediate server-side processing/billing cessation.

Normal Codex authentication was available; isolated test configurations lacking login do not imply normal Codex is unavailable. A future real test may reuse normal authentication with --ephemeral --ignore-user-config and an explicit local skill-path instruction once the downstream exact-route prerequisite is resolved.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -v -s plugins/zcode-coordinator/tests -p 'test_*.py'
python3 scripts/validate_package.py
```

Private runtime logs, session databases, account metadata, machine-specific receipts and unrelated source are excluded from the public repository/package. See the usage guide for supported setup steps and precise no-use/cancellation limitations.
