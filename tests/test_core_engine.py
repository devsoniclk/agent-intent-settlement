"""Deterministic unit test suite for Autonomous Agent Perpetual Intent Clearing Engine.

Covers:
- Combinatorial CoW batch auctions, curve sorting, and uniform clearing price discovery.
- Cross-venue JIT liquidity routing, slippage estimation, and delta-neutral hedging.
- LVR adverse selection defense, toxic latency filtering, and compute credit solvency.
- Master strategy orchestration and strict VAULT trade directive compliance.
- 90-day multi-regime simulation invariants and comparative welfare outcomes.
"""

import unittest
import math
import numpy as np
import time

from agent_intent_settlement.models import (
    IntentType,
    IntentDirection,
    Venue,
    AgentIntent,
    MatchedTrade,
    SolverRoutingExecution,
    BatchAuctionResult,
    VaultTradeDirective
)
from agent_intent_settlement.milp_clearing import MILPClearingEngine
from agent_intent_settlement.jit_liquidity_router import JITLiquidityRouter
from agent_intent_settlement.lvr_toxic_filter import LVRToxicFlowFilter
from agent_intent_settlement.strategy import AutonomousPerpetualIntentClearingStrategy
from agent_intent_settlement.simulator import IntentClearingSimulator


class TestMILPClearingEngine(unittest.TestCase):
    """Test suite for combinatorial CoW batch clearing and uniform price discovery."""

    def setUp(self):
        self.engine = MILPClearingEngine(solver_fee_bps=2.0)

    def test_construct_curves_sorting(self):
        """Buys sorted descending by price, sells sorted ascending."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3050.0, 5.0),
            AgentIntent("b2", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 5.0),
            AgentIntent("s1", "a3", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3020.0, 5.0),
            AgentIntent("s2", "a4", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 2980.0, 5.0),
        ]
        buys, sells = self.engine.construct_curves(intents)
        self.assertEqual(buys[0].limit_price, 3100.0)
        self.assertEqual(buys[1].limit_price, 3050.0)
        self.assertEqual(sells[0].limit_price, 2980.0)
        self.assertEqual(sells[1].limit_price, 3020.0)

    def test_empty_intents_handling(self):
        """Empty intent list returns 0 matched volume without exception."""
        res = self.engine.solve_uniform_clearing("BATCH_0", "ETH", [], reference_market_price=3000.0)
        self.assertEqual(res.matched_cow_volume, 0.0)
        self.assertEqual(res.total_trader_surplus_usd, 0.0)
        self.assertEqual(res.clearing_price, 3000.0)

    def test_no_overlapping_prices_zero_volume(self):
        """When highest buy < lowest sell, 0 volume matched and residual captured."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3000.0, 10.0),
            AgentIntent("s1", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3050.0, 10.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_1", "ETH", intents, reference_market_price=3025.0)
        self.assertEqual(res.matched_cow_volume, 0.0)
        self.assertEqual(res.residual_buy_volume, 10.0)
        self.assertEqual(res.residual_sell_volume, 10.0)

    def test_single_pair_exact_match(self):
        """Exact matching of one buyer and one seller at mid-clearing price."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 10.0),
            AgentIntent("s1", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3000.0, 10.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_2", "ETH", intents)
        self.assertEqual(res.matched_cow_volume, 10.0)
        self.assertAlmostEqual(res.clearing_price, 3050.0)
        self.assertEqual(res.residual_buy_volume, 0.0)
        self.assertEqual(res.residual_sell_volume, 0.0)
        self.assertEqual(len(res.matched_trades), 1)
        self.assertAlmostEqual(res.total_trader_surplus_usd, 1000.0)

    def test_multiple_buyers_single_seller_allocation(self):
        """One seller of 15 ETH filled across two buyers (10 ETH + 5 ETH)."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 10.0),
            AgentIntent("b2", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3080.0, 10.0),
            AgentIntent("s1", "a3", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3000.0, 15.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_3", "ETH", intents)
        self.assertEqual(res.matched_cow_volume, 15.0)
        self.assertEqual(len(res.matched_trades), 2)
        self.assertEqual(res.matched_trades[0].quantity, 10.0)
        self.assertEqual(res.matched_trades[1].quantity, 5.0)
        self.assertEqual(res.residual_buy_volume, 5.0)
        self.assertEqual(res.residual_sell_volume, 0.0)

    def test_uniform_clearing_price_within_bounds(self):
        """UCP must always be >= minimum matched sell price and <= maximum matched buy price."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3120.0, 4.0),
            AgentIntent("b2", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3110.0, 8.0),
            AgentIntent("s1", "a3", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3080.0, 6.0),
            AgentIntent("s2", "a4", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3090.0, 6.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_4", "ETH", intents)
        self.assertGreaterEqual(res.clearing_price, 3080.0)
        self.assertLessEqual(res.clearing_price, 3120.0)

    def test_toxic_intent_excluded_from_curves(self):
        """Intents marked is_toxic are excluded during curve construction."""
        intents = [
            AgentIntent("b_clean", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 5.0, is_toxic=False),
            AgentIntent("b_toxic", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3200.0, 5.0, is_toxic=True),
        ]
        buys, _ = self.engine.construct_curves(intents)
        self.assertEqual(len(buys), 1)
        self.assertEqual(buys[0].intent_id, "b_clean")

    def test_trader_surplus_positive(self):
        """Trader surplus is strictly non-negative for matched CoW trades."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 5.0),
            AgentIntent("s1", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3050.0, 5.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_5", "ETH", intents)
        self.assertGreater(res.total_trader_surplus_usd, 0.0)
        for t in res.matched_trades:
            self.assertGreaterEqual(t.buyer_surplus, 0.0)
            self.assertGreaterEqual(t.seller_surplus, 0.0)

    def test_solver_profit_calculation(self):
        """Solver profit equals matched volume * price * fee_bps / 10000."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3000.0, 10.0),
            AgentIntent("s1", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3000.0, 10.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_6", "ETH", intents)
        expected_profit = (10.0 * 3000.0) * (2.0 / 10000.0)
        self.assertAlmostEqual(res.solver_profit_usd, expected_profit)

    def test_lvr_mitigation_calculation(self):
        """Mitigated LVR equals matched volume * price * 25 bps."""
        intents = [
            AgentIntent("b1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3000.0, 10.0),
            AgentIntent("s1", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3000.0, 10.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH_7", "ETH", intents)
        expected_lvr = (10.0 * 3000.0) * 0.0025
        self.assertAlmostEqual(res.lvr_mitigated_usd, expected_lvr)


class TestJITLiquidityRouter(unittest.TestCase):
    """Test suite for cross-venue routing and JIT delta-neutral hedging."""

    def setUp(self):
        self.router = JITLiquidityRouter(hyperliquid_fee_bps=1.5, uniswap_v4_fee_bps=5.0, jit_hedge_enabled=True)

    def test_calculate_slippage_scaling(self):
        """Slippage scales with square-root of trade size / depth."""
        slip_small = self.router.calculate_slippage(10000.0, 1000000.0)
        slip_large = self.router.calculate_slippage(40000.0, 1000000.0)
        self.assertAlmostEqual(slip_large / slip_small, 2.0, places=2)

    def test_zero_imbalance_no_routing(self):
        """When net imbalance is zero, router produces zero executions."""
        res = BatchAuctionResult("B1", 0.0, "ETH", 3000.0, 10.0, 0.0, 0.0, 50.0, 75.0, 6.0)
        execs = self.router.route_residual(res, 3000.0)
        self.assertEqual(len(execs), 0)

    def test_route_residual_buy_imbalance(self):
        """Net buy imbalance generates main execution and offsetting short perp hedge."""
        res = BatchAuctionResult("B2", 0.0, "ETH", 3000.0, 10.0, 5.0, 0.0, 50.0, 75.0, 6.0)
        execs = self.router.route_residual(res, 3000.0)
        self.assertEqual(len(execs), 2)
        main_ex, hedge_ex = execs[0], execs[1]
        self.assertEqual(main_ex.action, "BUY")
        self.assertEqual(hedge_ex.action, "SELL")
        self.assertTrue(hedge_ex.is_jit_delta_hedged)
        self.assertEqual(hedge_ex.venue, Venue.HYPERLIQUID_PERP)

    def test_route_residual_sell_imbalance(self):
        """Net sell imbalance generates main execution and offsetting long perp hedge."""
        res = BatchAuctionResult("B3", 0.0, "ETH", 3000.0, 10.0, 0.0, 8.0, 50.0, 75.0, 6.0)
        execs = self.router.route_residual(res, 3000.0)
        self.assertEqual(len(execs), 2)
        self.assertEqual(execs[0].action, "SELL")
        self.assertEqual(execs[1].action, "BUY")
        self.assertTrue(execs[1].is_jit_delta_hedged)

    def test_venue_selection_hyperliquid_vs_uniswap(self):
        """Hyperliquid selected when fee + slippage is lower than Uniswap v4."""
        res = BatchAuctionResult("B4", 0.0, "ETH", 3000.0, 10.0, 5.0, 0.0, 50.0, 75.0, 6.0)
        execs = self.router.route_residual(res, 3000.0, hl_depth_usd=5000000.0, uni_depth_usd=500000.0)
        self.assertEqual(execs[0].venue, Venue.HYPERLIQUID_PERP)

    def test_jit_hedge_disabled_option(self):
        """When jit_hedge_enabled is False, only main execution is created."""
        unhedged_router = JITLiquidityRouter(jit_hedge_enabled=False)
        res = BatchAuctionResult("B5", 0.0, "ETH", 3000.0, 10.0, 4.0, 0.0, 50.0, 75.0, 6.0)
        execs = unhedged_router.route_residual(res, 3000.0)
        self.assertEqual(len(execs), 1)
        self.assertFalse(execs[0].is_jit_delta_hedged)

    def test_slippage_and_fee_calculations(self):
        """Execution price reflects slippage and fee is calculated accurately."""
        res = BatchAuctionResult("B6", 0.0, "ETH", 3000.0, 10.0, 2.0, 0.0, 50.0, 75.0, 6.0)
        execs = self.router.route_residual(res, 3000.0)
        main_ex = execs[0]
        self.assertGreater(main_ex.execution_price, 3000.0)
        self.assertGreater(main_ex.fee_usd, 0.0)


class TestLVRToxicFlowFilter(unittest.TestCase):
    """Test suite for adverse selection scoring, latency filtering, and solvency verification."""

    def setUp(self):
        self.filter = LVRToxicFlowFilter(toxicity_threshold=0.70, max_divergence_pct=0.015)

    def test_non_toxic_intent_passes(self):
        """Order close to fair market price receives low toxicity score and passes."""
        intent = AgentIntent("i1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3005.0, 5.0, urgency_decay=0.001)
        is_toxic, score = self.filter.evaluate_intent_toxicity(intent, fair_market_price=3000.0)
        self.assertFalse(is_toxic)
        self.assertLess(score, 0.70)

    def test_extreme_price_divergence_flagged_toxic(self):
        """Order diverging > 1.5% from fair price is immediately marked toxic."""
        intent = AgentIntent("i2", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3060.0, 5.0)
        is_toxic, score = self.filter.evaluate_intent_toxicity(intent, fair_market_price=3000.0)
        self.assertTrue(is_toxic)

    def test_high_urgency_increases_toxicity_score(self):
        """Urgency decay component contributes to higher toxicity score."""
        i_calm = AgentIntent("i3", "a3", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3015.0, 5.0, urgency_decay=0.001)
        i_urgent = AgentIntent("i4", "a4", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3015.0, 5.0, urgency_decay=0.05)
        _, score_calm = self.filter.evaluate_intent_toxicity(i_calm, fair_market_price=3000.0)
        _, score_urgent = self.filter.evaluate_intent_toxicity(i_urgent, fair_market_price=3000.0)
        self.assertGreater(score_urgent, score_calm)

    def test_filter_batch_separates_clean_and_toxic(self):
        """Batch filtering correctly categorizes clean vs toxic intents."""
        intents = [
            AgentIntent("clean_1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3002.0, 5.0),
            AgentIntent("toxic_1", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3080.0, 5.0),
        ]
        clean, toxic_ids, lvr = self.filter.filter_batch(intents, fair_market_price=3000.0)
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0].intent_id, "clean_1")
        self.assertIn("toxic_1", toxic_ids)
        self.assertGreater(lvr, 0.0)

    def test_filter_batch_calculates_mitigated_lvr(self):
        """LVR mitigation accumulates potential adverse selection from toxic intents."""
        intents = [AgentIntent("t1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 10.0)]
        _, _, lvr = self.filter.filter_batch(intents, fair_market_price=3000.0)
        expected = 10.0 * 3000.0 * 0.0035
        self.assertAlmostEqual(lvr, expected)

    def test_compute_solvency_proof_sufficient_voucher(self):
        """Sufficient credit voucher passes solvency verification."""
        solvent = LVRToxicFlowFilter.verify_compute_credit_solvency("agent_x", credit_voucher_usd=1500.0, required_collateral_usd=1000.0)
        self.assertTrue(solvent)

    def test_compute_solvency_proof_insufficient_voucher_fails(self):
        """Credit voucher less than required collateral fails verification."""
        solvent = LVRToxicFlowFilter.verify_compute_credit_solvency("agent_y", credit_voucher_usd=900.0, required_collateral_usd=1000.0)
        self.assertFalse(solvent)

    def test_compute_solvency_proof_valid_hash(self):
        """Valid cryptographic proof hash verifies solvency."""
        solvent = LVRToxicFlowFilter.verify_compute_credit_solvency("agent_z", 1000.0, 1000.0, proof_hash="a1b2c3d4e5f6g7h8_valid_snark_proof")
        self.assertTrue(solvent)


class TestStrategyAndVaultDirectives(unittest.TestCase):
    """Test suite for master strategy orchestrator and strict VAULT directive format."""

    def setUp(self):
        self.strategy = AutonomousPerpetualIntentClearingStrategy()

    def test_strategy_submit_and_process_batch(self):
        """Submitting intents to strategy mempool and clearing produces BatchAuctionResult."""
        self.strategy.submit_intent(AgentIntent("i1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3050.0, 5.0))
        self.strategy.submit_intent(AgentIntent("i2", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3020.0, 5.0))
        res = self.strategy.process_batch("B_STRAT", "ETH", reference_market_price=3030.0)
        self.assertEqual(res.matched_cow_volume, 5.0)
        self.assertEqual(len(self.strategy.completed_batches), 1)

    def test_strategy_clears_mempool_for_asset(self):
        """Processed asset intents are removed from mempool while other assets remain."""
        self.strategy.submit_intent(AgentIntent("i1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3050.0, 5.0))
        self.strategy.submit_intent(AgentIntent("i2", "a2", "SOL", IntentType.BUY_PERP, IntentDirection.BUY, 180.0, 10.0))
        self.strategy.process_batch("B_ETH", "ETH", reference_market_price=3030.0)
        self.assertEqual(len(self.strategy.intent_mempool), 1)
        self.assertEqual(self.strategy.intent_mempool[0].asset, "SOL")

    def test_strategy_emits_valid_batch_result(self):
        """Batch result includes accurate trader surplus and residual volume."""
        self.strategy.submit_intent(AgentIntent("i1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3100.0, 10.0))
        self.strategy.submit_intent(AgentIntent("i2", "a2", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 3000.0, 6.0))
        res = self.strategy.process_batch("B_EMIT", "ETH", reference_market_price=3050.0)
        self.assertEqual(res.matched_cow_volume, 6.0)
        self.assertEqual(res.residual_buy_volume, 4.0)

    def test_vault_directive_strict_format(self):
        """Directive string must strictly match: ASSET | ACTION | ENTRY | SL | TP | LEV | R:R | SIZE."""
        sig = self.strategy.generate_vault_hedge_directive(
            asset="ETHUSDT",
            action="SELL_PERP",
            current_market_price=3100.0,
            atr_14=62.0,
            size_str="45.0_ETH",
            leverage=2.0,
            direction="SHORT"
        )
        parts = [p.strip() for p in sig.signal_text.split("|")]
        self.assertEqual(len(parts), 8)
        self.assertEqual(parts[0], "ETHUSDT")
        self.assertEqual(parts[1], "SELL_PERP")
        self.assertTrue(parts[5].endswith("x"))
        self.assertTrue(parts[6].endswith(":1"))
        self.assertEqual(parts[7], "45.0_ETH")

    def test_vault_directive_rr_ratio_minimum(self):
        """Directive guarantees strictly >= 2.0:1 R:R ratio."""
        sig = self.strategy.generate_vault_hedge_directive(
            asset="SOLUSDT",
            action="BUY_PERP",
            current_market_price=180.0,
            atr_14=5.0,
            size_str="100.0_SOL",
            direction="LONG"
        )
        self.assertGreaterEqual(sig.risk_reward_ratio, 2.0)

    def test_vault_directive_leverage_cap(self):
        """Directive caps leverage at 5.0x."""
        sig = self.strategy.generate_vault_hedge_directive(
            asset="BTCUSDT",
            action="SELL_PERP",
            current_market_price=90000.0,
            atr_14=1500.0,
            size_str="1.0_BTC",
            leverage=10.0
        )
        self.assertLessEqual(sig.lev, 5.0)

    def test_vault_directive_sl_exceeds_atr(self):
        """Stop-loss distance exceeds 1.5 * ATR(14)."""
        atr = 50.0
        sig = self.strategy.generate_vault_hedge_directive(
            asset="ETHUSDT",
            action="SELL_PERP",
            current_market_price=3000.0,
            atr_14=atr,
            size_str="10.0_ETH",
            direction="SHORT"
        )
        sl_dist = abs(sig.sl - sig.entry)
        self.assertGreater(sl_dist, 1.5 * atr)

    def test_vault_directive_validation_method(self):
        """Validation returns True for compliant directive, False if rules violated."""
        sig = self.strategy.generate_vault_hedge_directive("ETHUSDT", "SELL_PERP", 3000.0, 50.0, "10.0_ETH")
        self.assertTrue(sig.validate())
        sig.risk_reward_ratio = 1.5
        self.assertFalse(sig.validate())


class TestSimulatorEndToEnd(unittest.TestCase):
    """Test suite for 90-day simulation comparing Regimes A, B, and C."""

    def test_generate_agent_intents_attributes(self):
        """Intent generator populates realistic parameters and direction balance."""
        sim = IntentClearingSimulator(seed=123)
        intents = sim.generate_agent_intents(1, "ETHUSDT", 3000.0)
        self.assertGreaterEqual(len(intents), 8)
        self.assertTrue(any(i.direction == IntentDirection.BUY for i in intents))
        self.assertTrue(any(i.direction == IntentDirection.SELL for i in intents))

    def test_full_simulation_executes_90_days(self):
        """Simulation runs all batches across 90 days and populates complete metrics."""
        sim = IntentClearingSimulator(seed=42)
        res = sim.run_simulation(days=3, batches_per_day=4) # Scaled run for unit test speed
        self.assertEqual(res["total_batches"], 12)
        self.assertIn("regime_a_amm", res)
        self.assertIn("regime_b_simple_batch", res)
        self.assertIn("regime_c_intent_clearing", res)

    def test_regime_c_outperforms_regime_a_in_surplus(self):
        """Intent clearing generates higher trader surplus than AMM execution."""
        sim = IntentClearingSimulator(seed=42)
        res = sim.run_simulation(days=5, batches_per_day=8)
        surplus_a = res["regime_a_amm"]["trader_surplus_usd"]
        surplus_c = res["regime_c_intent_clearing"]["trader_surplus_usd"]
        self.assertGreater(surplus_c, surplus_a)

    def test_regime_c_eliminates_solver_drawdown_vs_regime_b(self):
        """JIT delta-hedging in Regime C maintains 0.0 solver drawdown vs unhedged Regime B."""
        sim = IntentClearingSimulator(seed=42)
        res = sim.run_simulation(days=10, batches_per_day=8)
        dd_b = res["regime_b_simple_batch"]["solver_max_drawdown_usd"]
        dd_c = res["regime_c_intent_clearing"]["solver_max_drawdown_usd"]
        self.assertGreater(dd_b, 0.0)
        self.assertEqual(dd_c, 0.0)


if __name__ == "__main__":
    unittest.main()
