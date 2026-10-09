# Platform — AWS

Installed because the charter's **Deployment platforms** row names it. Lambda, ECS or
Fargate, App Runner, Amplify, Elastic Beanstalk, or EC2. The platform half of
`../roles/devops-sre.md` and `../templates/release-runbook.md`; it adds checks, never
replaces them. Mark a check that does not apply to the services in use `n/a`.

## Identity and accounts

- [ ] CI deploys through OIDC federation with a scoped role, not long-lived access keys
      stored as CI secrets.
- [ ] Each workload has its own IAM role with least privilege. On ECS, the task role (what
      the app may do) and the execution role (pulling images, reading secrets) are
      separate.
- [ ] Production is in its own account, or the reason it shares one is recorded.
- [ ] No one uses the root user for daily work, and it has MFA.

## Infrastructure as code

- [ ] Resources are defined in CDK, CloudFormation, SAM, Terraform, or Serverless
      Framework in the repository. Console changes are drift, and the runbook says how to
      detect it.
- [ ] Stateful resources (databases, buckets, tables) have deletion protection or a
      retain policy, so a stack change cannot delete them.

## Compute

- [ ] Lambda: timeout, memory, and reserved concurrency are set per function. Database
      access goes through RDS Proxy or an HTTP data API, because concurrency multiplies
      connections. Aliases or versions make rollback a pointer change.
- [ ] ECS: the deployment circuit breaker with rollback is on, and the health-check grace
      period covers start-up.
- [ ] Amplify / App Runner: each branch or environment has its own variables and backend,
      never production's.

## Data

- [ ] RDS / Aurora: automated backups and point-in-time recovery are on, retention is
      known, Multi-AZ is decided, and a restore has been done at least once. A manual
      snapshot is taken before a destructive migration.
- [ ] S3: Block Public Access is on unless a bucket is deliberately public and recorded as
      such. Versioning is on for buckets holding data that matters.
- [ ] CloudFront in front of S3 uses origin access control, so the bucket is not public.

## Secrets, cost, and logs

- [ ] Secrets come from Secrets Manager or Parameter Store, not plaintext environment
      variables in the template.
- [ ] Budgets and cost alarms exist. NAT gateways, idle load balancers, and log volume
      are the usual surprises.
- [ ] CloudWatch log groups have a retention period; the default keeps logs forever.
- [ ] The region matches the charter's data-residency requirement.
