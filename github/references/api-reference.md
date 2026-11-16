# GitHub API Reference

Base URL: `https://api.github.com` (GraphQL: `https://api.github.com/graphql`)

## Authentication

`User-Agent` is **required** on every request (requests without it are rejected). `Accept` and `X-GitHub-Api-Version` are strongly recommended.

```bash
curl \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  -H "User-Agent: my-app" \
  https://api.github.com/user
```

- **`Authorization: Bearer <token>`** — the recommended form. Works for fine-grained PATs, classic PATs, OAuth access tokens, GitHub App JWTs and `GITHUB_TOKEN`. `Authorization: token <token>` also works for classic PATs, but a **JWT must** use `Bearer`.
- **`Accept: application/vnd.github+json`** — current recommended media type. `application/vnd.github.v3+json` is the legacy form still accepted. Custom types use `application/vnd.github.PARAM+json` (e.g. `.diff`, `.patch`, `.raw`, `.sha`).
- **`X-GitHub-Api-Version`** — pin an API version to avoid surprise breaking changes. Current version is **`2026-03-10`**. Requests that omit the header default to `2022-11-28` (supported until March 10, 2028). An unsupported version returns `410 Gone`.

### GitHub App installation token
```bash
curl \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  -H "User-Agent: my-app" \
  https://api.github.com/app/installations
```

## Repository Endpoints

### Create Repository
```bash
POST /user/repos              # for the authenticated user
POST /orgs/{org}/repos        # for an organization

# Request body (common fields)
{
  "name": "repo-name",              # required
  "description": "Repository description",
  "private": false,
  "auto_init": true,                # create an initial commit with a README
  "gitignore_template": "Python",
  "license_template": "mit"         # SPDX id
}
```
Returns `201`. Classic PAT: `public_repo` or `repo`. Fine-grained PAT: "Administration" (write) or "Repository creation" (write).

### Get Repository
```bash
GET /repos/{owner}/{repo}

# Response includes:
# - html_url, clone_url, ssh_url
# - default_branch
# - permissions
# - visibility (public/private)
```

### List User Repositories
```bash
GET /user/repos
# Parameters: type (all, owner, member), sort, direction, per_page, page
```

## Branch Operations

### Get Branch
```bash
GET /repos/{owner}/{repo}/branches/{branch}
```

### Create Branch
```bash
POST /repos/{owner}/{repo}/git/refs

# Request body
{
  "ref": "refs/heads/feature-branch",
  "sha": "commit_sha"
}
```

## Commit Operations

### Create Commit
```bash
POST /repos/{owner}/{repo}/git/commits

{
  "message": "Commit message",
  "tree": "tree_sha",
  "parents": ["parent_sha"]
}
```

### Get Commit
```bash
GET /repos/{owner}/{repo}/commits/{sha}
```

## Pull Request Endpoints

### Create Pull Request
```bash
POST /repos/{owner}/{repo}/pulls

{
  "title": "PR Title",        # required unless "issue" is used
  "body": "PR Description",
  "head": "feature-branch",   # required
  "base": "main",             # required
  "draft": false
}
```
Returns `201`. Fine-grained PAT: "Pull requests" (write).

### List Pull Requests
```bash
GET /repos/{owner}/{repo}/pulls
# Parameters: state (open, closed, all), sort, direction
```

### Merge Pull Request
```bash
PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge

{
  "commit_title": "Merge PR",
  "commit_message": "Merge PR",
  "merge_method": "merge|squash|rebase",
  "sha": "head_commit_sha"
}
```
Returns `200 {sha, merged, message}`. Fine-grained PAT: "Contents" (write).

> **Note:** GitHub recommends the asynchronous merge endpoint `PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge-async` instead. The synchronous endpoint above does not support stacked pull requests or merging via a merge queue. `merge-async` accepts the same `merge_method` values plus `merge_action` (`default`|`direct_merge`|`merge_queue`) and `bypass_rules`, and you poll `GET .../merge-async/{uuid}` for the result.

