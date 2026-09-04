# docengine.app.presets — one-click direct-edit requests for the chat UI
# (docengine/app/main.py's POST /workflows/{jid}/revise). Each preset is
# nothing more than a canned instruction string — the SAME field a freeform
# chat message fills — so a preset is never a distinct code path through
# run_revision, only a shortcut past typing one out. New presets are added
# here, never in the pipeline or the endpoint.
PRESETS: list[dict] = [
    {
        "key": "simplify_language",
        "label_en": "Simplify the language",
        "label_mk": "Поедностави го јазикот",
        "instruction": (
            "Simplify the language of the targeted section(s): shorter sentences, "
            "plainer wording, no loss of meaning or of any required regulatory "
            "term. Do not remove or soften any acceptance criterion, blank "
            "write-in field, or citation."
        ),
    },
    {
        "key": "tighten",
        "label_en": "Tighten the wording",
        "label_mk": "Скрати го текстот",
        "instruction": (
            "Tighten the wording of the targeted section(s) — remove redundant "
            "phrasing and filler without dropping any requirement, blank "
            "write-in field, citation, or acceptance criterion."
        ),
    },
    {
        "key": "fix_bilingual_gap",
        "label_en": "Fix a missing translation",
        "label_mk": "Пополни го недостасувачкиот превод",
        "instruction": (
            "One or both languages are missing or incomplete in the targeted "
            "section(s). Add the missing Macedonian or English text so the "
            "section is fully bilingual, matching the meaning of whichever "
            "language is already present. Do not invent content that is not "
            "already stated in the other language."
        ),
    },
    {
        "key": "add_citation",
        "label_en": "Add or verify a citation",
        "label_mk": "Додај или потврди извор",
        "instruction": (
            "Every regulatory or method claim in the targeted section(s) needs "
            "a citation to a real, retrievable source. Add one where missing, "
            "using ragflow_search against your permitted corpus; where a claim "
            "cannot be verified against the corpus, mark it clearly rather than "
            "inventing a reference."
        ),
    },
    {
        "key": "expand_detail",
        "label_en": "Expand with more detail",
        "label_mk": "Прошири со повеќе детали",
        "instruction": (
            "Expand the targeted section(s) with more procedural detail — more "
            "explicit steps, clearer sequencing — without inventing facility "
            "specifics, measured values, dates, names, or signatures; those "
            "stay blank write-in fields."
        ),
    },
]

PRESETS_BY_KEY = {p["key"]: p for p in PRESETS}
