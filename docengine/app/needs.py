"""The [NEEDS INPUT: …] contract — what the engine does when it does not know.

An agent that lacks a facility specific has three ways to behave, and only one
of them is acceptable:

  1. **Invent something plausible.** Never. This is a GxP document: a
     fabricated room code, temperature limit or clause number is worse than no
     document at all, because it reads exactly like a real one.
  2. **Leave it silently blank.** Better, and what the engine used to ask for —
     but a blank in a forty-page bilingual document is invisible. Nobody
     downstream knows the document is unfinished, or which facts would finish
     it, so the gap is found (if ever) by proof-reading.
  3. **Write `[NEEDS INPUT: what is needed]`** — which this module collects and
     hands back with the finished draft as a list of questions to answer.

(3) is the contract. It keeps (1)'s prohibition absolute while making the gap
legible twice over: the marker is visible in the rendered .docx exactly where
the value belongs, AND it is extracted into the job result, so the person who
asked for the document is told what to supply instead of hunting for holes.

This is the one code-enforced half of a rule that was previously prompt-only.
The prompts still carry the instruction — nothing here can stop an agent from
inventing a value — but "did the agent tell us what it was missing" is now a
property the pipeline reads off the text rather than a hope.

NOT to be confused with a blank WRITE-IN field, which is the document working
as designed: a signature line, a measured result, a date of execution are all
filled in by a human at execution time and MUST stay blank. A NEEDS INPUT
marker is for something needed to FINISH AUTHORING — a room code, an
acceptance limit, an equipment ID the author was never given.
"""
import re

# Deliberately SINGLE square brackets. They render legibly in the .docx as
# [NEEDS INPUT: …] where the value belongs, they are what a person reading the
# document would expect a placeholder to look like, and they cannot collide
# with the engine's own [[TABLE]] / [[FORM]] / [[FORM:grid]] block markers
# (which are doubled) or with a Markdown link (which is followed by '(').
#
# The inner class excludes both brackets so a malformed or nested marker fails
# to match rather than swallowing the rest of the line, and the length cap
# stops a runaway '[' from consuming a paragraph.
MARKER = "NEEDS INPUT"
_NEEDS = re.compile(r"\[\s*NEEDS\s+INPUT\s*:\s*([^\[\]]{1,300}?)\s*\]", re.I)

# What the agents are told, in one place, so the wording cannot drift between
# the section-draft prompt, the repair prompt and the direct-edit prompt.
INSTRUCTION = (
    "MISSING INFORMATION — never guess. If a facility specific you need was "
    "not supplied (a room or equipment code, an acceptance limit, a "
    "responsible role, a reference document number, a frequency), do NOT "
    "invent a plausible-looking value and do NOT quietly leave it out: write "
    "[NEEDS INPUT: what you need] inline, exactly where the value belongs, "
    "describing the missing fact in a few words. It is reported back to the "
    "requester to fill in. Use the SAME English wording on both language "
    "sides so the pair reads as one question. This does NOT apply to blank "
    "write-in fields that a person fills during execution — signatures, "
    "measured results, dates of execution stay blank as designed."
)


def extract_needs(sections: list[dict]) -> list[dict]:
    """Every [NEEDS INPUT: …] marker in the document, in reading order.

    Returns [{"section": num, "item": text}]. Identical items within one
    section collapse to a single entry: the instruction asks for the same
    wording on both language sides, so the MK and EN halves of one gap are one
    question, not two.
    """
    out: list[dict] = []
    for s in sections:
        seen: set[str] = set()
        for m in _NEEDS.finditer(s.get("content") or ""):
            item = " ".join(m.group(1).split())
            key = item.casefold()
            if not item or key in seen:
                continue
            seen.add(key)
            out.append({"section": s.get("num", "?"), "item": item})
    return out


def needs_summary(needs: list[dict]) -> str:
    """One-line log/error summary — '3 open question(s): 4.0 room code; …'."""
    if not needs:
        return ""
    head = "; ".join(f"{n['section']} {n['item']}" for n in needs[:5])
    more = f" (+{len(needs) - 5} more)" if len(needs) > 5 else ""
    return f"{len(needs)} open question(s): {head}{more}"
