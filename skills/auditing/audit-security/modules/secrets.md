# Secrets & Credentials Security Review Module

Deep scan for exposed credentials, secrets, and insecure credential management patterns.

## Categories to Review

### 1. Hardcoded Credentials in Source Code
<!-- Standards: OWASP-Web-A02:2025, OWASP Serverless SAS-7, CNAS-5, CIS-GCP-1.x -->
- API keys, passwords, tokens directly in source files
- Database connection strings with embedded credentials
- OAuth client secrets in code
- Encryption keys or IVs hardcoded in source
- SSH private keys committed to repository

### 2. Environment Variable Exposure
<!-- Standards: OWASP-Web-A02:2025, CWE-532 -->
- `.env` files committed to git (check `.gitignore`)
- Secrets logged via `print`, `console.log`, or logger calls
- Environment variables with secrets exposed in error messages
- Process environment dumps in debug endpoints

### 3. Configuration File Secrets
<!-- Standards: OWASP-Web-A02:2025 -->
- Secrets in YAML, JSON, INI, TOML config files
- Default credentials in example/template config files
- Unencrypted credential storage in application configs
- Backup files containing secrets (`.bak`, `.old`, `.tmp`)

### 4. Git History
<!-- Standards: OWASP-Web-A02:2025 -->
- Secrets that were committed and then removed (still in history)
- Large commits that might contain credential files
- Force-pushed branches that had secrets

### 5. Cloud Provider Credentials
<!-- Standards: OWASP-Web-A02:2025, CIS-GCP-1.x, CIS-AWS-1.x -->
- AWS access keys (`AKIA...`)
- GCP service account JSON keys
- Azure connection strings and client secrets
- Third-party service API tokens (Stripe, SendGrid, Twilio, etc.)

### 6. Certificate & Key Files
<!-- Standards: OWASP-Web-A04:2025, OWASP Proactive Controls C2 -->
- Private keys in repository (`.pem`, `.key`, `.p12`, `.pfx`)
- Self-signed certificates used in production
- Certificate passwords in source code
- Expired or weak certificates

### 7. CI/CD & Build Secrets
<!-- Standards: CICD-SEC-6, OWASP-Web-A02:2025 -->
- Secrets in CI/CD pipeline configuration files
- Docker build arguments containing secrets
- Build scripts that echo or log secrets
- GitHub Actions workflows exposing secrets

### 8. Secret Management Patterns
<!-- Standards: OWASP Proactive Controls C2, NIST-CSF PR.DS -->
- Verify secrets are loaded from secure sources (Secret Manager, Vault, etc.)
- Check for fallback patterns that use hardcoded defaults
- Verify secret rotation mechanisms exist
- Check that secrets are not passed as command-line arguments (visible in process lists)

## Scanning Approach

1. Glob for all config files, env files, key files, and certificate files
2. Grep for high-entropy strings and known credential patterns
3. Check `.gitignore` for proper exclusion of secret files
4. If in a git repo, check git log for credential-related commits
5. Review secret loading patterns — verify they use proper secret management
6. Check logging code for accidental secret exposure

## Patterns to Grep For

```
# API keys and tokens
api[_-]?key\s*[:=]\s*['"][a-zA-Z0-9_\-]{20,}
token\s*[:=]\s*['"][a-zA-Z0-9_\-]{16,}
secret\s*[:=]\s*['"][^'"]{12,}
password\s*[:=]\s*['"][^'"]{8,}

# AWS credentials
AKIA[0-9A-Z]{16}
aws_secret_access_key|aws_access_key_id

# GCP credentials
"type"\s*:\s*"service_account"
private_key.*BEGIN.*PRIVATE.*KEY
client_secret.*[a-zA-Z0-9_\-]{20,}

# Azure credentials
DefaultEndpointsProtocol.*AccountKey
ClientSecret|client_secret.*[a-zA-Z0-9_\-]{30,}

# Database connection strings
mysql://.*:.*@|postgres://.*:.*@|mongodb://.*:.*@|redis://.*:.*@

# SSH keys
-----BEGIN.*PRIVATE.*KEY-----|ssh-rsa\s+AAAA|ssh-ed25519\s+AAAA

# Common third-party tokens
sk_live_|sk_test_|rk_live_|rk_test_       # Stripe
SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]   # SendGrid
xox[baprs]-[0-9a-zA-Z\-]{10,}             # Slack
gh[pousr]_[0-9a-zA-Z]{36}                  # GitHub

# JWT secrets
jwt[_-]?secret|signing[_-]?key\s*[:=]\s*['"][^'"]{16,}

# Secrets in logging
log.*(password|token|secret|key|credential)
print.*(password|token|secret|key|credential)
console\.log.*(password|token|secret|key|credential)

# Environment access (verify these pull from secure sources)
process\.env\.|os\.environ|os\.getenv|ENV\[
```

## Files to Scan

```
# Config files
**/*.yaml, **/*.yml, **/*.json, **/*.ini, **/*.conf, **/*.toml, **/*.cfg

# Environment files
**/.env*, **/.environment*, **/env.*, **/*.env

# Key/cert files
**/*.pem, **/*.key, **/*.p12, **/*.pfx, **/*.crt, **/*.cer

# CI/CD files
**/.github/workflows/*.yml, **/Jenkinsfile, **/.gitlab-ci.yml, **/cloudbuild.yaml

# Docker files
**/Dockerfile*, **/docker-compose*.yml, **/.dockerignore

# Backup/temp files
**/*.bak, **/*.backup, **/*.old, **/*.tmp, **/*~
```

## Git History Check (if in a git repo)

```bash
# Search recent commits for secret-related changes
git log --all --oneline -100 --grep="password\|secret\|key\|token\|credential" 2>/dev/null

# Check for large blobs that might be key files
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '/^blob/ && $3 > 10000' | head -20 2>/dev/null
```
