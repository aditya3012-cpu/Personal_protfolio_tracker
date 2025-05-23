import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import numpy as np
from nsetools import Nse
import requests
import json

# Configure Streamlit page
st.set_page_config(
    page_title="NSE Portfolio Tracker",
    page_icon="📈",
    layout="wide"
)

# Portfolio configuration with correct NSE symbols
PORTFOLIO_STOCKS = {
    'CDSL': {'name': 'Central Depository Services Ltd', 'quantity': 1},
    'MAZAGON': {'name': 'Mazagon Dock Shipbuilders Ltd', 'quantity': 1},
    'GRSE': {'name': 'Garden Reach Shipbuilders & Engineers Ltd', 'quantity': 1},
    'COCHINSHIP': {'name': 'Cochin Shipyard Ltd', 'quantity': 1}
}

# Initialize NSE object
@st.cache_resource
def get_nse():
    """Initialize NSE connection"""
    try:
        nse = Nse()
        return nse
    except Exception as e:
        st.error(f"Failed to initialize NSE connection: {e}")
        return None

@st.cache_data(ttl=30)  # Cache for 30 seconds
def get_stock_quote(_nse, symbol):  # Added underscore to prevent hashing
    """Get stock quote from NSE"""
    try:
        quote = _nse.get_quote(symbol)
        return quote
    except Exception as e:
        st.warning(f"Error fetching quote for {symbol}: {e}")
        return None

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_historical_data(_nse, symbol):  # Added underscore to prevent hashing
    """Get historical data for charts"""
    try:
        # Get top gainers/losers to validate connection
        data = _nse.get_top_gainers()
        if data:
            # Create sample historical data for visualization
            # Since nsetools doesn't provide historical data, we'll simulate it
            current_time = datetime.now()
            dates = [current_time - timedelta(minutes=x*5) for x in range(20, 0, -1)]
            
            # Get current price from quote
            quote = get_stock_quote(_nse, symbol)
            if quote:
                base_price = float(quote['lastPrice'])
                # Generate realistic price movements
                price_changes = np.random.normal(0, base_price * 0.002, 20)  # 0.2% volatility
                prices = [base_price + sum(price_changes[:i+1]) for i in range(20)]
                
                return pd.DataFrame({
                    'timestamp': dates,
                    'price': prices
                })
        return None
    except Exception as e:
        st.warning(f"Error fetching historical data for {symbol}: {e}")
        return None

def calculate_portfolio_metrics(portfolio_data):
    """Calculate portfolio metrics"""
    total_value = sum([data['current_price'] * data['quantity'] for data in portfolio_data.values()])
    total_invested = sum([data['prev_close'] * data['quantity'] for data in portfolio_data.values()])
    total_change = total_value - total_invested
    total_change_pct = (total_change / total_invested) * 100 if total_invested > 0 else 0
    
    return {
        'total_value': total_value,
        'total_invested': total_invested,
        'total_change': total_change,
        'total_change_pct': total_change_pct
    }

def format_indian_currency(amount):
    """Format currency in Indian style (lakhs, crores)"""
    if amount >= 10000000:  # 1 crore
        return f"₹{amount/10000000:.2f} Cr"
    elif amount >= 100000:  # 1 lakh
        return f"₹{amount/100000:.2f} L"
    else:
        return f"₹{amount:,.2f}"

