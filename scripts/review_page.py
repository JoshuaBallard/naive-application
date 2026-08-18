"""Render the compiled evidence as a review page.

Generated from build/evidence.compiled.json so it cannot drift from what the agent
actually sees. This is the review surface for the sanitization chain: Josh reads every
record here before it counts as approved.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "build" / "evidence.compiled.json"

TYPE_ORDER = [
    ("profile", "Profile"),
    ("work_history", "Work history"),
    ("project", "Projects"),
    ("role_requirement", "Role requirements"),
    ("gap", "Gaps"),
    ("belief", "Beliefs"),
    ("failure", "Failures"),
    ("alignment", "Why Naïve"),
    ("link", "Public links"),
    ("availability", "Availability"),
]

# Field render order per record type. Anything not listed is skipped deliberately.
FIELDS: dict[str, list[tuple[str, str]]] = {
    "profile": [("headline", "Headline"), ("location", "Location"),
                ("current_status", "Current status"), ("focus", "Focus")],
    "work_history": [("scope", "Scope"), ("technologies", "Technologies"),
                     ("disclosure_note", "Disclosure note")],
    "project": [("problem", "Problem"), ("what_josh_built", "What Josh built"),
                ("what_josh_learned", "What Josh learned"), ("technologies", "Technologies"),
                ("verified_claims", "Claims"), ("known_limitations", "Known limitations")],
    "role_requirement": [("requirement", "Requirement"), ("reasoning", "Reasoning"),
                         ("evidence_ids", "Cites")],
    "gap": [("gap", "The gap"), ("why_it_matters", "Why it matters"),
            ("honest_mitigation", "Honest mitigation"), ("evidence_ids", "Cites")],
    "belief": [("belief", "Belief"), ("reasoning", "Reasoning"), ("origin_ids", "Origin")],
    "failure": [("what_happened", "What happened"), ("what_it_taught", "What it taught"),
                ("fix", "Fix")],
    "alignment": [("points", "Points")],
    "link": [("links", "Links")],
    "availability": [("windows", "Windows"), ("booking_note", "Booking note")],
}

READ_FIRST = [
    ("work.current", "Full technical detail on a live defence environment, unattributed."),
    ("req.startup-product-0to1", "The must-have where the claim is most contestable."),
    ("req.llm-experience", "Marked SUPPORTED partly on the strength of this application itself."),
    ("req.location", "Reported as potentially blocking, above the verdict."),
    ("gap.repeat-gesture", "Names the Obvious application directly. Tell me if it is too blunt."),
]

STATUS_CLASS = {
    "SUPPORTED": "ok", "PARTIAL": "part", "INFERRED": "part",
    "UNKNOWN": "unk", "GAP": "gap",
}


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def field_block(label: str, value: object, record: dict) -> str:
    if value in (None, "", [], {}):
        return ""

    body = ""
    if label == "Claims":
        rows = []
        for claim in value:  # type: ignore[union-attr]
            kind = claim["verification"].replace("_", " ")
            cls = "ok" if claim["verification"] == "public_artifact" else "unk"
            link = (
                f'<a href="{esc(claim["evidence_url"])}">{esc(claim["evidence_url"])}</a>'
                if claim.get("evidence_url") else '<span class="none">no public artifact</span>'
            )
            rows.append(
                f'<li><p>{esc(claim["claim"])}</p>'
                f'<p class="meta"><span class="chip {cls}">{esc(kind)}</span> {link}</p></li>'
            )
        body = f'<ul class="claims">{"".join(rows)}</ul>'
    elif label == "Links":
        rows = [
            f'<li><a href="{esc(l["url"])}">{esc(l["label"])}</a>'
            f'<p class="sub">{esc(l["what_it_shows"])}</p></li>'
            for l in value  # type: ignore[union-attr]
        ]
        body = f'<ul class="links">{"".join(rows)}</ul>'
    elif label == "Windows":
        rows = [
            f'<li><code>{esc(w["id"])}</code> {esc(w["label"])} '
            f'<span class="sub">{esc(w["timezone"])}</span></li>'
            for w in value  # type: ignore[union-attr]
        ]
        body = f'<ul class="plain">{"".join(rows)}</ul>'
    elif label == "Points":
        rows = [
            f'<li><p class="lead">{esc(p["point"])}</p><p>{esc(p["reasoning"])}</p>'
            f'<p class="cites">{" ".join(f"<code>{esc(i)}</code>" for i in p["evidence_ids"])}</p></li>'
            for p in value  # type: ignore[union-attr]
        ]
        body = f'<ul class="points">{"".join(rows)}</ul>'
    elif label in ("Cites", "Origin"):
        body = f'<p class="cites">{" ".join(f"<code>{esc(i)}</code>" for i in value)}</p>'  # type: ignore
    elif label in ("Technologies", "Focus"):
        body = f'<p class="tags">{" ".join(f"<span class=tag>{esc(t)}</span>" for t in value)}</p>'  # type: ignore
    elif isinstance(value, list):
        body = f'<ul class="plain">{"".join(f"<li>{esc(i)}</li>" for i in value)}</ul>'
    else:
        body = f"<p>{esc(value)}</p>"

    return f'<div class="field"><h4>{esc(label)}</h4>{body}</div>'


def render_record(record: dict) -> str:
    rid = record["id"]
    chips = []

    if record["type"] == "role_requirement":
        cls = STATUS_CLASS[record["status"]]
        chips.append(f'<span class="chip {cls}">{esc(record["status"])}</span>')
        chips.append(f'<span class="chip flat">{esc(record["category"].replace("_", " "))}</span>')

    src = record["source_class"].replace("_", " ")
    chips.append(
        f'<span class="chip {"ok" if record["source_class"] == "public_artifact" else "unk"}">'
        f"{esc(src)}</span>"
    )
    if record.get("verification") == "self_reported":
        chips.append('<span class="chip unk">self reported</span>')
    if record.get("sensitive_details_removed"):
        chips.append('<span class="chip red">redacted</span>')

    head = ""
    if record["type"] == "work_history":
        span = f'{record["start"]} → {record["end"] or "present"}'
        head = f'<p class="org">{esc(record["organization"])} · {esc(span)}</p>'

    urls = []
    for key, label in (("public_url", "live"), ("public_repo", "repo"), ("evidence_url", "source")):
        if record.get(key):
            urls.append(f'<a href="{esc(record[key])}">{esc(label)}</a>')
    url_line = f'<p class="urls">{" · ".join(urls)}</p>' if urls else ""

    fields = "".join(
        field_block(label, record.get(key), record) for key, label in FIELDS.get(record["type"], [])
    )

    redaction = ""
    if record.get("redaction_note"):
        redaction = (
            f'<div class="redaction"><h4>Removed on the way in</h4>'
            f'<p>{esc(record["redaction_note"])}</p></div>'
        )

    return f"""<article class="record" id="{esc(rid)}">
  <header>
    <code class="rid">{esc(rid)}</code>
    <h3>{esc(record["title"])}</h3>
    {head}
    <p class="chips">{"".join(chips)}</p>
    <p class="summary">{esc(record["summary"])}</p>
    {url_line}
  </header>
  <div class="fields">{fields}</div>
  {redaction}
