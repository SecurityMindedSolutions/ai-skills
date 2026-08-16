# Terraform & Infrastructure-as-Code Security Review Module

Review Terraform configurations and other IaC files for security misconfigurations.

## Categories to Review

### 1. IAM & Access Control
<!-- Standards: OWASP-Web-A01:2025, OWASP Serverless SAS-4, CIS-GCP-1.x, CIS-AWS-1.x, NIST-CSF PR.AA -->
- Wildcard permissions (`Action: "*"`, `Resource: "*"`)
- Overly broad IAM policies (admin-level access where read-only suffices)
- Missing resource constraints on IAM policies
- Service accounts with excessive permissions
- Cross-account access without proper conditions
- Missing MFA requirements for sensitive operations
- **Dangerous IAM role compositions**: Check for role combinations on the same service account that together create privilege escalation paths. Examples: `roles/run.admin` + `roles/iam.serviceAccountUser` = deploy arbitrary code as any SA (project takeover); `roles/iam.securityAdmin` + `roles/iam.serviceAccountUser` = grant any role to any principal; `roles/storage.admin` at project level = modify Terraform state, frontend assets, and function source code. Flag these combinations even if individual roles seem justified.
- **Project-level vs resource-level bindings**: Flag project-level IAM bindings (e.g., `roles/secretmanager.secretAccessor` at project level) when resource-level bindings already exist for the same SA. The project-level binding is likely redundant and grants broader access than intended.
- **Runtime vs build-time permissions**: Service accounts used by runtime workloads (Cloud Functions, Cloud Run) should not have build-time permissions (`roles/cloudbuild.builds.builder`, `roles/artifactregistry.createOnPushWriter`). These indicate a legacy "do everything" SA that needs decomposition.

### 2. Network Security
<!-- Standards: OWASP-Web-A02:2025, CNAS-6, CIS-GCP-3.x, CIS-AWS-5.x, NIST-CSF PR.IR -->
- Security groups/firewall rules open to `0.0.0.0/0` on non-web ports
- Missing network segmentation (everything in default VPC)
- Unrestricted egress rules
- SSH (22) or RDP (3389) open to the internet
- Missing private subnets for backend services
- Load balancers without WAF
- **Forwarded-host / origin isolation (CDN-fronted origins)**: When an origin trusts a forwarded-host
  header (`X-Forwarded-Host`, or a custom `X-*-Forwarded-Host`) set by an edge/CDN to select which
  tenant or content to serve, two IaC controls must both be present: (1) the trusted edge/LB
  **strips or overwrites** any inbound copy of that header (e.g. an LB `custom_request_headers` that
  clears it, a header-normalization rule) so a client cannot spoof it; and (2) the origin is
  **network-restricted to the CDN** — a WAF/Cloud-Armor IP allowlist of the CDN's published ranges
  and/or mTLS origin-pull — so the origin cannot be reached directly, bypassing the edge. Flag a
  CDN-fronted origin that lacks either the inbound-header strip or the origin network lock. Note that
  IaC only proves the controls are *declared*; whether they are *enforced on the wire* is out of
  scope for static review.
- **Scoped origin routing**: an origin/backend reachable via a customer-facing edge (custom domains,
  public hostnames) should route only the public surface; sensitive backends (auth, admin, tenant
  management APIs) must not be reachable through that edge's URL map. Flag url-map/routing rules that
  expose privileged backends on a public custom-domain path.

### 3. Encryption
<!-- Standards: OWASP-Web-A04:2025, OWASP Proactive Controls C2, CIS-GCP-5.x, NIST-CSF PR.DS -->
- Storage without encryption at rest (S3, GCS, RDS, Cloud SQL)
- Missing encryption in transit (TLS not enforced)
- Using default encryption keys instead of customer-managed (CMK/CMEK)
- Weak encryption algorithms or key sizes
- Missing key rotation policies

