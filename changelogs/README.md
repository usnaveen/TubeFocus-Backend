# Backend Changelogs

This directory contains changelog entries documenting significant changes to the TubeFocus backend.

## Format

Each changelog entry follows this format:

```markdown
# [Version/Date] - Feature/Change Name

**Type:** Feature | Bug Fix | Refactor | Performance | Security | Documentation  
**Date:** YYYY-MM-DD  
**Author:** Name  
**Branch:** branch-name  
**PR:** #number (if applicable)

## Summary

Brief description of the change.

## Changes Made

- Detailed change 1
- Detailed change 2
- Detailed change 3

## Impact

- Who/what is affected by this change
- Performance implications
- Breaking changes (if any)

## Testing

- How this was tested
- Test results

## Rollback Plan

- How to revert if needed

## Related Issues/PRs

- Links to related issues
- Links to related PRs
```

## Naming Convention

Changelog files should be named: `YYYY-MM-DD-brief-description.md`

Examples:
- `2026-01-22-cursor-rules-and-mcp-setup.md`
- `2026-01-22-git-workflow-improvements.md`
- `2026-01-15-transcript-approach-change.md`

## When to Create a Changelog

Create a changelog entry for:
- ✅ New features
- ✅ Significant refactoring
- ✅ Architecture changes
- ✅ API changes (breaking or major)
- ✅ Security fixes
- ✅ Performance improvements
- ✅ Deployment changes
- ✅ Dependency updates (major versions)

Don't create for:
- ❌ Minor bug fixes
- ❌ Typo corrections
- ❌ Code formatting
- ❌ Minor documentation updates

## Automation

Cursor AI is configured to:
1. Detect significant changes
2. Prompt for changelog creation
3. Generate changelog draft
4. Save to this directory

## Integration with Git

Each significant change should:
1. Be developed in a feature branch
2. Have a changelog entry created
3. Be committed with the feature
4. Include changelog in the PR

## Example Workflow

```bash
# 1. Create feature branch
git checkout -b feature/new-scoring-algorithm

# 2. Make changes
# ... code changes ...

# 3. Create changelog
# Cursor AI will prompt or you can manually create

# 4. Commit everything
git add .
git commit -m "feat: implement new scoring algorithm

See changelogs/2026-01-22-new-scoring-algorithm.md for details"

# 5. Push and create PR
git push -u origin feature/new-scoring-algorithm
```

## Archive Policy

Changelogs are never deleted but may be moved to `changelogs/archive/YYYY/` after one year.
