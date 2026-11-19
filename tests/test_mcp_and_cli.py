"""Unit test suite for FastMCP JSON-RPC server and Click/Rich CLI in agent-intent-settlement."""

import json
import unittest
from click.testing import CliRunner

from agent_intent_settlement.mcp_server import AgentIntentSettlementMCPServer
from agent_intent_settlement.cli import main
from agent_intent_settlement.models import AgentIntent, IntentType, IntentDirection


class TestMCPServer(unittest.TestCase):
    """Test suite for stdio FastMCP server request dispatching and tool executions."""

    def setUp(self):
        self.server = AgentIntentSettlementMCPServer()

    def test_mcp_initialize(self):
        """MCP initialize request returns server info and capabilities."""
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        resp = self.server.handle_request(req)
        self.assertEqual(resp["id"], 1)
        self.assertIn("serverInfo", resp["result"])
        self.assertEqual(resp["result"]["serverInfo"]["name"], "agent-intent-settlement")

    def test_mcp_tools_list(self):
        """MCP tools/list returns all 7 advertised tools."""
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        resp = self.server.handle_request(req)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertEqual(len(tools), 7)
        self.assertIn("submit_intent", tool_names)
        self.assertIn("clear_batch", tool_names)
        self.assertIn("route_residual_jit", tool_names)
        self.assertIn("filter_toxic_intents", tool_names)
        self.assertIn("verify_compute_solvency", tool_names)
        self.assertIn("get_mempool_status", tool_names)
        self.assertIn("generate_vault_directive", tool_names)

    def test_mcp_submit_and_clear_batch_flow(self):
        """Submit intents via MCP tool call and clear batch."""
        # 1. Submit buy intent
        call_buy = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "submit_intent",
                "arguments": {
                    "intent_id": "MCP-BUY-1",
                    "agent_id": "agent_alpha",
                    "asset": "ETHUSDT",
                    "direction": "BUY",
                    "limit_price": 3105.0,
                    "quantity": 10.0,
                }
            }
        }
        resp_buy = self.server.handle_request(call_buy)
        self.assertNotIn("error", resp_buy)
        data_buy = json.loads(resp_buy["result"]["content"][0]["text"])
        self.assertEqual(data_buy["status"], "enqueued")

        # 2. Submit sell intent
        call_sell = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "submit_intent",
                "arguments": {
                    "intent_id": "MCP-SELL-1",
                    "agent_id": "agent_beta",
                    "asset": "ETHUSDT",
                    "direction": "SELL",
                    "limit_price": 3095.0,
                    "quantity": 10.0,
                }
            }
        }
        resp_sell = self.server.handle_request(call_sell)
        self.assertNotIn("error", resp_sell)

        # 3. Check mempool status
        call_status = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_mempool_status",
                "arguments": {"asset": "ETHUSDT"}
            }
        }
        resp_status = self.server.handle_request(call_status)
        data_status = json.loads(resp_status["result"]["content"][0]["text"])
        self.assertEqual(data_status["total_queued"], 2)

        # 4. Clear batch
        call_clear = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "clear_batch",
                "arguments": {
                    "batch_id": "BATCH-MCP-01",
                    "asset": "ETHUSDT",
                    "reference_market_price": 3100.0,
                }
            }
        }
        resp_clear = self.server.handle_request(call_clear)
        self.assertNotIn("error", resp_clear)
        data_clear = json.loads(resp_clear["result"]["content"][0]["text"])
        self.assertEqual(data_clear["matched_cow_volume"], 10.0)
        self.assertEqual(data_clear["clearing_price"], 3100.0)

    def test_mcp_solvency_verification(self):
        """MCP tool call for verify_compute_solvency."""
        call_solv = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "verify_compute_solvency",
                "arguments": {
                    "agent_id": "agent_gpu_cluster",
                    "credit_voucher_usd": 5000.0,
                    "required_collateral_usd": 4000.0,
                    "proof_hash": "proof_valid_12345678"
                }
            }
        }
        resp = self.server.handle_request(call_solv)
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertTrue(data["is_solvent"])

    def test_mcp_vault_directive(self):
        """MCP tool call for generate_vault_directive."""
        call_vd = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "generate_vault_directive",
                "arguments": {
                    "asset": "ETHUSDT",
                    "action": "SELL_PERP",
                    "current_market_price": 3100.0,
                    "atr_14": 62.0,
                    "size_str": "45.0_ETH",
                    "leverage": 2.0,
                    "direction": "SHORT"
                }
            }
        }
        resp = self.server.handle_request(call_vd)
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertTrue(data["is_valid"])
        self.assertEqual(data["asset"], "ETHUSDT")

    def test_mcp_unknown_tool_and_method(self):
        """Unknown tool returns JSON-RPC error."""
        call_bad = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "non_existent_tool", "arguments": {}}
        }
        resp = self.server.handle_request(call_bad)
        self.assertIn("error", resp)

        bad_method = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "unknown_rpc_method",
            "params": {}
        }
        resp_m = self.server.handle_request(bad_method)
        self.assertEqual(resp_m["error"]["code"], -32601)


class TestCLI(unittest.TestCase):
    """Test suite for Click/Rich CLI commands."""

    def setUp(self):
        self.runner = CliRunner()

    def test_cli_status(self):
        """CLI status command exits with 0 and prints status."""
        result = self.runner.invoke(main, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Autonomous Agent Perpetual Intent Clearing Engine", result.output)
        self.assertIn("HYPERLIQUID_PERP", result.output)

    def test_cli_clear(self):
        """CLI clear command simulates a batch clearing."""
        result = self.runner.invoke(main, ["clear", "--asset", "ETHUSDT", "--price", "3100.0"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Batch Cleared successfully", result.output)

    def test_cli_benchmark_short(self):
        """CLI benchmark runs short simulation and renders table."""
        result = self.runner.invoke(main, ["benchmark", "--days", "1", "--batches-per-day", "2"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Performance Metric", result.output)
        self.assertIn("Regime C", result.output)


if __name__ == "__main__":
    unittest.main()