</article>"""


def main() -> int:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    records = artifact["records"]

    sections = []
    index = []
    for type_key, label in TYPE_ORDER:
        ids = artifact["index"]["by_type"].get(type_key, [])
        if not ids:
            continue
        index.append(f'<a href="#s-{type_key}">{esc(label)} <span>{len(ids)}</span></a>')
        body = "".join(render_record(records[rid]) for rid in ids)
        sections.append(
            f'<section id="s-{type_key}"><h2>{esc(label)}'
            f'<span class="count">{len(ids)}</span></h2>{body}</section>'
        )

    read_first = "".join(
        f'<li><a href="#{esc(rid)}"><code>{esc(rid)}</code></a><p>{esc(why)}</p></li>'
        for rid, why in READ_FIRST
    )

    out = TEMPLATE
    for token, value in (
        ("%%COUNT%%", str(artifact["record_count"])),
        ("%%HASH%%", artifact["content_hash"][:12]),
        ("%%BUILT%%", artifact["built_at"]),
        ("%%INDEX%%", "".join(index)),
        ("%%READFIRST%%", read_first),
        ("%%SECTIONS%%", "".join(sections)),
    ):
        out = out.replace(token, value)

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "build" / "review.html"
    target.write_text(out, encoding="utf-8")
    print(f"wrote {target} ({len(out) // 1024} KB, {artifact['record_count']} records)")
    return 0


TEMPLATE = r"""<title>Naïve Application Evidence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:ital,wght@0,400;0,500;1,400&display=swap">
<style>
:root {
  --ground:#FBFAF8; --surface:#FFFFFF; --sunk:#F4F2ED;
  --ink:#1A1D23; --body:#343941; --muted:#6E747C;
  --rule:#E2DFD8; --rule-soft:#EEEBE4;
  --ok:#2F6F5E; --ok-bg:#E6F0EC;
  --part:#8A5A12; --part-bg:#F6EEDE;
  --gap:#9C4430; --gap-bg:#F7E9E5;
  --unk:#5B616A; --unk-bg:#ECEAE4;
  --sans:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  --serif:"IBM Plex Serif",Georgia,serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#14161A; --surface:#1B1E23; --sunk:#212429;
    --ink:#EDEBE6; --body:#C4C7CC; --muted:#8B9199;
    --rule:#2C3037; --rule-soft:#23262C;
    --ok:#74C3A8; --ok-bg:#1B2C27;
    --part:#D6A45E; --part-bg:#2C2618;
    --gap:#DE8B72; --gap-bg:#2E211D;
    --unk:#9AA0A8; --unk-bg:#24272C;
  }
}
:root[data-theme="dark"]{
  --ground:#14161A; --surface:#1B1E23; --sunk:#212429;
  --ink:#EDEBE6; --body:#C4C7CC; --muted:#8B9199;
  --rule:#2C3037; --rule-soft:#23262C;
  --ok:#74C3A8; --ok-bg:#1B2C27;
  --part:#D6A45E; --part-bg:#2C2618;
  --gap:#DE8B72; --gap-bg:#2E211D;
  --unk:#9AA0A8; --unk-bg:#24272C;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--body);
  font-family:var(--sans); font-size:16px; line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px; margin:0 auto; padding:0 24px}