def main():
    # Title and header
    st.title("📈 NSE Stock Portfolio Tracker")
    st.markdown("Real-time tracking of CDSL, Mazagon Dock, GRSE, and Cochin Shipyard using NSE Tools")
    
    # Initialize NSE
    nse = get_nse()
    if not nse:
        st.error("Unable to connect to NSE. Please check your internet connection and try again.")
        return
    
    # Sidebar controls
    st.sidebar.header("Settings")
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=False)
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 30, 300, 60)
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        # Clear cache to force fresh data
        get_stock_quote.clear()
        get_historical_data.clear()
        st.rerun()
    
    # NSE connection status
    st.sidebar.subheader("NSE Connection Status")
    try:
        test_data = nse.get_top_gainers()
        if test_data and len(test_data) > 0:
            st.sidebar.success("✅ NSE Connected")
        else:
            st.sidebar.warning("⚠️ NSE Connection Issues")
    except:
        st.sidebar.error("❌ NSE Disconnected")
    
    # Create placeholders
    header_placeholder = st.empty()
    metrics_placeholder = st.empty()
    chart_placeholder = st.empty()
    table_placeholder = st.empty()
    
    # Fetch portfolio data
    portfolio_data = {}
    fetch_success = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (symbol, stock_info) in enumerate(PORTFOLIO_STOCKS.items()):
        status_text.text(f"Fetching data for {stock_info['name']}...")
        progress_bar.progress((i + 1) / len(PORTFOLIO_STOCKS))
        
        quote = get_stock_quote(nse, symbol)
        
        if quote:
            try:
                current_price = float(quote['lastPrice'])
                prev_close = float(quote['previousClose'])
                change = float(quote['change'])
                change_pct = float(quote['pChange'])
                
                # Get additional data
                high = float(quote.get('dayHigh', current_price))
                low = float(quote.get('dayLow', current_price))
                volume = quote.get('totalTradedVolume', 'N/A')
                
                portfolio_data[symbol] = {
                    'name': stock_info['name'],
                    'current_price': current_price,
                    'prev_close': prev_close,
                    'change': change,
                    'change_pct': change_pct,
                    'quantity': stock_info['quantity'],
                    'value': current_price * stock_info['quantity'],
                    'high': high,
                    'low': low,
                    'volume': volume,
                    'symbol': symbol
                }
                fetch_success += 1
                
            except (ValueError, KeyError) as e:
                st.warning(f"Data parsing error for {symbol}: {e}")
        else:
            st.warning(f"No data received for {symbol}")
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    if portfolio_data:
        # Calculate portfolio metrics
        portfolio_metrics = calculate_portfolio_metrics(portfolio_data)
        
        # Display portfolio summary
        with header_placeholder.container():
            st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.markdown(f"**Data Source:** NSE Tools (Live NSE Data)")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Portfolio Value",
                    format_indian_currency(portfolio_metrics['total_value']),
                    f"₹{portfolio_metrics['total_change']:+,.2f}"
                )
            with col2:
                color = "normal" if portfolio_metrics['total_change_pct'] >= 0 else "inverse"
                st.metric(
                    "Total Return %",
                    f"{portfolio_metrics['total_change_pct']:+.2f}%",
                    delta_color=color
                )
            with col3:
                st.metric(
                    "Stocks Tracked",
                    f"{fetch_success}/{len(PORTFOLIO_STOCKS)}"
                )
            with col4:
                st.metric(
                    "Total Invested",
                    format_indian_currency(portfolio_metrics['total_invested'])
                )
        
        # Individual stock metrics
        with metrics_placeholder.container():
            st.subheader("Individual Stock Performance")
            cols = st.columns(len(portfolio_data))
            
            for i, (symbol, data) in enumerate(portfolio_data.items()):
                with cols[i]:
                    color = "normal" if data['change'] >= 0 else "inverse"
                    st.metric(
                        data['name'].split(' ')[0],
                        f"₹{data['current_price']:.2f}",
                        f"{data['change']:+.2f} ({data['change_pct']:+.2f}%)",
                        delta_color=color
                    )
                    # Additional info
                    st.caption(f"H: ₹{data['high']:.2f} | L: ₹{data['low']:.2f}")
        
        # Charts section
        with chart_placeholder.container():
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Portfolio Composition")
                labels = [data['name'].split(' ')[0] for data in portfolio_data.values()]
                values = [data['value'] for data in portfolio_data.values()]
                colors = ['#00ff00' if data['change'] >= 0 else '#ff4444' for data in portfolio_data.values()]
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.4,
                    marker_colors=colors,
                    textinfo='label+percent',
                    textposition='outside'
                )])
                fig_pie.update_layout(
                    title="Portfolio Value Distribution",
                    showlegend=True,
                    height=400
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.subheader("Price vs Previous Close")
                symbols = list(portfolio_data.keys())
                current_prices = [portfolio_data[s]['current_price'] for s in symbols]
                prev_closes = [portfolio_data[s]['prev_close'] for s in symbols]
                
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    x=symbols,
                    y=prev_closes,
                    name='Previous Close',
                    marker_color='lightblue',
                    opacity=0.7
                ))
                fig_bar.add_trace(go.Bar(
                    x=symbols,
                    y=current_prices,
                    name='Current Price',
                    marker_color=['green' if portfolio_data[s]['change'] >= 0 else 'red' for s in symbols]
                ))
                
                fig_bar.update_layout(
                    title="Current vs Previous Close Prices",
                    xaxis_title="Stocks",
                    yaxis_title="Price (₹)",
                    barmode='group',
                    height=400
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        
        # Detailed table
        with table_placeholder.container():
            st.subheader("Detailed Portfolio View")
            
            table_data = []
            for symbol, data in portfolio_data.items():
                table_data.append({
                    'Stock': data['name'],
                    'Symbol': symbol,
                    'Current Price (₹)': f"{data['current_price']:.2f}",
                    'Previous Close (₹)': f"{data['prev_close']:.2f}",
                    'Change (₹)': f"{data['change']:+.2f}",
                    'Change (%)': f"{data['change_pct']:+.2f}%",
                    'Day High (₹)': f"{data['high']:.2f}",
                    'Day Low (₹)': f"{data['low']:.2f}",
                    'Quantity': data['quantity'],
                    'Value (₹)': f"{data['value']:.2f}",
                    'Volume': str(data['volume']) if data['volume'] != 'N/A' else 'N/A'
                })
            
            df = pd.DataFrame(table_data)
            
            # Style the dataframe with colors
            def style_changes(val):
                if 'Change' in val.name and '₹' in str(val):
                    try:
                        num_val = float(str(val).replace('₹', '').replace('+', '').replace('%', '').replace(',', ''))
                        if '+' in str(val):
                            return 'background-color: #d4edda; color: #155724'
                        elif num_val < 0:
                            return 'background-color: #f8d7da; color: #721c24'
                    except:
                        pass
                return ''
            
            styled_df = df.style.applymap(style_changes)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Market summary
        st.subheader("Market Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            gainers = sum(1 for data in portfolio_data.values() if data['change'] > 0)
            st.metric("Gainers", gainers, f"out of {len(portfolio_data)}")
        
        with col2:
            losers = sum(1 for data in portfolio_data.values() if data['change'] < 0)
            st.metric("Losers", losers, f"out of {len(portfolio_data)}")
        
        with col3:
            avg_change = sum(data['change_pct'] for data in portfolio_data.values()) / len(portfolio_data)
            st.metric("Avg Change %", f"{avg_change:.2f}%")
    
    else:
        st.error("Unable to fetch data for any stocks. Please check NSE connection and try again.")
        st.info("💡 **Troubleshooting Tips:**")
        st.info("1. Check your internet connection")
        st.info("2. Try refreshing the page")
        st.info("3. NSE data might be unavailable during market holidays")
    
    # Footer
    st.markdown("---")
    st.markdown("**Note:** Data provided by NSE Tools. Prices are real-time during market hours.")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
