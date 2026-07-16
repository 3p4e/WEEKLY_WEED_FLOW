# BMad Master — Orchestration Notes

<!-- [AGENT:bmad-master] [CAT:decisions] [SRC:bmad-plugin] [SEEDED] -->

## Routing Rules (Constitutional)
- NEVER execute specialist workflows directly
- ALWAYS route via call_subordinate after CSV lookup
- Natural language requests → check EXTRAS routing manifest first
- Multiple matches → show list, ask user to pick

## Project State Protocol
- Read 02-bmad-state.md before every delegation
- Update 02-bmad-state.md after every phase transition
- Active artifact must be tracked in state

## Delegation Reminders
<!-- Append project-specific routing notes here -->
