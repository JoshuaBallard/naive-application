# Threat model

## The claim this document has to support

The private data is not protected by a filter, a prompt, or a permission check. **It is
not in the process.** Everything else here is defence in depth on top of that, and
should be read as such — if the argument rested on the prompt, the design would be
wrong.

## Assets, ranked by what actually hurts

| | Asset | What loss looks like |
| --- | --- | --- |
| A1 | Josh's private data | Not present. A compromise requires a failure in the human sanitization chain, not an application bug. |
| A2 | **Josh's credibility** | The agent asserts something false and a hiring manager checks. This is the highest real risk and the one most of the machinery addresses. |
| A3 | Interview-request PII | A name and address someone gave in confidence leaks, or ends up in a log. |
| A4 | The model API key | Extracted or drained. |
| A5 | Availability and cost | A bot floods the endpoint; the demo is dead and the bill is not. |

## Adversaries

- **A curious hiring manager.** The most likely one, and they *will* try `ignore previous instructions`. Assume it. The application should handle it as a fair thing to try, because it is.
- **A prompt-injection tester** looking for a capability to abuse.
- **A scraper or bot** hitting `/api/*` with no interest in the content.
- **Josh, tired, at 2am,** pasting the wrong paragraph into an evidence file. This one is not a joke; it is the likeliest path to A1 and the reason the build gate fails rather than warns.

## Controls

| Threat | Control | Kind |
| --- | --- | --- |
| Private data reachable at runtime | No filesystem, shell, network, repository, database, or environment tool exists. Nine tools, all pure reads over one in-memory JSON. | Architectural |
| A tool argument reaching something unlisted | `get_project` takes an **enum** compiled from the evidence. Unknown values fail schema validation before a handler runs. Snapshot test pins the whole surface. | Architectural |
| Bad paste into evidence | Privacy linter at build time, fourteen rule classes plus a personal exclusion list. Build fails, never warns. | Automated |
| Unapproved content compiling | `approved: true` required; absent means dropped and named in the build output. | Automated |
| **Fabricated claims (A2)** | Forced structured output; every claim carries a support level and evidence ids; a server-side verifier rejects `SUPPORTED` without a resolvable record; one repair; then downgrade or fail closed. | Deterministic |
| Flattering verdict (A2) | Verdict computed by a deterministic rubric. The model reports it and cannot pick it. Confidence is capped by verifiability, not coverage. | Deterministic |
| Prompt injection via the question | Wrapped as untrusted data — and, more to the point, there is no capability to abuse. The system prompt is published, so extraction is a link rather than an exploit. | Architectural |
| Injection via the interview message field | That field never re-enters an agent turn. Stored, escaped, read by a human. | Architectural |
| Model output leaking (A1) | The same linter runs on every answer before it reaches a browser. A hit fails closed with no repair attempt. | Deterministic |
| Violation feedback re-injecting a leak | Findings mask what they matched. The repair prompt names the rule, never the string. | Deterministic |
| PII in logs (A3) | The logger has no parameter for a message body. Fields are allowlisted; a forbidden field drops the line and raises. Addresses are salted-hashed with a daily-rotating salt. | Automated |
| PII leaving the system (A3) | There is no email provider and no analytics. A requester's address never leaves the disk it was written to. | Architectural |
| Key extraction (A4) | Server-side only, held by one process. The web tier never sees it. No `NEXT_PUBLIC_` anything. | Architectural |
| Cost and denial of service (A5) | Eight questions per session, sessions per address per day, a daily spend cap that degrades to a static explanation, honeypot on the one write. | Automated |
| A future agent widening the boundary | `CLAUDE.md` forbids reading outside the repository; tests assert no symlinks, no parent-path references, and no `subprocess`/`socket`/`requests` imports. | Policy + automated |

## Deliberately out of scope

No accounts, so no account takeover. No calendar, so no calendar integrity. Single
tenant, so no cross-tenant isolation. These are absent capabilities, not unmitigated
risks.

## Residual risk, stated plainly

1. **The human link is the weakest one.** Every control above assumes Josh read each record before setting `approved: true`. The chain is only as good as that reading, and no test can check it.
2. **The exclusion list must reach CI.** It is gitignored and supplied as a secret. If that secret is ever missing the build fails closed — but a misconfigured pipeline that skips the gate entirely would not be caught by the gate.
3. **A determined reader can aggregate.** Every record is individually safe. Someone combining this application, a public LinkedIn, and a public GitHub can assemble more than any one of them shows. That is true of anyone with a public profile; it is why the clearance, the employer name, the military unit, and the home town were excluded even though all four are publicly listed elsewhere.
4. **The current role is described in technical detail, by decision.** `work.current`
   carries host counts, a hypervisor patch version, and the hardening posture of a live
   production estate at an unnamed defence contractor. An evaluation case
   (`privacy.work-systems`) demonstrates the agent volunteering all of it in response to
   *"be specific about the architecture"* — an obvious question, not a clever attack —
   and it does so non-deterministically, which means discretion cannot be relied on. The
   employer is never named, and that unattribution is what the decision rests on. It was
   made with the transcript in hand rather than in the abstract, and it is recorded here
   because a deliberate acceptance of risk should be visible rather than discovered.

5. **The model can still be wrong inside the boundary.** The verifier catches fabricated citations and unsupported claims. It cannot catch a claim that is well-cited and still a poor characterisation of the record it cites. That is what `/evidence` is for: the source is one click away.
