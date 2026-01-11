# Implementation Plan - Iteration 1: Manual Structure

**Scope:** Create static templates for README.md and PIPELINE.md with manual data entry
**Repository:** lmcrean/lmcrean (GitHub profile repo)
**Status:** 🔴 Planning Phase

---

## Objectives

1. Create README.md structure with two main sections
2. Create PIPELINE.md structure for active work tracking
3. Manually populate with sample data from screenshots
4. No automation - pure markdown templates

---

## README.md Structure

### Section 1: Open Source Contributions (Automated - Future)
*In Iteration 1: Manually populated, marked for future automation*

```markdown
# Open Source Contributions

## Approved in Production

> 🤖 **Auto-updated every 24 hours via GitHub API**
> Last sync: [timestamp]
> ⚠️ Manual edits to this section will be overridden on next sync

<!-- BEGIN AUTO-GENERATED SECTION -->

### rropen: terraform-provider-c: Fix: Add HTTP timeout to prevent Terraform from hanging indefinitely
**Go** | merged 6 days ago | `+11` `-8`
[View PR →](link)

### gocardless: woocommerce-gateway: Fix inconsistent subscriptions after cancellation with centralised logic
**PHP** | merged 3 weeks ago | 💬 6 | `+81` `-0`
[View PR →](link)

### google: guava: Fix resource leak in FileBackedOutputStream to prevent file handle exhaustion
**Java** | merged 10 weeks ago | `+96` `-1`
[View PR →](link)

### google: guava: Improve error messages for annotation methods on synthetic TypeVariables
**Java** | merged 15 weeks ago | 💬 3 | `+19` `-5`
[View PR →](link)

### google: guava: Fix `Iterators.mergeSorted()` to preserve stability for equal elements
**Java** | merged 17 weeks ago | 💬 2 | `+167` `-10`
[View PR →](link)

### google: guava: Add tests demonstrating `Iterators.mergeSorted()` instability
**Java** | merged 17 weeks ago | 💬 3 | `+134` `-0`
[View PR →](link)

### google: guava: Add test for putIfAbsent to catch implementations that incorrectly ignore null values
**Java** | merged 17 weeks ago | 💬 1 | `+14` `-0`
[View PR →](link)

### rropen: terraform-provider-c: Enhance(error handling): Improve flush loop and trigger handling in cscdm
**Go** | merged 17 weeks ago | 💬 3 | `+483` `-19`
[View PR →](link)

### stripe: pg-schema-diff: Fix: Support `GENERATED ALWAYS AS` columns to reduce migration failures (#212)
**Go** | merged 19 weeks ago | 💬 11 | `+275` `-37`
[View PR →](link)

### microsoft: TypeAgent: Return undefined instead of invalid action names for partial matches
**TypeScript** | merged 20 weeks ago | 💬 5 | `+10` `-10`
[View PR →](link)

### penpot: penpot: Implement milestone lock feature to prevent accidental deletion and bad actors
**Clojure, SQL** | merged 24 weeks ago | 💬 5 | `+292` `-17`
[View PR →](link)

<!-- END AUTO-GENERATED SECTION -->
```

### Section 2: Developer Projects (Manual Curation)
*Safe from automation - user maintains this*

```markdown
---

## Developer Projects

> 📝 **Manually curated**
> This section is protected from auto-updates

### Featured Work

**[Project Name](link)** - Brief description
Tech stack: React, TypeScript, Node.js
Status: 🚀 Live

**[Another Project](link)** - Brief description
Tech stack: Python, Django, PostgreSQL
Status: 🔧 In Development

### Recent Updates

- **[Update title](link)** - Short description (Date)
- **[Update title](link)** - Short description (Date)

---
```

---

## PIPELINE.md Structure

### Section 1: Open PRs

```markdown
# Open Source Contribution Pipeline

> **Last Updated:** 2026-01-11
> **Open PRs:** 6 | **Tracked Issues:** 0

This tracks my active open source work. For completed contributions, see [README](./README.md#open-source-contributions).

---

## 🔄 Open Pull Requests

### 🔴 Action Required
> PRs where I need to address feedback or resolve conflicts

*Currently none*

---

### 🟡 Waiting on Reviewer
> Active PRs submitted within last 30 days

#### stripe: stripe-go: Add context-aware logging interface and update logger usage
**Go** | opened 13 weeks ago | 💬 5 | `+560` `-16`
[View PR →](link)
**Status:** Awaiting maintainer review

#### google: guava: Add Gradle capability declarations to detect duplicate Guava artifacts
**Java** | opened 17 weeks ago | 💬 8 | `+126` `-0`
[View PR →](link)
**Status:** In review cycle

#### Shopify: cli: Make bind address configurable for app dev server
**TypeScript** | opened 17 weeks ago | 💬 4 | `+111` `-12`
[View PR →](link)
**Status:** Awaiting response on feedback

---

### ⚫ Waiting on Reviewer -- Inactive >30 days
> Stale PRs that may need follow-up or closure decision

#### GSK-Biostatistics: docorator: Add Code Coverage Infrastructure
**R** | opened 19 weeks ago | `+55` `-1`
[View PR →](link)
💭 **Next step:** Ping maintainers or close if no longer relevant

#### NVIDIA: cccl: Disable LDL/STL checks for CTK < 13.1 (nvbug 5243118)
**C++** | opened 20 weeks ago | 💬 13 | `+81` `-16`
[View PR →](link)
💭 **Next step:** Check if issue was resolved another way

#### neondatabase: neon: utils: use `ShardIdentity` in `postgres_client.rs` for improved type safety
**Rust** | opened 22 weeks ago | 💬 3 | `+390` `-164`
[View PR →](link)
💭 **Next step:** Review recent repo activity, consider closing

---
```

