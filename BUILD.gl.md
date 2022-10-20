# Building GL Versions

GL (Greenlight) versions are performance-optimized builds of Core Lightning designed specifically for Blockstream's Greenlight service. This document describes how GL versions are built, maintained, and released.

## Overview

### What are GL Versions?

GL versions are special releases of Core Lightning (CLN) that include:
- **Performance optimizations** for Greenlight's multi-tenant, cloud-hosted architecture
- **Static linking** for reproducible deployments
- **Clang compilation** for performance
- **Always-current plugin versions** (cln-lsps-client, cln-renepay) even in stable release branches

### Naming Convention

GL versions follow the pattern: `v{UPSTREAM_VERSION}gl{REVISION}`

Examples:
- `v25.05gl1` - First GL release based on upstream v25.05
- `v25.05gl2` - Second GL release (with patches) based on v25.05
- `v24.11gl1` - First GL release based on upstream v24.11

## GL-Specific Modifications

GL builds include performance patches cherry-picked from the GL development branch. These patches are organized by category:

### Performance Optimizations

#### UTXO Set Management
The main optimization disables UTXO set updates during normal operation, reducing memory usage and sync time for Greenlight's managed node deployments:
- `gl: Skip updates to the utxoset when running on greenlight`
- `gl: Switch to envvar to disable utxoset`

#### Fee Handling
Closing feerate calculation tweaks optimized for Greenlight's operational parameters:
- `gl: Closign feerate tweaks`

#### Gossip Protocol
Permissive gossip map mode for better network robustness:
- `gl: Add GOSSMAP_PERMISSIVE mode`

#### Synchronization
Improvements for faster initialization and better HTLC handling:
- Allow outgoing HTLCs before full bitcoind sync
- Wait for onchaind acknowledgment of new spends
- Send CHANNEL_REESTABLISH on closed channels

### Plugin Strategy

GL versions always include the latest versions of these plugins from the master branch:
- **cln-lsps-client**: LSPS protocol support (Lightning Service Provider)
- **cln-renepay**: Advanced payment retrying mechanism

This ensures Greenlight users get the latest payment improvements regardless of which CLN version is deployed.

## Build Process

### Local Builds

To build a GL version locally:

```bash
# Tag the current branch with the GL version name
git tag -a -m "v25.05gl1" v25.05gl1

# Run the build script
python3 build.py v25.05gl1
```

The script will:
1. Create an annotated git tag
2. Configure the build with `CC=clang --disable-valgrind --enable-static`
3. Compile CLN
4. Install to `cln-versions/v25.05gl1/`
5. Generate a manifest with SHA256 checksums and metadata
6. Create a `.tar.bz2` archive
7. Verify the compiled version matches the expected tag
8. Upload to GCS bucket (if `ci-service-account.json` exists)

### CI Pipeline Builds

Builds are automatically triggered by GitLab CI when pushing version branches (branches matching the regex `/^v/`).

**Pipeline stages:**

1. **GL Version Build**: `build.py $CI_COMMIT_BRANCH`
   - Builds the tagged GL version
   - Creates `lightningd-v25.05gl1.tar.bz2`

2. **Master Build**: Creates git worktree of master branch
   - Builds latest master as backup plugin source
   - Creates `lightningd-mst.tar.bz2`

3. **Plugin Bundling**: Post-processing step
   - Extracts from master build:
     - `usr/local/libexec/c-lightning/plugins/cln-lsps-client`
     - `usr/local/libexec/c-lightning/plugins/cln-renepay`
   - Rebundles with GL version artifacts
   - Creates final `lightningd-v25.05gl1.tar.bz2`

4. **Artifact Storage**: Archives never expire
   - Stored in GitLab CI
   - Also uploaded to `gs://greenlight-artifacts/cln/`

### Build Configuration

**Environment:**
- Base: Ubuntu 20.04
- Rust: 1.60
- Python: 3.10 (via UV)
- Dependencies: Poetry for Python package management

**Compiler flags:**
```bash
./configure CC=clang --disable-valgrind --enable-static
make -j$(nproc)
```

**Installation:**
```bash
make DESTDIR=cln-versions/v25.05gl1 install
```

## Creating a New GL Version

### Step 1: Branch from Upstream Release

```bash
# Fetch latest upstream tags
git fetch origin

# Create GL branch from upstream release tag
git checkout -b v25.05gl1 v25.05
```

### Step 2: Cherry-pick GL Patches

Identify and cherry-pick GL-specific patches from the GL development branch:

```bash
# See available GL patches
git log --oneline --all --grep="^gl:" | head -20

# Cherry-pick relevant patches
git cherry-pick <commit-hash>
git cherry-pick <commit-hash>
# ... repeat for all GL patches needed
```

Common patches to cherry-pick (in order):
- UTXO set optimizations
- Gossip improvements
- Fee handling tweaks
- Sync/HTLC improvements

### Step 3: Tag the Release

