import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ============================================================================
# PHASE 1: UNIT NORMALIZATION & DATA FRESHNESS
# ============================================================================

def normalize_units(value, scale='M'):
    """
    Converts raw financial values to a consistent scale.
    
    Args:
        value: The raw numerical value.
        scale: 'M' for Millions (default), 'B' for Billions.
    
    Returns:
        Normalized value as a float, or None if input is invalid.
    """
    if value is None:
        return None
    try:
        divisor = 1_000_000 if scale == 'M' else 1_000_000_000
        return float(value) / divisor
    except (TypeError, ValueError):
        return None


def check_data_freshness(balance_sheet):
    """
    Checks if the most recent annual filing is stale (> 18 months old).
    
    Args:
        balance_sheet: pandas DataFrame from yfinance.
    
    Returns:
        Tuple: (is_stale: bool, filing_date: str, warning_message: str or None)
    """
    if balance_sheet is None or balance_sheet.empty:
        return True, None, "No balance sheet data available."
    
    try:
        # Column names are typically dates
        most_recent_date = balance_sheet.columns[0]
        
        # Convert to datetime if it's a Timestamp
        if hasattr(most_recent_date, 'to_pydatetime'):
            filing_date = most_recent_date.to_pydatetime()
        else:
            filing_date = pd.to_datetime(most_recent_date)
        
        stale_threshold = datetime.now() - timedelta(days=18 * 30)  # ~18 months
        
        is_stale = filing_date < stale_threshold
        date_str = filing_date.strftime('%Y-%m-%d')
        
        warning = None
        if is_stale:
            warning = f"⚠️ STALE DATA: Most recent filing is from {date_str} (> 18 months old). Credit risk assessment may be unreliable."
        
        return is_stale, date_str, warning
        
    except Exception as e:
        return True, None, f"Could not determine data freshness: {e}"


# ============================================================================
# PHASE 2: SECTOR-SPECIFIC Z-SCORE LOGIC
# ============================================================================

NON_MANUFACTURING_SECTORS = [
    'Technology', 
    'Consumer Cyclical', 
    'Consumer Defensive', 
    'Communication Services', 
    'Financial Services',
    'Healthcare',
    'Real Estate'
]


def get_financial_data(ticker):
    """
    Fetches necessary financial data for Altman Z-Score calculation.
    Includes unit normalization, freshness check, and sector detection.
    
    Returns:
        dict with normalized data, metadata (sector, freshness), or None on error.
    """
    try:
        stock = yf.Ticker(ticker)
        bs = stock.balance_sheet
        financials = stock.financials
        info = stock.info
        
        if bs.empty or financials.empty:
            return None

        # Data freshness check
        is_stale, filing_date, freshness_warning = check_data_freshness(bs)

        # Get most recent year
        recent_bs = bs.iloc[:, 0]
        recent_fin = financials.iloc[:, 0]
        
        data = {
            '_metadata': {
                'ticker': ticker,
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                'filing_date': filing_date,
                'is_stale': is_stale,
                'freshness_warning': freshness_warning,
                'currency': info.get('currency', 'USD'),
                'unit': 'Millions'
            }
        }
        
        # Raw values (for debugging/display)
        raw_total_assets = recent_bs.get('Total Assets')
        
        # === Normalized Values (in Millions) ===
        data['Total Assets'] = normalize_units(raw_total_assets)
        
        # Working Capital
        tca = recent_bs.get('Total Current Assets')
        tcl = recent_bs.get('Total Current Liabilities')
        if tca is not None and tcl is not None:
            data['Working Capital'] = normalize_units(tca - tcl)
        else:
            wc = recent_bs.get('Working Capital')
            data['Working Capital'] = normalize_units(wc)

        data['Retained Earnings'] = normalize_units(recent_bs.get('Retained Earnings'))
        data['EBIT'] = normalize_units(recent_fin.get('EBIT'))
        
        tl = recent_bs.get('Total Liabilities Net Minority Interest') or recent_bs.get('Total Liabilities')
        data['Total Liabilities'] = normalize_units(tl)
        
        # Market Value of Equity (already in currency, normalize)
        data['Market Value of Equity'] = normalize_units(info.get('marketCap'))
        
        # Book Value of Equity (for Z'' formula)
        stockholders_equity = recent_bs.get('Stockholders Equity') or recent_bs.get('Total Equity Gross Minority Interest')
        data['Book Value of Equity'] = normalize_units(stockholders_equity)
        
        data['Total Revenue'] = normalize_units(recent_fin.get('Total Revenue'))
        
        return data
        
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None


