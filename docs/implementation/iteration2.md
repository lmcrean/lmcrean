# Implementation Plan - Iteration 2: GitHub API Integration

**Scope:** Automate data fetching with GitHub API and implement bidirectional sync
**Repository:** lmcrean/lmcrean (GitHub profile repo)
**Status:** 🟡 Planning Phase

---

## Objectives

1. Implement GitHub API integration to fetch merged PRs automatically
2. Implement PR override logic from lmcrean/developer-portfolio
3. Auto-categorize open PRs by age and status
4. Set up daily sync (every 24 hours)
5. Implement bidirectional sync for Developer Projects section
6. Sort issues by newest first in PIPELINE.md

---

## Technical Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────┐
│              GitHub API (GraphQL/REST)              │
│  - User's merged PRs across all repos              │
│  - User's open PRs with status/age                 │
│  - Issues from tracked repos (lmcrean, etc.)       │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│            PR Override Database Query               │
│     (lmcrean/developer-portfolio NeonDB)           │
│  - Custom PR titles                                 │
│  - Manual descriptions                              │
│  - Priority overrides                               │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│              Data Processing Layer                  │
│  - Merge API data with overrides                   │
│  - Categorize PRs (Action/Active/Inactive)         │
│  - Calculate relative dates                         │
│  - Sort issues by newest first                      │
│  - Format markdown                                  │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│         README.md + PIPELINE.md Update              │
│  - Preserve "Developer Projects" manual section    │
│  - Update "Open Source Contributions" section      │
│  - Update "Open PRs" section                        │
│  - Update tracked repo issues                       │
└─────────────────────────────────────────────────────┘
```

---

## GitHub API Integration

### Authentication
- Use GitHub Personal Access Token (PAT)
- Store in repository secrets: `GITHUB_TOKEN`
- Required scopes: `repo`, `read:user`, `read:org`

### GraphQL Queries

#### Query 1: Fetch Merged PRs
```graphql
query($username: String!, $limit: Int!) {
  user(login: $username) {
    pullRequests(
      first: $limit
      states: MERGED
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes {
        title
        url
        repository {
          nameWithOwner
        }
        mergedAt
        additions
        deletions
        comments {
          totalCount
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
      }
    }
  }
}
```

#### Query 2: Fetch Open PRs
```graphql
query($username: String!) {
  user(login: $username) {
    pullRequests(
      first: 50
      states: OPEN
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      nodes {
        title
        url
        repository {
          nameWithOwner
        }
        createdAt
        updatedAt
        additions
        deletions
        comments {
          totalCount
        }
        isDraft
        reviewDecision
        labels(first: 10) {
          nodes {
            name
          }
        }
      }
    }
  }
}
```

#### Query 3: Fetch Issues from Tracked Repos
```graphql
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    issues(
      first: 50
      states: OPEN
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      nodes {
        number
        title
        url
        createdAt
        updatedAt
        labels(first: 10) {
          nodes {
            name
          }
        }
        comments {
          totalCount
        }
      }
    }
  }
}
```

---

## PR Override Logic

### Study Source: lmcrean/developer-portfolio

Reference files to examine:
- Database schema: `pr_order`, `pr_labels`, `label_templates` tables
- API endpoints: `/api/tasks/order`
- Override logic implementation

### Override Structure

```typescript
interface PROverride {
  prUrl: string;
  customTitle?: string;
  customDescription?: string;
  hide?: boolean;
  priority?: number;
  customLabels?: string[];
}
```

### Application Rules

1. **Title Override:** If custom title exists, use it instead of GitHub PR title
2. **Hide Flag:** If `hide: true`, exclude from both README and PIPELINE
3. **Priority:** Higher priority PRs appear first within their category
4. **Custom Labels:** Add user-defined context labels (e.g., "Major contribution", "Bug fix")

### Database Query

```sql
SELECT
  pr_url,
  custom_title,
  custom_description,
  hide,
  priority,
  custom_labels
FROM pr_overrides
WHERE user_id = $1
```

---

## PR Categorization Logic

### Auto-Categorization Rules

```typescript
function categorizePR(pr: PullRequest): Category {
  const daysSinceUpdate = calculateDays(pr.updatedAt);

  // 🔴 Action Required
  if (pr.reviewDecision === 'CHANGES_REQUESTED') return 'ACTION_REQUIRED';
  if (pr.isDraft === false && pr.hasConflicts === true) return 'ACTION_REQUIRED';

  // ⚫ Inactive >30 days
  if (daysSinceUpdate > 30) return 'INACTIVE';

  // 🟡 Waiting on Reviewer (default for open PRs <30 days)
  return 'WAITING_ON_REVIEWER';
}
```

### Sorting Rules

**Within each category:**
1. Sort by priority (if override exists)
2. Then by `updatedAt` (most recent first)
3. Break ties by `createdAt`

**For issues in tracked repos:**
- Sort by `createdAt` newest first (as requested)

---

## Bidirectional Sync for Developer Projects

### Protection Mechanism

```markdown
<!-- BEGIN AUTO-GENERATED SECTION -->
... automated content ...
<!-- END AUTO-GENERATED SECTION -->

