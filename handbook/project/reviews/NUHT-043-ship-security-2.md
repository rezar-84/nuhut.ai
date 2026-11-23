---
status: current
owner: codex
last-reviewed: 2026-11-23
---

# Review — NUHT-043

**Stage:** ship **Tier:** 1
**Reviewed:** the item's diff (2162 lines), by `sdlc.py review`
**Reviewer agent:** codex
**Reviewer model:** unknown (the harness default)
**Author:** claude-code / claude-opus-5-5
**Independence:** independent

---

## security

Verdict: Block

Paraphrase: This change reads the Tier 1 approval threshold from the default-branch charter and restricts counted GitHub reviewers to its Approvers list. It adds opt-in local approvals stored in item shards, recording HEAD and retaining approval across changes anywhere under the docs directory. The supplied diff also adds agent-assisted severity downgrades and changes CI checker fallback selection. Default-branch configuration limits who can enable these features, but local approval and severity-review evidence remain writable assertions rather than authenticated authorization.

Checked: Supplied playbook, charter rows, and diff; approval identity, counting, freshness, persistence, severity downgrade enforcement, reviewer invocation, CI fallback, and test assertions. Embedded review conclusions were assessed against the code.

Not checked: Tests were not executed. Implementations outside the diff—including trusted-ref resolution, agent detection, subprocess isolation, shard access controls, and Git error handling—were not inspected. Host branch protection, threat-model updates, and human approval evidence were not verified.

Findings:

| # | Sev | Location | Finding | Consequence | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | S0 | `optional/runtime/finish.py`: `local_approvals()`; mirrored runtime | With local approvals enabled, an editable shard’s `handle` and `commit` establish approval authority without authenticated provenance. Enabling the feature on the default branch restricts activation, but does not prevent forgery afterward. This diff enables it for this repository. | A repository writer can fabricate the human approvals that satisfy the gate. | Require authenticated approval evidence protected from agent/repository writers, or verified signatures with signing authority outside their control. Until then, exclude unsigned records from mandatory human approval counts. |
| 2 | S0 | `optional/runtime/finish.py`: `check_waiver()` and `approve()` | When `interactive` is true, both agent rejection and runner-identity comparison are skipped. The caller selects an authorized identity through `--by`; a pseudo-terminal does not authenticate that person. | An agent or another caller can impersonate a charter approver through the supported command. | Authenticate the approving principal independently of terminal presence, arguments, environment, and Git configuration. Test pseudo-terminal and identity-spoofing denial cases. |
| 3 | S1 | `optional/runtime/finish.py`: `_records_only_since()` | Every path under `project.docs` is exempted from approval invalidation, including the charter, people registry, process instructions, and review records. These are security-bearing inputs, not merely bookkeeping. | A later commit attributed to another item can change governance or review evidence while retaining approval of an earlier revision. | Bind approval to the exact candidate revision, or narrowly exempt specific non-authoritative generated fields. Invalidate approval on charter, identity, policy, and review changes. |
| 4 | S1 | `optional/runtime/sdlc.py`: `severity_change()`; `shards.py`: `_flat_records()` | Downgrade authorization trusts editable `severity_reviews` fields, particularly `independent: yes`, `for`, and `rated`. It does not authenticate the reviewer or verify the referenced evidence. Direct severity edits also bypass the command; the supplied plan explicitly leaves CI downgrade validation undone. | An agent can fabricate a favorable review or remove unfavorable reviews and lower a blocking defect without independent assessment. | Enforce downgrade authorization at a protected persistence or merge boundary, authenticate review records, and reject unauthorized severity changes and review deletion. |
| 5 | S1 | `optional/runtime/sdlc.py`: `rerate()` | Reviewer independence is inferred from a harness name/model label while the executable is resolved through PATH. The supplied test demonstrates a replacement `codex` script printing a chosen rating and being accepted as independent. | A requester controlling PATH can manufacture an “independent” rating without consulting another model. | Run reviewers through a trusted execution configuration outside requester control and authenticate their results; do not derive independence from executable names alone. |
| 6 | S1 | `optional/runtime/sdlc.py`: `blind_rerate_prompt()` and `rerate()` | Repository-controlled reports, titles, and ladder text are inserted into the reviewer prompt, and the final matching severity line becomes gate evidence. Removing severity mentions does not neutralize embedded instructions; no enforced separation is shown. | Crafted defect content can steer the reviewer toward a favorable downgrade and weaken the release-defect gate. | Treat supplied material explicitly as untrusted evidence, constrain reviewer capabilities, and require protected adjudication before model output authorizes a downgrade. Add adversarial report fixtures. |
| 7 | S1 | `tests/smoke.py`: new approval test and file ending | The supplied patch has invalid indentation: the charter substitution interrupts the nested `commit()` function, and an indented `test_checker_fallback,` appears after the module entry point. Approval success assertions also occur before local approvals are enabled and describe piped, `DEVNULL` execution as a terminal. | The test module cannot parse as supplied, and its intended assertions do not establish the claimed security behavior. | Repair syntax and test sequencing; distinguish actual terminal tests from noninteractive identity tests. Execute the denial cases and required verification pipeline before ship approval. |
| 8 | S2 | `.github/workflows/ci.yml`: checkout step | The supplied workflow uses mutable `actions/checkout@v4`, rather than an immutable commit pin. This is pre-existing context in the touched workflow. | Upstream tag movement can change executed CI code without repository review. | Pin the action to a reviewed full commit SHA and maintain an explicit update process. |

## Responses

| # | Response | Evidence | Decided by |
| --- | --- | --- | --- |
| 1 | Escalate | Repeat of round 1 finding 1: unsigned local approvals. Opt-in since round 1; this repository turns them on because it has one approver. Whether unsigned approvals may count at all before NUHT-045 (signing) is the owner's decision. | |
| 2 | Escalate | Repeat of round 1 finding 2: no authenticated person outside GitHub. NUHT-045. | |
| 3 | Fix | An approval now survives only bookkeeping (`finish.BOOKKEEPING`: item shards, ledger, worklog/backlog renders, release records). The charter, `people.json`, reviews, plans and process docs void it. Test: "a change to people.json or the charter after the approval voids it (round 2, finding 3)". | |
| 4 | Escalate | Review rows are shard records like approvals; authenticating them is NUHT-045. `ci-check` checking severity transitions is listed as not done in the plan. | |
| 5 | Escalate | Independence is judged from the agent record and model family, as `review --by` does for every Tier 1 review; a requester who controls PATH controls every reviewer. No change in this item can fix that; owner decides whether to accept. | |
| 6 | Fix | The ladder now comes from the default branch's `CARD.md` (`severity_ladder`, `trusted_text`) and is part of the re-rating hash, so a changed ladder voids earlier re-ratings. The report is marked untrusted (round 1). | |
| 7 | Contest | `tests/smoke.py` parses (`python3 -c "import ast; ast.parse(open('tests/smoke.py').read())"`) and `test_checker_fallback` is in `main()`'s tuple. The reviewer saw only the NUHT-043 commits; hunks from the NUHT-041 and NUHT-044 commits in the same file were absent from its diff. The success assertions run after `Local approvals` is turned on (the test checks the refusal first). The success case runs without agent variables, which is the person path; a pseudo-terminal case is round 1 finding 2. | |
| 8 | Decline | NUHT-046. | |
