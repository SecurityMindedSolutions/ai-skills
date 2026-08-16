# Secret Scanning Alert Triage Module

Secret scanning alerts are **report-only**. This module NEVER auto-fixes because rotating secrets could break production systems. Instead, it provides structured triage information and rotation checklists.

## Alert Structure

Secret scanning alerts from the GitHub API include:

```
alert.secret_type              → e.g., "github_personal_access_token"
alert.secret_type_display_name → human-readable name
alert.state                    → "open", "resolved"
alert.resolution               → null, "false_positive", "revoked", "used_in_tests", "wont_fix"
alert.created_at               → when the secret was first detected
alert.push_protection_bypassed → whether push protection was bypassed
alert.locations_url            → API URL to get location details
```

## Triage Information to Gather

For each open alert:

### 1. Exposure Timeline
- `created_at`: When GitHub first detected the secret
- Calculate days exposed: `today - created_at`
- Check `push_protection_bypassed`: If true, someone explicitly bypassed push protection

### 2. Location Details
```bash
gh api "{alert.locations_url}" --jq '.[].details'
```
Determine:
- Is the secret in the current HEAD of a branch? (active exposure)
- Is it only in git history? (requires history rewriting to fully remove)
- Which file(s) and line(s) contain the secret?

### 3. Git History Check
If the secret is in the current HEAD:
- It's actively exposed in the repo
- Priority: rotate immediately, then remove from code

If the secret is only in history:
- It's been removed from current code but persists in git history
- Priority: rotate the secret, then consider history cleanup

## Provider-Specific Rotation Checklists

### GitHub Personal Access Token (`github_personal_access_token`)
- [ ] Go to GitHub Settings > Developer settings > Personal access tokens
- [ ] Identify the token by its prefix
- [ ] Revoke the compromised token
- [ ] Generate a new token with minimum required scopes
- [ ] Update all systems using the old token
- [ ] Store the new token in a secret manager (not in code)

### GitHub OAuth App Secret (`github_oauth_secret`)
- [ ] Go to GitHub Settings > Developer settings > OAuth Apps
- [ ] Regenerate the client secret
- [ ] Update all deployment configurations
- [ ] Verify OAuth flow still works

### AWS Access Key (`aws_access_key_id`, `aws_secret_access_key`)
- [ ] Log into AWS IAM Console
- [ ] Identify the IAM user/role associated with the key
- [ ] Check CloudTrail for unauthorized usage since exposure date
- [ ] Create a new access key for the IAM user
- [ ] Update all systems using the old key
- [ ] Deactivate the old key (don't delete yet - monitor for breakage)
- [ ] After 7 days with no issues, delete the old key
- [ ] Consider switching to IAM roles instead of access keys

### GCP Service Account Key (`google_cloud_private_key_id`)
- [ ] Go to GCP Console > IAM > Service Accounts
- [ ] Identify the service account
- [ ] Check audit logs for unauthorized usage
- [ ] Create a new key for the service account
- [ ] Update all systems using the old key
- [ ] Delete the old key from GCP
- [ ] Consider using Workload Identity instead of key files

### Azure Secret (`azure_*`)
- [ ] Log into Azure Portal > Azure Active Directory
- [ ] Identify the application registration
- [ ] Check sign-in logs for unauthorized usage
- [ ] Generate a new client secret
- [ ] Update all deployment configurations
- [ ] Delete the old secret

### Slack Token (`slack_token`, `slack_webhook_url`)
- [ ] Go to Slack API > Your Apps
- [ ] Regenerate the token/webhook
- [ ] Update all integrations
- [ ] Check Slack audit logs for unauthorized usage

### Generic API Key / Password
- [ ] Identify the service this key belongs to
- [ ] Check the service's logs for unauthorized usage since exposure date
- [ ] Rotate the key/password through the service's admin interface
- [ ] Update all systems using the old credential
- [ ] Store the new credential in a secret manager

## Git History Cleanup

If the secret persists in git history and rotation alone isn't sufficient:

**Recommended tool**: `git-filter-repo` (preferred over `git filter-branch`)

```bash
# Install git-filter-repo
pip install git-filter-repo

# Remove a specific file from all history
git filter-repo --invert-paths --path {file_containing_secret}

# Or replace specific strings
git filter-repo --replace-text expressions.txt
# where expressions.txt contains: literal:THE_SECRET_VALUE==>REDACTED
```

**WARNING**: History rewriting requires force-pushing and affects all collaborators. Only recommend this for repos where:
- The secret cannot be rotated (legacy system, third-party)
- Compliance requirements mandate removal from history
- The repo has few collaborators (minimize disruption)

For most cases, rotating the secret is sufficient. The old value in history becomes useless once rotated.

## Output Format

For each secret scanning alert, produce:

```
SECRET ALERT: {secret_type_display_name}
  Repo: {org}/{repo}
  Alert #: {number}
  Severity: {severity based on secret type - API keys are high, webhooks are medium}
  Exposed since: {created_at} ({N} days)
  Location: {file}:{line} (in HEAD: yes/no, in history: yes/no)
  Push protection bypassed: {yes/no}

  ROTATION CHECKLIST:
  {provider-specific checklist from above}

  ADDITIONAL STEPS:
  - [ ] Verify no unauthorized usage during exposure window
  - [ ] Update secret storage to use {recommended secret manager}
  - [ ] Add pre-commit hook to prevent future secret commits
  {- [ ] Consider git history cleanup (secret persists in history) — if applicable}
```

## Recommendations Section

Always include these general recommendations:

1. **Enable GitHub push protection** if not already enabled - prevents secrets from being pushed
2. **Use a secret manager** (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, HashiCorp Vault) instead of environment files or config files
3. **Add pre-commit hooks** using tools like `detect-secrets` or `gitleaks` for local scanning
4. **Rotate all exposed secrets** regardless of whether the alert is dismissed - the secret value is compromised once committed