---

## Developer Projects

<!-- MANUAL SECTION - DO NOT AUTO-UPDATE -->
... user's manual content ...
<!-- END MANUAL SECTION -->
```

### Sync Algorithm

```typescript
function updateMarkdownFile(template: string, autoContent: string): string {
  const autoSectionRegex = /<!-- BEGIN AUTO-GENERATED SECTION -->[\s\S]*?<!-- END AUTO-GENERATED SECTION -->/;

  if (template.match(autoSectionRegex)) {
    // Replace only the auto-generated section
    return template.replace(
      autoSectionRegex,
      `<!-- BEGIN AUTO-GENERATED SECTION -->\n${autoContent}\n<!-- END AUTO-GENERATED SECTION -->`
    );
  }

  // If markers don't exist, create them and preserve existing content
  return addSectionMarkers(template, autoContent);
}
```

---

## GitHub Actions Workflow

### Workflow File: `.github/workflows/update-portfolio.yml`

```yaml
name: Update Portfolio

on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight UTC
  workflow_dispatch:      # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest

    permissions:
      contents: write
      pull-requests: read

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          npm install @octokit/graphql
          npm install pg  # For NeonDB connection

      - name: Fetch GitHub data
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
        run: node scripts/fetch-portfolio-data.js

      - name: Update README.md
        run: node scripts/update-readme.js

      - name: Update PIPELINE.md
        run: node scripts/update-pipeline.js

      - name: Commit changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          if git diff --quiet; then
            echo "No changes to commit"
            exit 0
          fi

          git add README.md PIPELINE.md
          git commit -m "chore: auto-update portfolio data [$(date +%Y-%m-%d)]"
          git push
```

---

## Script Implementation

### File Structure

```
lmcrean/lmcrean/
├── .github/
│   └── workflows/
│       └── update-portfolio.yml
├── scripts/
│   ├── fetch-portfolio-data.js     # Fetch from GitHub API + NeonDB
│   ├── update-readme.js            # Update README.md
│   ├── update-pipeline.js          # Update PIPELINE.md
│   └── utils/
│       ├── github-api.js           # GitHub GraphQL client
│       ├── database.js             # NeonDB connection
│       └── markdown-parser.js      # Markdown manipulation
├── data/
│   └── portfolio-cache.json        # Intermediate data storage
├── README.md
└── PIPELINE.md
```

### Sample Script: `fetch-portfolio-data.js`

```javascript
const { graphql } = require('@octokit/graphql');
const { Client } = require('pg');
const fs = require('fs');

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const DATABASE_URL = process.env.DATABASE_URL;
const USERNAME = 'lmcrean';

async function fetchMergedPRs() {
  const query = `
    query($username: String!) {
      user(login: $username) {
        pullRequests(first: 50, states: MERGED, orderBy: {field: UPDATED_AT, direction: DESC}) {
          nodes {
            title
            url
            repository { nameWithOwner }
            mergedAt
            additions
            deletions
            comments { totalCount }
          }
        }
      }
    }
  `;

  const result = await graphql(query, {
    username: USERNAME,
    headers: { authorization: `token ${GITHUB_TOKEN}` }
  });

  return result.user.pullRequests.nodes;
}

async function fetchPROverrides() {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();

  const result = await client.query(`
    SELECT pr_url, custom_title, custom_description, hide, priority
    FROM pr_overrides
    WHERE user_id = 'lmcrean'
  `);

  await client.end();
  return result.rows;
}

async function main() {
  const mergedPRs = await fetchMergedPRs();
  const openPRs = await fetchOpenPRs();
  const overrides = await fetchPROverrides();
  const trackedIssues = await fetchTrackedIssues(['lmcrean', 'marking-assistant']);

  // Apply overrides
  const processedPRs = applyOverrides(mergedPRs, overrides);

  // Save to cache
  fs.writeFileSync('data/portfolio-cache.json', JSON.stringify({
    mergedPRs: processedPRs,
    openPRs,
    trackedIssues,
    lastUpdated: new Date().toISOString()
  }, null, 2));

  console.log('Portfolio data fetched successfully');
}

