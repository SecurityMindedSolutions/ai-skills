# CI/CD Pipeline Security Review Module
<!-- Standards: OWASP-CICD-SEC-1 through CICD-SEC-10, OWASP-Web-A08, CNAS-4 -->

Review CI/CD pipeline configurations for security misconfigurations, credential exposure, and supply chain risks.

## Categories to Review

### 1. GitHub Actions Workflow Security
<!-- Standards: CICD-SEC-4 (PPE), CICD-SEC-7, CICD-SEC-8 -->
- Are action versions pinned to full commit SHAs (`uses: actions/checkout@<sha>`) instead of mutable tags (`@v4`, `@main`)?
- Is `pull_request_target` used? If so, does it check out PR code (dangerous — allows arbitrary code execution from forks)?
- Are `GITHUB_TOKEN` permissions scoped with a `permissions:` block (not using default broad permissions)?
- Are secrets passed only to trusted steps (not to third-party actions or scripts that could exfiltrate)?
- Are third-party marketplace actions from verified publishers or audited before use?
- Is `persist-credentials: false` set on checkout steps that don't need git push?
- Are workflow triggers appropriately scoped (not running on all events)?
- Are environment protection rules used for production deployments?

### 2. Cloud Build / Build Pipeline Configuration
<!-- Standards: CICD-SEC-5, CICD-SEC-6, CICD-SEC-7 -->
- Are secrets referenced from Secret Manager (not hardcoded in `cloudbuild.yaml` env vars)?
- Are build step images from trusted registries (gcr.io, docker.io official)?
- Are build step images pinned to digests or specific versions (not `:latest`)?
- Are `--privileged` flags absent from build steps?
- Is the build service account scoped to minimum required permissions?
- Are build logs configured to not expose secrets (no `echo $SECRET` patterns)?
- Are substitution variables used safely (not interpolated into shell commands)?

### 3. Pipeline Flow Controls
<!-- Standards: CICD-SEC-1 -->
- Are branch protection rules configured for main/production branches (detectable from workflow trigger conditions)?
- Do deployment workflows require manual approval gates?
- Is there separation between build and deploy stages?
- Are production deployments restricted to specific branches?
- Is force-push to protected branches blocked (detectable from branch protection rules in IaC)?

### 4. Artifact Integrity
<!-- Standards: CICD-SEC-9, OWASP-Web-A08 -->
- Are Docker images referenced by digest (`@sha256:...`) in deployment configs?
- Are lockfiles (`package-lock.json`, `requirements.txt` with hashes) verified during CI builds (`npm ci`, not `npm install`)?
- Are build artifacts signed or checksummed?
- Is there a `--frozen-lockfile` or `npm ci` pattern in CI (prevents dependency modification during build)?
- Are container images scanned for vulnerabilities in CI?

### 5. Credential Hygiene in Pipelines
<!-- Standards: CICD-SEC-6 -->
- Are long-lived credentials used in CI (service account keys, API tokens) or short-lived (workload identity, OIDC tokens)?
- Are CI secrets scoped to specific environments/workflows (not org-wide)?
- Are secrets rotated (detectable from naming patterns like `_V2`, rotation workflows)?
- Do build scripts avoid printing secrets (`set +x` before secret usage)?
- Are `.npmrc`, `.pypirc`, or other credential files generated at build time (not committed)?
- Are service account key files (`*.json`) excluded from artifact uploads?

### 6. Third-Party Service Governance
<!-- Standards: CICD-SEC-8 -->
- Are GitHub Apps / OAuth Apps inventoried and reviewed?
- Are webhook URLs pointing to known/internal services?
- Are GitHub Actions from third-party authors pinned and audited?
- Are CI plugins/integrations from verified sources?

### 7. Pipeline Logging and Visibility
<!-- Standards: CICD-SEC-10 -->
- Are build logs retained for audit purposes?
- Are deployment events logged (who triggered, what was deployed, when)?
- Is there alerting on failed deployments or unusual build activity?
- Are build logs accessible only to authorized users (not public)?

## Scanning Approach

1. Glob for all CI/CD configuration files (GitHub Actions, Cloud Build, Jenkins, GitLab CI)
2. Read each workflow/pipeline file and check against the categories above
3. Check for secret patterns in pipeline configurations
4. Verify action/image version pinning
5. Check for dangerous trigger patterns (`pull_request_target`, `workflow_dispatch` without restrictions)
6. Verify lockfile usage patterns in build steps

## Patterns to Grep For

```
# GitHub Actions - dangerous patterns
pull_request_target
actions/checkout.*ref.*github\.event\.pull_request
permissions:\s*write-all|permissions:\s*\{\}
GITHUB_TOKEN

# Unpinned actions (tag-based, not SHA)
uses:.*@v\d|uses:.*@main|uses:.*@master|uses:.*@latest

# Secret exposure in scripts
echo.*\$\{\{.*secrets\.|echo.*\$SECRET|echo.*\$API_KEY|set -x.*secret
env:.*\$\{\{.*secrets\.

# Cloud Build patterns
_SECRET_|secretEnv|availableSecrets
--privileged|--net=host
:latest|:$_TAG|:$BRANCH_NAME

# Credential files
\.npmrc|\.pypirc|\.docker/config\.json|gcloud.*key.*\.json
service.account.*\.json|credentials.*\.json

# Lockfile usage (good pattern - verify presence)
npm ci|pip install.*--require-hashes|pip install.*-r.*requirements
--frozen-lockfile|--immutable

# Artifact integrity
@sha256:|image.*@sha256:|digest:

# Build flow
manual.*approval|environment.*protection|required_reviewers
concurrency:|cancel-in-progress
```

## Files to Scan

```
# GitHub Actions
**/.github/workflows/*.yml
**/.github/workflows/*.yaml
**/.github/dependabot.yml

# Google Cloud Build
**/cloudbuild.yaml
**/cloudbuild.*.yaml
**/cloudbuild/*.yaml

# Other CI/CD
**/Jenkinsfile
**/.gitlab-ci.yml
**/.circleci/config.yml
**/azure-pipelines.yml
**/.travis.yml

# Build scripts
**/scripts/build.*
**/scripts/deploy.*
**/scripts/ci-*
**/scripts/pre-deploy.*
**/Makefile

# Docker build
**/Dockerfile*
**/docker-compose*.yml
**/.dockerignore

# Package management
**/.npmrc
**/.yarnrc*
**/pip.conf
**/.pypirc
```
