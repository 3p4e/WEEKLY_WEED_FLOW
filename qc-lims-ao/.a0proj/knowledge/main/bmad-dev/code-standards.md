# Amelia — Project Coding Standards

<!-- [AGENT:bmad-dev] [CAT:standards] [SRC:bmad-plugin] [SEEDED] -->

## General Standards
- Follow existing code style in the project
- All tests must pass before marking any story complete
- Use TDD: write tests first, then implementation
- No placeholder code — only production-ready implementation

## Agent Zero Plugin Conventions
- Extensions: `extensions/python/{hook_point}/{number}_{name}.py`
- Use `Path(__file__).resolve().parents[N]` for plugin root resolution
- Handle all exceptions gracefully — never crash the agent init
- Log via `agent.context.log` not print()

## BMAD Project Conventions
- All BMAD artifacts in `.a0proj/_bmad-output/`
- Planning artifacts: `planning-artifacts/`
- Implementation artifacts: `implementation-artifacts/`
- State updates: always patch `02-bmad-state.md` after phase transitions
