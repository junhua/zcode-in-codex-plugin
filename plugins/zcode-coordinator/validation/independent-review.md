# Independent review — ZCode Coordinator 0.3.0

**Conclusion: implementation and public-content review passed for the documented macOS scope. No blocking findings remain in this candidate.** This is approval of the reviewed guardrails and publication content, not a claim of successful real ZCode inference or a perfect remote processing/billing cutoff.

## Reviewed runtime fingerprints

Paths below are relative to `plugins/zcode-coordinator/skills/zcode/scripts/`:

| Module | SHA-256 |
| --- | --- |
| `zcode_job.py` | `90c6db8cd21fa1f1192fa68e1ff5a9ec2aa09d428396f7a2cebe5de65129633a` |
| `policy.py` | `0e09f2b9e6daba60a1b69f71de9e184ec10c6c8786684863779b54f999df807f` |
| `protocol_bridge.py` | `6d6be7d73f36bb8f54084dcb81651a549107aa987d2897c8d51a09705b164b06` |

## Independent validation

- A full **45-test independent fixture run passed in 44.559 seconds**. After the final small current-day cutoff correction, all **six pure-policy tests** and the **active-boundary integration test** passed again. Together these runs cover the current 46 distinct cases. The implementation agent also recorded a full final 46-test pass.
- An additional **23,040 independent minute/budget admission checks** across multiple dates passed. Fixed UTC+08 exclusion, the 60-second buffer, timeout equality and timezone/DST conversion match the intended daily rule.
- Four additional direct stdio fixtures passed: terminal-before-ACK acceptance, terminal-before-rejected-ACK refusal, stale-input terminal exclusion, and requested-plan/effective-edit refusal before task submission.
- The restricted runtime-preferences callback and refusal of an unknown credential request passed independently. Its fixed response was checked against the pinned protocol schema: empty additional directories, search/tool search off, subagents/memory/automatic question resolution off, and the documented context-budget strategy. It supplies no credentials or approval.
- Synthetic integration tests exercise the actual macOS sandbox and process controls, including protected job/control files, selection profile, isolated HOME and `.git` pointer; ownership checks; group cleanup; retained partial work; and refusal after Git-pointer tampering.

Tests use fake CLI/stdin servers and disposable synthetic repositories. They copy runtime scripts and inject only fixture clock/catalog data in those copies; no production policy-bypass option was added. The reviewer issued no real model/provider request, changed no global settings or credentials, and modified no implementation.

## Findings addressed

The daily [14:00,18:00) UTC+08 policy applies to inference-bearing starts/resumes every day. Admission is repeated in the controller, supervisor and bridge, including after asynchronous preparation and immediately before task text is sent. Active jobs use wall time and a planned monotonic deadline; the final guard also catches a current-day cutoff after a clock rewind. Interruption retains local artifacts and requires explicit later resume.

The bounded same-process app-server adapter verifies provider/model/effort and exact permission mode, expected session ID and canonical local workspace before subscribing/sending. Client-generated session identity also scopes the sole permitted host callback. Explicit per-input selection has no configured fallback. Completion requires an accepted send ACK and matching input/turn IDs, with traceability preserved; a result cannot win a race against a rejected send. Unknown/mismatched routes, host actions, scopes and malformed protocol fields fail closed. Refusal evidence distinguishes input not attempted, attempted with unknown acceptance, and accepted input.

The installed transport mapping is checked rather than assumed; relevant later overrides are rejected. Selection/control files remain child-unwritable. The `.git` indirection file is now protected by the sandbox and fingerprinted before trusted Git inspection/resume, preventing a delegated edit from redirecting supervisor plumbing into another checkout.

## Research, readiness and publication

Reviewed [official GLM-5.3 documentation](https://docs.z.ai/guides/llm/glm-5.3) and [official Flash documentation](https://docs.z.ai/guides/vlm/glm-5.3-flash). The documented thinking/effort and modality facts support the public description; the routing matrix is correctly labeled a local cost-conscious heuristic, not a measured optimum or universal pricing claim. Media attachments are unsupported by this wrapper even though Flash supports native multimodal inputs.

The latest installed-interface preflight remained **failed before inference**: its account/host registry did not expose the requested Flash route. No `session/send`, effective route, response or edits were claimed. Public docs distinguish this from the earlier standalone account-link issue and do not promise that ordinary CLI login alone fixes app-server readiness. Unsupported setup is reported rather than bypassed or simulated.

Reviewed all **23 tracked/staged public files**; index blobs matched the inspected working files, with the superseded independent report to be replaced by this one. No personal machine paths, private job identifiers, raw runtime logs/databases, account state or machine-specific receipts were included. Versioned manifests, marketplace, skill, provenance, routing/validation docs, license/NOTICE, links and offline validation are consistent; staged diff checks passed. The reviewed origin is the explicitly requested `https://github.com/junhua/zcode-in-codex-plugin.git`.

No publication blockers remain once this current report replaces the superseded review and is staged. The reviewer performed no commit or push. Remote in-flight work, OS suspension/scheduling and surviving/escaped descendants remain disclosed limits; local cancellation is not an absolute provider-side cutoff guarantee.
