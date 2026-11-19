"""Example: Asymmetric order flow clearing with automated JIT perpetual delta hedging."""

from agent_intent_settlement import (
    AutonomousPerpetualIntentClearingStrategy,
    AgentIntent,
    IntentType,
    IntentDirection,
)


def main():
    print("=== Asymmetric Flow Clearing & JIT Perpetual Delta Hedging ===")

    strategy = AutonomousPerpetualIntentClearingStrategy(
        solver_fee_bps=2.0,
        jit_hedge_enabled=True,
    )

    # Heavily buy-biased flow: 25 ETH buy demand vs 10 ETH sell reserve
    strategy.submit_intent(
        AgentIntent("B-01", "buyer-large", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3010.0, 25.0)
    )
    strategy.submit_intent(
        AgentIntent("S-01", "seller-small", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2990.0, 10.0)
    )

    print("Queued asymmetric intents: 25.0 ETH Buy vs 10.0 ETH Sell.")

    result = strategy.process_batch(
        batch_id="BATCH-ASYMM-01",
        asset="ETHUSDT",
        reference_market_price=3000.0,
    )

    print(f"\n--- Batch Execution ---")
    print(f"CoW Matched: {result.matched_cow_volume:.2f} ETH (Zero Slippage, Zero L1 Gas)")
    print(f"Residual Buy Imbalance: {result.residual_buy_volume:.2f} ETH")

    print("\n--- Cross-Venue Routing & 100% Delta Neutrality Preservation ---")
    for r in result.residual_executions:
        hedge_tag = "[JIT PERPETUAL HEDGE]" if r.is_jit_delta_hedged else "[OUTSIDE ROUTE]"
        print(f"  {hedge_tag} {r.venue.value}: {r.action} {r.quantity:.2f} ETH @ ${r.execution_price:.2f} (Slippage: {r.slippage_bps:.2f} bps)")

    # Emit VAULT directive
    directive = strategy.generate_vault_hedge_directive(
        asset="ETHUSDT",
        action="BUY",
        current_market_price=3000.0,
        atr_14=42.0,
        size_str=f"{result.residual_buy_volume:.1f} ETH",
        leverage=2.0,
        direction="LONG",
    )
    print(f"\n--- Strict Institutional VAULT Directive ---")
    print(f"Directive Signal: {directive.signal_text}")
    print(f"Risk/Reward Ratio: {directive.risk_reward_ratio:.2f}:1 (Valid: {directive.validate()})")


if __name__ == "__main__":
    main()