### 4. Public Exposure
<!-- Standards: OWASP-Web-A02:2025, CIS-GCP-5.x, CIS-AWS-2.x -->
- Public S3/GCS buckets (unless intentionally serving static content)
- Public database instances (RDS, Cloud SQL with public IP)
- Public IP addresses on backend services
- Public container registries
- Storage buckets with `allUsers` or `allAuthenticatedUsers` access

### 5. Logging & Monitoring
<!-- Standards: OWASP-Web-A09:2025, OWASP Proactive Controls C9, CIS-GCP-2.x, CIS-AWS-3.x, NIST-CSF DE.CM -->
- Missing audit logging (CloudTrail, Cloud Audit Logs)
- Missing flow logs on VPCs/subnets
- Log destinations without encryption
- Missing alerts on security-relevant events
- Short log retention periods

### 6. Database Security
<!-- Standards: OWASP-Web-A02:2025, CIS-GCP-6.x, CIS-AWS-4.x -->
- Database instances with public IP addresses
- Missing SSL enforcement on database connections
- Default database credentials or weak passwords
- Missing automated backups
- Missing deletion protection on production databases
- Overly permissive database security groups

### 7. Serverless & Container Security
<!-- Standards: OWASP Serverless SAS-4, SAS-8, CNAS-9, CWE-770 -->
- Cloud Functions/Lambda with overly broad IAM roles
- Container images from untrusted registries
- Missing resource limits (memory, CPU, timeout)
- Environment variables containing secrets (instead of Secret Manager references)
- Missing VPC connectors for database access
- **Timeout configured** — functions without explicit timeout use platform defaults (which may be too generous). Check for `timeout_seconds` or `timeout` on all function definitions.
- **Max instances limit** — functions without `max_instance_count` or `max_instances` can auto-scale without bound, enabling billing attacks. Every function should have a max instances cap.
- **Concurrency limit** — for HTTP-triggered functions, check `max_instance_request_concurrency` or equivalent. Unbounded concurrency can exhaust downstream resources (DB connections).
- **Min instances** — if set, verify it's justified (cost implications of always-warm functions).
- **Ingress settings** — functions should restrict ingress to `ALLOW_INTERNAL_AND_GCLB` or `ALLOW_INTERNAL_ONLY` unless they need public access.

### 8. CIS GCP Benchmark Alignment
<!-- Standards: CIS GCP Foundations v3.0 sections 1, 2, 4, 7 -->

**IAM (CIS 1.x):**
- Are primitive roles (`roles/owner`, `roles/editor`) used? These are overly broad — prefer predefined or custom roles.
- Are user-managed service account keys present? Prefer workload identity federation.
- Are service account keys rotated (if keys exist, check for rotation mechanisms or key age > 90 days).
- Are custom IAM roles scoped to minimum permissions?

**Logging & Monitoring (CIS 2.x):**
- Are log sinks configured for audit logs (export to BigQuery, GCS, or Pub/Sub)?
- Are metric filters / log-based alerting configured for:
  - IAM policy changes
  - Audit configuration changes
  - Custom role changes
  - VPC network changes
  - Firewall rule changes
  - Network route changes
  - Cloud SQL configuration changes
  - Storage bucket permission changes
- Are log retention policies configured (not default 30 days)?
- **Application security-event alerting** (not just infra-change alerting): are alert policies /
  metric filters declared for application-level security events — repeated failed authentication
  (e.g. N failed logins per user/hour), authorization/permission denials and cross-tenant access
  attempts, privilege escalation, and auth from new geo/device? Infra-change alerts (IAM/firewall/
  route changes above) are necessary but do not cover application abuse. Flag a system that logs
  these events (structured logs exist) but declares no alert policy to act on them — logging without
  alerting leaves detection dependent on someone reading logs.

**Compute (CIS 4.x):**
- Is OS Login enabled on instances (`enable-oslogin = true` in metadata)?
- Are instances using Shielded VM features (`shielded_instance_config` block)?
- Is serial port access disabled (`serial-port-enable = false` in metadata)?
- Are project-wide SSH keys disabled on instances (`block-project-ssh-keys = true`)?
- Is IP forwarding disabled on instances unless required (`can_ip_forward = false`)?
- Are instances using default service account with full API access scopes?

