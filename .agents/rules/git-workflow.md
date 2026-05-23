# Rule: Git Workflow

## Never push directly to main

All changes MUST go through feature branches and pull requests.

### Requirements

1. **Feature branches only** — Create a descriptive branch (e.g. `feat/admin-light-theme`, `fix/photo-proxy`) for every change.
2. **Never commit to main** — `main` is protected. No direct commits, no direct pushes.
3. **User creates the PR** — After pushing to the feature branch, the user decides when to create and merge the PR.
4. **No auto-deploy** — Pushing to a feature branch does NOT trigger deployment. Only merging to `main` deploys.

### Correct workflow

```bash
# ✅ Create feature branch
git checkout -b feat/my-feature

# ✅ Commit and push to feature branch
git add -A
git commit -m "feat: description"
git push origin feat/my-feature

# ✅ Then tell the user the branch is ready for PR
```

### Forbidden

```bash
# ❌ Never push directly to main
git push origin main

# ❌ Never commit on main
git checkout main && git commit

# ❌ Never create PRs without user approval
gh pr create --merge
```
