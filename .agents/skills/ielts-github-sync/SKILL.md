---
name: ielts-github-sync
description: Synchronize saved IELTS Coach Tata milestones and hourly backups to its authorized private GitHub repository. Use for this project's scheduled sync, sync retry, and milestone publication.
---

# IELTS GitHub Sync

Locate the repo containing `AGENTS.md`, `scripts/hourly_sync.py` and `materials.json`. Read [project policy](../../../AGENTS.md) and [sync operations](../../../scripts/README.md). The authorized destination is the private `octhariaus-tata/ielts-coach-tata` repository, branch `main`.

The user authorizes automatic synchronization after important saved milestones and once each hour on this laptop. Missing screenshot/recording rehearsal does not block backup: preserve its honest pending status. A GitHub backup is not proof of learning readiness or improved IELTS scores.

Run one bounded attempt:

```sh
python3 scripts/hourly_sync.py --root PROJECT_ROOT --message "Simpan milestone IELTS Coach Tata"
```

The helper locks local session mutations and Git operations, validates persisted session/feedback data and correction references, rebuilds derived summaries, then uses the safe Git synchronizer. It checks the remote and fast-forwards a clean clone; it commits/pushes permitted saved changes. Read the JSON result and local `.local/scheduled-sync.json` report. Report synchronization only for `status: synced` plus `remote_verified: true`.

- A busy writer/Git operation defers this run. Do not bypass a lock or repeat in a loop.
- Offline, authentication failure, a corrupt source, divergent history, or local changes with a newer remote preserve local files. Stop this attempt and surface the specific failure; retry at the next scheduled run or after the coach resolves it.
- This workflow preserves attempts, answers and feedback. Do not regrade, invent progress, play audio, complete rehearsal, rewrite policy, discard changes, reset, force-push, expose credentials, change accounts, or broaden the remote/allowlist.
- Credentials and device readiness stay local. The skill travels with the repo; the hourly schedule is configured in Codex for this laptop and needs its local files, Git access, computer and app to be available.

Scheduled runs stay quiet for unchanged or routine successful state and busy deferrals. Notify when failure, conflict, or required user action changes the actionable state. Milestone runs may give a brief confirmation with the verified commit when useful. Use the existing credential setup; a changed authorization/access requirement is handled by the user.