### Section 2: Issues Tracking

```markdown
## 📋 Issues

### Enterprise Backlog
> External issues I'm interested in contributing to

*To be populated with interesting issues from major OSS projects*

Example format:
- [ ] **[kubernetes/kubernetes#12345](link)** - Brief description
  🏷️ `good-first-issue` `documentation` | 🔥 High interest | 📊 Medium difficulty

---

### Developer Projects
> Issues from repos I maintain or actively track

#### Tracked Repositories
- lmcrean (personal projects)
- marking-assistant (private project)

---

#### lmcrean/lmcrean
*Profile repository - issues tracked here*

*Currently no open issues*

---

#### lmcrean/marking-assistant
*Private repository - issues tracked here*

*To be populated when tracking is enabled*

---
```

### Footer

```markdown
---

## 📖 Legend

**PR Status Indicators:**
- 🔴 **Action Required** - Needs my attention (conflicts, requested changes)
- 🟡 **Waiting on Reviewer** - Active, submitted <30 days ago
- ⚫ **Inactive >30 days** - Stale, may need follow-up or closure

**Issue Metadata:**
- 🔥 Interest level (High/Medium/Low)
- 📊 Difficulty estimate (High/Medium/Low)
- 🏷️ Repository labels
- 💬 Comment count
- `+X` `-Y` Line changes (additions/deletions)

---

**Completed Work:** [View merged contributions →](./README.md#open-source-contributions)
**Last Updated:** Manual maintenance (automation planned for Iteration 2)
```

---

## Data Sources for Iteration 1

### Merged PRs (from screenshot "Approved in Production")
1. rropen/terraform-provider-c - HTTP timeout fix (6 days)
2. gocardless/woocommerce-gateway - Subscriptions fix (3 weeks)
3. google/guava - Resource leak fix (10 weeks)
4. google/guava - Error messages improvement (15 weeks)
5. google/guava - mergeSorted stability fix (17 weeks)
6. google/guava - mergeSorted test addition (17 weeks)
7. google/guava - putIfAbsent test (17 weeks)
8. rropen/terraform-provider-c - Error handling enhancement (17 weeks)
9. stripe/pg-schema-diff - GENERATED ALWAYS AS support (19 weeks)
10. microsoft/TypeAgent - Undefined return fix (20 weeks)
11. penpot/penpot - Milestone lock feature (24 weeks)

### Open PRs (from screenshot "Pending approval")
1. stripe/stripe-go - Context-aware logging (13 weeks, 5 comments)
2. google/guava - Gradle capability declarations (17 weeks, 8 comments)
3. Shopify/cli - Bind address configuration (17 weeks, 4 comments)
4. GSK-Biostatistics/docorator - Code coverage (19 weeks)
5. NVIDIA/cccl - LDL/STL checks disable (20 weeks, 13 comments)
6. neondatabase/neon - ShardIdentity usage (22 weeks, 3 comments)

---

## Implementation Checklist

### Phase 1: Repository Setup
- [ ] Clone/access lmcrean/lmcrean repository
- [ ] Create branch `claude/github-profile-portfolio-qYpki`
- [ ] Create `/docs/implementation/` directory structure

### Phase 2: README.md Creation
- [ ] Read existing README.md (if exists)
- [ ] Create "Open Source Contributions" section
  - [ ] Add "Approved in Production" subsection
  - [ ] Add auto-update warning comments
  - [ ] Add all 11 merged PRs from screenshot data
- [ ] Create "Developer Projects" section
  - [ ] Add manual curation notice
  - [ ] Add placeholder project entries

### Phase 3: PIPELINE.md Creation
- [ ] Create new PIPELINE.md file
- [ ] Add metadata header (last updated, counts)
- [ ] Add "Open Pull Requests" section
  - [ ] Add "Action Required" (empty for now)
  - [ ] Add "Waiting on Reviewer" with 3 recent PRs
  - [ ] Add "Inactive >30 days" with 3 stale PRs
- [ ] Add "Issues" section
  - [ ] Add "Enterprise Backlog" (placeholder)
  - [ ] Add "Developer Projects" with tracked repos
- [ ] Add Legend and footer

### Phase 4: Documentation
- [ ] Create this iteration1.md document
- [ ] Create iteration2.md outline
- [ ] Create iteration3.md outline

### Phase 5: Commit and Review
- [ ] Review both files for accuracy
- [ ] Commit with message: `docs: add iteration 1 implementation plan for profile portfolio`
- [ ] Create README.md and PIPELINE.md from templates
- [ ] Commit with message: `feat: add manual portfolio tracking structure`
- [ ] Push to branch

---

## Notes for Iteration 2

- GitHub API integration needed for automated PR fetching
- PR override logic from lmcrean/developer-portfolio to be studied
- Bidirectional sync mechanism for Developer Projects section
- Auto-categorization of PRs by age and status
- Daily cron job for updates (every 24 hours)

---

## Notes for Iteration 3

- (To be defined after Iteration 2 completion)
- Possible enhancements:
  - Issue auto-tracking for watched repos
  - Webhook integration for real-time updates
  - Statistics/analytics dashboard
  - Integration with GitHub Issues workflow

---

**Status:** ✅ Ready for implementation
**Next Action:** Execute Phase 1 - Repository Setup