a{color:var(--ok); text-decoration-thickness:1px; text-underline-offset:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--ok); outline-offset:3px; border-radius:2px}
code{font-family:var(--mono); font-size:.86em}

/* ---- masthead ---- */
.masthead{border-bottom:1px solid var(--rule); background:var(--surface)}
.masthead .wrap{padding-top:56px; padding-bottom:40px}
.eyebrow{
  font-family:var(--mono); font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); margin:0 0 18px;
}
h1{
  font-family:var(--sans); font-weight:600; font-size:clamp(30px,4.4vw,44px);
  line-height:1.1; letter-spacing:-.02em; color:var(--ink); margin:0 0 16px; text-wrap:balance;
}
.standfirst{font-family:var(--serif); font-size:19px; line-height:1.62; max-width:64ch; margin:0 0 32px}
.stats{display:flex; flex-wrap:wrap; gap:0; border:1px solid var(--rule); border-radius:3px; overflow:hidden}
.stat{flex:1 1 150px; padding:14px 18px; border-right:1px solid var(--rule); background:var(--sunk)}
.stat:last-child{border-right:0}
.stat dt{font-family:var(--mono); font-size:10.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin:0 0 4px}
.stat dd{margin:0; font-family:var(--mono); font-size:15px; color:var(--ink); font-variant-numeric:tabular-nums}

