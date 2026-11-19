"""Example: End-to-end CoW batch auction execution with multi-agent intents."""

import time
from agent_intent_settlement import (
    AutonomousPerpetualIntentClearingStrategy,
    AgentIntent,
    IntentType,
    IntentDirection,
)


def main():
    print("=== Autonomous Agent CoW Batch Auction Execution ===")

    strategy = AutonomousPerpetualIntentClearingStrategy(
        solver_fee_bps=2.0,
        jit_hedge_enabled=True,
        toxicity_threshold=0.70,
    )

    # 1. Ingest multi-agent intents
    intents = [
        AgentIntent("B-01", "agent-alpha", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3015.0, 4.0),
        AgentIntent("B-02", "agent-gamma", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3025.0, 2.5),
        AgentIntent("B-03", "agent-delta", "ETHUSDT", IntentType.SPOT_SWAP, IntentDirection.BUY, 3010.0, 1.5),
        AgentIntent("S-01", "agent-omega", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2985.0, 5.0),
        AgentIntent("S-02", "agent-sigma", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2995.0, 2.0),
        AgentIntent("S-03", "agent-toxic", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2800.0, 10.0), # Toxic
    ]

    for i in intents:
        strategy.submit_intent(i)

    print(f"Queued {len(intents)} intents into mempool.")

    # 2. Process batch
    result = strategy.process_batch(
        batch_id="BATCH-EXAMPLE-01",
        asset="ETHUSDT",
        reference_market_price=3000.0,
        intraday_vol=0.02,
    )

    print("\n--- Auction Outcome ---")
    print(f"Batch ID: {result.batch_id}")
    print(f"Asset: {result.asset}")
    print(f"Uniform Clearing Price: ${result.clearing_price:.4f}")
    print(f"CoW Matched Volume: {result.matched_cow_volume:.4f} ETH")
    print(f"Residual Buy Volume: {result.residual_buy_volume:.4f} ETH")
    print(f"Residual Sell Volume: {result.residual_sell_volume:.4f} ETH")
    print(f"Total Trader Surplus: ${result.total_trader_surplus_usd:.2f}")
    print(f"LVR Mitigated: ${result.lvr_mitigated_usd:.2f}")
    print(f"Solver Profit: ${result.solver_profit_usd:.2f}")

    print("\n--- Matched CoW Trades ---")
    for t in result.matched_trades:
        print(f"  {t.trade_id}: {t.buy_intent_id} <-> {t.sell_intent_id} | {t.quantity:.4f} ETH @ ${t.clearing_price:.2f} | Surplus: ${t.buyer_surplus + t.seller_surplus:.2f}")

    print("\n--- Cross-Venue Residual Routing & Delta Hedges ---")
    for r in result.residual_executions:
        print(f"  {r.route_id}: {r.venue.value} | {r.action} {r.quantity:.4f} ETH @ ${r.execution_price:.2f} | Hedge: {r.is_jit_delta_hedged}")


if __name__ == "__main__":
    main()
