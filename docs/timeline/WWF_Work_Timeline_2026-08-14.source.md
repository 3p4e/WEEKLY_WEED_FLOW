<!--HEADERDATA
doctype: FORM
code: WWF-TIMELINE-2026-0814
version: 01
mk_title: Временска лента на работата
en_title: Work Timeline
-->

# Временска лента на работата|Work Timeline

[[FORM:grid]]
№ на документ~~Document № ||| WWF-TIMELINE-2026-0814
Опфат на лентата~~Band coverage ||| вторник 11.08.2026 16:00 → петок 14.08.2026 08:00 (Скопје, UTC+2) — 64 часа / 64 hours
Извор на податоци~~Data source ||| git коммит-печати + deploy евиденција (kvm4) / git commit timestamps + deploy records (kvm4)
Изготвено~~Generated ||| петок / Friday 14.08.2026, Скопје / Skopje
[[/FORM]]

Секој ред од лентата е сегмент од 8 часа; секоја колона е цртичка на линијарот за еден час (+0 … +7 од почетокот на сегментот). Ќелија со код означува работа во тој час; „·“ означува час без евидентирана WWF работа — ништо не е фабрикувано.|||Each band row is an 8-hour segment; each column is a ruler tick for one hour (+0 … +7 from the segment start). A coded cell marks work during that hour; “·” marks an hour with no recorded WWF work — nothing is fabricated.

# 01 Лента-линијар (64 часа)|01 Ruler Band (64 hours)

[[TABLE:data]]
Сегмент (почеток, Скопје)~~Segment (start, Skopje) ||| +0 ||| +1 ||| +2 ||| +3 ||| +4 ||| +5 ||| +6 ||| +7
вт~~Tue 11.08 16:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
ср~~Wed 12.08 00:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
ср~~Wed 12.08 08:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
ср~~Wed 12.08 16:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
чет~~Thu 13.08 00:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
чет~~Thu 13.08 08:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
чет~~Thu 13.08 16:00 ||| · ||| · ||| · ||| · ||| · ||| · ||| · ||| ·
пет~~Fri 14.08 00:00 ||| · ||| · ||| · ||| · ||| · ||| A ||| A·P·I ||| I·V·D·T
[[/TABLE]]

**Вкупно активно во лентата: ≈ 2 h 15 min** (петок 05:45–08:00, непрекинато); без евидентирана WWF работа: ≈ 61 h 45 min од 64 h.|||**Active inside the band: ≈ 2 h 15 min** (Friday 05:45–08:00, continuous); no recorded WWF work: ≈ 61 h 45 min of 64 h.

# 02 Часовни блокови во лентата (петок 14.08)|02 Time Chunks Inside the Band (Friday 14.08)

[[TABLE:data]]
Код~~Code ||| Задача~~Task ||| Време (Скопје)~~Time (Skopje) ||| Траење~~Duration
A ||| Анализа на SP-COA-COQ архивите + извлекување seed податоци (71 сорти / 78 серии)~~SP-COA-COQ archive analysis + seed-data extraction (71 strains / 78 batches) ||| 05:45 – 06:22 ||| ≈ 37 min
P ||| План за имплементација + одлуки на сопственикот (4 прашања)~~Implementation plan + owner decisions (4 questions) ||| 06:22 – 06:40 ||| ≈ 18 min
I ||| Имплементација Inc 1–7 (8 коммити, 9a73fa8 → 61c3aed)~~Implementation Inc 1–7 (8 commits, 9a73fa8 → 61c3aed) ||| 06:40 – 07:10 ||| ≈ 30 min
V ||| Полни суити + push (backend 694, frontend 316, bandit чист)~~Full suites + push (backend 694, frontend 316, bandit clean) ||| 07:10 – 07:40 ||| ≈ 30 min
D ||| Продукциски deploy v88/v128 (снимки → build → миграции 0059/0060 → swap → верификација)~~Production deploy v88/v128 (snapshots → build → migrations 0059/0060 → swap → verification) ||| 07:25 – 07:50 ||| ≈ 25 min
T ||| Овој временски документ (DocEngine)~~This timeline document (DocEngine) ||| 07:45 – 08:00 ||| ≈ 15 min
[[/TABLE]]

