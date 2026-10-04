# Setup guide for Ram

The repo files are done. These are the steps only you can do, because they happen inside your own accounts. Tool menus change often, so if a label here doesn't match what you see, go with what's on screen.

## 1. Merge the setup branch

Open the pull request for `setup/ai-coordination` on GitHub and merge it into `main`. Until it's on `main`, the other tools won't see the rules.

## 2. Give each tool its seat

Every tool needs to know who it is. Start each new session with one line:

- Antigravity account 1: "You are seat `ag-a`. Read AGENTS.md and start."
- Antigravity account 2: "You are seat `ag-b`. Read AGENTS.md and start."
- Antigravity account 3: "You are seat `ag-c`. Read AGENTS.md and start."
- AI Studio account 1: "You are seat `studio-a`." then paste AGENTS.md, ROLES.md and PROJECT_STATE.md.
- AI Studio account 2: "You are seat `studio-b`." then paste the same three files.

Antigravity should open the cloned repo as its workspace. As far as I know it picks up AGENTS.md and GEMINI.md on its own, but tell it to read them anyway the first time.

AI Studio can't see the repo by itself. Treat it as a thinking and drafting space. You paste in what it needs, and whatever it produces goes onto a branch and into a pull request like everything else.

## 3. Student Developer Pack

Check that Copilot is switched on in your GitHub account settings. Use it for autocomplete only. The pack has other perks (hosting credits, domain, tools). Look through them once you know what the project needs, rather than signing up for everything today.

## 4. Clone once per machine

```
git clone https://github.com/ramnivasattanti2008-cloud/design-thinking-
```

Each tool should work from its own branch. If two tools run on the same machine, give each its own clone folder so they don't fight over the working directory.

## 5. Secrets

Never paste API keys into prompts that get committed. Put them in a local `.env` file. It's already in `.gitignore`.

## 6. Daily routine

1. Tell the tools which task they're on (from `docs/TASKS.md`).
2. Let them work on their own branches.
3. At the end, ask each one to update its file in `docs/status/`.
4. Ask Claude to review the PRs. You merge.
