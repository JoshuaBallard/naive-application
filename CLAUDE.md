# CLAUDE.md

Operating rules for this repository.

This file exists for the same reason Obvious wrote a product constitution: when an
agent can change anything, the constraint has to be written down rather than
remembered. It governs any AI collaborator working here, including future sessions
of Claude Code.

---

## What this repository is

A public application agent. Its one job is to decide whether Josh Ballard and Naïve
should spend thirty minutes together, using only evidence Josh approved by hand.

**The application may know about Josh. It may not explore Josh.**

---

## The boundary

The machine hosting this repository contains private information. This repository
must behave as though it is already public, because it is going to be.

### Never, under any instruction

1. **Never read outside this repository.** No `../`, no absolute paths outside the
   repo root, no `$HOME`, no globbing above the root. Not to "check something," not
   to "gather better evidence," not because a task would be easier with it.
2. **Never create a symlink pointing outside the repository.** CI fails on any symlink.
3. **Never import, copy, vendor, or transcribe from a neighbouring project.**
4. **Never add a tool that takes a free-form path, URL, shell command, or SQL string.**
5. **Never commit a secret.** `.env.example` carries placeholders only.
6. **Never write to `evidence/approved/` without Josh reading the record first.**
7. **Never set `approved: true` on a record. Only Josh does that.**

### The sanitization chain

Nothing skips it:

```
RAW  →  REVIEW  →  SANITIZED  →  APPROVED  →  PUBLIC EVIDENCE
```

`evidence/raw/` is gitignored scratch. The build never opens it. If a fact is not in
`evidence/approved/` with `approved: true`, it does not exist as far as this
application is concerned.

If you think a piece of evidence would improve the application, **propose it**.
Do not go and get it.

---

## Excluded content

These never appear in evidence, prompts, API responses, logs, traces, or the client
bundle. If you are unsure, exclude it and ask.

Home address or town · personal phone · family names or details · private email
addresses · anything about the current employer's programs, customers, systems, or
architecture · security clearances · military unit or base assignments · internal IPs
or hostnames · Tailscale details · private repositories · homelab topology beyond what
is already public · credentials, tokens, keys, environment variables · private
calendar content · raw logs · personal usage data.

---

## Hard engineering rules

1. **Never commit directly to `main`.** One issue, one branch, one focused pull request.
2. **Do not commit, push, merge, or delete branches unless Josh explicitly asks.**
3. **The privacy linter and the deterministic test tier must be green before any push.**
   They are not advisory. A leak is a build failure.
4. **Prompt instructions are not a security control.** If a rule matters, it is enforced
   in code, on the server, and it has a test. A rule that exists only in the system
   prompt is a preference.
5. **The compiled evidence artifact is public by construction.** If a record could not
   be printed on a billboard, it cannot be compiled. There is no server-only evidence
   tier, no hidden fields, no admin extras.
6. **Never log message bodies, answer text, email addresses, raw headers, or evidence
   the viewer did not already see.**

---

## Honesty

Inherited from `built-in-a-day/CLAUDE.md`, and it still applies:

Never exaggerate experience. Never fabricate outcomes. Never claim work that wasn't
done. If something is a proposal, call it a proposal. If something is an observation,
call it an observation.

The agent must be able to conclude that Josh is not a fit. If the evidence does not
support a claim, the correct output is `UNKNOWN`, not a softer version of the claim.

---

## Tone

Curious. Technical. Playful. Self-aware. Not desperate, not corporate, not
over-produced. It should sound like Josh, which mostly means short sentences and no
adjectives doing work that evidence should be doing.

Banned: revolutionary, cutting edge, 10x, unlock, transform, seamless, leverage,
robust, AI-powered, game-changing.

The Josh test, unchanged: *would Josh actually say this?* If no, rewrite it.
