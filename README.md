# An application agent

This is a job application for the Member of Technical Staff role at Naïve. It is also
a small working system, because writing about how you think about agent boundaries is
less interesting than building one and letting people try to break it.

It has one job:

> Determine whether Josh Ballard and Naïve should spend thirty minutes together.

It is allowed to conclude that they should not. An application that cannot reach a
negative conclusion is an advert, and it reads like one.

---

## The one idea

**The security control is absence, not enforcement.**

Nothing private here is protected by a prompt, a filter, or a permission check. It is
not in the process. The agent reads one compiled JSON file and has no other capability:

```
no filesystem    no shell         no network     no repository access
no database      no env access    no calendar    no credentials to lose
```

Nine tools, all pure reads over that one file, plus one write that a human has to
approve. `get_project` takes an **enum** built from the compiled evidence rather than a
string, so there is no argument a viewer can craft that reaches something unlisted —
unknown values fail schema validation before a handler runs.

Everything else in this repository is defence in depth on top of that.

## How evidence gets in

Nothing is discovered, scraped, or inferred. Every fact was written by hand and read by
a human before it counted.

```
RAW → REVIEW → SANITIZED → APPROVED → PUBLIC EVIDENCE
```

`npm-style build gate`, five stages, first failure stops the build:

| Gate | What it does |
| --- | --- |
| Schema | Pydantic, `extra="forbid"`. A typo'd field fails the build. `approved` has no default. |
| Approval | Anything without `approved: true` is dropped before it is parsed, and named in the output. |
| Privacy | Every string in every record through a linter: IPs, hostnames, key shapes, phone numbers, non-allowlisted emails and URL hosts, and a personal exclusion list. |
| Integrity | Every cross-reference must resolve to a real approved record. |
| Hash | Deterministic content hash, so evidence drift is one changed line in a diff. |

Two behaviours worth knowing. Findings **mask what they matched** — a linter that
prints the secret in order to report the secret has moved the leak, not stopped it. And
the build **fails closed** if the exclusion list is missing: a linter that cannot load
its blocklist must not report a clean run.

The exclusion list itself is gitignored. A list of things you want suppressed is a tidy
summary of the things you want suppressed.

## How an answer gets out

```
question → length cap → wrapped as untrusted data
         → tools run, latency and evidence ids recorded
         → submit_answer (forced, strict schema)
         → SERVER-SIDE VERIFIER
              ├─ passed                      → shown, citations resolved
              ├─ fabricated / unsupported id → one repair, violations fed back
              ├─ still wrong                 → downgraded: SUPPORTED becomes INFERRED
              ├─ privacy hit                 → FAIL CLOSED, no repair, no retry
              └─ prose instead of schema     → FAIL CLOSED
```

Every claim declares a support level and names the evidence records behind it.
`SUPPORTED` with no resolvable record is **rejected by the server**, not softened. The
fit verdict is computed by a deterministic rubric over the requirement records — the
model reports it and cannot pick it, because a model asked "is this candidate good"
drifts toward yes.

Model choice is therefore a cost decision, not a safety one. That is the point of
putting the guarantee in code.

## What it will not do

It will not discuss private repositories, home infrastructure, family, a current
employer's systems, or a calendar. Not because those answers are embarrassing — because
they are not in the process, and no amount of asking changes that.

It will not book anything. `request_interview` writes a row marked
`pending_human_approval`. No calendar is touched, no invitation is sent, and nobody is
committed to anything until Josh confirms by hand.

There is no secret to extract. The system prompt is published. The tool list is
published. The entire evidence set is browsable. If extracting the prompt were a
meaningful attack, the security would be in the wrong place.

## Running it

```bash
scripts/dev pytest -q                          # the test suite
scripts/dev python -m app.evidence.compile     # rebuild the evidence artifact
scripts/dev python /repo/scripts/smoke.py "…"  # one real question, needs ANTHROPIC_API_KEY
```

`scripts/dev` runs everything in the API container, so nothing is installed on the
host. Secrets come from a gitignored `.env` and are never baked into an image.

## Deliberately not built

No accounts, no login, no vector database, no multi-agent orchestration, no calendar
integration, no runtime web fetch, no admin path that can edit evidence, and no
dependency on Naïve's own SDK.

That last one is a decision rather than an omission. Their starter template gives every
user a vault, a payment card, an inbox, and third-party connections, governed by an
Account Kit. This application needs none of it. Least privilege means not installing the
capability — a capability you did not install cannot be misconfigured, exploited, or
talked into running.

---

Built by Josh Ballard. The gaps are in here too — that is `/fit`, and it is the part
worth reading.
