# Allowed data

`api/app/evidence/policy.py` is the version of this document that runs. If the two
disagree, the code wins and this file is the bug.

## What may enter the evidence layer

Anything Josh would put on a public portfolio, and nothing else. In practice:

- Professional background at résumé level, and named past employers
- Public projects, with URLs a stranger can open
- Technologies used, and sanitized architecture descriptions
- Lessons learned, including failures
- Outcomes Josh is permitted to share
- Public GitHub, website, and LinkedIn links
- Technical strengths, and documented gaps
- Views on agent systems, human review, and governance
- Interview windows Josh wrote down by hand

## Allowlists

**Domains.** Every URL in every record must resolve to a host on the list in
`policy.py`. An approved link cannot quietly become an arbitrary link because someone
edited YAML in a hurry.

**Email.** Exactly one address, already public on the Built in a Day site. That is what
makes it approvable rather than merely convenient.

## The test a record has to pass

> Could this be printed on a billboard?

If no, it cannot be compiled. There is one definition of public here, which is what
makes shipping the whole evidence set to a browser safe: there is no second tier to
leak.

## Verification is recorded, not assumed

Each claim declares how a stranger could check it:

| | |
| --- | --- |
| `public_artifact` | A live URL or commit log. Must carry the link. |
| `self_reported` | Josh's word. Work history is all of this, and the agent says so. |
| `inferred` | A reading across records, never presented as evidence. |

Keeping these apart is most of the point of the application.
