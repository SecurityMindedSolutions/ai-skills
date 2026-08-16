# Dependency & Supply Chain Security Review Module

Scan package manifests for known vulnerabilities, outdated packages, and supply chain risks.

## Categories to Review

### 1. Known Vulnerabilities (CVEs)
<!-- Standards: OWASP-Web-A03:2025, OWASP Proactive Controls C6, NIST-CSF ID.RA -->
- Run `pip-audit` for Python packages
- Run `npm audit` for Node.js packages
- Check for High/Critical severity CVEs
- Identify transitive dependency vulnerabilities

### 2. Outdated Packages
<!-- Standards: OWASP-Web-A03:2025, OWASP Proactive Controls C6 -->
- Major version behind (potential missing security patches)
- Packages with known end-of-life dates
- Packages no longer maintained (archived repos)

### 3. Version Pinning
<!-- Standards: OWASP-Web-A08:2025, CICD-SEC-3 -->
- Unpinned versions in production (using `>=` without upper bound, `*`, `latest`)
- Missing lock files (`package-lock.json`, `poetry.lock`, etc.)
- Inconsistencies between manifest and lock file
- Git-based dependencies (unstable, unaudited)

### 4. Supply Chain Risks
<!-- Standards: OWASP-Web-A03:2025, OWASP-Web-A08:2025, CICD-SEC-3, CNAS-4 -->
- Packages from non-standard registries
- Private registry configured over HTTP (not HTTPS)
- Recently published packages (< 30 days old)
- Packages with very low download counts
- Typosquatting candidates (names similar to popular packages)
- Dependency confusion: private package names that could collide with public registry packages (check `.npmrc` for registry scoping, `pip.conf` for `--extra-index-url` without `--index-url`)

### 5. Dev vs Production Dependencies
<!-- Standards: OWASP-Web-A02:2025 -->
- Dev/test dependencies included in production builds
- Debug/profiling packages in production requirements
- Testing frameworks shipped to production

### 6. Container Base Images (if Dockerfiles exist)
<!-- Standards: OWASP-Web-A03:2025, CNAS-1, CICD-SEC-9 -->
- Using `latest` tag (unpinned)
- Outdated base images with known CVEs
- Images from unofficial registries
- Running as root in container

## Scanning Approach

1. Find all package manifest files in the target path
2. For each ecosystem found, run the appropriate audit tool
3. Check version pinning practices
4. Identify outdated packages
5. Flag supply chain risk indicators

## Package Files to Find

```
# Python
**/requirements*.txt
**/setup.py
**/pyproject.toml
**/Pipfile
**/Pipfile.lock
**/poetry.lock

# Node.js
**/package.json
**/package-lock.json
**/yarn.lock
**/pnpm-lock.yaml

# Go
**/go.mod
**/go.sum

# Rust
**/Cargo.toml
**/Cargo.lock

# Java
**/pom.xml
**/build.gradle
**/gradle.lockfile

# Ruby
**/Gemfile
**/Gemfile.lock

# Containers
**/Dockerfile*
**/docker-compose*.yml
```

## Audit Commands to Run

**Python** (run in each directory containing requirements.txt):
```bash
# pip-audit for CVE scanning
pip-audit -r requirements.txt --desc --format json 2>/dev/null || echo "pip-audit not available"

# Check for outdated packages
pip list --outdated --format json 2>/dev/null || echo "pip list not available"
```

**Node.js** (run in each directory containing package.json):
```bash
# npm audit for CVE scanning
npm audit --json 2>/dev/null || echo "npm audit not available"

# Check for outdated packages
npm outdated --json 2>/dev/null || echo "npm outdated not available"
```

**General checks** (always run):
```bash
# Find unpinned versions in Python requirements
grep -n '>=' requirements*.txt 2>/dev/null
grep -n '\*' requirements*.txt 2>/dev/null

# Find unpinned versions in package.json
grep -n '"latest"' package.json 2>/dev/null
grep -n '"\*"' package.json 2>/dev/null

# Find git dependencies
grep -rn 'git+\|git://' requirements*.txt package.json 2>/dev/null

# Check Dockerfiles for latest tags
grep -n 'FROM.*:latest\|FROM.*[^:]*$' Dockerfile* 2>/dev/null
```

## Anti-Patterns to Flag

```
# Unpinned versions
>=.*without.*<|~=.*major|\*|latest

# HTTP registries
--index-url.*http://|registry.*http://|--trusted-host

# Git dependencies
git\+https://|git://|github:

# Dependency confusion indicators
--extra-index-url|--index-url.*http://|registry.*http://
\.npmrc|pip\.conf|.pypirc

# Dev in prod indicators
devDependencies.*used.*production|test.*requirements.*production

# Container issues
FROM.*:latest|FROM.*:.*[0-9]$|USER.*root|--privileged
```