## Issues Endpoints

### Create Issue
```bash
POST /repos/{owner}/{repo}/issues

{
  "title": "Issue title",
  "body": "Issue description",
  "labels": ["bug", "enhancement"],
  "assignees": ["username"]
}
```

### List Issues
```bash
GET /repos/{owner}/{repo}/issues
# Parameters: state, labels, sort, direction
```

## Branch Protection

Branch protection is configured through the REST API or repository/organization **rulesets** — there is no `.github/branch-protection.yml` file.

```bash
PUT /repos/{owner}/{repo}/branches/{branch}/protection

{
  "required_status_checks": {
    "strict": true,
    "checks": [{ "context": "ci/tests", "app_id": null }]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```
Requires admin permission (fine-grained PAT: "Administration" write). `required_status_checks`, `enforce_admins`, `required_pull_request_reviews`, and `restrictions` are all required fields — pass `null` to disable one. Prefer `checks` over `contexts`, which is being closed down.

## Webhooks

### Create Webhook
```bash
POST /repos/{owner}/{repo}/hooks

{
  "name": "web",
  "active": true,
  "events": ["push", "pull_request"],
  "config": {
    "url": "https://example.com/webhook",
    "content_type": "json"
  }
}
```

## Rate Limiting

Primary limits:

| Caller | Limit |
|---|---|
| Unauthenticated | 60 requests/hour (per originating IP) |
| Authenticated (PAT / OAuth / user-to-server token) | 5,000 requests/hour |
| GitHub App installation token | 5,000/hour, scaling to max 12,500/hour (with the repo/org counts) |
| GitHub App or OAuth app owned by a GitHub Enterprise Cloud org | 15,000/hour |
| `GITHUB_TOKEN` in GitHub Actions | 1,000 requests/hour per repo (15,000/hour under GitHub Enterprise Cloud) |
| Git LFS (separate bucket) | 300 req/min unauthenticated, 3,000 req/min authenticated |

- **Check limits**: `GET /rate_limit` — this call does **not** count against your primary limit.
- **Response headers are authoritative**: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`, `x-ratelimit-used`, `x-ratelimit-resource`. If they disagree with `GET /rate_limit`, trust the headers.
- **Secondary rate limits** apply in addition (concurrent request caps, point-based per-minute caps on REST/GraphQL, and content-creation caps). There is no endpoint to inspect them. When hit, you get `403`/`429` with a `retry-after` header (or a message) — honor it and back off exponentially.
- Exceeding a limit returns `403` or `429` with `x-ratelimit-remaining: 0`.

## Common Response Codes

- `200` - Success
- `201` - Created
- `204` - No Content
- `304` - Not Modified
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden (also used for rate limits and insufficient scope)
- `404` - Not Found (also returned when you lack access)
- `410` - Gone (unsupported API version)
- `422` - Validation Failed
- `429` - Too Many Requests (rate limit)

## Pagination

REST list endpoints return **30 items per page** by default. `per_page` max is **100** (larger values are silently clamped, not rejected).

```bash
# Link header in the response (present only when there is more than one page)
Link: <https://api.github.com/user/repos?page=2>; rel="next",
      <https://api.github.com/user/repos?page=5>; rel="last"

# Query parameters
?page=2&per_page=100
```
`rel` may be `next`, `prev`, `first`, `last`. Some endpoints use `before`/`after` or `since` cursors instead of `page`. With the CLI, `gh api --paginate` collects all pages for you.

## GraphQL API

GitHub also provides a GraphQL API at `https://api.github.com/graphql` (separate rate limit, calculated in points). Authenticate the same way; a JWT requires `Authorization: Bearer`.

```graphql
query {
  repository(owner: "octocat", name: "Hello-World") {
    name
    description
    stargazers {
      totalCount
    }
  }
}
```
```bash
gh api graphql -f query='query { viewer { login } }'
```
