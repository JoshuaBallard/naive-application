# What this application collects about you

Short version: as little as it can, and none of it goes anywhere.

## If you only read

Nothing is stored. There are no analytics, no tracking pixels, no session recording, and
no third-party scripts. Someone poking at a security demo should not be tracked, and
saying so is part of the demonstration.

## If you ask a question

A session row is created holding an opaque id, a timestamp, and a **salted hash of your
IP address**. The salt rotates daily, so today's hashes cannot be correlated with
yesterday's even by someone holding every log. It exists to rate-limit and nothing else.

**Your question is not stored and not logged.** The logger has no parameter for a
message body — pass one and the line is dropped and an error is raised instead. What is
logged is structural: which tools ran, how many evidence records were read, whether
verification passed, latency, token counts, cost.

## If you request a conversation

Your name, email, chosen window, and optional message are stored in one isolated table.

- Nothing is sent to a calendar. No invitation is created.
- Nothing is sent to a third party. **There is no email provider in this system**, which means your address never leaves the disk it was written to.
- Your details are never logged. The log line for a submitted request contains a reference id and nothing else.
- The status is `pending_human_approval` until Josh confirms by hand.

Retention: 90 days, then deleted. To have a request removed sooner, ask via the address
on the site and it will be deleted rather than marked.

## What the application knows about Josh

All of it, browsable, at `/evidence`. There is no hidden tier. If a record could not be
published it could not have been compiled, which is why the whole set can be handed to
your browser safely.

## Reporting a problem

If you find a way to make this application say something it should not, or reveal
something it should not, that is a genuinely useful finding and it will be published in
the red-team results with credit if you want it.
