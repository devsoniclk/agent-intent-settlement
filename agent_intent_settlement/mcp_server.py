"""Model Context Protocol (MCP) server for Autonomous Perpetual Intent Clearing Engine.

Exposes institutional batch auction clearing, toxic flow filtering, JIT routing,
ZK solvency verification, and strict VAULT trade directives over JSON-RPC 2.0 stdio transport.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .models import (
    AgentIntent,
    BatchAuctionResult,
    IntentDirection,
    IntentType,
    MatchedTrade,
    SolverRoutingExecution,
    VaultTradeDirective,
    Venue,
)
from .strategy import AutonomousPerpetualIntentClearingStrategy
from .simulator import IntentClearingSimulator
from .lvr_toxic_filter import LVRToxicFlowFilter


class AgentIntentSettlementMCPServer:
    """Stdio JSON-RPC 2.0 MCP server for autonomous multi-agent intent clearing."""

    def __init__(
        self,
        strategy: Optional[AutonomousPerpetualIntentClearingStrategy] = None,
    ) -> None:
        self.strategy = strategy or AutonomousPerpetualIntentClearingStrategy()
        self.simulator = IntentClearingSimulator(strategy=self.strategy)

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming JSON-RPC 2.0 MCP protocol requests."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "agent-intent-settlement",
                        "version": "0.1.0",
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "submit_intent",
                            "description": "Submit a declarative trading or compute lease intent to the batch mempool.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"},
                                    "asset": {"type": "string", "description": "e.g., ETHUSDT, SOLUSDT"},
                                    "direction": {"type": "string", "enum": ["BUY", "SELL"]},
                                    "limit_price": {"type": "number"},
                                    "quantity": {"type": "number"},
                                    "intent_type": {
                                        "type": "string",
                                        "enum": ["BUY_PERP", "SELL_PERP", "SPOT_SWAP", "COMPUTE_LEASE"],
                                        "default": "BUY_PERP",
                                    },
                                    "min_fill_ratio": {"type": "number", "default": 0.0},
                                    "urgency_decay": {"type": "number", "default": 0.0},
                                    "compute_voucher_id": {"type": "string"},
                                    "solvency_hash": {"type": "string"},
                                },
                                "required": ["agent_id", "asset", "direction", "limit_price", "quantity"],
                            },
                        },
                        {
                            "name": "clear_batch",
                            "description": "Solve discrete batch auction for an asset: filters toxic flow, discovers Uniform Clearing Price (UCP), executes internal CoW matches, and routes residual cross-venue with JIT delta hedge.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "batch_id": {"type": "string"},
                                    "asset": {"type": "string"},
                                    "reference_market_price": {"type": "number"},
                                    "intraday_vol": {"type": "number", "default": 0.03},
                                    "hl_depth_usd": {"type": "number", "default": 2500000.0},
                                    "uni_depth_usd": {"type": "number", "default": 1000000.0},
                                },
                                "required": ["batch_id", "asset", "reference_market_price"],
                            },
                        },
                        {
                            "name": "route_residual_jit",
                            "description": "Cross-venue JIT routing with automated offsetting perpetual delta hedging to eliminate solver inventory risk.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "batch_id": {"type": "string"},
                                    "asset": {"type": "string"},
                                    "residual_buy_volume": {"type": "number"},
                                    "residual_sell_volume": {"type": "number"},
                                    "market_price": {"type": "number"},
                                },
                                "required": ["batch_id", "asset", "residual_buy_volume", "residual_sell_volume", "market_price"],
                            },
                        },
                        {
                            "name": "filter_toxic_intents",
                            "description": "Screen a list of intents for adverse selection and latency arbitrage.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "fair_market_price": {"type": "number"},
                                    "intraday_vol": {"type": "number", "default": 0.03},
                                },
                                "required": ["fair_market_price"],
                            },
                        },
                        {
                            "name": "verify_compute_solvency",
                            "description": "Verify cryptographic proof of solvency for compute credit vouchers before batch inclusion.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"},
                                    "credit_voucher_usd": {"type": "number"},
                                    "required_collateral_usd": {"type": "number"},
                                    "proof_hash": {"type": "string"},
                                },
                                "required": ["agent_id", "credit_voucher_usd", "required_collateral_usd"],
                            },
                        },
                        {
                            "name": "get_mempool_status",
                            "description": "Inspect currently queued intents and completed auction history in the mempool.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "asset": {"type": "string"},
                                },
                            },
                        },
                        {
                            "name": "generate_vault_directive",
                            "description": "Generate an institutional VAULT compliant trade directive: ASSET | ACTION | ENTRY | SL | TP | LEV | R:R | SIZE.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "asset": {"type": "string"},
                                    "action": {"type": "string", "enum": ["BUY_PERP", "SELL_PERP", "BUY", "SELL"]},
                                    "current_market_price": {"type": "number"},
                                    "atr_14": {"type": "number"},
                                    "size_str": {"type": "string"},
                                    "leverage": {"type": "number", "default": 2.0},
                                    "direction": {"type": "string", "enum": ["LONG", "SHORT"], "default": "SHORT"},
                                },
                                "required": ["asset", "action", "current_market_price", "atr_14", "size_str"],
                            },
                        },
                    ],
                },
            }

        elif method == "tools/call":
            params_obj = params.get("arguments", {})
            tool_name = params.get("name")
            return self._call_tool(req_id, tool_name, params_obj)

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }

    def _call_tool(
        self, req_id: Any, tool_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatch tool calls to internal algorithms."""
        try:
            if tool_name == "submit_intent":
                itype = IntentType(args.get("intent_type", "BUY_PERP"))
                direction = IntentDirection(args["direction"])
                intent_id = args.get("intent_id") or f"INT-{args['asset'][:3]}-{int(time.time()*1000)}"
                intent = AgentIntent(
                    intent_id=intent_id,
                    agent_id=args["agent_id"],
                    asset=args["asset"],
                    intent_type=itype,
                    direction=direction,
                    limit_price=float(args["limit_price"]),
                    quantity=float(args["quantity"]),
                    min_fill_ratio=float(args.get("min_fill_ratio", 0.0)),
                    urgency_decay=float(args.get("urgency_decay", 0.0)),
                    timestamp=time.time(),
                    compute_voucher_id=args.get("compute_voucher_id"),
                    solvency_hash=args.get("solvency_hash"),
                )
                self.strategy.submit_intent(intent)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "status": "enqueued",
                                        "intent_id": intent_id,
                                        "pending_in_mempool": len(self.strategy.intent_mempool),
                                    },
                                    indent=2,
                                ),
                            }
                        ]
                    },
                }

            elif tool_name in ("clear_batch", "solve_batch"):
                batch_id = args["batch_id"]
                asset = args["asset"]
                ref_price = float(args["reference_market_price"])
                vol = float(args.get("intraday_vol", 0.03))
                hl_depth = float(args.get("hl_depth_usd", 2500000.0))
                uni_depth = float(args.get("uni_depth_usd", 1000000.0))

                batch_res = self.strategy.process_batch(
                    batch_id=batch_id,
                    asset=asset,
                    reference_market_price=ref_price,
                    intraday_vol=vol,
                    hl_depth_usd=hl_depth,
                    uni_depth_usd=uni_depth,
                )

                output_dict = {
                    "batch_id": batch_res.batch_id,
                    "asset": batch_res.asset,
                    "clearing_price": round(batch_res.clearing_price, 4),
                    "matched_cow_volume": round(batch_res.matched_cow_volume, 4),
                    "residual_buy_volume": round(batch_res.residual_buy_volume, 4),
                    "residual_sell_volume": round(batch_res.residual_sell_volume, 4),
                    "total_trader_surplus_usd": round(batch_res.total_trader_surplus_usd, 2),
                    "lvr_mitigated_usd": round(batch_res.lvr_mitigated_usd, 2),
                    "solver_profit_usd": round(batch_res.solver_profit_usd, 2),
                    "num_matched_trades": len(batch_res.matched_trades),
                    "num_residual_routes": len(batch_res.residual_executions),
                    "matched_trades": [
                        {
                            "trade_id": t.trade_id,
                            "buy_intent": t.buy_intent_id,
                            "sell_intent": t.sell_intent_id,
                            "quantity": t.quantity,
                            "clearing_price": t.clearing_price,
                            "surplus": round(t.buyer_surplus + t.seller_surplus, 2),
                        }
                        for t in batch_res.matched_trades
                    ],
                    "residual_executions": [
                        {
                            "route_id": r.route_id,
                            "venue": r.venue.value,
                            "action": r.action,
                            "quantity": r.quantity,
                            "price": round(r.execution_price, 4),
                            "slippage_bps": round(r.slippage_bps, 2),
                            "is_jit_hedge": r.is_jit_delta_hedged,
                        }
                        for r in batch_res.residual_executions
                    ],
                }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(output_dict, indent=2)}]
                    },
                }

            elif tool_name in ("filter_toxic_intents", "evaluate_toxicity"):
                fair_p = float(args["fair_market_price"])
                vol = float(args.get("intraday_vol", 0.03))

                if "direction" in args and "limit_price" in args:
                    intent = AgentIntent(
                        intent_id="EVAL",
                        agent_id="eval-agent",
                        asset=args.get("asset", "ETHUSDT"),
                        intent_type=IntentType.BUY_PERP,
                        direction=IntentDirection(args["direction"]),
                        limit_price=float(args["limit_price"]),
                        quantity=float(args.get("quantity", 1.0)),
                        urgency_decay=float(args.get("urgency_decay", 0.0)),
                    )
                    is_toxic, score = self.strategy.toxic_filter.evaluate_intent_toxicity(
                        intent, fair_p, vol
                    )
                    out = {
                        "is_toxic": is_toxic,
                        "toxicity_score": round(score, 4),
                        "toxicity_threshold": self.strategy.toxic_filter.toxicity_threshold,
                        "action_recommended": "DROP_INTENT" if is_toxic else "INCLUDE_IN_BATCH",
                    }
                else:
                    clean, toxic_ids, lvr = self.strategy.toxic_filter.filter_batch(
                        self.strategy.intent_mempool,
                        fair_market_price=fair_p,
                        intraday_vol=vol,
                    )
                    out = {
                        "clean_intents_count": len(clean),
                        "toxic_intents_count": len(toxic_ids),
                        "toxic_ids": toxic_ids,
                        "estimated_lvr_mitigation_usd": round(lvr, 2),
                    }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(out, indent=2)}
                        ]
                    },
                }

            elif tool_name in ("verify_compute_solvency", "verify_solvency"):
                valid = LVRToxicFlowFilter.verify_compute_credit_solvency(
                    agent_id=args["agent_id"],
                    credit_voucher_usd=float(args["credit_voucher_usd"]),
                    required_collateral_usd=float(args["required_collateral_usd"]),
                    proof_hash=args.get("proof_hash"),
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "solvency_verified": valid,
                                        "is_solvent": valid,
                                        "agent_id": args["agent_id"],
                                        "credit_voucher_usd": args["credit_voucher_usd"],
                                        "required_collateral_usd": args["required_collateral_usd"],
                                    },
                                    indent=2,
                                ),
                            }
                        ]
                    },
                }

            elif tool_name == "route_residual_jit":
                market_p = float(args.get("market_price", args.get("reference_market_price", 3000.0)))
                if "residual_buy_volume" in args or "residual_sell_volume" in args:
                    res_buy = float(args.get("residual_buy_volume", 0.0))
                    res_sell = float(args.get("residual_sell_volume", 0.0))
                else:
                    direction = str(args.get("direction", "BUY")).upper()
                    qty = float(args.get("residual_qty", 0.0))
                    res_buy = qty if direction == "BUY" else 0.0
                    res_sell = qty if direction == "SELL" else 0.0

                dummy_res = BatchAuctionResult(
                    batch_id=args["batch_id"],
                    timestamp=time.time(),
                    asset=args["asset"],
                    clearing_price=market_p,
                    matched_cow_volume=0.0,
                    residual_buy_volume=res_buy,
                    residual_sell_volume=res_sell,
                    total_trader_surplus_usd=0.0,
                    lvr_mitigated_usd=0.0,
                    solver_profit_usd=0.0,
                )
                executions = self.strategy.router.route_residual(
                    batch_result=dummy_res,
                    market_price=market_p,
                )
                has_hedge = any(ex.is_jit_delta_hedged for ex in executions)
                out = {
                    "batch_id": args["batch_id"],
                    "asset": args["asset"],
                    "is_hedged": has_hedge,
                    "executions_count": len(executions),
                    "executions": [
                        {
                            "route_id": ex.route_id,
                            "venue": ex.venue.value,
                            "action": ex.action,
                            "quantity": ex.quantity,
                            "price": ex.execution_price,
                            "fee_usd": ex.fee_usd,
                            "is_jit_delta_hedged": ex.is_jit_delta_hedged,
                        }
                        for ex in executions
                    ],
                }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(out, indent=2)}]},
                }

            elif tool_name == "get_mempool_status":
                asset_filter = args.get("asset")
                intents = self.strategy.intent_mempool
                if asset_filter:
                    intents = [i for i in intents if i.asset == asset_filter]
                out = {
                    "total_queued": len(intents),
                    "completed_batches": len(self.strategy.completed_batches),
                    "intents": [
                        {
                            "intent_id": i.intent_id,
                            "agent_id": i.agent_id,
                            "asset": i.asset,
                            "direction": i.direction.value,
                            "limit_price": i.limit_price,
                            "quantity": i.quantity,
                        }
                        for i in intents
                    ],
                }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(out, indent=2)}]},
                }

            elif tool_name == "generate_vault_directive":
                directive = self.strategy.generate_vault_hedge_directive(
                    asset=args["asset"],
                    action=args["action"],
                    current_market_price=float(args["current_market_price"]),
                    atr_14=float(args["atr_14"]),
                    size_str=args["size_str"],
                    leverage=float(args.get("leverage", 2.0)),
                    direction=args.get("direction", "SHORT"),
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "signal_text": directive.signal_text,
                                        "is_valid": directive.validate(),
                                        "asset": directive.asset,
                                        "action": directive.action,
                                        "entry": directive.entry,
                                        "sl": directive.sl,
                                        "tp": directive.tp,
                                        "lev": directive.lev,
                                        "risk_reward_ratio": round(directive.risk_reward_ratio, 2),
                                        "rr_ratio": round(directive.risk_reward_ratio, 2),
                                        "size": directive.size,
                                    },
                                    indent=2,
                                ),
                            }
                        ]
                    },
                }

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                }

        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(exc)},
            }

    def run_stdio(self) -> None:
        """Run stdio loop reading JSON-RPC messages."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


AgentIntentClearingMCPServer = AgentIntentSettlementMCPServer


def main() -> None:
    server = AgentIntentSettlementMCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
