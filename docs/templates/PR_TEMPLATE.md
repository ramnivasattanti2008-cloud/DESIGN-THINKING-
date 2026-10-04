# Pull Request Template

## Description
- **Seat:** [ag-a | ag-b | ag-c | studio-a | studio-b | claude]
- **Branch:** `<seat>/<short-task>`
- **Task ID:** T-XXX (from `docs/TASKS.md`)
- **Summary of Changes:** [1-3 sentences explaining what was built or changed]

## Lane & File Ownership Check
- [ ] Only touched files assigned to my seat in `docs/ROLES.md`.
- [ ] No shared files (root configs, manifests) modified unless assigned by `claude`.
- [ ] Change size is bounded (< 300 lines of code).

## Integrity & Verification Checklist
- [ ] Code has been executed and verified locally (no unverified claims).
- [ ] All tests pass (`python -m unittest discover tests`).
- [ ] No hardcoded secrets, API keys, or tokens committed.
- [ ] Updated my seat's status file (`docs/status/<seat>.md`).
