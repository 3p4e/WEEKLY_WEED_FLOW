#!/usr/bin/env python3
"""
Verification Script for Multi-Agent SOP Generation System

Validates that all 11 chapter agents are properly implemented and integrated.
Can be run as: python verify_agents.py
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from CONTENT_CREATOR_FRAMEWORK.agents import (
    BaseAgent,
    AgentRole,
    AgentResponse,
    MemoryContext,
    create_chapter_agent,
    # Chapter agents
    CoverAgent,
    PurposeAgent,
    ScopeAgent,
    DefinitionsAgent,
    RACIAgent,
    RegulatoryAgent,
    ProcedureAgent,
    DocumentationAgent,
    TrainingAgent,
    AnnexAgent,
    AssemblerAgent,
)


def verify_imports():
    """Verify all agent imports."""
    print("✓ Checking imports...")

    agents_to_check = [
        ("BaseAgent", BaseAgent),
        ("AgentRole", AgentRole),
        ("AgentResponse", AgentResponse),
        ("MemoryContext", MemoryContext),
        ("create_chapter_agent", create_chapter_agent),
        ("CoverAgent", CoverAgent),
        ("PurposeAgent", PurposeAgent),
        ("ScopeAgent", ScopeAgent),
        ("DefinitionsAgent", DefinitionsAgent),
        ("RACIAgent", RACIAgent),
        ("RegulatoryAgent", RegulatoryAgent),
        ("ProcedureAgent", ProcedureAgent),
        ("DocumentationAgent", DocumentationAgent),
        ("TrainingAgent", TrainingAgent),
        ("AnnexAgent", AnnexAgent),
        ("AssemblerAgent", AssemblerAgent),
    ]

    for name, obj in agents_to_check:
        if obj is None:
            print(f"  ✗ {name} is None")
            return False
        print(f"  ✓ {name}")

    return True


def verify_agent_roles():
    """Verify all agent roles are defined."""
    print("\n✓ Checking AgentRole enum...")

    expected_roles = [
        "COVER",
        "PURPOSE",
        "SCOPE",
        "DEFINITIONS",
        "RACI",
        "REGULATORY",
        "PROCEDURE",
        "DOCUMENTATION",
        "TRAINING",
        "ANNEX",
        "DIAGRAM",
        "ASSEMBLER",
    ]

    actual_roles = [role.name for role in AgentRole]

    for role in expected_roles:
        if role in actual_roles:
            print(f"  ✓ AgentRole.{role}")
        else:
            print(f"  ✗ AgentRole.{role} missing")
            return False

    return True


def verify_agent_classes():
    """Verify agent class inheritance."""
    print("\n✓ Checking agent classes...")

    agent_classes = [
        ("CoverAgent", CoverAgent),
        ("PurposeAgent", PurposeAgent),
        ("ScopeAgent", ScopeAgent),
        ("DefinitionsAgent", DefinitionsAgent),
        ("RACIAgent", RACIAgent),
        ("RegulatoryAgent", RegulatoryAgent),
        ("ProcedureAgent", ProcedureAgent),
        ("DocumentationAgent", DocumentationAgent),
        ("TrainingAgent", TrainingAgent),
        ("AnnexAgent", AnnexAgent),
        ("AssemblerAgent", AssemblerAgent),
    ]

    for name, agent_class in agent_classes:
        # Check inheritance
        if issubclass(agent_class, BaseAgent):
            print(f"  ✓ {name} extends BaseAgent")
        else:
            print(f"  ✗ {name} does not extend BaseAgent")
            return False

        # Check required methods
        required_methods = ["generate_content", "validate_content"]
        for method in required_methods:
            if hasattr(agent_class, method):
                print(f"    ✓ {method}()")
            else:
                print(f"    ✗ {method}() missing")
                return False

    return True


def verify_factory_function():
    """Verify create_chapter_agent factory function."""
    print("\n✓ Checking factory function...")

    agent_configs = [
        (AgentRole.COVER, "gpt-4-turbo"),
        (AgentRole.PURPOSE, "gpt-4-turbo"),
        (AgentRole.SCOPE, "gpt-4-turbo"),
        (AgentRole.DEFINITIONS, "gemini-1.5-pro"),
        (AgentRole.RACI, "gpt-4-turbo"),
        (AgentRole.REGULATORY, "gpt-4-turbo"),
        (AgentRole.PROCEDURE, "gemini-1.5-pro"),
        (AgentRole.DOCUMENTATION, "gpt-4-turbo"),
        (AgentRole.TRAINING, "gpt-4-turbo"),
        (AgentRole.ANNEX, "gemini-1.5-pro"),
        (AgentRole.ASSEMBLER, "gpt-4-turbo"),
    ]

    # Mock LLM client (minimal)
    class MockLLMClient:
        pass

    mock_llm = MockLLMClient()

    for role, expected_model in agent_configs:
        try:
            agent = create_chapter_agent(role, mock_llm)
            if agent.model == expected_model:
                print(f"  ✓ {role.value:15} → {expected_model}")
            else:
                print(
                    f"  ✗ {role.value:15} → {agent.model} (expected {expected_model})"
                )
                return False
        except Exception as e:
            print(f"  ✗ {role.value:15} failed: {e}")
            return False

    return True


def verify_agent_interface():
    """Verify common agent interface."""
    print("\n✓ Checking agent interface consistency...")

    # Mock LLM client
    class MockLLMClient:
        pass

    mock_llm = MockLLMClient()

    # Test a few agents
    test_roles = [AgentRole.PURPOSE, AgentRole.PROCEDURE, AgentRole.ASSEMBLER]

    for role in test_roles:
        agent = create_chapter_agent(role, mock_llm)

        # Check attributes
        attrs = ["role", "llm_client", "model", "memory_context"]
        for attr in attrs:
            if hasattr(agent, attr):
                print(f"  ✓ {role.value:15}.{attr}")
            else:
                print(f"  ✗ {role.value:15}.{attr} missing")
                return False

    return True


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Multi-Agent SOP Generation System - Verification")
    print("=" * 60)

    checks = [
        ("Imports", verify_imports),
        ("Agent Roles", verify_agent_roles),
        ("Agent Classes", verify_agent_classes),
        ("Factory Function", verify_factory_function),
        ("Agent Interface", verify_agent_interface),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} check failed with exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
        if not result:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All verifications passed! System is ready for integration.\n")
        return 0
    else:
        print("\n✗ Some verifications failed. Please review the output above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
