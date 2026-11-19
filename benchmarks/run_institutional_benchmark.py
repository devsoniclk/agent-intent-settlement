"""Benchmark runner and comparative analysis for Autonomous Agent Perpetual Intent Clearing Engine.

Executes 90-day multi-agent stress simulation across:
1. Regime A: Continuous AMM Execution (Traditional DEX)
2. Regime B: Simple Batch Auction without JIT Hedging
3. Regime C: Autonomous Perpetual Intent Clearing Engine (Ours)

Emits institutional dossier and VAULT trade directives.
"""

import sys
from agent_intent_settlement.simulator import IntentClearingSimulator
from agent_intent_settlement.strategy import AutonomousPerpetualIntentClearingStrategy


def run_benchmark():
    """Execute simulation benchmark and format results table."""
    sim = IntentClearingSimulator(seed=42)
    results = sim.run_simulation(days=90, batches_per_day=24)

    reg_a = results["regime_a_amm"]
    reg_b = results["regime_b_simple_batch"]
    reg_c = results["regime_c_intent_clearing"]

    print("=" * 105)
    print("AUTONOMOUS AGENT PERPETUAL INTENT CLEARING ENGINE — 90-DAY INSTITUTIONAL BENCHMARK")
    print("=" * 105)
    print(f"Total Batches Processed: {results['total_batches']:,} | Simulation Duration: {results['days']} Days")
    print(f"Total Agent Volume Cleared: ${reg_c['total_volume_usd']:,.2f}")
    print("-" * 105)
    print(f"{'Performance Metric':<35} | {'Regime A: AMM':<20} | {'Regime B: Simple Batch':<20} | {'Regime C: Intent Engine':<22}")
    print("-" * 105)
    print(f"{'Internal CoW Match Rate %':<35} | {'0.00%':<20} | {reg_b['cow_match_rate_pct']:<19.2f}% | {reg_c['cow_match_rate_pct']:<21.2f}%")
    print(f"{'Total Trader Surplus ($)':<35} | ${reg_a['trader_surplus_usd']:<19,.2f} | ${reg_b['trader_surplus_usd']:<19,.2f} | ${reg_c['trader_surplus_usd']:<21,.2f}")
    print(f"{'LVR Loss / Mitigation ($)':<35} | -${reg_a['lvr_loss_usd']:<18,.2f} | -${reg_b['lvr_loss_usd']:<18,.2f} | +${reg_c['lvr_mitigated_usd']:<20,.2f}")
    print(f"{'Slippage / Gas Friction ($)':<35} | -${reg_a['slippage_friction_usd']:<18,.2f} | {'Excluded in CoW':<20} | {'Zero on CoW Matches':<22}")
    print(f"{'Solver Net Profit ($)':<35} | {'$0.00 (No Solvers)':<20} | ${reg_b['solver_pnl_usd']:<19,.2f} | ${reg_c['solver_pnl_usd']:<21,.2f}")
    print(f"{'Solver Max Drawdown ($)':<35} | {'N/A':<20} | -${reg_b['solver_max_drawdown_usd']:<18,.2f} | ${reg_c['solver_max_drawdown_usd']:<21,.2f}")
    print("=" * 105)

    # Generate VAULT Trade Directives
    strategy = AutonomousPerpetualIntentClearingStrategy()
    print("\n" + "=" * 105)
    print("MANDATORY VAULT INSTITUTIONAL TRADE DIRECTIVES (JIT Delta-Neutral Hedges & Basis Execution)")
    print("Format: ASSET | ACTION | ENTRY | SL | TP | LEV | R:R | SIZE")
    print("=" * 105)

    sig1 = strategy.generate_vault_hedge_directive(
        asset="ETHUSDT",
        action="SELL_PERP",
        current_market_price=3100.0,
        atr_14=62.0,
        size_str="45.0_ETH",
        leverage=2.0,
        direction="SHORT"
    )
    print(f"SIGNAL 1: {sig1.signal_text}")

    sig2 = strategy.generate_vault_hedge_directive(
        asset="SOLUSDT",
        action="BUY_PERP",
        current_market_price=182.50,
        atr_14=5.20,
        size_str="600.0_SOL",
        leverage=2.0,
        direction="LONG"
    )
    print(f"SIGNAL 2: {sig2.signal_text}")

    sig3 = strategy.generate_vault_hedge_directive(
        asset="BTCUSDT",
        action="SELL_PERP",
        current_market_price=92000.0,
        atr_14=1800.0,
        size_str="1.20_BTC",
        leverage=1.5,
        direction="SHORT"
    )
    print(f"SIGNAL 3: {sig3.signal_text}")
    print("=" * 105)

    return results


if __name__ == "__main__":
    run_benchmark()