_Блоковите V и D се делумно паралелни (суитата течеше додека почна deploy-от), па збирот на траењата е поголем од календарските 2 h 15 min._|||_Chunks V and D partially overlap (the suite was still running when the deploy started), so the summed durations exceed the 2 h 15 min wall-clock._

# 03 Легенда: сите фамилии на задачи досега|03 Legend: All Task Families To Date

Распоните се изведени од првиот до последниот коммит по ден (Скопје, UTC+2) и не значат непрекината работа. Фамилиите пред 11.08 16:00 се НАДВОР од лентата и не се цртаат на неа.|||Spans are derived from the first-to-last commit per day (Skopje, UTC+2) and do not imply continuous work. Families before 11.08 16:00 are OUTSIDE the band and are never drawn onto it.

[[TABLE:data]]
Фамилија~~Family ||| Датуми~~Dates ||| Распон по git~~Git span ||| Во лентата?~~In band?
QMS/QC документ-мотор + изданија v74–v77 (QCSOP 011/012)~~QMS/QC document engine + releases v74–v77 (QCSOP 011/012) ||| 21 – 24.07 ||| ≈ 23 h · 4 дена~~≈ 23 h · 4 days ||| пред лентата~~before band
Прегледи на кодот + CI доверливост~~Code reviews + CI trustworthiness ||| 28 – 29.07 ||| ≈ 24 h · 2 дена~~≈ 24 h · 2 days ||| пред лентата~~before band
Mass Weed дизајн-систем (v111 – v120)~~Mass Weed design system (v111 – v120) ||| 30.07 – 31.07 (+04.08) ||| ≈ 30 h · 3 дена~~≈ 30 h · 3 days ||| пред лентата~~before band
Одгледување 0052–0054 + QC ремедијација (H1/M1–M10)~~Cultivation 0052–0054 + QC remediation (H1/M1–M10) ||| 05.08 ||| ≈ 19 h · 1 ден~~≈ 19 h · 1 day ||| пред лентата~~before band
QC LIMS: потенца Фази A–C + M5 (eCoA)~~QC LIMS: potency Phases A–C + M5 (eCoA) ||| 07.08, 08:27 – 21:28 ||| ≈ 13 h · 1 ден~~≈ 13 h · 1 day ||| пред лентата~~before band
Продукциски deploy v87/v127~~Production deploy v87/v127 ||| 08.08, 20:45 – 21:10 ||| ≈ 25 min ||| пред лентата~~before band
Letta-stack deprecation + PR №40~~Letta-stack deprecation + PR №40 ||| 09.08, 03:29 – 04:23 ||| ≈ 1 h ||| пред лентата~~before band
SPC handoff: анализа + Inc 1–8 + deploy v88/v128 + овој документ (A·P·I·V·D·T)~~SPC handoff: analysis + Inc 1–8 + deploy v88/v128 + this document (A·P·I·V·D·T) ||| пет 14.08, 05:45 – 08:00~~Fri 14.08, 05:45 – 08:00 ||| ≈ 2 h 15 min ||| ВО ЛЕНТАТА~~IN BAND
[[/TABLE]]

**Забелешка за интегритет.** Меѓу вторник 11.08 16:00 и петок 14.08 ~05:45 нема евидентирана WWF работа (нула коммити, нула deploy настани); лентата тоа го прикажува искрено со „·“ наместо да смести стари блокови во празните часови.|||**Integrity note.** Between Tuesday 11.08 16:00 and Friday 14.08 ~05:45 there is no recorded WWF work (zero commits, zero deploy events); the band shows this honestly with “·” rather than shifting older chunks into the empty hours.

МК ГМП сертифицирано постројение|||MK GMP Certified Facility
