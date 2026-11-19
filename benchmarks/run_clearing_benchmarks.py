"""Benchmark suite: Throughput and latency scaling of combinatorial MILP clearing engine."""

import time
from agent_intent_settlement import (
    AutonomousPerpetualIntentClearingStrategy,
    IntentClearingSimulator,
)


def run_benchmarks():
    print("=== Combinatorial Intent Clearing Engine Performance Benchmarks ===")

    sim = IntentClearingSimulator(seed=42)
    scales = [50, 200, 500, 1000, 2500]

    print(f"{'Intents':<10} | {'Solve Time (ms)':<16} | {'Throughput (intents/s)':<22} | {'Matched Vol':<14} | {'Trader Surplus ($)':<18}")
    print("-" * 86)

    for count in scales:
        strategy = AutonomousPerpetualIntentClearingStrategy()
        intents = sim.generate_synthetic_intents(
            asset="ETHUSDT",
            count=count,
            reference_price=3000.0,
            volatility=0.02,
            toxic_ratio=0.10,
        )
        for i in intents:
            strategy.submit_intent(i)

        t0 = time.perf_counter()
        res = strategy.process_batch(
            batch_id=f"BENCH-{count}",
            asset="ETHUSDT",
            reference_market_price=3000.0,
            intraday_vol=0.02,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        throughput = count / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0.0

        print(
            f"{count:<10} | {elapsed_ms:<16.2f} | {throughput:<22.1f} | {res.matched_cow_volume:<14.2f} | ${res.total_trader_surplus_usd:<17.2f}"
        )


if __name__ == "__main__":
    run_benchmarks()
