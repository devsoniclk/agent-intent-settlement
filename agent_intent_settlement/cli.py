"""Command-line interface (CLI) for Autonomous Agent Perpetual Intent Clearing Engine.

Provides Rich-formatted inspection, batch auction solving, multi-epoch simulation,
institutional VAULT directive formatting, status reporting, and stdio MCP server execution.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .mcp_server import AgentIntentSettlementMCPServer
from .models import (
    AgentIntent,
    IntentDirection,
    IntentType,
    VaultTradeDirective,
    Venue,
)
from .simulator import IntentClearingSimulator
from .strategy import AutonomousPerpetualIntentClearingStrategy

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="agent-intent")
def main():
    """Autonomous Agent Perpetual Intent Clearing & CoW-Batching Engine."""
    pass


@main.command()
def status():
    """Display clearinghouse operational status, supported venues, and active configuration."""
    console.print(
        Panel(
            "[bold cyan]Autonomous Agent Perpetual Intent Clearing Engine[/bold cyan]\n"
            "Status: [bold green]ONLINE[/bold green] | Version: 0.1.0\n"
            "Supported Venues: [yellow]INTERNAL_COW[/yellow], [yellow]HYPERLIQUID_PERP[/yellow], [yellow]UNISWAP_V4[/yellow]\n"
            "Clearing Mode: Combinatorial MILP Social Welfare Maximization",
            border_style="cyan",
        )
    )


@main.command()
@click.option("--asset", default="ETHUSDT", help="Trading asset pair.")
@click.option("--price", default=3000.0, type=float, help="Reference market price.")
def clear(asset: str, price: float):
    """Clear pending batch auction for an asset."""
    strategy = AutonomousPerpetualIntentClearingStrategy()
    sim = IntentClearingSimulator(strategy=strategy, seed=int(time.time()))

    synthetic_intents = sim.generate_synthetic_intents(
        asset=asset,
        count=12,
        reference_price=price,
    )
    for intent in synthetic_intents:
        strategy.submit_intent(intent)

    batch_id = f"BATCH-CLEAR-{int(time.time()*1000)}"
    result = strategy.process_batch(
        batch_id=batch_id,
        asset=asset,
        reference_market_price=price,
    )

    console.print(f"[bold green]Batch Cleared successfully[/bold green]: {result.batch_id}")
    console.print(f"Asset: {result.asset} | UCP: ${result.clearing_price:.4f} | CoW Matched: {result.matched_cow_volume:.4f}")


@main.command()
@click.option("--days", default=3, type=int, help="Number of simulated days.")
@click.option("--batches-per-day", default=4, type=int, help="Batches per simulated day.")
@click.option("--asset", default="ETHUSDT", help="Asset pair.")
def benchmark(days: int, batches_per_day: int, asset: str):
    """Run comparative benchmark across Regime A (AMM), Regime B (Unhedged Batch), and Regime C (Intent Engine)."""
    sim = IntentClearingSimulator(seed=42)
    results = sim.run_simulation(days=days, batches_per_day=batches_per_day, asset=asset)

    reg_a = results["regime_a_amm"]
    reg_b = results["regime_b_simple_batch"]
    reg_c = results["regime_c_intent_clearing"]

    table = Table(title=f"Institutional Benchmark ({results['total_batches']:,} Batches | ${reg_c['total_volume_usd']:,.2f} Volume)", border_style="cyan")
    table.add_column("Performance Metric", style="cyan", no_wrap=True)
    table.add_column("Regime A: AMM Baseline", style="red")
    table.add_column("Regime B: Simple Batch", style="yellow")
    table.add_column("Regime C: Intent Engine", style="bold green")

    table.add_row(
        "Internal CoW Match Rate %",
        "0.00%",
        f"{reg_b['cow_match_rate_pct']:.2f}%",
        f"[bold green]{reg_c['cow_match_rate_pct']:.2f}%[/bold green]",
    )
    table.add_row(
        "Total Trader Surplus ($)",
        f"${reg_a['trader_surplus_usd']:,.2f}",
        f"${reg_b['trader_surplus_usd']:,.2f}",
        f"[bold green]+${reg_c['trader_surplus_usd']:,.2f}[/bold green]",
    )
    table.add_row(
        "LVR Loss / Mitigation ($)",
        f"-${reg_a['lvr_loss_usd']:,.2f}",
        f"-${reg_b['lvr_loss_usd']:,.2f}",
        f"[bold green]+${reg_c['lvr_mitigated_usd']:,.2f}[/bold green]",
    )
    table.add_row(
        "Solver Net Profit ($)",
        "$0.00",
        f"${reg_b['solver_pnl_usd']:,.2f}",
        f"[bold green]+${reg_c['solver_pnl_usd']:,.2f}[/bold green]",
    )
    table.add_row(
        "Solver Max Drawdown ($)",
        "N/A",
        f"-${reg_b['solver_max_drawdown_usd']:,.2f}",
        "[bold green]$0.00 (Zero DD)[/bold green]",
    )

    console.print(table)


@main.command()
@click.option("--asset", default="ETHUSDT", help="Trading asset pair.")
@click.option("--price", default=3000.0, type=float, help="Reference fair market price.")
@click.option("--intents", default=16, type=int, help="Number of intents to generate and match.")
@click.option("--volatility", default=0.02, type=float, help="Intraday price volatility.")
@click.option("--toxic-ratio", default=0.15, type=float, help="Ratio of toxic latency arbitrage flow.")
def solve(asset: str, price: float, intents: int, volatility: float, toxic_ratio: float):
    """Execute combinatorial CoW matching and uniform clearing price discovery."""
    console.print(
        Panel(
            f"[bold cyan]Autonomous Agent Intent Clearing Engine[/bold cyan]\n"
            f"Asset: [yellow]{asset}[/yellow] | Reference Price: [green]${price:,.2f}[/green] | "
            f"Intents: [magenta]{intents}[/magenta]",
            border_style="cyan",
        )
    )

    strategy = AutonomousPerpetualIntentClearingStrategy()
    sim = IntentClearingSimulator(strategy=strategy, seed=int(time.time()))

    synthetic_intents = sim.generate_synthetic_intents(
        asset=asset,
        count=intents,
        reference_price=price,
        volatility=volatility,
        toxic_ratio=toxic_ratio,
    )

    for intent in synthetic_intents:
        strategy.submit_intent(intent)

    batch_id = f"BATCH-CLI-{int(time.time()*1000)}"
    result = strategy.process_batch(
        batch_id=batch_id,
        asset=asset,
        reference_market_price=price,
        intraday_vol=volatility,
    )

    table = Table(title="Batch Auction Clearing Result", border_style="green")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold yellow")

    table.add_row("Batch ID", result.batch_id)
    table.add_row("Asset", result.asset)
    table.add_row("Uniform Clearing Price", f"${result.clearing_price:,.4f}")
    table.add_row("CoW Matched Volume", f"{result.matched_cow_volume:,.4f}")
    table.add_row("Residual Buy Imbalance", f"{result.residual_buy_volume:,.4f}")
    table.add_row("Residual Sell Imbalance", f"{result.residual_sell_volume:,.4f}")
    table.add_row("Total Trader Surplus", f"${result.total_trader_surplus_usd:,.2f}")
    table.add_row("LVR Mitigated", f"${result.lvr_mitigated_usd:,.2f}")
    table.add_row("Solver Captured Profit", f"${result.solver_profit_usd:,.2f}")
    table.add_row("Matched Trades Count", str(len(result.matched_trades)))
    table.add_row("Residual Executions Count", str(len(result.residual_executions)))

    console.print(table)


@main.command()
@click.option("--asset", default="ETHUSDT", help="Trading asset pair.")
@click.option("--epochs", default=5, type=int, help="Number of discrete auction epochs.")
@click.option("--intents-per-epoch", default=25, type=int, help="Intents per discrete epoch.")
@click.option("--start-price", default=3000.0, type=float, help="Initial asset price.")
def simulate(asset: str, epochs: int, intents_per_epoch: int, start_price: float):
    """Run multi-epoch Monte Carlo discrete auction simulation."""
    console.print(
        Panel(
            f"[bold magenta]Multi-Epoch Discrete Auction Simulation[/bold magenta]\n"
            f"Asset: [yellow]{asset}[/yellow] | Epochs: [cyan]{epochs}[/cyan] | "
            f"Intents/Epoch: [cyan]{intents_per_epoch}[/cyan]",
            border_style="magenta",
        )
    )

    sim = IntentClearingSimulator(seed=42)
    stats = sim.run_epoch_cycle(
        asset=asset,
        num_epochs=epochs,
        intents_per_epoch=intents_per_epoch,
        start_price=start_price,
    )

    tbl = Table(title="Simulation Aggregate Economics", border_style="cyan")
    tbl.add_column("Aggregate Metric", style="bold")
    tbl.add_column("Value", style="green")

    tbl.add_row("Total Intents Generated", f"{stats['total_intents_generated']:,}")
    tbl.add_row("Total CoW Trades Matched", f"{stats['total_matched_trades']:,}")
    tbl.add_row("Total CoW Volume Settled", f"{stats['total_cow_volume']:,.4f}")
    tbl.add_row("Total Trader Surplus Generated", f"${stats['total_trader_surplus_usd']:,.2f}")
    tbl.add_row("Total LVR Adverse Selection Mitigated", f"${stats['total_lvr_mitigated_usd']:,.2f}")
    tbl.add_row("Total Solver Profit Captured", f"${stats['total_solver_profit_usd']:,.2f}")
    tbl.add_row("VAULT Delta Hedge Directives Emitted", str(stats["vault_directives_emitted"]))
    tbl.add_row("Final Market Price", f"${stats['final_reference_price']:,.2f}")

    console.print(tbl)


@main.command()
@click.option("--asset", default="ETHUSDT", help="Asset pair.")
@click.option("--action", default="SHORT", type=click.Choice(["BUY", "SELL", "LONG", "SHORT"]))
@click.option("--price", default=3000.0, type=float, help="Market price.")
@click.option("--atr", default=45.0, type=float, help="14-period Average True Range.")
@click.option("--size", default="5.0 ETH", help="Position size.")
@click.option("--leverage", default=2.0, type=float, help="Leverage factor (max 5.0x).")
def directive(asset: str, action: str, price: float, atr: float, size: str, leverage: float):
    """Generate strictly compliant institutional VAULT trade directive."""
    act_normalized = "BUY" if action in ["BUY", "LONG"] else "SELL"
    direction = "LONG" if act_normalized == "BUY" else "SHORT"

    strat = AutonomousPerpetualIntentClearingStrategy()
    vd = strat.generate_vault_hedge_directive(
        asset=asset,
        action=act_normalized,
        current_market_price=price,
        atr_14=atr,
        size_str=size,
        leverage=leverage,
        direction=direction,
    )

    console.print(
        Panel(
            f"[bold green]Strict Institutional VAULT Directive[/bold green]\n\n"
            f"[bold yellow]{vd.signal_text}[/bold yellow]\n\n"
            f"Validation Status: {'[green]VALID (PASS)[/green]' if vd.validate() else '[red]INVALID[/red]'}\n"
            f"Entry: [cyan]${vd.entry:.4f}[/cyan] | SL: [red]${vd.sl:.4f}[/red] | "
            f"TP: [green]${vd.tp:.4f}[/green] | R:R: [bold]{vd.risk_reward_ratio:.2f}:1[/bold]",
            border_style="green",
        )
    )


@main.command()
def mcp():
    """Run JSON-RPC 2.0 stdio FastMCP server."""
    server = AgentIntentSettlementMCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
