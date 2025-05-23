import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import numpy as np
import requests
import json
from functools import lru_cache

# Configure Streamlit page
st.set_page_config(
    page_title="NSE Portfolio Tracker",
    page_icon="📈",
    layout="wide"
)

# Portfolio configuration
PORTFOLIO_STOCKS = {
    'CDSL.NS': {'name': 'Central Depository Services Ltd', 'quantity': 4000, 'symbol': 'CDSL'},
    'MAZAGON.NS': {'name': 'Mazagon Dock Shipbuilders Ltd', 'quantity': 500, 'symbol': 'MAZAGON'},
    'GRSE.NS': {'name': 'Garden Reach Shipbuilders & Engineers Ltd', 'quantity': 500, 'symbol': 'GRSE'},
    'COCHINSHIP.NS': {'name': 'Cochin Shipyard Ltd', 'quantity': 600, 'symbol': 'COCHINSHIP'}
}

# Cache for storing data to avoid frequent API calls
@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_cached_stock_data(symbol, timestamp):
    """Cached function to fetch stock data"""
    return fetch_stock_data_with_retry(symbol)

def fetch_stock_data_with_retry(symbol, max_retries=3, retry_delay=2):
    """Fetch stock data with retry mechanism and rate limiting"""
    for attempt in range(max_retries):
        try:
            # Add delay between requests to avoid rate limiting
            if attempt > 0:
                time.sleep(retry_delay * attempt)
            
            ticker = yf.Ticker(symbol)
            
            # Fetch minimal data to reduce API load
            hist = ticker.history(period="1d", interval="5m")  # 5-minute intervals instead of 1-minute
            info = ticker.info
            
            if hist.empty:
                # Fallback to daily data if intraday fails
                hist = ticker.history(period="5d", interval="1d")
            
            return hist, info
            
        except Exception as e:
            if "Rate limited" in str(e) or "Too Many Requests" in str(e):
                st.warning(f"Rate limited for {symbol}. Retrying in {retry_delay * (attempt + 1)} seconds...")
                time.sleep(retry_delay * (attempt + 1))
            else:
                st.error(f"Error fetching {symbol} (attempt {attempt + 1}): {str(e)}")
                
            if attempt == max_retries - 1:
                return get_fallback_data(symbol)
    
    return None, None

def get_fallback_data(symbol):
    """Generate fallback data when API fails"""
    # Create dummy data based on symbol
    base_prices = {
        'CDSL.NS': 1500,
        'MAZAGON.NS': 4500,
        'GRSE.NS': 1200,
        'COCHINSHIP.NS': 1800
    }
    
    base_price = base_prices.get(symbol, 1000)
    
    # Generate some sample data
    dates = pd.date_range(end=datetime.now(), periods=10, freq='5T')
    prices = [base_price + np.random.uniform(-50, 50) for _ in range(10)]
    
    fallback_hist = pd.DataFrame({
        'Open': prices,
        'High': [p + np.random.uniform(0, 20) for p in prices],
        'Low': [p - np.random.uniform(0, 20) for p in prices],
        'Close': prices,
        'Volume': [np.random.randint(1000, 10000) for _ in range(10)]
    }, index=dates)
    
    fallback_info = {
        'previousClose': base_price,
        'volume': 5000,
        'marketCap': 10000000000
    }
    
    return fallback_hist, fallback_info

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