/* ---- chain ---- */
.chain{display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:28px 0 0; padding:0; list-style:none}
.chain li{font-family:var(--mono); font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted)}
.chain li.here{color:var(--ok); font-weight:600}
.chain li:not(:last-child)::after{content:"→"; margin-left:8px; color:var(--rule)}

/* ---- read first ---- */
.first{border-bottom:1px solid var(--rule); background:var(--ground)}
.first .wrap{padding:36px 24px}
.first h2{font-size:13px; font-family:var(--mono); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin:0 0 18px; font-weight:500}
.first ol{list-style:none; margin:0; padding:0; display:grid; gap:2px}
.first li{display:grid; grid-template-columns:minmax(180px,240px) 1fr; gap:20px; padding:11px 0; border-top:1px solid var(--rule-soft); align-items:baseline}
.first li p{margin:0; font-size:14.5px; color:var(--muted)}
.first code{color:var(--ink)}

/* ---- index ---- */
.index{position:sticky; top:0; z-index:5; background:var(--surface); border-bottom:1px solid var(--rule)}
.index .wrap{display:flex; gap:2px; overflow-x:auto; padding:0 24px; scrollbar-width:thin}
.index a{
  flex:0 0 auto; padding:12px 14px; font-size:12.5px; color:var(--muted);
  text-decoration:none; border-bottom:2px solid transparent; white-space:nowrap;
}
.index a:hover{color:var(--ink); border-bottom-color:var(--rule)}
.index a span{font-family:var(--mono); font-size:11px; color:var(--muted); margin-left:5px}

/* ---- sections ---- */
main{padding:8px 0 96px}
section{padding-top:52px}
section h2{
  font-size:13px; font-family:var(--mono); font-weight:500; letter-spacing:.13em;
  text-transform:uppercase; color:var(--muted); margin:0 0 20px;
  padding-bottom:10px; border-bottom:1px solid var(--rule); display:flex; align-items:baseline; gap:10px;
}
section h2 .count{margin-left:auto; font-variant-numeric:tabular-nums}

/* ---- record ---- */
.record{
  background:var(--surface); border:1px solid var(--rule); border-radius:3px;
  margin-bottom:16px; overflow:hidden;
}
.record > header{padding:22px 26px 20px; border-bottom:1px solid var(--rule-soft)}
.rid{display:block; color:var(--muted); font-size:11.5px; letter-spacing:.03em; margin-bottom:7px}
.record h3{font-size:21px; font-weight:600; letter-spacing:-.01em; color:var(--ink); margin:0 0 6px; line-height:1.25; text-wrap:balance}
.org{margin:0 0 10px; font-family:var(--mono); font-size:12.5px; color:var(--muted)}
.summary{font-family:var(--serif); font-size:16.5px; line-height:1.6; margin:12px 0 0; max-width:68ch; color:var(--body)}
.urls{margin:12px 0 0; font-family:var(--mono); font-size:12px}

.chips{display:flex; flex-wrap:wrap; gap:6px; margin:0}
.chip{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
  padding:3px 8px; border-radius:2px; font-weight:500; white-space:nowrap;
}
.chip.ok{color:var(--ok); background:var(--ok-bg)}
.chip.part{color:var(--part); background:var(--part-bg)}
.chip.gap{color:var(--gap); background:var(--gap-bg)}
.chip.unk,.chip.flat{color:var(--unk); background:var(--unk-bg)}
.chip.red{color:var(--gap); background:var(--gap-bg)}

