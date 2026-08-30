from __future__ import annotations

import unittest

from enterprise_fabric.model_gateway import validate_tool_suggestions


class ModelGatewayTests(unittest.TestCase):
    def test_accepts_only_allowlisted_tools_and_deduplicates(self) -> None:
        result = validate_tool_suggestions(
            {"tools": ["payments.lookup", "integration.trace", "payments.lookup"]},
            ["payments.lookup", "integration.trace"],
        )
        self.assertEqual(result, ["payments.lookup", "integration.trace"])

    def test_rejects_hallucinated_tool(self) -> None:
        with self.assertRaises(ValueError):
            validate_tool_suggestions(
                {"tools": ["payments.delete_everything"]},
                ["payments.lookup"],
            )


if __name__ == "__main__":
    unittest.main()
