# Platform — Kubernetes

Installed because the charter's **Deployment platforms** row names it. Any distribution,
managed or self-run, with Helm, Kustomize, or plain manifests. The platform half of
`../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check `n/a` with a reason rather than deleting it.

## Workloads

- [ ] Every container has CPU and memory requests, and a memory limit. A pod without
      requests is scheduled on hope; one without a memory limit can starve its node.
- [ ] Readiness, liveness, and (for slow starters) startup probes are distinct. Liveness
      checks the process only: a liveness probe that checks the database restarts every
      pod when the database blips.
- [ ] The process handles `SIGTERM` and drains within `terminationGracePeriodSeconds`,
      with a `preStop` delay where the load balancer needs time to stop sending traffic.
- [ ] Anything that must stay available runs at least two replicas with a
      `PodDisruptionBudget`, so a node drain does not take it down.
- [ ] Images are referenced by an immutable tag or digest, never `latest`.
- [ ] Pods run as non-root with a restrictive `securityContext` (no privilege
      escalation, read-only root filesystem where possible).

## Configuration and secrets

- [ ] Secrets come from an external store or are encrypted in the repository (External
      Secrets, Sealed Secrets, SOPS). A Kubernetes `Secret` in git is only base64.
- [ ] Encryption at rest for Secrets is enabled on the cluster, or its absence is
      recorded as a risk.
- [ ] Service accounts and RBAC grant each workload and each deployer only what it needs.
- [ ] NetworkPolicies restrict which pods can reach the database and internal services.

## Deploy and rollback

- [ ] A rolling update runs old and new pods at once, so schema changes work with both.
      Migrations run once, as a Job or a pre-upgrade hook, not in every pod's start-up.
- [ ] Rollback is written down (`helm rollback`, `kubectl rollout undo`, or reverting the
      GitOps commit). It does not revert migrations, CRDs, or persistent volumes.
- [ ] If GitOps (Argo CD, Flux) manages the cluster, manual `kubectl` edits are known to be
      reverted, and emergency changes go through the repository.

## Storage and ingress

- [ ] Persistent volumes use a storage class whose reclaim policy matches the data's
      value; `Delete` removes the data with the claim.
- [ ] Volume snapshots or database backups exist off-cluster, and a restore has been done
      at least once outside production.
- [ ] Ingress certificates are issued and renewed automatically (for example
      cert-manager), and renewal failure alerts someone.