```bash
# Create annotated tag
git tag -a -m "v25.05gl1" v25.05gl1

# Verify tag
git describe --always --dirty=-modded --abbrev=7
# Output: v25.05gl1
```

### Step 4: Push to Trigger CI

```bash
# Push the branch and tag
git push origin v25.05gl1:v25.05gl1
git push origin v25.05gl1

# Or push both together
git push origin v25.05gl1 --tags
```

This triggers the GitLab CI pipeline automatically.

### Step 5: Verify Build Artifacts

Monitor the pipeline:
- GitLab: CI/CD → Pipelines
- Output artifact: `lightningd-v25.05gl1.tar.bz2`
- Check build logs for any errors

Verify the artifact:
```bash
# Extract and verify
tar -xjf lightningd-v25.05gl1.tar.bz2
cat manifest.json | jq .
# Check sha256sums
sha256sum usr/local/bin/lightningd
```

## Technical Details

### Directory Structure

```
cln-versions/
├── v25.05gl1/
│   ├── usr/
│   │   ├── local/
│   │   │   ├── bin/           # Executables (lightningd, lightning-cli, etc.)
│   │   │   ├── libexec/
│   │   │   │   └── c-lightning/
│   │   │   │       └── plugins/  # Built-in plugins
│   │   │   └── share/
│   │   │       ├── doc/
│   │   │       └── man/         # Man pages
│   └── manifest.json            # Build metadata and checksums
└── v24.11gl1/
    └── ...
```

### Manifest Format

The `manifest.json` file contains:

```json
{
  "commit": "<git-commit-hash>",
  "compilation_time": "<ISO-8601-timestamp>",
  "version": "v25.05gl1",
  "sha256sums": [
    ["usr/local/bin/lightningd", "<sha256-hash>"],
    ["usr/local/bin/lightning-cli", "<sha256-hash>"],
    ...
  ]
}
```

This enables:
- **Reproducible builds**: Verify exact binaries deployed
- **Security auditing**: Track what's included in each version
- **Change tracking**: Compare checksums between releases

### Artifact Upload

If `CI_SERVICE_ACCOUNT` environment variable is set, the build script uploads the final archive to Google Cloud Storage:

```
gs://greenlight-artifacts/cln/lightningd-v25.05gl1.tar.bz2
```

Requires:
- Google Cloud service account JSON credentials
- Write permissions on the bucket

### Plugin Bundling Process

The CI pipeline performs a sophisticated plugin merge:

1. **Build both versions**:
   - GL version: `lightningd-v25.05gl1.tar.bz2`
   - Master version: `lightningd-mst.tar.bz2`

2. **Extract GL base archive**:
   ```bash
   mkdir -p tmp
   tar -C tmp -xvjf lightningd-v25.05gl1.tar.bz2
   ```

3. **Extract master plugins only**:
   ```bash
   tar -C tmp -xvjf lightningd-mst.tar.bz2 \
     usr/local/libexec/c-lightning/plugins/cln-lsps-client \
     usr/local/libexec/c-lightning/plugins/cln-renepay
   ```

4. **Rebundle with GL version**:
   ```bash
   tar -C tmp -cvjf lightningd-v25.05gl1.tar.bz2 usr manifest.json
   ```

Result: GL version with stable base but latest plugins.

## Troubleshooting

### Build Fails with Version Mismatch

**Error**: `AssertionError: comp_version != branch`

**Cause**: Compiled version doesn't match expected tag.

**Solution**:
1. Check git tag is correct: `git describe --always`
2. Verify tag is annotated (not lightweight): `git cat-file -t v25.05gl1`
3. Check configure script recognizes the tag

### Missing GCS Upload

**Note**: If `ci-service-account.json` doesn't exist, the build completes but skips GCS upload. This is normal for local builds.

### Manifest Generation Fails

**Cause**: Permission issues when generating SHA256 hashes

**Solution**: Ensure build directory is writable and files are readable:
```bash
chmod -R u+r cln-versions/v25.05gl1/
ls -la cln-versions/v25.05gl1/manifest.json
```

### Plugin Bundling Issues

**Error**: Plugins not found in master archive

**Solution**:
1. Verify master build completed successfully
2. Check plugin exists in master: `tar -tjf lightningd-mst.tar.bz2 | grep cln-lsps-client`
3. Ensure tar extraction paths are exact

## Known Issues

### GitLab CI Artifact Path Bug

**File**: `.gitlab-ci.yml:73`

**Issue**: Artifact glob pattern uses literal braces instead of variable expansion
```yaml
# Current (incorrect):
- lightningd-{$CI_COMMIT_BRANCH}.tar.bz2

# Should be:
- lightningd-$CI_COMMIT_BRANCH.tar.bz2
```

**Impact**: Artifacts may not be properly registered with GitLab CI. Recommended fix: Update the glob pattern to use correct variable syntax.

## Related Files

- `build.py` - Main build script
- `.gitlab-ci.yml` - GitLab CI pipeline configuration
- `pyproject.toml` - Python dependencies for build tools
- `Makefile` - CLN build configuration
