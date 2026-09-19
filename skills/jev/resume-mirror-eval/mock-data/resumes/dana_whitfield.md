# Dana Whitfield
Portland, OR | dana.whitfield@example.com | (555) 010-2231 | github.com/dwhitfield-example

## Summary
Platform engineer with nine years running container infrastructure for regulated
businesses. I like boring, well-documented systems and I have a habit of writing the
runbook before the incident.

## Experience

### Staff Infrastructure Engineer, Acme Freight Systems (Portland, OR)
March 2021 - present

- Run the EKS estate for a freight-billing SaaS: 11 clusters across us-west-2 and
  us-east-1, roughly 1,400 pods at steady state. Upgraded from 1.24 to 1.29 with
  zero customer-facing downtime by moving every team onto blue/green node groups.
- Wrote the Terraform module library (47 modules, Terragrunt for environment
  layering) that the four product squads now consume. Cut the median time for a
  new service to reach production from three weeks to four days.
- Replaced a hand-rolled Jenkins setup with GitHub Actions for build and ArgoCD for
  delivery. Rollbacks went from "page Dana" to a one-line revert in the app repo.
- Introduced SLOs for the settlement API (99.95% availability, p99 under 400ms) and
  built the error-budget dashboards in Grafana on top of Prometheus and Tempo traces
  exported via the OpenTelemetry collector.
- Rolled out Istio for mutual TLS between services after our PCI DSS assessor asked
  for encryption in transit inside the cluster. Used it later for canary releases.
- Migrated secrets from SSM Parameter Store to Vault with Kubernetes auth; IAM roles
  for service accounts everywhere, and a monthly script that reports unused
  permissions so we can trim them.
- On the SOC 2 Type II side I own the evidence for change management and access
  review controls. Most of it is exported automatically from GitHub and Okta now.
- One of six people on the infra on-call rotation. Ran the postmortem for our
  worst incident (a 3h40m settlement outage in 2023 caused by a CoreDNS
  misconfiguration) and the follow-up work that came out of it.

### Site Reliability Engineer, Globex Health (Remote)
June 2017 - February 2021

- Kept a Kubernetes-on-EC2 (kops) platform alive for a telehealth company through a
  10x traffic increase in spring 2020. Wrote most of the Python tooling for cluster
  autoscaling before Karpenter existed.
- Built the initial Prometheus and Alertmanager stack and the alerting standards
  the team still uses. Reduced pages per week from about 40 to under 8.
- Managed PostgreSQL on RDS and a small self-hosted Kafka cluster for audit events.

### Systems Administrator, Initech Payroll (Boise, ID)
August 2015 - May 2017

- Linux administration, Puppet, Nagios. First exposure to PCI and the joy of
  quarterly ASV scans.

## Skills
Kubernetes (EKS, kops), Terraform, Terragrunt, GitHub Actions, ArgoCD, Istio,
Prometheus, Grafana, Tempo, OpenTelemetry, Vault, AWS IAM, Python, some Go,
PostgreSQL, Kafka, Linux.

## Other
Speaker, KubeCon NA 2023 lightning talk on error budgets for payment systems.
Occasional contributor to the terraform-aws-eks module (documentation fixes, one
bug fix in node group tagging).
