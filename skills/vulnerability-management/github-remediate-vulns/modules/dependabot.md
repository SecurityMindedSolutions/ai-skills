# Dependabot Alert Remediation Module

Apply version bumps for Dependabot alerts with available patches. Test-gated: every fix must pass the test suite or it gets reverted.

## Ecosystem Detection

Identify the package ecosystem from manifest files:

| Ecosystem | Manifest Files | Lock Files | Bump Command |
|-----------|---------------|------------|--------------|
| npm | `package.json` | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` | `npm install {pkg}@{version}` |
| pip | `requirements.txt`, `requirements/*.txt` | none (or `pip-compile`) | Edit file directly, then `pip install -r requirements.txt` |
| pip (pyproject) | `pyproject.toml` | `poetry.lock`, `uv.lock` | `poetry update {pkg}` or `uv lock` |
| go | `go.mod` | `go.sum` | `go get {pkg}@v{version}` |
| bundler | `Gemfile` | `Gemfile.lock` | `bundle update {pkg}` |
| cargo | `Cargo.toml` | `Cargo.lock` | `cargo update -p {pkg}` |
| maven | `pom.xml` | none | Edit `<version>` in pom.xml |
| gradle | `build.gradle` | `gradle.lockfile` | Edit version in build.gradle |

## Classification Logic

For each Dependabot alert, check the `security_vulnerability` object:

```
alert.security_vulnerability.first_patched_version.identifier  → target version
alert.security_vulnerability.vulnerable_version_range           → current constraint
alert.dependency.package.name                                   → package name
alert.dependency.package.ecosystem                              → ecosystem
alert.dependency.manifest_path                                  → file to update
alert.security_advisory.severity                                → severity level
alert.security_advisory.cve_id                                  → CVE identifier
```

**AUTO-FIX** if ALL of these are true:
- `first_patched_version` exists (there IS a fix available)
- The bump is patch or minor (e.g., 2.3.1 -> 2.3.2, or 2.3.1 -> 2.4.0)
- The repo has a detectable test suite

**ASSISTED-FIX** if ANY of these are true:
- The bump is a major version (e.g., 2.x -> 3.x) - may have breaking changes
- No test suite detected (can't validate the fix)
- Multiple alerts require bumping the same package to different versions

**MANUAL** if:
- No `first_patched_version` exists
- The vulnerability is in a transitive dependency with no direct fix
- The package is deprecated with no replacement

## Remediation Process

### 1. Read the manifest file

Use Read tool to get the current manifest content. Find the line(s) referencing the vulnerable package.

### 2. Determine version bump

Parse the alert JSON for:
- Current version (from manifest)
- Target version (`first_patched_version.identifier`)
- Bump type: compare major.minor.patch segments

### 3. Update the manifest

**npm (package.json)**:
- Find the package in `dependencies` or `devDependencies`
- Update the version string, preserving the prefix (`^`, `~`, or exact)
- If current is `^2.3.1` and target is `2.3.2`, update to `^2.3.2`
- If current is `~2.3.1` and target is `2.4.0`, update to `~2.4.0`
- For exact pins (`2.3.1`), update to exact (`2.3.2`)

**pip (requirements.txt)**:
- Find the line with the package name (case-insensitive match)
- Update the version specifier: `flask==2.3.1` -> `flask==2.3.2`
- Handle various formats: `pkg==ver`, `pkg>=ver`, `pkg~=ver`, `pkg>=ver,<upper`
- For pinned versions (`==`), update to the patched version
- For ranges (`>=`), update the lower bound if the current range includes vulnerable versions

**pip (pyproject.toml)**:
- Find the package in `[project.dependencies]` or `[tool.poetry.dependencies]`
- Update the version constraint

**go (go.mod)**:
- Find the `require` line for the module
- Update version: `github.com/foo/bar v1.2.3` -> `github.com/foo/bar v1.2.4`

### 4. Regenerate lock files

After updating the manifest, regenerate lock files:

```bash
# npm - prefer full install since tests usually need node_modules
# npm install --package-lock-only can fail if node_modules doesn't exist
npm install

# yarn
yarn install

# pnpm
pnpm install

# pip with pip-tools
pip-compile requirements.in

# poetry
poetry lock

# uv
uv lock

# go
go mod tidy

# bundler
bundle install

# cargo
cargo update
```

### 5. Validate lock file consistency

After regeneration, check for issues:

```bash
# npm - check for broken dependency tree
npm ls --all 2>&1 | grep "ERESOLVE\|ERR\|invalid" || echo "OK"

# pip - check dependency compatibility
pip check 2>&1 || echo "pip check not available"

# go - verify module graph
go mod verify 2>&1 || echo "OK"
```

If validation fails, revert the change and classify as MANUAL with the error details.

### 6. Run tests

Detect and run the test suite:

```bash
# Check CLAUDE.md first for custom test commands
# Then try standard commands based on ecosystem:

# npm
npm test

# pytest
pytest

# go
go test ./...

# bundler
bundle exec rspec

# cargo
cargo test
```

### 7. Handle results

**Tests pass**: Keep the change, add to the "fixed" list with details:
```
{package}: {old_version} -> {new_version} (CVE-XXXX-XXXXX, {severity})
```

**Tests fail**: Revert ALL changes for this package:
```bash
git checkout -- {manifest_file} {lock_file}
```
Add to the "failed" list with the test failure output (first 50 lines).

### 8. Group commits

Group all successful fixes for a single repo into ONE commit. The commit message should list all packages bumped:

```
fix: bump vulnerable dependencies

- flask: 2.3.1 -> 2.3.3 (CVE-2024-XXXXX, high)
- requests: 2.28.0 -> 2.31.0 (CVE-2024-YYYYY, medium)
- lodash: 4.17.20 -> 4.17.21 (CVE-2024-ZZZZZ, critical)
```

## Multiple Alerts for Same Package

When multiple Dependabot alerts exist for the same package:
1. Find the highest patched version that resolves ALL alerts
2. Apply a single bump to that version
3. List all resolved CVEs in the fix report

## Transitive Dependencies

If the alert is for a transitive (indirect) dependency:
1. Check if updating the direct parent dependency resolves it
2. If yes, bump the parent dependency instead
3. If no direct path to fix, classify as MANUAL
4. Note: `npm audit fix` can sometimes resolve transitive issues - try it as a fallback for npm ecosystems

## Output Format

Return results as structured data:

```
FIXED:
- {repo}: {package} {old} -> {new} ({cve}, {severity}) [alert #{number}]

FAILED (reverted):
- {repo}: {package} {old} -> {new} - Test failure: {first line of error}

SKIPPED (manual):
- {repo}: {package} - {reason}
```
