"""
Mermaid Diagram Generation Module

Generates process diagrams, flowcharts, swimlane diagrams, and other visualizations
for embedding in SOPs using Mermaid.js with high-contrast styling.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class DiagramType(Enum):
    """Supported diagram types"""
    FLOWCHART = "flowchart"
    SWIMLANE = "swimlane"  # Uses flowchart with subgraphs
    SEQUENCE = "sequenceDiagram"
    DECISION_TREE = "flowchart"  # Flowchart with decisions
    GANTT = "gantt"


class MermaidTheme:
    """Mermaid diagram styling with high contrast"""

    # Purely Plant Color Palette
    PRIMARY = "#228B22"  # Forest Green
    SECONDARY = "#FFD700"  # Gold
    TERTIARY = "#87CEEB"  # Sky Blue
    DANGER = "#DC143C"  # Crimson
    SUCCESS = "#32CD32"  # Lime Green
    WARNING = "#FF8C00"  # Dark Orange

    @staticmethod
    def get_init_config() -> str:
        """Get Mermaid init config for high contrast theme"""
        return f"""%%{{init: {{
            'theme': 'forest',
            'themeVariables': {{
                'primaryColor': '{MermaidTheme.PRIMARY}',
                'primaryBorderColor': '#1a5c1a',
                'secondaryColor': '{MermaidTheme.SECONDARY}',
                'secondaryBorderColor': '#cc9900',
                'tertiaryColor': '{MermaidTheme.TERTIARY}',
                'tertiaryBorderColor': '#6495ed',
                'dangerColor': '{MermaidTheme.DANGER}',
                'dangerBorderColor': '#8b0000',
                'successColor': '{MermaidTheme.SUCCESS}',
                'successBorderColor': '#006400'
            }}
        }}}}%%"""


class MermaidFlowchart:
    """Helper for building Mermaid flowcharts"""

    def __init__(self, title: str, direction: str = "TD"):
        """
        Initialize flowchart builder.

        Args:
            title: Chart title
            direction: Direction (TD=Top-Down, LR=Left-Right, etc.)
        """
        self.title = title
        self.direction = direction
        self.nodes: Dict[str, str] = {}
        self.edges: List[tuple] = []
        self.subgraphs: Dict[str, List[str]] = {}

    def add_node(self, node_id: str, label: str, node_type: str = "default"):
        """
        Add a node to the flowchart.

        Args:
            node_id: Unique node identifier
            label: Node display label
            node_type: Node type (default, process, decision, start, end)
        """
        # Mermaid node syntax
        if node_type == "start":
            self.nodes[node_id] = f"{node_id}([{label}])"
        elif node_type == "end":
            self.nodes[node_id] = f"{node_id}([{label}])"
        elif node_type == "decision":
            self.nodes[node_id] = f"{node_id}{{{label}}}"
        else:
            self.nodes[node_id] = f'{node_id}["{label}"]'

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        label: Optional[str] = None,
        style: str = "default",
    ):
        """
        Add an edge between nodes.

        Args:
            from_id: Source node ID
            to_id: Destination node ID
            label: Optional edge label
            style: Edge style (default, success, danger, warning)
        """
        if label:
            edge = (from_id, to_id, f"|{label}|")
        else:
            edge = (from_id, to_id, "")

        self.edges.append(edge)

    def add_subgraph(self, subgraph_id: str, title: str, node_ids: List[str]):
        """
        Add a subgraph (used for swimlanes).

        Args:
            subgraph_id: Unique subgraph ID
            title: Subgraph title
            node_ids: List of node IDs to include
        """
        self.subgraphs[subgraph_id] = {"title": title, "nodes": node_ids}

    def build(self) -> str:
        """Build the complete Mermaid flowchart code."""
        lines = [
            MermaidTheme.get_init_config(),
            f"flowchart {self.direction}",
        ]

        # Add nodes
        for node_code in self.nodes.values():
            lines.append(f"    {node_code}")

        # Add edges
        for from_id, to_id, label in self.edges:
            if label:
                lines.append(f"    {from_id} -->|{label}| {to_id}")
            else:
                lines.append(f"    {from_id} --> {to_id}")

        return "\n".join(lines)


class DiagramAgent:
    """
    AI Agent for generating diagrams from SOP procedures.

    Uses LLM to convert procedure steps into appropriate Mermaid diagrams.
    """

    def __init__(self, llm_client, model: str = "gpt-4-turbo"):
        """
        Initialize diagram agent.

        Args:
            llm_client: LLM client for diagram generation
            model: Model to use for analysis
        """
        self.llm_client = llm_client
        self.model = model

    async def generate_flowchart_from_procedure(
        self,
        procedure_steps: List[Dict[str, Any]],
        title: str = "Process Flowchart",
    ) -> str:
        """
        Generate a Mermaid flowchart from procedure steps.

        Args:
            procedure_steps: List of procedure step dictionaries
            title: Title for the flowchart

        Returns:
            Mermaid flowchart code
        """
        try:
            # Create flowchart builder
            flowchart = MermaidFlowchart(title, direction="TD")

            # Add start node
            flowchart.add_node("start", "Start Process", node_type="start")
            prev_node = "start"

            # Add procedure steps as nodes
            for i, step in enumerate(procedure_steps):
                step_id = f"step_{i+1}"
                step_title = step.get("title", f"Step {i+1}")

                # Check if step has decision points
                if step.get("decision_points"):
                    flowchart.add_node(step_id, step_title, node_type="decision")
                    # Add branches for each decision
                    for j, decision in enumerate(step.get("decision_points", [])):
                        branch_id = f"branch_{i+1}_{j+1}"
                        flowchart.add_node(
                            branch_id, decision.get("outcome", f"Outcome {j+1}")
                        )
                        flowchart.add_edge(
                            step_id, branch_id, decision.get("condition", "")
                        )
                        prev_node = branch_id
                else:
                    flowchart.add_node(step_id, step_title, node_type="process")
                    flowchart.add_edge(prev_node, step_id)
                    prev_node = step_id

            # Add end node
            flowchart.add_node("end", "End Process", node_type="end")
            flowchart.add_edge(prev_node, "end")

            return flowchart.build()

        except Exception as e:
            logger.error(f"Failed to generate flowchart: {e}")
            return ""

    async def generate_swimlane_diagram(
        self,
        roles: List[str],
        steps: List[Dict[str, Any]],
        title: str = "Responsibility Swimlane",
    ) -> str:
        """
        Generate swimlane diagram showing responsibilities.

        Args:
            roles: List of roles/departments
            steps: List of steps with role assignments
            title: Diagram title

        Returns:
            Mermaid swimlane code (as flowchart with subgraphs)
        """
        try:
            flowchart = MermaidFlowchart(title, direction="LR")

            # Create subgraph for each role
            node_counter = 0
            for role in roles:
                role_id = role.lower().replace(" ", "_")
                role_steps = [s for s in steps if s.get("responsible") == role]

                for step in role_steps:
                    node_id = f"n_{node_counter}"
                    flowchart.add_node(node_id, step.get("title", "Step"))
                    node_counter += 1

                # Add subgraph (swimlane)
                if role_steps:
                    flowchart.add_subgraph(role_id, role, [f"n_{i}" for i in range(node_counter - len(role_steps), node_counter)])

            return flowchart.build()

        except Exception as e:
            logger.error(f"Failed to generate swimlane diagram: {e}")
            return ""

    async def generate_sequence_diagram(
        self,
        actors: List[str],
        interactions: List[Dict[str, Any]],
        title: str = "Process Sequence",
    ) -> str:
        """
        Generate sequence diagram for workflow interactions.

        Args:
            actors: List of actors in the sequence
            interactions: List of interactions between actors
            title: Diagram title

        Returns:
            Mermaid sequence diagram code
        """
        try:
            lines = [
                MermaidTheme.get_init_config(),
                f"sequenceDiagram",
                f"    title {title}",
            ]

            # Add actors (participants)
            for actor in actors:
                lines.append(f"    participant {actor}")

            # Add interactions
            for interaction in interactions:
                from_actor = interaction.get("from", "").replace(" ", "")
                to_actor = interaction.get("to", "").replace(" ", "")
                message = interaction.get("message", "")
                is_return = interaction.get("is_return", False)

                if from_actor and to_actor:
                    if is_return:
                        lines.append(f"    {from_actor}-->{to_actor}: {message}")
                    else:
                        lines.append(f"    {from_actor}>>{to_actor}: {message}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to generate sequence diagram: {e}")
            return ""

    async def generate_decision_tree(
        self,
        root_decision: Dict[str, Any],
        title: str = "Decision Tree",
    ) -> str:
        """
        Generate decision tree diagram.

        Args:
            root_decision: Root decision with branches
            title: Diagram title

        Returns:
            Mermaid flowchart decision tree code
        """
        try:
            flowchart = MermaidFlowchart(title, direction="TD")

            def add_decision_node(node: Dict, parent_id: Optional[str] = None, label: Optional[str] = None):
                """Recursively add decision nodes"""
                node_id = f"dec_{node.get('id', 'unknown')}"
                decision_text = node.get("decision", "Decision")

                flowchart.add_node(node_id, decision_text, node_type="decision")

                if parent_id:
                    flowchart.add_edge(parent_id, node_id, label)

                # Add branches
                for branch in node.get("branches", []):
                    branch_condition = branch.get("condition", "")
                    branch_outcome = branch.get("outcome", "")

                    if branch.get("branches"):
                        # Recursive decision
                        add_decision_node(
                            branch,
                            node_id,
                            branch_condition,
                        )
                    else:
                        # Leaf node (outcome)
                        outcome_id = f"out_{branch.get('id', 'unknown')}"
                        flowchart.add_node(outcome_id, branch_outcome, node_type="process")
                        flowchart.add_edge(node_id, outcome_id, branch_condition)

            add_decision_node(root_decision)
            return flowchart.build()

        except Exception as e:
            logger.error(f"Failed to generate decision tree: {e}")
            return ""

    async def generate_gantt_chart(
        self,
        activities: List[Dict[str, Any]],
        title: str = "Project Timeline",
    ) -> str:
        """
        Generate Gantt chart for timeline visualization.

        Args:
            activities: List of activities with dates
            title: Chart title

        Returns:
            Mermaid Gantt code
        """
        try:
            lines = [
                f"gantt",
                f"    title {title}",
                f"    dateFormat YYYY-MM-DD",
            ]

            for activity in activities:
                task_id = activity.get("id", "task").replace(" ", "_")
                task_name = activity.get("name", "Task")
                start_date = activity.get("start_date", "2026-02-01")
                end_date = activity.get("end_date", "2026-02-15")
                depends_on = activity.get("depends_on")

                if depends_on:
                    lines.append(f"    {task_id} : {task_name} : {start_date}, {end_date}")
                    lines.append(f"    {task_id} : crit, after {depends_on}, {end_date}")
                else:
                    lines.append(f"    {task_id} : {task_name} : {start_date}, {end_date}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to generate Gantt chart: {e}")
            return ""


def create_diagram_agent(llm_client, model: str = "gpt-4-turbo") -> DiagramAgent:
    """
    Factory function to create diagram agent.

    Args:
        llm_client: LLM client instance
        model: Model to use

    Returns:
        Initialized DiagramAgent
    """
    return DiagramAgent(llm_client=llm_client, model=model)
