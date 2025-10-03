import pandas as pd
import pandas_ta as ta
from backtester import BackTester


def process_data(data):
    """
    Computes the indicators for the V3 highly-filtered strategy.
    """
    # 1. Donchian Channels (40-period)
    data.ta.donchian(lower_length=40, upper_length=40, append=True)

    # 2. ADX (14-period)
    data.ta.adx(length=14, append=True)

    # 3. ATR (14-period)
    data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)

    # 4. Volume EMA (20-period)
    data['volume_ema'] = ta.ema(data['volume'], length=20)

    # 5. SMA (200-period) for the long-term trend filter
    data.ta.sma(length=200, append=True)

    # 6. RSI (14-period) for momentum confirmation
    data.ta.rsi(length=14, append=True)

    return data


def strat(data):
    """
    Implements V3: a highly-filtered Donchian Breakout strategy.
    - Filters: 200 SMA, ADX > 25, Rising ADX, RSI Momentum, Volume
    - Exit: Dual ATR Trailing (1.8x) and Hard Stop-Loss (10%)
    """
    data['signals'] = 0
    position = 0
    trailing_stop = 0.0
    hard_stop = 0.0

    # --- Strategy Parameters ---
    donchian_period = 40
    adx_threshold = 25
    atr_multiplier = 1.8
    volume_multiplier = 1.5
    sma_period = 200
    rsi_period = 14
    hard_stop_loss_pct = 0.10

    # --- Define column names for clarity ---
    upper_band = f'DCU_{donchian_period}_{donchian_period}'
    lower_band = f'DCL_{donchian_period}_{donchian_period}'
    sma_col = f'SMA_{sma_period}'
    rsi_col = f'RSI_{rsi_period}'

    # Start loop where all indicators are valid
    for i in range(sma_period, len(data)):

        # --- EXIT LOGIC ---
        if position == 1:  # In a long position
            if data.loc[i, 'close'] < trailing_stop or data.loc[i, 'close'] < hard_stop:
                data.loc[i, 'signals'] = -1
                position = 0
                trailing_stop = 0.0
                hard_stop = 0.0
            else:
                new_stop = data.loc[i, 'close'] - (data.loc[i, 'ATR'] * atr_multiplier)
                trailing_stop = max(trailing_stop, new_stop)

        elif position == -1:  # In a short position
            if data.loc[i, 'close'] > trailing_stop or data.loc[i, 'close'] > hard_stop:
                data.loc[i, 'signals'] = 1
                position = 0
                trailing_stop = 0.0
                hard_stop = 0.0
            else:
                new_stop = data.loc[i, 'close'] + (data.loc[i, 'ATR'] * atr_multiplier)
                trailing_stop = min(trailing_stop, new_stop)

        # --- ENTRY LOGIC ---
        elif position == 0:
            # Define all entry conditions for clarity
            is_uptrend = data.loc[i, 'close'] > data.loc[i, sma_col]
            is_downtrend = data.loc[i, 'close'] < data.loc[i, sma_col]
            is_trending_adx = data.loc[i, 'ADX_14'] > adx_threshold
            volume_confirmed = data.loc[i, 'volume'] > (data.loc[i, 'volume_ema'] * volume_multiplier)
            rsi_bullish = data.loc[i, rsi_col] > 50
            rsi_bearish = data.loc[i, rsi_col] < 50
            adx_is_rising = data.loc[i, 'ADX_14'] > data.loc[i - 1, 'ADX_14']

            # Long breakout: Requires ALL filters to be true
            if (is_uptrend and is_trending_adx and adx_is_rising and rsi_bullish and volume_confirmed and
                    data.loc[i, 'close'] > data.loc[i - 1, upper_band]):
                data.loc[i, 'signals'] = 1
                position = 1
                trailing_stop = data.loc[i, 'close'] - (data.loc[i, 'ATR'] * atr_multiplier)
                hard_stop = data.loc[i, 'close'] * (1 - hard_stop_loss_pct)

            # Short breakout: Requires ALL filters to be true
            elif (is_downtrend and is_trending_adx and adx_is_rising and rsi_bearish and volume_confirmed and
                  data.loc[i, 'close'] < data.loc[i - 1, lower_band]):
                data.loc[i, 'signals'] = -1
                position = -1
                trailing_stop = data.loc[i, 'close'] + (data.loc[i, 'ATR'] * atr_multiplier)
                hard_stop = data.loc[i, 'close'] * (1 + hard_stop_loss_pct)

    return data
def main():
    """
    Main function to run the backtest.
    """
    # Load the data
    data = pd.read_csv("BTC_2019_2023_1d.csv")

    # Process data to add indicators
    processed_data = process_data(data.copy())

    # Apply the strategy to generate signals
    result_data = strat(processed_data.copy())

    # Save results to a CSV for the backtester
    csv_file_path = "final_data.csv"
    result_data.to_csv(csv_file_path, index=False)
    print(f"Strategy data saved to {csv_file_path}")

    # Initialize and run the backtester
    bt = BackTester("BTC", signal_data_path=csv_file_path, master_file_path=csv_file_path, compound_flag=1)
    bt.get_trades(1000)

    print("\n--- Trades and PnL ---")
    if not bt.trades:
        print("No trades were executed.")
    else:
        for trade in bt.trades:
            print(f"{trade} | PnL: {trade.pnl():.2f}")

    print("\n--- Backtest Statistics ---")
    stats = bt.get_statistics()
    if stats:
        for key, val in stats.items():
            print(f"{key:<25}: {val}")
    else:
        print("No statistics to display.")


if _name_ == "_main_":
    main()
