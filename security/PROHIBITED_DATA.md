# Prohibited data

Never in evidence, prompts, API responses, logs, traces, or the client bundle. When in
doubt, exclude and ask.

## Categories

- Home address, town, or exact personal location
- Personal phone numbers and private email addresses
- Family names, details, or anything downstream of "family"
- Anything about the current employer's programs, customers, systems, or architecture
- Security clearances, and classified, export-controlled, or otherwise sensitive government information
- Military unit designations and duty stations
- Internal IP addresses, private hostnames, VPN or overlay-network details
- Private repositories and internal repository URLs
- Homelab topology beyond what is already public
- Credentials, tokens, API keys, environment variables
- Private calendar content — event names, attendees, free/busy
- Raw logs, database contents, personal usage data
- Security-control details that should not be public

## Some of these are publicly true anyway

The current employer, a clearance, a military unit, and a home town are all on Josh's
public LinkedIn. They are excluded regardless, for two reasons.

They do no work. None of them makes the case for a role at an AI startup, and a fact
that adds nothing is pure cost.

And **aggregation is the real risk.** Individually public facts, assembled in one place
by a system that answers questions tirelessly and for free, is a different exposure from
the same facts sitting on four separate pages. A résumé is read once by a person. This
is queryable.

## Where the specific terms live

Not in this repository. The first draft of `policy.py` listed them in committed source,
which would have published every fact the list exists to suppress, in one convenient
place, in a public repo.

**A blocklist is exactly as sensitive as the things on it.** The terms live in
`security/exclusions.local.txt`, gitignored and supplied to CI as a secret. The build
fails closed if it is missing: a linter that cannot load its blocklist must not report a
clean run.

## Refusing well

When the agent declines, it names the **category** — private infrastructure, family, a
current employer's systems — and does not repeat the specific product, service, or
hostname the question mentioned.

Repeating a name back confirms it exists, and confirmation is disclosure.
