"""Unit tests for MILP combinatorial batch clearing and uniform clearing price discovery."""

import pytest
from agent_intent_settlement.models import (
    AgentIntent,
    IntentDirection,
    IntentType,
)
from agent_intent_settlement.milp_clearing import MILPClearingEngine


class TestMILPClearing:
    """Test suite for combinatorial CoW batch clearing."""

    def setup_method(self):
        self.engine = MILPClearingEngine(solver_fee_bps=2.0)

    def test_construct_curves_sorting_and_toxic_exclusion(self):
        intents = [
            AgentIntent("B1", "a1", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3010.0, 1.0),
            AgentIntent("B2", "a2", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3050.0, 2.0),
            AgentIntent("B3_toxic", "a3", "ETH", IntentType.BUY_PERP, IntentDirection.BUY, 3200.0, 5.0, is_toxic=True),
            AgentIntent("S1", "a4", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 2990.0, 1.5),
            AgentIntent("S2", "a5", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 2980.0, 2.5),
            AgentIntent("S3_toxic", "a6", "ETH", IntentType.SELL_PERP, IntentDirection.SELL, 2700.0, 3.0, is_toxic=True),
        ]
        buys, sells = self.engine.construct_curves(intents)

        # Toxic should be excluded
        assert len(buys) == 2
        assert len(sells) == 2

        # Buys descending
        assert buys[0].intent_id == "B2" # 3050.0
        assert buys[1].intent_id == "B1" # 3010.0

        # Sells ascending
        assert sells[0].intent_id == "S2" # 2980.0
        assert sells[1].intent_id == "S1" # 2990.0

    def test_solve_empty_batch(self):
        res = self.engine.solve_uniform_clearing("BATCH-EMPTY", "ETHUSDT", [], reference_market_price=3000.0)
        assert res.matched_cow_volume == 0.0
        assert res.residual_buy_volume == 0.0
        assert res.residual_sell_volume == 0.0
        assert res.clearing_price == 3000.0
        assert len(res.matched_trades) == 0

    def test_solve_single_sided_buys(self):
        intents = [
            AgentIntent("B1", "a1", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3010.0, 2.0),
            AgentIntent("B2", "a2", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3020.0, 3.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH-BUY-ONLY", "ETHUSDT", intents, reference_market_price=3000.0)
        assert res.matched_cow_volume == 0.0
        assert res.residual_buy_volume == 5.0
        assert res.residual_sell_volume == 0.0
        assert len(res.matched_trades) == 0

    def test_solve_single_sided_sells(self):
        intents = [
            AgentIntent("S1", "a1", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2990.0, 4.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH-SELL-ONLY", "ETHUSDT", intents, reference_market_price=3000.0)
        assert res.matched_cow_volume == 0.0
        assert res.residual_buy_volume == 0.0
        assert res.residual_sell_volume == 4.0
        assert len(res.matched_trades) == 0

    def test_solve_overlapping_cow_trades(self):
        intents = [
            AgentIntent("B1", "buyer1", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3010.0, 4.0),
            AgentIntent("B2", "buyer2", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 3020.0, 2.0),
            AgentIntent("S1", "seller1", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2990.0, 3.0),
            AgentIntent("S2", "seller2", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 2980.0, 5.0),
        ]
        # Total buy volume = 6.0, Total sell volume = 8.0.
        # Max matchable = 6.0.
        res = self.engine.solve_uniform_clearing("BATCH-01", "ETHUSDT", intents, reference_market_price=3000.0)

        assert res.matched_cow_volume == 6.0
        assert res.residual_buy_volume == 0.0
        assert res.residual_sell_volume == 2.0 # 8.0 - 6.0
        assert len(res.matched_trades) > 0

        # Uniform Clearing Price must satisfy buyer willingness (p <= 3010) and seller willingness (p >= 2990)
        assert 2980.0 <= res.clearing_price <= 3020.0
        assert res.total_trader_surplus_usd > 0.0
        assert res.lvr_mitigated_usd > 0.0
        assert res.solver_profit_usd > 0.0

    def test_no_overlap_intents(self):
        intents = [
            AgentIntent("B1", "b1", "ETHUSDT", IntentType.BUY_PERP, IntentDirection.BUY, 2950.0, 1.0),
            AgentIntent("S1", "s1", "ETHUSDT", IntentType.SELL_PERP, IntentDirection.SELL, 3050.0, 1.0),
        ]
        res = self.engine.solve_uniform_clearing("BATCH-NO-OVERLAP", "ETHUSDT", intents, reference_market_price=3000.0)
        assert res.matched_cow_volume == 0.0
        assert res.residual_buy_volume == 1.0
        assert res.residual_sell_volume == 1.0
        assert res.total_trader_surplus_usd == 0.0
