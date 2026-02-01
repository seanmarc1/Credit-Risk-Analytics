import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import financial_data as fd
import news_agent as na

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="Due Diligence Tool", 
    layout="wide",
    page_icon="📊"
)

st.title("📊 Financial Due Diligence Dashboard")
st.markdown("### Institutional-Grade Credit Risk Analysis")

# ============================================================================
# SIDEBAR
# ============================================================================
st.sidebar.header("⚙️ Configuration")
api_key = st.sidebar.text_input("OpenAI API Key (Optional)", type="password")
st.sidebar.markdown("---")
st.sidebar.markdown("**About**")
st.sidebar.caption("This tool calculates the Altman Z-Score (Manufacturing) or Z'' (Non-Manufacturing) based on sector classification.")

# ============================================================================
# PDF GENERATION
# ============================================================================
def generate_pdf_memo(ticker, metadata, z_score, risk_cat, formula, metrics, analyst_notes, news_summary):
    """Generates a Risk Memo PDF."""
    if not FPDF_AVAILABLE:
        return None
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Header
    pdf.cell(0, 10, f"CREDIT RISK MEMO - {ticker}", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    pdf.ln(10)
    
    # Company Info
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Company Information", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Sector: {metadata.get('sector', 'N/A')}", ln=True)
    pdf.cell(0, 6, f"Industry: {metadata.get('industry', 'N/A')}", ln=True)
    pdf.cell(0, 6, f"Filing Date: {metadata.get('filing_date', 'N/A')}", ln=True)
    if metadata.get('is_stale'):
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 6, "WARNING: Data may be stale (> 18 months old)", ln=True)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # Z-Score Results
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Credit Risk Assessment", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Formula Used: {formula or 'N/A'}", ln=True)
    pdf.cell(0, 6, f"Z-Score: {z_score:.4f}" if z_score else "Z-Score: N/A", ln=True)
    
    # Color code risk
    if risk_cat == "Safe Zone":
        pdf.set_text_color(0, 128, 0)
    elif risk_cat == "Grey Zone":
        pdf.set_text_color(255, 165, 0)
    else:
        pdf.set_text_color(255, 0, 0)
    pdf.cell(0, 6, f"Risk Category: {risk_cat}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # Key Metrics Table
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Key Financial Metrics (in Millions)", ln=True)
    pdf.set_font("Arial", "", 9)
    for key, val in metrics.items():
        if key != '_metadata' and val is not None:
            pdf.cell(0, 5, f"  {key}: {val:,.2f}M", ln=True)
    pdf.ln(5)
    
    # News Summary
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Risk Intelligence Summary", ln=True)
    pdf.set_font("Arial", "", 9)
    # Truncate if too long
    news_text = news_summary[:500] + "..." if len(news_summary) > 500 else news_summary
    pdf.multi_cell(0, 5, news_text)
    pdf.ln(5)
    
    # Analyst Notes
    if analyst_notes:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Analyst Notes", ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.multi_cell(0, 5, analyst_notes)
    
    # Output
    return pdf.output(dest='S').encode('latin-1')


# ============================================================================
# MAIN UI
# ============================================================================
ticker_input = st.text_input("Enter Tickers (comma separated, e.g., AAPL, TSLA, CAT)", "AAPL")

# Session state for analyst notes
if 'analyst_notes' not in st.session_state:
    st.session_state.analyst_notes = {}

if st.button("🔍 Analyze", type="primary"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    
    if not tickers:
        st.warning("Please enter at least one ticker.")
    else:
        for ticker in tickers:
            with st.expander(f"📈 Analysis for {ticker}", expanded=True):
                col1, col2 = st.columns([1, 1])
                
                # Fetch Financial Data
                with st.spinner(f"Fetching data for {ticker}..."):
                    data = fd.get_financial_data(ticker)
                
                if not data:
                    st.error(f"Could not fetch financial data for {ticker}. Check ticker symbol or try again later.")
                    continue
                
                metadata = data.get('_metadata', {})
                
                # Calculate Z-Score (updated function returns 3 values)
                z_score, risk_cat, formula = fd.calculate_altman_z_score(data)
                
                with col1:
                    st.subheader("📊 Financial Health")
                    
                    # Freshness Warning
                    if metadata.get('freshness_warning'):
                        st.warning(metadata.get('freshness_warning'))
                    
                    # Sector & Formula Info
                    st.caption(f"**Sector:** {metadata.get('sector', 'N/A')} | **Formula:** {formula or 'N/A'}")
                    
                    if z_score is not None:
                        # Z-Score Metric
                        delta_color = "normal"
                        if risk_cat == "Distress Zone":
                            delta_color = "inverse"
                        st.metric("Altman Z-Score", f"{z_score:.4f}")
                        
                        # Risk Badge
                        if risk_cat == "Safe Zone":
                            st.success(f"🟢 {risk_cat}")
                        elif risk_cat == "Grey Zone":
                            st.warning(f"🟡 {risk_cat}")
                        else:
                            st.error(f"🔴 {risk_cat}")
                        
                        # Key Metrics Display
                        st.markdown("#### Key Metrics (Millions)")
                        metrics_df = pd.DataFrame([
                            {"Metric": k, "Value (M)": f"{v:,.2f}" if v else "N/A"}
                            for k, v in data.items() if k != '_metadata'
                        ])
                        st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                    else:
                        st.error(f"Could not calculate Z-Score: {risk_cat}")

                # AI News Analysis
                with col2:
                    st.subheader("🔎 AI Risk Intelligence")
                    with st.spinner(f"Searching news for {ticker}..."):
                        snippets = na.get_news_snippets(ticker)
                        news_summary = na.summarize_news(ticker, snippets, api_key=api_key)
                        
                        st.info("Latest News Analysis")
                        st.write(news_summary)
                        
                        if not api_key:
                            st.caption("💡 Enter OpenAI API Key in sidebar for AI summarization.")
                
                # ============================================================
                # PHASE 3: ANALYST NOTES
                # ============================================================
                st.markdown("---")
                st.subheader("📝 Analyst Notes")
                
                notes_key = f"notes_{ticker}"
                analyst_notes = st.text_area(
                    f"Add qualitative observations for {ticker}:",
                    value=st.session_state.analyst_notes.get(ticker, ""),
                    height=100,
                    placeholder="e.g., Recent management change, upcoming debt maturity, litigation concerns...",
                    key=notes_key
                )
                st.session_state.analyst_notes[ticker] = analyst_notes
                
                # PDF Export Button
                if FPDF_AVAILABLE and z_score is not None:
                    if st.button(f"📄 Generate Risk Memo PDF for {ticker}", key=f"pdf_{ticker}"):
                        pdf_bytes = generate_pdf_memo(
                            ticker=ticker,
                            metadata=metadata,
                            z_score=z_score,
                            risk_cat=risk_cat,
                            formula=formula,
                            metrics=data,
                            analyst_notes=analyst_notes,
                            news_summary=news_summary
                        )
                        if pdf_bytes:
                            st.download_button(
                                label=f"⬇️ Download {ticker}_RiskMemo.pdf",
                                data=pdf_bytes,
                                file_name=f"{ticker}_RiskMemo_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key=f"download_{ticker}"
                            )
                elif not FPDF_AVAILABLE:
                    st.caption("⚠️ Install `fpdf` to enable PDF export: `pip install fpdf`")

st.markdown("---")
st.caption("Financial data provided by yfinance. Credit models based on Altman Z-Score methodology.")
