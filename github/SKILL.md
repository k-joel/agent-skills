---
name: github
description: Comprehensive GitHub operations including repository management, commits, pull requests, issues, and GitHub API interactions. Use when the user needs to perform any GitHub-related tasks such as creating repositories, pushing commits, managing branches, creating pull requests, managing issues, or working with GitHub Actions. This skill provides both command-line and API-based approaches for GitHub operations.
---

# GitHub Operations Skill

This skill provides comprehensive guidance for performing GitHub operations including repository management, commits, branches, pull requests, issues, and GitHub API interactions.

## Quick Start

### Authentication

Prefer the GitHub CLI (`gh`) — it handles auth, pagination, and formatting so you do not have to manage tokens and raw HTTP yourself.

1. **GitHub CLI (`gh`)** — preferred for interactive and scripted use
2. **Personal Access Token (PAT)** — for direct REST/GraphQL calls and headless automation
3. **SSH Keys** — for git-only operations over SSH

Set up and verify `gh` auth:

```bash
gh auth login                 # interactive login (browser or token)
gh auth status                # confirm the active account and scopes
gh auth token                 # print the token gh is using (for use with curl)
```

For headless/CI use, skip the interactive login and provide a token through the environment instead — `gh` reads `GH_TOKEN` (preferred) or `GITHUB_TOKEN`:

```bash
export GH_TOKEN=ghp_your_token
gh api user                   # works without any interactive step
```

### Token choice

- **Fine-grained PAT** is the recommended default. It has a 30-day default expiry, scoped repository/organization permissions, and is authorized for SAML SSO at creation time. Use it unless you need a capability it does not yet cover.
- **Classic PAT** is the fallback (e.g. write access to public repos you do not own, or the few endpoints fine-grained tokens do not cover). Classic tokens left unused for a year are auto-revoked.
- In GitHub Actions, use the built-in `GITHUB_TOKEN` — never a long-lived PAT — and grant it least privilege via the `permissions:` key.

See `references/permissions.md` for the full scope/permission reference.

### Basic Workflow
1. Authenticate with GitHub (verify with `gh auth status` or `GET /user`)
2. Perform the required operation (create repo, push code, etc.)
3. Verify the operation completed successfully

## Repository Operations

### Creating a Repository

**Using GitHub CLI (preferred):**
```bash
gh repo create my-test-repo --public --description "My test repository"
# useful flags: --add-readme, --gitignore <name>, --license <spdx>, --clone, --source <dir>
```

**Using GitHub API (curl):**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  https://api.github.com/user/repos \
  -d '{"name":"my-test-repo","description":"My test repository","private":false}'
```

### Cloning a Repository
```bash
git clone https://github.com/username/repository.git
# or with SSH
git clone git@github.com:username/repository.git
```

## Git Operations

### Initializing and Committing
```bash
# Initialize repository
git init

# Add files
git add .

# Commit changes
git commit -m "Initial commit"

# Set remote origin
git remote add origin https://github.com/username/repository.git

# Push to GitHub
git push -u origin main
```

### Branch Management
```bash
# Create and switch to a new branch
git switch -c feature-branch

# Switch branches
git switch main

# Merge branches
git merge feature-branch

# Delete branch
git branch -d feature-branch
```

## Pull Requests

### Creating a Pull Request
```bash
# Using GitHub CLI
gh pr create --title "Feature implementation" --body "Description of changes"

# List pull requests
gh pr list

# View specific PR
gh pr view 123
```

### Reviewing and Merging
```bash
# Review PR
gh pr review 123 --approve --body "Looks good!"

# Merge PR (--merge, --squash, or --rebase; --delete-branch cleans up)
gh pr merge 123 --squash
```

## Issues Management

### Creating Issues
```bash
gh issue create --title "Bug report" --body "Description of the bug"
```

### Listing and Managing Issues
```bash
# List issues
gh issue list

# View issue
gh issue view 456

# Close issue
gh issue close 456 --comment "Fixed in PR #123"
```

## GitHub API Operations

### Recommended request headers

`User-Agent` is **required** — requests without it are rejected. `Accept` and the version header are strongly recommended.

```bash
curl \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  -H "User-Agent: my-app" \
  https://api.github.com/user