.fields{padding:6px 26px 22px}
.field{padding:16px 0; border-bottom:1px solid var(--rule-soft)}
.field:last-child{border-bottom:0; padding-bottom:2px}
.field h4{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--muted); font-weight:500; margin:0 0 8px;
}
.field p{margin:0 0 8px; max-width:70ch; font-family:var(--serif); font-size:15.5px; line-height:1.62}
.field p:last-child{margin-bottom:0}
.field ul{margin:0; padding-left:0; list-style:none; display:grid; gap:10px}
ul.plain li{position:relative; padding-left:18px; max-width:70ch; font-family:var(--serif); font-size:15.5px; line-height:1.6}
ul.plain li::before{content:"—"; position:absolute; left:0; color:var(--rule)}
ul.claims li{padding-left:14px; border-left:2px solid var(--rule)}
ul.claims p{font-size:15px}
ul.claims .meta{font-family:var(--mono); font-size:11.5px; display:flex; flex-wrap:wrap; gap:8px; align-items:center}
ul.claims .meta a{word-break:break-all}
ul.links li{padding-left:0}
ul.links a{font-family:var(--mono); font-size:13.5px}
ul.links .sub,ul.plain .sub{display:block; font-family:var(--sans); font-size:13.5px; color:var(--muted); margin-top:2px}
ul.points li{padding-left:14px; border-left:2px solid var(--rule)}
ul.points .lead{font-family:var(--sans); font-weight:500; color:var(--ink); font-size:15px}
.none{color:var(--muted); font-style:italic}
.cites{font-family:var(--mono); font-size:11.5px; display:flex; flex-wrap:wrap; gap:6px}
.cites code{background:var(--sunk); padding:2px 6px; border-radius:2px; color:var(--muted)}
.tags{display:flex; flex-wrap:wrap; gap:5px; font-family:var(--mono)}
.tag{font-size:11px; padding:2px 7px; background:var(--sunk); border-radius:2px; color:var(--muted)}

.redaction{padding:16px 26px 18px; background:var(--gap-bg); border-top:1px solid var(--rule-soft)}
.redaction h4{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--gap); font-weight:600; margin:0 0 6px;
}
.redaction p{margin:0; max-width:70ch; font-family:var(--serif); font-size:15px; line-height:1.6; color:var(--body)}

footer{border-top:1px solid var(--rule); background:var(--surface)}
footer .wrap{padding:30px 24px 50px}
footer p{font-family:var(--mono); font-size:12px; color:var(--muted); margin:0 0 6px; max-width:80ch}

@media (max-width:700px){
  .first li{grid-template-columns:1fr; gap:4px}
  .record > header,.fields,.redaction{padding-left:18px; padding-right:18px}
  .stat{flex:1 1 100%; border-right:0; border-bottom:1px solid var(--rule)}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important; transition:none!important}}
</style>

<header class="masthead">
  <div class="wrap">
    <p class="eyebrow">Sanitization review · not yet public</p>
    <h1>Everything the application is allowed to know</h1>
    <p class="standfirst">
      Forty-two records compiled from <code>evidence/approved/</code>. This is the agent's entire
      world model — there is no second tier, no server-only evidence, and no hidden fields. Read
      each record as a stranger would, because that is who reads it next.
    </p>
    <dl class="stats">
      <div class="stat"><dt>Records</dt><dd>%%COUNT%%</dd></div>
      <div class="stat"><dt>Content hash</dt><dd>%%HASH%%</dd></div>
      <div class="stat"><dt>Compiled</dt><dd>%%BUILT%%</dd></div>
      <div class="stat"><dt>Dropped</dt><dd>0</dd></div>
    </dl>
    <ul class="chain">
      <li>Raw</li><li>Review</li><li class="here">Sanitized</li><li>Approved</li><li>Public evidence</li>
    </ul>
  </div>
</header>

<section class="first">
  <div class="wrap">
    <h2>Read these five first</h2>
    <ol>%%READFIRST%%</ol>
  </div>
</section>

<nav class="index" aria-label="Record types"><div class="wrap">%%INDEX%%</div></nav>

<main class="wrap">%%SECTIONS%%</main>

<footer>
  <div class="wrap">
    <p>Generated from build/evidence.compiled.json by scripts/review_page.py.</p>
    <p>Nothing on this page was fetched, inferred, or discovered. Every record was written by hand and passed a five-stage build gate: schema, approval, privacy linter, cross-reference integrity, content hash.</p>
  </div>
</footer>
"""

if __name__ == "__main__":
    raise SystemExit(main())
