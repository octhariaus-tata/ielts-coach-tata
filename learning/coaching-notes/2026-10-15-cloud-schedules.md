# Cloud schedule handoff — 15 October 2026, Asia/Jakarta

Operational configuration record, not learner progress. Source: owner requests and verified automation UI/tool results in the 15 October scheduling chat.

## Current schedules

| Purpose | Schedule (Asia/Jakarta) | Execution and status | Identifier |
| --- | --- | --- | --- |
| Belajar IELTS Tata — weekdays, siap 09.00 — cloud | Monday–Friday, 08:45; around 09:00 delivery is a target | Cloud, active; first scheduled output untested | `6ad0247556588191b8b10f04251563c0` |
| Prepare Tata’s next IELTS lesson — cloud | Sunday–Thursday, 19:00, for the next weekday | Cloud, active; first preparation/artifact creation untested | `6ad023d5f92c8191b6b8b3124da6377f` |
| Original local morning card | Monday–Friday, 08:45 | Paused on this laptop to prevent duplicates | `kartu-ielts-tata-weekdays-siap-09-00` |
| Original local evening preparation | Sunday–Thursday, 19:00 | Paused on this laptop to prevent duplicates | `prepare-tata-s-next-ielts-lesson` |
| IELTS GitHub sync tiap jam | Every hour | Local, active, with private-destination verification guard | `ielts-github-sync-tiap-jam` |

Cloud tasks are visible in the signed-in account's [Scheduled page](https://chatgpt.com/scheduled). Setup and source-access checks are in the [cloud setup chat](https://chatgpt.com/c/6ad023b6-3bb8-83ec-a4ef-5a75b5eaf558). Settings and active task entries were inspected directly. The other laptop has not been inspected; do not claim it has the same local automation configuration.

## Source and output limits

- Both cloud tasks use fresh, read-only GitHub state from `octhariaus-tata/ielts-coach-tata`, `main`. Required project files and the current lesson record were fetched in the cloud setup session. Remote records can omit unsynced laptop work.
- New lessons follow the current 40-minute, teaching-first preference. Preserve active lesson IDs, budgets, pending prompts and responses; do not start, advance, grade or complete sessions during scheduled preparation. Friday recap uses real recorded evidence only.
- Evening preparation maintains one primary and one backup. New cloud output is an **unregistered cloud draft**, intended as private downloadable JSON artifacts when supported. Actual scheduled artifact generation is untested. The local coach must validate source freshness, content, answers, schema and packet registration before using a draft. Cloud artifacts do not automatically enter this repository or another laptop.
- No repository writes, learner-record mutations, audio playback, submissions, account/permission changes, or answer/transcript disclosure in notifications are permitted in the cloud task prompts.
- The local hourly backup cannot be moved to the cloud as an equivalent operation: cloud tasks cannot read unsynced laptop files. Local credentials, device readiness and local scheduler configuration do not travel with Git.
- Do not create duplicate cloud schedules from this note. Inspect the existing task IDs in Scheduled. Check each laptop for old local schedules separately before enabling work there.

## Repository visibility and publication authorization

The original authorization named a **private** repository. The owner subsequently confirmed intentional public visibility in this chat ("i am making it public now", followed by "so just do the update") and authorized publishing this operational handoff and STATUS update to the same repository. No repository visibility or account setting was changed by the coach. On 15 October, the connected GitHub metadata endpoint returned `visibility: public`, `pull: true`, `push: false`. This was checked again while preparing this handoff. It contradicts the older private-repository statement in project status; no visibility change was performed by this session and its cause is unknown.

The local hourly automation prompt now requires a fresh check that this exact repository is private **before invoking the publishing runner**. Public, unknown or inaccessible visibility blocks publishing while preserving local files; unchanged warnings remain quiet. The guard is a scheduler instruction, not a new enforcement check in the Python scripts. This guard remains in place for future automatic publication of learner records; the owner’s latest instruction authorizes this operational handoff update to the public repository. Cloud tasks remain read-only. Do not infer new connector write permissions from the owner’s authorization.

Initial `scripts/sync.py status` also returned `offline`, `fetch_failed`, `remote_verified: false`; cached equal heads are not fresh remote verification. This note and the STATUS update are saved locally and are **not synchronized** until a successful push and fresh remote check are recorded. The owner has now confirmed the public destination for these operational updates; use the existing safe sync workflow without changing visibility or credentials.

Startup handoff: when the learner says mulai/lanjut or opens work in this project, follow the existing safe sync startup workflow, read STATUS.md and this handoff, and reuse the existing cloud task IDs rather than asking the owner to paste this chat or recreating schedules. A running/idle chat is not automatically refreshed by a GitHub push. If a pull is blocked or offline, preserve local work and report the version limit; do not claim the handoff was fetched.

Git stores this handoff, not the automation installation itself. Another session should read it alongside fresh project state, inspect the cloud task settings, and distinguish private cloud drafts from registered local packets. No learner response, score, progress or active lesson was changed for this handoff.
