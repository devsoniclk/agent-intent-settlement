"""Unit tests for JSON-RPC 2.0 MCP server."""

import json
import pytest
from agent_intent_settlement.mcp_server import AgentIntentSettlementMCPServer


class TestMCPServer:
    """Test suite for MCP server request handling."""

    def setup_method(self):
        self.server = AgentIntentSettlementMCPServer()

    def test_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        res = self.server.handle_request(req)
        assert res["id"] == 1
        assert res["result"]["protocolVersion"] == "2024-11-05"
        assert res["result"]["serverInfo"]["name"] == "agent-intent-settlement"

    def test_tools_list(self):
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        res = self.server.handle_request(req)
        assert res["id"] == 2
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert len(tools) == 7
        assert "submit_intent" in tool_names
        assert "clear_batch" in tool_names
        assert "route_residual_jit" in tool_names
        assert "filter_toxic_intents" in tool_names
        assert "verify_compute_solvency" in tool_names
        assert "get_mempool_status" in tool_names
        assert "generate_vault_directive" in tool_names

    def test_ping(self):
        req = {"jsonrpc": "2.0", "id": 3, "method": "ping"}
        res = self.server.handle_request(req)
        assert res["id"] == 3
        assert res["result"] == {}

    def test_unknown_method(self):
        req = {"jsonrpc": "2.0", "id": 4, "method": "unknown_rpc_call"}
        res = self.server.handle_request(req)
        assert res["id"] == 4
        assert "error" in res
        assert res["error"]["code"] == -32601

    def test_tool_submit_intent_and_clear_batch(self):
        # 1. Submit buy intent
        req1 = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "submit_intent",
                "arguments": {
                    "agent_id": "agent-1",
                    "asset": "ETHUSDT",
                    "direction": "BUY",
                    "limit_price": 3020.0,
                    "quantity": 2.0,
                    "intent_type": "BUY_PERP",
                },
            },
        }
        res1 = self.server.handle_request(req1)
        assert res1["id"] == 10
        content1 = json.loads(res1["result"]["content"][0]["text"])
        assert content1["status"] == "enqueued"

        # 2. Submit sell intent
        req2 = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "submit_intent",
                "arguments": {
                    "agent_id": "agent-2",
                    "asset": "ETHUSDT",
                    "direction": "SELL",
                    "limit_price": 2980.0,
                    "quantity": 1.5,
                    "intent_type": "SELL_PERP",
                },
            },
        }
        res2 = self.server.handle_request(req2)
        assert res2["id"] == 11

        # 3. Clear batch
        req3 = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "clear_batch",
                "arguments": {
                    "batch_id": "BATCH-MCP-01",
                    "asset": "ETHUSDT",
                    "reference_market_price": 3000.0,
                },
            },
        }
        res3 = self.server.handle_request(req3)
        assert res3["id"] == 12
        content3 = json.loads(res3["result"]["content"][0]["text"])
        assert content3["asset"] == "ETHUSDT"
        assert content3["matched_cow_volume"] == 1.5
        assert content3["residual_buy_volume"] == 0.5

    def test_tool_evaluate_toxicity(self):
        req = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "filter_toxic_intents",
                "arguments": {
                    "direction": "BUY",
                    "limit_price": 3200.0,
                    "quantity": 10.0,
                    "fair_market_price": 3000.0,
                },
            },
        }
        res = self.server.handle_request(req)
        assert res["id"] == 20
        content = json.loads(res["result"]["content"][0]["text"])
        assert content["is_toxic"] is True
        assert content["action_recommended"] == "DROP_INTENT"

    def test_tool_verify_solvency(self):
        req = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "verify_compute_solvency",
                "arguments": {
                    "agent_id": "agent-zk",
                    "credit_voucher_usd": 1000.0,
                    "required_collateral_usd": 800.0,
                    "proof_hash": "proof_hash_1234567890",
                },
            },
        }
        res = self.server.handle_request(req)
        assert res["id"] == 30
        content = json.loads(res["result"]["content"][0]["text"])
        assert content["is_solvent"] is True

    def test_tool_generate_vault_directive(self):
        req = {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "generate_vault_directive",
                "arguments": {
                    "asset": "ETHUSDT",
                    "action": "SELL",
                    "current_market_price": 3000.0,
                    "atr_14": 40.0,
                    "size_str": "2.5 ETH",
                    "leverage": 2.0,
                    "direction": "SHORT",
                },
            },
        }
        res = self.server.handle_request(req)
        assert res["id"] == 40
        content = json.loads(res["result"]["content"][0]["text"])
        assert content["is_valid"] is True
        assert "ETHUSDT | SELL" in content["signal_text"]

    def test_tool_route_residual_jit(self):
        req = {
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {
                "name": "route_residual_jit",
                "arguments": {
                    "batch_id": "B-ROUTE-01",
                    "asset": "ETHUSDT",
                    "residual_qty": 3.0,
                    "direction": "BUY",
                    "reference_market_price": 3000.0,
                },
            },
        }
        res = self.server.handle_request(req)
        assert res["id"] == 50
        content = json.loads(res["result"]["content"][0]["text"])
        assert content["is_hedged"] is True
        assert content["executions_count"] >= 1
