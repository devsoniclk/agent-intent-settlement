"""Example: Autonomous AI Swarm Declarative Intent Settlement with JIT Delta Hedging."""

from agent_intent_settlement.models import AgentIntent, IntentType, IntentDirection
from agent_intent_settlement.strategy import AutonomousPerpetualIntentClearingStrategy


def main():
    print("=== Multi-Agent Intent Settlement & CoW Batch Clearing ===")
    strategy = AutonomousPerpetualIntentClearingStrategy(
        solver_fee_bps=2.0,
        jit_hedge_enabled=True,
        toxicity_threshold=0.70
    )

    market_price = 3100.0
    asset = "ETHUSDT"

    # Agent 1 wants to rebalance portfolio and buy 12 ETH with limit 3105
    strategy.submit_intent(AgentIntent(
        intent_id="INT-A01",
        agent_id="agent_alpha",
        asset=asset,
        intent_type=IntentType.BUY_PERP,
        direction=IntentDirection.BUY,
        limit_price=3105.0,
        quantity=12.0
    ))

    # Agent 2 wants to purchase compute lease and buy 8 ETH with limit 3102
    strategy.submit_intent(AgentIntent(
        intent_id="INT-B02",
        agent_id="agent_beta",
        asset=asset,
        intent_type=IntentType.COMPUTE_LEASE,
        direction=IntentDirection.BUY,
        limit_price=3102.0,
        quantity=8.0
    ))

    # Agent 3 takes profit and sells 15 ETH with min price 3096
    strategy.submit_intent(AgentIntent(
        intent_id="INT-C03",
        agent_id="agent_gamma",
        asset=asset,
        intent_type=IntentType.SELL_PERP,
        direction=IntentDirection.SELL,
        limit_price=3096.0,
        quantity=15.0
    ))

    # Agent 4 executes basis trade and sells 10 ETH with min price 3098
    strategy.submit_intent(AgentIntent(
        intent_id="INT-D04",
        agent_id="agent_delta",
        asset=asset,
        intent_type=IntentType.SELL_PERP,
        direction=IntentDirection.SELL,
        limit_price=3098.0,
        quantity=10.0
    ))

    # Toxic latency arbitrageur attempting to front-run stale feed
    strategy.submit_intent(AgentIntent(
        intent_id="INT-TOXIC",
        agent_id="toxic_sniper",
        asset=asset,
        intent_type=IntentType.BUY_PERP,
        direction=IntentDirection.BUY,
        limit_price=3180.0, # Excessive divergence (+2.58%)
        quantity=25.0,
        urgency_decay=0.08
    ))

    # Process batch auction
    result = strategy.process_batch(
        batch_id="BATCH-PROD-001",
        asset=asset,
        reference_market_price=market_price,
        intraday_vol=0.02
    )

    print(f"\n[Batch Result: {result.batch_id}]")
    print(f"Uniform Clearing Price (UCP): ${result.clearing_price:,.2f}")
    print(f"Matched CoW Volume: {result.matched_cow_volume:.2f} {asset}")
    print(f"Total Trader Surplus: ${result.total_trader_surplus_usd:,.2f}")
    print(f"Mitigated LVR Leakage: ${result.lvr_mitigated_usd:,.2f}")
    print(f"Solver Captured Fee: ${result.solver_profit_usd:,.2f}")

    print("\nMatched P2P CoW Trades:")
    for t in result.matched_trades:
        print(f"  - Trade {t.trade_id}: {t.quantity:.2f} {t.asset} @ ${t.clearing_price:,.2f} "
              f"(Buyer Surplus: ${t.buyer_surplus:.2f}, Seller Surplus: ${t.seller_surplus:.2f})")

    print(f"\nResidual Unhedged Volume:")
    print(f"  Buy Residual: {result.residual_buy_volume:.2f} {asset}")
    print(f"  Sell Residual: {result.residual_sell_volume:.2f} {asset}")

    print("\nRouted Executions & JIT Delta Hedges:")
    for ex in result.residual_executions:
        hedge_flag = "[JIT HEDGE]" if ex.is_jit_delta_hedged else "[ORDER ROUTE]"
        print(f"  - {hedge_flag} {ex.venue.value}: {ex.action} {ex.quantity:.2f} {ex.asset} "
              f"@ ${ex.execution_price:,.2f} (Slippage: {ex.slippage_bps:.2f} bps, Fee: ${ex.fee_usd:.2f})")


if __name__ == "__main__":
    main()
