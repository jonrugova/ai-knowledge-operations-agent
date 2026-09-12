import ast
import unittest
from pathlib import Path

import agent


class AgentToolContractTests(unittest.TestCase):
    def setUp(self):
        self.function_tools = [
            tool for tool in agent.TOOLS if tool.get("type") == "function"
        ]
        self.tools_by_name = {
            tool["name"]: tool for tool in self.function_tools
        }

    def test_exposed_tool_names_are_unique(self):
        names = [tool["name"] for tool in self.function_tools]

        self.assertEqual(len(names), len(set(names)))

    def test_required_tools_are_exposed(self):
        expected_names = {
            "search_company_knowledge",
            "calculate_delivery_timeline",
            "request_human_approval",
        }

        self.assertEqual(expected_names, set(self.tools_by_name))

    def test_human_decision_capabilities_are_not_exposed(self):
        dangerous_names = {
            "decide_approval",
            "approve_request",
            "reject_request",
            "approve",
            "reject",
            "execute_approved_rush",
            "resume_approved_workflow",
        }

        self.assertTrue(dangerous_names.isdisjoint(self.tools_by_name))

    def test_every_function_tool_is_strict(self):
        for tool in self.function_tools:
            with self.subTest(tool=tool["name"]):
                self.assertIs(tool.get("strict"), True)

    def test_parameter_schemas_reject_additional_properties(self):
        for tool in self.function_tools:
            with self.subTest(tool=tool["name"]):
                self.assertIs(
                    tool["parameters"].get("additionalProperties"),
                    False,
                )

    def test_every_declared_property_is_required(self):
        for tool in self.function_tools:
            with self.subTest(tool=tool["name"]):
                parameters = tool["parameters"]
                declared = set(parameters.get("properties", {}))
                required = set(parameters.get("required", []))
                self.assertEqual(required, declared)

    def test_request_human_approval_required_parameters(self):
        parameters = self.tools_by_name[
            "request_human_approval"
        ]["parameters"]

        self.assertEqual(
            set(parameters["required"]),
            {"reason", "user_request"},
        )
        self.assertNotIn("approval_type", parameters["properties"])
        self.assertNotIn("requested_by", parameters["properties"])

    def test_python_sets_canonical_type_for_approval_tool_dispatch(self):
        source = Path(agent.__file__).read_text(encoding="utf-8")

        self.assertIn(
            "approval_type=CANONICAL_RUSH_APPROVAL_TYPE",
            source,
        )

    def test_instructions_include_approval_and_execution_safety(self):
        instructions = agent.INSTRUCTIONS.lower()
        required_phrases = [
            "two-week rush, do not confirm the rush",
            "rush is not approved yet",
            "pending or rejected approval must never be treated as approved",
            "the agent itself cannot approve, reject, or directly execute",
            "protected actions resume only after an authorized human approval",
            "the human approval workflow reports execution",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, instructions)

    def test_instructions_define_internal_employee_context(self):
        instructions = agent.INSTRUCTIONS.lower()
        required_phrases = [
            "internal company knowledge and operations assistant",
            "the user is a company employee, not the customer",
            "do not assume the employee is the customer",
            "customer-facing reply wording",
            "using retrieved company knowledge",
            "otherwise, answer as an internal operational assistant",
        ]

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, instructions)

    def test_agent_imports_request_but_not_decision_function(self):
        source = Path(agent.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        approval_store_imports = set()

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "approval_store"
            ):
                approval_store_imports.update(
                    imported.name for imported in node.names
                )

        self.assertIn("create_approval_request", approval_store_imports)
        self.assertNotIn("decide_approval", approval_store_imports)


if __name__ == "__main__":
    unittest.main()