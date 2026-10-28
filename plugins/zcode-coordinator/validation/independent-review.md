# Independent review — ZCode Coordinator 0.2.0

**Implementation conclusion: passed for the documented macOS scope.** No blocking code findings remain in the reviewed wrapper. Real inference, editing, authentication readiness and real session resume have not been established. This report does not attest to a Git push, release, or successful live end-to-end run.

Reviewed wrapper: `skills/zcode/scripts/zcode_job.py` in the plugin package.

**SHA-256:** `27a375f42d34fab64c479e655a3aeea0a85a029012262b9190d92fc96826a099`.

## Independent evidence

The reviewer independently ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3.13 -m unittest discover -s tests -p 'test_jobs.py' -v
```

**29 tests passed in 17.907 seconds.** All model/service behavior in this suite uses fake CLI fixtures and disposable synthetic Git repositories. It covers existing lifecycle/scope/protocol guarantees plus account-catalog selection validation, missing/invalid option rejection, and secret-free job-local profile generation. No model/provider requests, user repositories, installed configuration changes, or credential edits were performed by the reviewer.

A separate actual macOS sandbox test attempted to modify both the generated provider profile and isolated HOME configuration. Both writes were denied and both files' hashes remained unchanged. Runtime writes remained allowed. This verifies the revised boundary rather than merely checking profile path strings.

## Selection-path review

The wrapper accepts model/provider IDs only as wrapper arguments. It validates against the installed desktop bundle's built-in account catalog and rejects unsupported CLI layouts, custom endpoints, credential fields, unknown models and unsupported reasoning levels. Rule matching now uses whole-string matching consistent with the inspected source's anchored model patterns.

The generated provider JSON contains only empty provider/model override collections and the selected provider/model/options. It copies no user configuration, key, token, or endpoint. The original provider configuration and account credentials remain outside the child's permitted write paths. Configured selection is recorded separately from proof that inference occurred, and resume retains the selection while revalidating the current catalog.

The review identified that ZCode polls its personal provider file during execution. The initial writable-runtime placement could therefore allow the execution agent to alter a validated profile after launch. This finding is closed: both the selection file and isolated HOME configuration now live in a control directory outside child-write allowances. Existing registry/report protection, explicit permission mode, removed command tools, project/ancestor configuration rejection, owned cancellation and conservative cleanup states remain in place.

## Live readiness and public delivery

Observed real synthetic attempts selected the catalog-enabled GLM-5.3 model, including an advertised reasoning level, but exited before any session/model response or edits. The documented standalone account-link identity prerequisite explains the initialization blocker; existing desktop account credentials alone do not prove standalone provider readiness. The supported user-controlled login/model confirmation steps are accurately described, and no undocumented CLI model flag or copied-credential workaround was introduced. A nested isolated Codex CLI was not claimed as tested when it lacked login.

Public deliverables must keep this failed-live-test distinction, use the 0.2.0 validation/model-selection description, and exclude personal absolute paths, runtime databases/logs, account/provider state, private prompts and raw job registries. The implementation reviewer changed no implementation or global configuration; this report is the review artifact.

## Public staging closeout

Reviewed the exact 19 staged files in the publication candidate. Staged blobs matched the inspected working files, including the reviewed wrapper hash and the same tests/fake CLI used for the independent run. No personal machine paths, private task/job identifiers, raw runtime logs/databases, account state, install/discovery receipts, or old-version validation were included. README, model setup, provenance and validation accurately distinguish fixture passes, installation/discovery and failed pre-inference live attempts. The public marketplace points to the packaged plugin, versions are 0.2.0, license/NOTICE are included, offline validation passes, and the staged diff has no whitespace errors. The documented future Codex flags were checked against actual installed help.

The reviewed origin is the user-requested `https://github.com/junhua/zcode-in-codex-plugin.git`. No publication-content blockers remain for this candidate and that target. The reviewer performed no commit or push.