```

- `Authorization: Bearer <token>` works for fine-grained PATs, classic PATs, OAuth, GitHub App JWTs and `GITHUB_TOKEN`. (`Authorization: token <token>` also works for classic PATs, but a JWT **must** use `Bearer`.)
- `Accept: application/vnd.github+json` is the current recommended media type. `application/vnd.github.v3+json` is the legacy form.
- `X-GitHub-Api-Version` — pin this to avoid surprise breaking changes. Current version is `2026-03-10`; requests that omit the header default to `2022-11-28` (supported until March 2028).

### Using `gh api` instead of raw curl

`gh api` attaches auth and headers for you and handles pagination:

```bash
gh api repos/{owner}/{repo}                       # REST
gh api --paginate /user/repos                     # auto-paginate
gh api graphql -f query='query { viewer { login } }'   # GraphQL
```

### Common API Endpoints

- **User repos**: `GET /user/repos`
- **Create repo**: `POST /user/repos` (org: `POST /orgs/{org}/repos`)
- **Get repo**: `GET /repos/{owner}/{repo}`
- **Create issue**: `POST /repos/{owner}/{repo}/issues`
- **Create PR**: `POST /repos/{owner}/{repo}/pulls`
- **Merge PR**: `PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge`
- **Branch protection**: `PUT /repos/{owner}/{repo}/branches/{branch}/protection`

See `references/api-reference.md` for payloads, rate limits, and pagination.

## GitHub Actions

### Basic Workflow File

Pin third-party actions to a full commit SHA in security-sensitive repos. Current majors run on the Node 24 runtime.

```yaml
name: CI

on: [push, pull_request]

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v7

    - name: Setup Node.js
      uses: actions/setup-node@v7
      with:
        node-version: '24'

    - name: Install dependencies
      run: npm ci

    - name: Run tests
      run: npm test
```

### Current major versions of common official actions

| Action | Current major |
|---|---|
| `actions/checkout` | `v7` |
| `actions/setup-node` | `v7` |
| `actions/setup-python` | `v7` |
| `actions/github-script` | `v9` |
| `actions/upload-artifact` | `v7` |
| `actions/download-artifact` | `v8` |

Verify before pinning — majors move. `actions/github-script@v9` removed `require('@actions/github')`; use the injected `getOctokit` for extra clients.

### Workflow security

- **Grant least privilege** with `permissions:` at workflow or job level (e.g. `contents: read` by default, `issues: write` only where needed).
- **Use OIDC for cloud deploys** instead of long-lived secrets: add `permissions: id-token: write` and use the provider's official login action.
- **Never interpolate untrusted input into `run:` blocks** — `${{ github.event.* }}` fields like `title` and `body` are attacker-controlled. Pass them through `env:` and reference the shell variable instead.
- **Avoid `pull_request_target`** (and checking out fork code in it) — it runs with elevated privileges and enables "pwn request" attacks. GitHub blocks `pull_request_target` by default in public repositories.

## Security Best Practices

1. **Never commit secrets** - Use GitHub Secrets / OIDC for sensitive data
2. **Use .gitignore** - Exclude sensitive files and build artifacts
3. **Branch protection** - Enable branch protection rules (or rulesets) for the main branch
4. **Code scanning** - Enable GitHub Code Scanning for security analysis
5. **Dependabot** - Enable Dependabot for dependency updates
6. **Least-privilege tokens** - Prefer fine-grained PATs and scope them down

## Troubleshooting

### Common Issues

1. **Authentication failed** - Verify the token is valid and has the required scopes/permissions (`gh auth status`)
2. **Permission denied (403)** - Check repository access rights, and whether you hit a rate limit
3. **Resource not accessible by integration** - The token's permissions are insufficient (common with `GITHUB_TOKEN`)
4. **Merge conflicts** - Resolve conflicts before merging
5. **Large files** - Use Git LFS for large files

### Debugging Commands
```bash
# Check git status
git status

# View git log
git log --oneline

# Check remote URLs
git remote -v

# Test GitHub CLI authentication
gh auth status

# Check rate limit (does not consume your primary quota)
gh api /rate_limit
```

## Scripts

This skill includes Python scripts for common GitHub operations. See the `scripts/` directory for:
- `create_repo.py` - Create repositories programmatically
- `push_commit.py` - Commit and push changes

## References

See the `references/` directory for:
- `api-reference.md` - Complete GitHub API reference
- `permissions.md` - Required permissions for different operations
- `workflows.md` - Common GitHub workflows and patterns
