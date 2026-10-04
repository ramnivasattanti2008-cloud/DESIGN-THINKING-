# MIRROR AI Developer & Seat Cheat Sheet

Quick reference guide for developers and AI seats working on MIRROR.

---

## 1. Quick Seat Rules
- **Stay in your lane:** Check `docs/ROLES.md`. Only touch your folder.
- **Never push to `main`:** Branch format is `<seat>/<short-task>`.
- **Keep PRs small:** Target < 300 lines per PR.
- **Update your status file:** Always document what you finished, what's in progress, and files touched in `docs/status/<seat>.md` before ending your turn.

---

## 2. Essential Commands

### Testing
```bash
# Run all tests with unittest
python -m unittest discover -s tests -p "test_*.py" -v

# Run verification invariant test specifically
python -m unittest tests/smoke/test_verification_invariant.py -v
```

### Git Worktrees (Multi-Seat Development)
```bash
# Check current worktree status
git worktree list

# Rebase seat branch on latest main
git pull origin main --rebase
```

### UI Preview
- Open `src/ui/web_preview/index.html` or `public/index.html` in any browser to interactively test all 6 core mobile screens.

---

## 3. The MIRROR Golden Rule
> **"No task is marked complete unless verification confirms the result."**
> Confidence $\ge 0.85$ required. Ambiguous states must demote to `UNCERTAIN_REVIEW`.