def calculate_altman_z_score(data):
    """
    Calculates Altman Z-Score, dynamically choosing between:
    - Z (Manufacturing): 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
    - Z'' (Non-Manufacturing): 6.56A + 3.26B + 6.72C + 1.05D (no Sales component)
    
    Returns:
        Tuple: (z_score, risk_category, formula_used)
    """
    if not data:
        return None, "No Data", None

    try:
        metadata = data.get('_metadata', {})
        sector = metadata.get('sector', 'Unknown')
        
        total_assets = data.get('Total Assets')
        if not total_assets or total_assets == 0:
            return None, "Missing Total Assets", None

        working_capital = data.get('Working Capital')
        if working_capital is None:
            return None, "Missing Working Capital", None
        
        retained_earnings = data.get('Retained Earnings')
        if retained_earnings is None:
            return None, "Missing Retained Earnings", None
        
        ebit = data.get('EBIT')
        if ebit is None:
            return None, "Missing EBIT", None
        
        # Common ratios
        A = working_capital / total_assets
        B = retained_earnings / total_assets
        C = ebit / total_assets

        # Determine which formula to use
        use_z_double_prime = sector in NON_MANUFACTURING_SECTORS
        
        if use_z_double_prime:
            # Z'' Formula (Non-Manufacturing)
            # Uses Book Value of Equity instead of Market Value
            bve = data.get('Book Value of Equity')
            total_liabilities = data.get('Total Liabilities')
            
            if bve is None or total_liabilities is None or total_liabilities == 0:
                return None, "Missing Book Value of Equity or Liabilities", None
            
            D = bve / total_liabilities
            
            z_score = (6.56 * A) + (3.26 * B) + (6.72 * C) + (1.05 * D)
            formula_used = "Z'' (Non-Manufacturing)"
            
            # Z'' thresholds are different
            if z_score > 2.6:
                risk_category = "Safe Zone"
            elif z_score > 1.1:
                risk_category = "Grey Zone"
            else:
                risk_category = "Distress Zone"
        else:
            # Standard Z Formula (Manufacturing)
            mve = data.get('Market Value of Equity')
            total_liabilities = data.get('Total Liabilities')
            sales = data.get('Total Revenue')
            
            if mve is None or total_liabilities is None or total_liabilities == 0:
                return None, "Missing MVE or Liabilities", None
            if sales is None:
                return None, "Missing Sales", None
            
            D = mve / total_liabilities
            E = sales / total_assets
            
            z_score = (1.2 * A) + (1.4 * B) + (3.3 * C) + (0.6 * D) + (1.0 * E)
            formula_used = "Z (Manufacturing)"
            
            if z_score > 3.0:
                risk_category = "Safe Zone"
            elif z_score > 1.8:
                risk_category = "Grey Zone"
            else:
                risk_category = "Distress Zone"
            
        return z_score, risk_category, formula_used

    except Exception as e:
        return None, f"Calculation Error: {e}", None


if __name__ == "__main__":
    test_tickers = ["AAPL", "CAT"]  # Tech (Z'') vs Industrial (Z)
    
    for ticker in test_tickers:
        print(f"\n{'='*50}")
        print(f"Fetching data for {ticker}...")
        data = get_financial_data(ticker)
        
        if data:
            meta = data.get('_metadata', {})
            print(f"Sector: {meta.get('sector')}")
            print(f"Filing Date: {meta.get('filing_date')}")
            if meta.get('freshness_warning'):
                print(meta.get('freshness_warning'))
            
            print(f"\nNormalized Values (in Millions):")
            for key, val in data.items():
                if key != '_metadata' and val is not None:
                    print(f"  {key}: {val:,.2f}M")
            
            z, risk, formula = calculate_altman_z_score(data)
            print(f"\nFormula Used: {formula}")
            print(f"Z-Score: {z:.4f}" if z else f"Z-Score: {z}")
            print(f"Risk Category: {risk}")
        else:
            print("Failed to fetch data.")