main().catch(console.error);
```

---

## Implementation Checklist

### Phase 1: Setup Infrastructure
- [ ] Create `/scripts/` directory structure
- [ ] Create `/data/` directory for cache
- [ ] Install dependencies: `@octokit/graphql`, `pg`
- [ ] Create GitHub Actions workflow file

### Phase 2: Implement Data Fetching
- [ ] Create `github-api.js` utility
  - [ ] Implement merged PRs query
  - [ ] Implement open PRs query
  - [ ] Implement issues query for tracked repos
- [ ] Create `database.js` utility
  - [ ] Connect to NeonDB (developer-portfolio)
  - [ ] Query PR overrides
- [ ] Create `fetch-portfolio-data.js` main script
  - [ ] Combine API + database data
  - [ ] Apply override logic
  - [ ] Save to cache file

### Phase 3: Implement PR Categorization
- [ ] Create categorization logic
  - [ ] Detect "Action Required" PRs
  - [ ] Detect "Inactive >30 days" PRs
  - [ ] Default to "Waiting on Reviewer"
- [ ] Implement sorting within categories
  - [ ] Sort by priority (if override)
  - [ ] Then by updatedAt
- [ ] Sort issues by newest first (createdAt DESC)

### Phase 4: Implement Markdown Updates
- [ ] Create `markdown-parser.js` utility
  - [ ] Parse existing README.md
  - [ ] Identify auto-generated vs manual sections
  - [ ] Preserve manual content
- [ ] Create `update-readme.js` script
  - [ ] Generate "Approved in Production" markdown
  - [ ] Replace auto-generated section only
  - [ ] Preserve "Developer Projects" section
- [ ] Create `update-pipeline.js` script
  - [ ] Generate "Open PRs" sections (3 categories)
  - [ ] Generate tracked repo issues sections
  - [ ] Update metadata (counts, timestamp)

### Phase 5: Testing
- [ ] Test GitHub API queries manually
- [ ] Test NeonDB connection and override fetching
- [ ] Test markdown parsing and section replacement
- [ ] Test full pipeline locally: `node scripts/fetch-portfolio-data.js`
- [ ] Test workflow manually: trigger via `workflow_dispatch`

### Phase 6: Security & Secrets
- [ ] Add `GITHUB_TOKEN` to repository secrets
- [ ] Add `NEON_DATABASE_URL` to repository secrets
- [ ] Verify workflow permissions (contents: write)

### Phase 7: Documentation
- [ ] Document script usage in `/scripts/README.md`
- [ ] Add troubleshooting guide
- [ ] Document override database schema

### Phase 8: Deploy & Monitor
- [ ] Push workflow to repository
- [ ] Enable workflow in Actions tab
- [ ] Monitor first automatic run
- [ ] Verify README.md and PIPELINE.md updates
- [ ] Check for any errors in workflow logs

---

## Testing Strategy

### Local Testing Commands

```bash
# Test GitHub API fetch
node scripts/fetch-portfolio-data.js

# Test README update (dry run)
node scripts/update-readme.js --dry-run

# Test PIPELINE update (dry run)
node scripts/update-pipeline.js --dry-run

# Full pipeline test
npm run test:portfolio
```

### Manual Workflow Trigger

```bash
# Trigger via GitHub CLI
gh workflow run update-portfolio.yml

# View workflow status
gh run list --workflow=update-portfolio.yml

# View workflow logs
gh run view <run-id> --log
```

---

## Error Handling

### Graceful Degradation

1. **GitHub API Rate Limit:** Cache last successful fetch, skip update
2. **Database Connection Failure:** Continue without overrides, log warning
3. **Markdown Parse Error:** Preserve existing file, log error
4. **Git Conflict:** Abort commit, send notification

### Monitoring

- Log all errors to workflow output
- Send email notification on failure (via GitHub Actions)
- Keep last 7 days of portfolio cache as backup

---

## Success Criteria

- [ ] README.md "Open Source Contributions" section auto-updates daily
- [ ] PIPELINE.md "Open PRs" section categorizes correctly
- [ ] PR overrides from developer-portfolio database are applied
- [ ] Manual "Developer Projects" section remains untouched
- [ ] Issues in tracked repos are listed newest first
- [ ] Workflow runs successfully without manual intervention
- [ ] Changes are committed and pushed automatically

---

**Status:** 🟡 Ready for implementation after Iteration 1 completion
**Estimated Effort:** 2-3 days
**Dependencies:** Iteration 1 must be complete
