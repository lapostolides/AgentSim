---
name: update-docs
description: Update ARCHITECTURE.md documentation files in src directories after code changes
user_invocable: true
---

# update-docs

Update ARCHITECTURE.md documentation files to reflect recent code changes.

## When to Use
- After adding new files to any src/agentsim/ directory
- After significantly modifying existing files (new exports, changed patterns, new data flow)
- After adding a new subdirectory under src/agentsim/
- NOT needed for: bug fixes, minor refactors, test-only changes, config changes

## Process

1. Identify which directories were affected by recent changes:
   - Run `git diff --name-only HEAD~1` (or appropriate range) to find changed files
   - Map changed files to their parent directories under src/agentsim/

2. For each affected directory that has an ARCHITECTURE.md:
   - Read the current ARCHITECTURE.md
   - Read the changed .py files in that directory
   - Update the ARCHITECTURE.md to reflect:
     - New files added (add a ### section)
     - Changed exports or key functions
     - New data flow connections
     - Removed files (remove their section)
   - Keep the existing format and structure
   - Do NOT rewrite sections that weren't affected

3. For affected directories that DON'T have an ARCHITECTURE.md yet:
   - Create one following the standard format (see below)

4. Commit the updated docs: `docs: update ARCHITECTURE.md for {directories}`

## Standard Format

```markdown
# {Directory Name}

> One-sentence summary of this package's responsibility.

## Files

### filename.py
Brief description and key exports.

## Data Flow
How data moves through this package.

## Key Patterns
Design patterns used.

## Dependencies
What this depends on and what depends on it.
```

## Important
- Read the actual code before updating docs — don't guess
- Keep docs concise (150-300 lines max per file)
- Focus on what a developer needs to know in a fresh session
- Don't document __pycache__ or test files