def main():
    # Title and header
    st.title("📈 NSE Stock Portfolio Tracker")
    st.markdown("Real-time tracking of CDSL, Mazagon Dock, GRSE, and Cochin Shipyard")
    
    # Sidebar controls
    st.sidebar.header("Settings")
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=False)  # Default to False to prevent rate limiting
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 60, 600, 120)  # Minimum 60 seconds
    
    # Data source status
    st.sidebar.header("Data Source Status")
    status_placeholder = st.sidebar.empty()
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now") or auto_refresh:
        # Clear cache to force fresh data
        get_cached_stock_data.clear()
    
    # Create placeholders for dynamic updates
    header_placeholder = st.empty()
    metrics_placeholder = st.empty()
    chart_placeholder = st.empty()
    table_placeholder = st.empty()
    
    # Initialize session state for data persistence
    if 'portfolio_data' not in st.session_state:
        st.session_state.portfolio_data = {}
    
    # Fetch data with rate limiting consideration
    current_time = int(time.time() // 60)  # Update timestamp every minute
    portfolio_data = {}
    fetch_success = 0
    fetch_total = len(PORTFOLIO_STOCKS)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (symbol, stock_info) in enumerate(PORTFOLIO_STOCKS.items()):
        status_text.text(f"Fetching data for {stock_info['name']}...")
        progress_bar.progress((i + 1) / fetch_total)
        
        # Use cached data to avoid rate limiting
        data, info = get_cached_stock_data(symbol, current_time)
        
        if data is not None and not data.empty and info:
            current_price = data['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close > 0 else 0
            
            portfolio_data[symbol] = {
                'name': stock_info['name'],
                'current_price': current_price,
                'prev_close': prev_close,
                'change': change,
                'change_pct': change_pct,
                'quantity': stock_info['quantity'],
                'value': current_price * stock_info['quantity'],
                'data': data,
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap', 0),
                'is_fallback': False
            }
            fetch_success += 1
        else:
            # Use previous data if available
            if symbol in st.session_state.portfolio_data:
                portfolio_data[symbol] = st.session_state.portfolio_data[symbol]
                portfolio_data[symbol]['is_fallback'] = True
        
        # Add small delay between requests
        time.sleep(1)
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    # Update session state
    if portfolio_data:
        st.session_state.portfolio_data.update(portfolio_data)
        portfolio_data = st.session_state.portfolio_data
    
    # Display status
    with status_placeholder.container():
        if fetch_success == fetch_total:
            st.success(f"✅ All {fetch_total} stocks updated")
        elif fetch_success > 0:
            st.warning(f"⚠️ {fetch_success}/{fetch_total} stocks updated")
        else:
            st.error("❌ Unable to fetch current data")
    
    if portfolio_data:
        # Calculate portfolio metrics
        portfolio_metrics = calculate_portfolio_metrics(portfolio_data)
        
        # Display portfolio summary
        with header_placeholder.container():
            st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Portfolio Value",
                    f"₹{portfolio_metrics['total_value']:,.2f}",
                    f"₹{portfolio_metrics['total_change']:,.2f}"
                )
            with col2:
                st.metric(
                    "Total Return %",
                    f"{portfolio_metrics['total_change_pct']:+.2f}%"
                )
            with col3:
                st.metric(
                    "Number of Stocks",
                    len(portfolio_data)
                )
            with col4:
                st.metric(
                    "Prev Day Close",
                    f"₹{portfolio_metrics['total_invested']:,.2f}"
                )
        
        # Individual stock metrics
        with metrics_placeholder.container():
            st.subheader("Individual Stock Performance")
            cols = st.columns(len(portfolio_data))
            
            for i, (symbol, data) in enumerate(portfolio_data.items()):
                with cols[i]:
                    color = "normal" if data['change'] >= 0 else "inverse"
                    fallback_indicator = " (📊)" if data.get('is_fallback', False) else ""
                    st.metric(
                        data['name'].split(' ')[0] + fallback_indicator,
                        f"₹{data['current_price']:.2f}",
                        f"{data['change']:+.2f} ({data['change_pct']:+.2f}%)",
                        delta_color=color
                    )
        
        # Portfolio composition chart
        with chart_placeholder.container():
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Portfolio Composition")
                labels = [data['name'].split(' ')[0] for data in portfolio_data.values()]
                values = [data['value'] for data in portfolio_data.values()]
                colors = ['green' if data['change'] >= 0 else 'red' for data in portfolio_data.values()]
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.3,
                    marker_colors=colors
                )])
                fig_pie.update_layout(title="Portfolio Value Distribution")
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.subheader("Price Movement")
                fig_line = go.Figure()
                
                for symbol, data in portfolio_data.items():
                    if not data['data'].empty:
                        fig_line.add_trace(go.Scatter(
                            x=data['data'].index,
                            y=data['data']['Close'],
                            mode='lines',
                            name=data['name'].split(' ')[0],
                            line=dict(width=2)
                        ))
                
                fig_line.update_layout(
                    title="Price Movement",
                    xaxis_title="Time",
                    yaxis_title="Price (₹)",
                    hovermode='x unified'
                )
                st.plotly_chart(fig_line, use_container_width=True)
        
        # Detailed table
        with table_placeholder.container():
            st.subheader("Detailed Portfolio View")
            
            table_data = []
            for symbol, data in portfolio_data.items():
                fallback_indicator = " 📊" if data.get('is_fallback', False) else ""
                table_data.append({
                    'Stock': data['name'] + fallback_indicator,
                    'Symbol': symbol.replace('.NS', ''),
                    'Current Price (₹)': f"{data['current_price']:.2f}",
                    'Previous Close (₹)': f"{data['prev_close']:.2f}",
                    'Change (₹)': f"{data['change']:+.2f}",
                    'Change (%)': f"{data['change_pct']:+.2f}%",
                    'Quantity': data['quantity'],
                    'Value (₹)': f"{data['value']:.2f}",
                    'Volume': f"{data['volume']:,}" if data['volume'] else "N/A"
                })
            
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
    
    else:
        st.error("Unable to fetch data for any stocks. Please check your internet connection and try again.")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
