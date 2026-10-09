---
status: draft
owner: devops-sre
last-reviewed: YYYY-MM-DD
---

# Release runbook — {{PROJECT_NAME}}

> Written so that someone who did not build the change can execute it, and so that
> someone woken at 3am can reverse it. If a step needs knowledge that is only in
> somebody's head, that is the finding.

## Environments

Purpose, source branch, and who may deploy are declared in `charter.md` → Environments.
Add only the deploy-time specifics here:

| Environment | URL / target | Deploy command or pipeline | Smoke check after deploy |
| --- | --- | --- | --- |
| | | | |

**Promotion path:** _(the order a change moves through the environments above, and what
must pass at each step before the next — or "one environment: production", which is a
fact to record, not a gap to hide)_

**Platform checks:** for each platform in `charter.md` → **Deployment platforms** that has
a checklist in `../platforms/`, run its deploy and rollback items as part of this
runbook. A platform with no checklist is reviewed against `../roles/devops-sre.md` alone.

## Pre-flight

- [ ] All checks green on the release commit (`../process/04-quality-gates.md`).
- [ ] No open S0/S1; S2 waivers recorded with follow-up IDs.
- [ ] Required approvals obtained.
- [ ] Migrations reviewed, with the reverse path tested in a non-production environment.
- [ ] Backup current and **restore verified** — not merely scheduled (see Backup & restore procedure below).
- [ ] Configuration and secrets present in the target environment, validated at startup.
- [ ] Dependent teams or consumers notified of anything breaking.
- [ ] Rollback procedure below re-read and known to work for this change.

## Procedure

1. _(Step, with the exact command or action.)_
2. _(Migration order relative to the deploy — state whether it runs before, during, or
   after, and whether old code can run against the new schema.)_
3. _(Deploy.)_
4. _(Post-deploy steps: cache purge, index rebuild, feature flag, warm-up.)_

State the expected duration and what "still normal" looks like at each step.

## Smoke checks

The minimum set proving the release is alive. Run every time; automate where possible.

- [ ] _(Critical journey 1 — completes end to end.)_
- [ ] _(Critical journey 2.)_
- [ ] _(Authentication works, and denial still denies.)_
- [ ] _(A representative write reaches the datastore and is readable back.)_
- [ ] _(The TLS certificate is valid and not near expiry; HTTP redirects to HTTPS without a loop.)_
- [ ] _(Search-engine ownership verification and analytics tags are still present, where
      the project uses them.)_
- [ ] _(Health, error rate, and latency within normal range.)_

## Monitoring window

- Watch for: _(duration)_
- Signals: _(error rate, latency, queue depth, specific business metric)_
- **Rollback trigger:** _(the specific, pre-agreed threshold — decided now, not during
  the incident, when the temptation is always to wait one more minute.)_

## Rollback

1. _(Exact steps.)_
2. _(Data implications — what happens to records written by the new version, and whether
   the old version can read them.)_
3. _(Who to tell.)_

**Last executed:** _(date, environment. If this says "never", the rollback is a theory.)_

## Backup & restore procedure

> An untested backup is an assumption, not a recovery plan. Restore drills must be executed
> periodically in an isolated/staging environment to verify data integrity.

- [ ] **Snapshot creation:** Backup datastores (database dump, object store snapshot, state volumes) prior to release.
- [ ] **Storage replication:** Verify the snapshot reaches storage outside the failure domain it protects — another provider, region, or machine.
- [ ] **Restore command:** `_(Exact command or script to restore snapshot into a fresh environment)_`
- [ ] **Data integrity verification:**
  - Check record counts and checksums against pre-backup baseline.
  - Verify relational integrity and constraints.
  - Test application boot and primary query against restored database.
- **Last restore drill executed:** _(date, target environment, recovery time achieved)_

## Communications

| Audience | When | Channel | Message owner |
| --- | --- | --- | --- |

## Post-release

- [ ] Backlog IDs in the release marked `Done`.
- [ ] Worklog entry written, including what was verified in production.
- [ ] Metrics baselined for anything the measurement plan tracks.
- [ ] Anything learned folded back into this runbook — while it is still fresh.
