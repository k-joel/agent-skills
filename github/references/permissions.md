# GitHub Permissions Guide

Two token types exist. **GitHub recommends fine-grained PATs over classic PATs whenever possible.**

| | Classic PAT | Fine-grained PAT |
|---|---|---|
| Recommendation | Fallback | **Preferred** |
| Granularity | Broad scopes | Per-repository + per-permission |
| Expiry | Optional; tokens unused for 1 year are auto-revoked | Defaults to **30 days**; `expires_in` accepts 1–366 days or `none` |
| SAML SSO | Needs a separate authorization step after creation | Authorized for SSO **at creation time** |
| Limit | — | 50 tokens per user |

## Classic PAT Scopes

### Repository Scopes
- **repo** - Full control of private and public repositories (implies `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`)
- **repo:status** - Access commit status
- **repo_deployment** - Access deployment status
- **public_repo** - Access public repositories only
- **repo:invite** - Accept repository invitations
- **security_events** - Read and write security events
- **delete_repo** - Delete repositories

### Hook and Key Scopes
- **admin:repo_hook** / **write:repo_hook** / **read:repo_hook** - Repository hooks
- **admin:public_key** / **write:public_key** / **read:public_key** - Public keys
- **admin:org_hook** - Organization hooks
- **admin:gpg_key** / **write:gpg_key** / **read:gpg_key** - GPG keys

### Organization Scopes
- **admin:org** - Full organization administration
- **write:org** - Read and write organization membership, projects, and teams
- **read:org** - Read organization membership, projects, and teams

### User Scopes
- **user** - Update ALL user data (implies `user:email` and `user:follow`)
- **read:user** - Read user profile data
- **user:email** - Access user email addresses
- **user:follow** - Follow and unfollow users

### Other Scopes
- **gist** - Create, update, delete, and list gists
- **notifications** - Access notifications
- **project** - Read and write projects
- **read:project** - Read projects only
- **write:packages** - Upload packages
- **read:packages** - Download packages
- **delete:packages** - Delete packages
- **workflow** - Add and update GitHub Actions workflow files
- **read:audit_log** - Read audit log data
- **codespace** - Full control of codespaces
- **offline_access** - Refresh tokens for OAuth apps

> Scopes normalize upward: granting `user` also grants `user:email` and `user:follow`; `repo` grants its sub-scopes. Request the narrowest scope that does the job.

## Minimum Required Scopes for Common Operations

### Create Public Repository
- `public_repo` (or `repo` for both public and private)

### Create Private Repository
- `repo`

### Push Code to Repository
- `repo` (for private repos)
- `public_repo` (for public repos)

### Create Issues
- `repo` (for private repos)
- `public_repo` (for public repos)

### Create Pull Requests
- `repo` (for private repos)
- `public_repo` (for public repos)

### Read Repository Contents
- `repo` (for private repos)
- No scope needed for public repos

### Manage Organization Repositories
- `admin:org` or `write:org`

### Access User Email
- `user:email`

## Fine-grained Personal Access Tokens

Fine-grained PATs grant per-repository and per-permission access. The **Metadata** repository permission is always granted and is **read-only** — every other permission is `read` or `read`/`write`.

### Repository Access (which repos the token can see)
- **No access** - Cannot access the repository
- **Read-only** - Can read repository contents
- **Read and write** - Can read and write to repository
- **Administrator** - Full administrative access

Select either "All repositories" or "Only select repositories".

### Repository Permissions
- **Administration** - Repository administration (also required to create repos, with "Repository creation")
- **Repository creation** - Create new repositories
- **Contents** - Read/write repository contents (also needed to merge PRs)
- **Metadata** - Read-only repository metadata (always granted)
- **Pull requests** - Read/write pull requests
- **Issues** - Read/write issues
- **Actions** - Read/write GitHub Actions
- **Secrets** - Read/write secrets
- **Environments** - Read/write environments
- **Pages** - Read/write GitHub Pages
- **Discussions** - Read/write discussions
- **Checks** - Read/write checks
- **Workflows** - Read/write GitHub Actions workflow files

### Organization Permissions
- **Members** - Read/write organization members
- **Projects** - Read/write organization projects

## GitHub App Permissions

GitHub Apps request the same per-permission model as fine-grained PATs (Contents, Issues, Pull requests, Administration, Metadata, etc.) plus organization permissions such as **Members** and **Projects**. Installation tokens inherit only the permissions the app was granted, and the app must be installed on the target repository/organization.

## Best Practices

### 1. Principle of Least Privilege
- Grant only the permissions needed for the task
- Use fine-grained tokens when possible
- Regularly review and rotate tokens

### 2. Token Security
- Never commit tokens to version control
- Use environment variables (`GH_TOKEN`/`GITHUB_TOKEN`) or secret managers
- Set expiration dates on tokens (fine-grained default is 30 days)
- Monitor token usage
- In GitHub Actions prefer the built-in `GITHUB_TOKEN` + `permissions:` over a PAT

### 3. Organization Security
- Use GitHub Organizations for team management
- Implement branch protection rules (or rulesets)
- Require code review for sensitive branches
- Enable security scanning

### 4. Audit and Monitoring
- Regularly review audit logs (`read:audit_log` scope)
- Monitor for unusual activity
- Set up alerts for security events
- Review installed GitHub Apps

## Common Permission Errors

### "Resource not accessible by integration"
The token (usually a `GITHUB_TOKEN` or GitHub App installation token) lacks the required permission. Add the permission to the workflow `permissions:` key or the app's permission set.

### "Bad credentials"
Token is invalid or expired. Generate a new token.

### "Requires authentication"
No token provided or token doesn't have required scope.

### "Not found" (404)
Resource doesn't exist **or** the token lacks access — GitHub returns 404 instead of 403 to avoid leaking existence.

### "SAML SSO enforcement" / 403 with `X-GitHub-SSO`
A classic PAT is not authorized for a SAML SSO organization. Follow the authorization URL in the `X-GitHub-SSO` response header, or use a fine-grained token (authorized at creation).

## Token Management Commands

### Check Token Scopes
The response to any API call includes an `X-OAuth-Scopes` header (classic PATs). `GET /rate_limit` is a cheap way to check this and does not consume your primary quota.

```bash
curl -I \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "User-Agent: my-app" \
  https://api.github.com/rate_limit
# inspect the X-OAuth-Scopes response header
```

### Manage Tokens
GitHub → Settings → Developer settings → Personal access tokens
- **Fine-grained tokens** → "Generate new token (fine-grained)"
- **Tokens (classic)** → "Generate new token (classic)"
