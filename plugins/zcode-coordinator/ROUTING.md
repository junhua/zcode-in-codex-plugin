# Task routing and research — policy 2026-10-28.1

This matrix is **our cost-conscious heuristic**, not an empirically proven optimum. Optimize the total cost of a verified outcome, including retries and human review. Classify the task from its specification; do not relabel risk to force a cheaper route. Escalate on diagnostic evidence rather than blind retries. The high default intentionally differs from the vendor's recommendation of max for complex coding.

| Task | Route | Why |
| --- | --- | --- |
| Mechanical changes, narrow extraction/search, explicit simple tests or boilerplate | GLM-5.3-Flash / low | Narrow, clear acceptance criteria favor the cheapest adequate route. |
| Bounded routine fixes/features/test writing | GLM-5.3-Flash / high | Cost-conscious default with some reasoning headroom. |
| Difficult, fully specified textual UI-state reasoning | GLM-5.3-Flash / max | A specialized choice, not a mandatory intermediate escalation. |
| Clear task needing flagship capability but little search/ambiguity | GLM-5.3 / low | Narrow niche; use only when Flash capability is insufficient. |
| Cross-file debugging, nontrivial refactoring, architecture/integration analysis, ambiguous or cross-service work | GLM-5.3 / high | More demanding coordination and reasoning. |
| Hardest failures, complex invariants/migration planning, long-horizon work with high cost of error | GLM-5.3 / max | Highest effort when evidence and error cost warrant it. |
| Security/data-loss scope | GLM-5.3 / high; max for hard cases, plus independent review | Model choice alone does not make a change safe. |

Media/file attachments are **not accepted by this wrapper**; local code files remain available to the file tools. Visual tasks are refused rather than treating a text prompt as a media transport. A future verified media adapter could consider Flash/max for difficult visual UI reasoning; this release supports textual UI-state specifications only.

## Verified facts and interface evidence

Checked 2026-10-28 against [official GLM-5.3 documentation](https://docs.z.ai/guides/llm/glm-5.3), [official Flash documentation](https://docs.z.ai/guides/vlm/glm-5.3-flash), the [official model README](https://github.com/zai-org/GLM-5/blob/main/README.md), and [ZCode model connection guidance](https://zcode.z.ai/en/docs/configuration): official IDs are `glm-5.3` and `glm-5.3-flash`; both use always-enabled thinking and `low/high/max`, defaulting to `max`. Omitted/unrecognized effort can fall back to max in the documented model implementation, while a provider may instead reject it. Therefore this wrapper validates the enum and sends an explicit effort every time. GLM-5.3 is text-only; Flash's native media capabilities do not imply wrapper support.

The installed ZCode 0.17.0 catalog uses `GLM-5.3` / `GLM-5.3-Flash` IDs. For its inspected Z.AI coding-plan Anthropic transport, the mapping sends `thinking.type=enabled` and `output_config.effort=<explicit level>`. This differs from an OpenAI-compatible API's `reasoning_effort`; providers must not be assumed identical. The wrapper checks that known mapping and rejects relevant later overrides or unknown transports instead of evaluating arbitrary mapping expressions. It records catalog/mapping fingerprints. The superseded GLM-5.2 reasoning-depth document was not used. FlashX throughput claims are not attributed to Flash, and no universal pricing claim is made.

## Before inference

A per-job selection-only profile contains no credentials, user rules or endpoint changes. A bounded app-server process creates/resumes a session, reads its authoritative snapshot, and requires exact provider, model, effort and permission mode. It then submits `session/send` with explicit `modelSelection` and a generated `inputId`. Results require the matching turn/input and an accepted send ACK. Unknown effective values or unsupported host actions fail before submission; a prompt asking for model X is never model selection.

Reports retain requested and effective routes separately, policy version, rationale, task classification, transport/catalog evidence, snapshot fingerprint and inference verification limits. A runtime snapshot proves the selected route in that process; it is not independent proof of a provider's internal implementation or model quality. Real provider execution remains unverified while account/host registry setup is incomplete. No model/provider fallback is configured.