**BigQuery (CIS 7.x):**
- Are BigQuery datasets restricted (no `allUsers` or `allAuthenticatedUsers` in access blocks)?
- Is CMEK configured for BigQuery datasets where required?
- Are default table expiration policies set where appropriate?

### 9. State & Secrets Management
<!-- Standards: OWASP-Web-A02:2025, OWASP Proactive Controls C5 -->
- Terraform state stored locally (not remote backend)
- Missing state encryption
- Missing state locking
- Secrets in `.tfvars` files or variable defaults
- Secret values in Terraform outputs
- Unpinned provider versions (`required_providers` without version constraints allows supply chain attacks via compromised providers)

## Scanning Approach

1. Find all `.tf`, `.tfvars`, and related IaC files
2. Check IAM policies for least privilege violations
3. Check network rules for overly permissive access
4. Verify encryption is enabled on all storage and databases
5. Check for public exposure of resources
6. Verify logging and monitoring configurations
7. Check for secrets in Terraform variables or outputs

## Patterns to Grep For

```
# IAM wildcards
"Action".*"\*"|actions.*=.*\["\*"\]|permissions.*=.*\["\*"\]
"Resource".*"\*"|resources.*=.*\["\*"\]
"Principal".*"\*"|members.*=.*\["allUsers"\]|members.*=.*\["allAuthenticatedUsers"\]

# Open network rules
0\.0\.0\.0/0|::/0
from_port.*0.*to_port.*65535|protocol.*"-1"
ingress.*0\.0\.0\.0|source_ranges.*0\.0\.0\.0

# Missing encryption
encrypted\s*=\s*false|kms_key_id\s*=\s*""|storage_encrypted.*false
ssl_enforcement_enabled.*false|require_ssl.*false

# Public exposure
acl.*public|public_access.*enabled|publicly_accessible.*true
associate_public_ip.*true|map_public_ip.*true
allow_blob_public_access.*true|uniform_bucket_level_access.*false

# Missing logging
enable_logging.*false|logging.*disabled|access_logs.*false
cloud_audit_logging.*false|flow_logs.*false

# Database exposure
publicly_accessible.*true|authorized_networks.*0\.0\.0\.0
deletion_protection.*false|backup_retention.*0

# Secrets in config
default\s*=\s*"[^"]{16,}"|password.*=.*"[^"]+"|secret.*=.*"[^"]+"

# State management
backend\s*"local"|terraform\.tfstate

# Provider pinning
required_providers.*\{[^}]*version|provider\s*"[^"]*"\s*\{(?!.*version)

# Container/serverless
FROM.*:latest|image.*:latest
privileged.*true|host_network.*true|run_as_root

# Serverless resource limits
timeout_seconds|timeout\s*=|max_instance_count|max_instances
max_instance_request_concurrency|min_instance_count|min_instances
ingress_settings|ALLOW_INTERNAL|ALLOW_ALL

# CIS GCP - primitive roles
roles/owner|roles/editor|roles/viewer
primitive_role|basic_role

# CIS GCP - service account keys
google_service_account_key|service_account_key

# CIS GCP - logging
google_logging_metric|log_sink|logging_sink
metric_filter|notification_channel|alert_policy
log_retention_days|retention_days

# CIS GCP - compute hardening
enable-oslogin|shielded_instance_config|serial-port-enable
block-project-ssh-keys|can_ip_forward

# CIS GCP - BigQuery
google_bigquery_dataset|bigquery.*access|allUsers.*bigquery
default_table_expiration_ms|kms_key_name.*bigquery
```

## Files to Scan

```
**/*.tf
**/*.tfvars
**/*.tf.json
**/terraform.tfstate (should NOT exist in repo)
**/backend.tf
**/variables.tf
**/outputs.tf
**/provider.tf
**/*.yaml (CloudFormation, Kubernetes)
**/cloudbuild.yaml
**/.github/workflows/*.yml
```
