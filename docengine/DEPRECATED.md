# ⚠️ FROZEN MIRROR — engine fork development moved to 3p4e/letta-stack (2026-08-09)

By owner decision, **all Letta technology development happens in
[3p4e/letta-stack](https://github.com/3p4e/letta-stack)**. This `docengine/` tree
(engine line B: the §6D kv-primitives fork `dfdd5271 / 86feab6a / 7aa1d076` +
`pp_format_layout_addons.py`, plus the declarative `gf_*` fleet app) was copied there as
`apps/wwf-docengine/` and is developed there.

**This copy receives no engine edits.** The two engine lines (A: ACME_SOP master =
live volume; B: this fork) are being merged into v2.0.0 in letta-stack — top open work
item in its `START_HERE.md`. Until the merge lands, neither line may be edited in its old
home repo (letta-stack `review/LETTA_TECH_REVIEW_2026-08-09.md` §2).

WWF app development against the deployed docengine continues here as a *consumer*;
engine/fleet changes flow letta-stack → deployment.
