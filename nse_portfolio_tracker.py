import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import numpy as np
import yfinance as yf
import requests
import json

# Configure Streamlit page
st.set_page_config(
    page_title="NSE Portfolio Tracker",
    page_icon="📈",
    layout="wide"
)

# Portfolio configuration with Yahoo Finance symbols for NSE stocks
PORTFOLIO_STOCKS = {
    'CDSL.NS': {'name': 'Central Depository Services Ltd', 'quantity': 4000, 'symbol': 'CDSL'},
    'MAZDOCK.NS': {'name': 'Mazagon Dock Shipbuilders Ltd', 'quantity': 500, 'symbol': 'MAZDOCK'},
    'GRSE.NS': {'name': 'Garden Reach Shipbuilders & Engineers Ltd', 'quantity': 500, 'symbol': 'GRSE'},
    'COCHINSHIP.NS': {'name': 'Cochin Shipyard Ltd', 'quantity': 600, 'symbol': 'COCHINSHIP'}
}

@st.cache_data(ttl=30)  # Cache for 30 seconds
def get_stock_quote(symbol):
    """Get stock quote using yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Get current data
        info = ticker.info
        hist = ticker.history(period="2d")
        
        if len(hist) >= 2:
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            
            day_high = hist['High'].iloc[-1]
            day_low = hist['Low'].iloc[-1]
            volume = hist['Volume'].iloc[-1]
            
            return {
                'lastPrice': current_price,
                'previousClose': prev_close,
                'change': change,
                'pChange': change_pct,
                'dayHigh': day_high,
                'dayLow': day_low,
                'totalTradedVolume': volume
            }
        elif len(hist) == 1:
            # If only one day of data available
            current_price = hist['Close'].iloc[-1]
            return {
                'lastPrice': current_price,
                'previousClose': current_price,
                'change': 0,
                'pChange': 0,
                'dayHigh': hist['High'].iloc[-1],
                'dayLow': hist['Low'].iloc[-1],
                'totalTradedVolume': hist['Volume'].iloc[-1]
            }
        return None
    except Exception as e:
        st.warning(f"Error fetching quote for {symbol}: {e}")
        return None

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_historical_data(symbol):
    """Get historical data for charts"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="5m")
        
        if not hist.empty:
            # Reset index to get timestamp as a column
            hist = hist.reset_index()
            return pd.DataFrame({
                'timestamp': hist['Datetime'],
                'price': hist['Close']
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

def test_connection():
    """Test Yahoo Finance connection"""
    try:
        test_ticker = yf.Ticker("RELIANCE.NS")
        test_data = test_ticker.history(period="1d")
        return not test_data.empty
    except:
        return False

def main():
    # Title and header
    st.title("📈 NSE Stock Portfolio Tracker")    
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
    
    # Connection status
    st.sidebar.subheader("Data Connection Status")
    if test_connection():
        st.sidebar.success("✅ Yahoo Finance Connected")
    else:
        st.sidebar.error("❌ Connection Issues")
    
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
        
        quote = get_stock_quote(symbol)
        
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
                
                portfolio_data[stock_info['symbol']] = {
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
                    'symbol': stock_info['symbol']
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
        
        # Historical price chart
        st.subheader("Intraday Price Movement")
        chart_symbol = st.selectbox("Select stock for intraday chart:", list(portfolio_data.keys()))
        
        if chart_symbol:
            # Find the corresponding Yahoo Finance symbol
            yf_symbol = None
            for yf_sym, info in PORTFOLIO_STOCKS.items():
                if info['symbol'] == chart_symbol:
                    yf_symbol = yf_sym
                    break
            
            if yf_symbol:
                hist_data = get_historical_data(yf_symbol)
                if hist_data is not None and not hist_data.empty:
                    fig_line = go.Figure()
                    fig_line.add_trace(go.Scatter(
                        x=hist_data['timestamp'],
                        y=hist_data['price'],
                        mode='lines',
                        name=f'{chart_symbol} Price',
                        line=dict(color='blue', width=2)
                    ))
                    
                    fig_line.update_layout(
                        title=f"{portfolio_data[chart_symbol]['name']} - Intraday Price Movement",
                        xaxis_title="Time",
                        yaxis_title="Price (₹)",
                        height=400
                    )
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.info("No intraday data available for this stock")
        
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
                    'Volume': f"{data['volume']:,}" if data['volume'] != 'N/A' else 'N/A'
                })
            
            df = pd.DataFrame(table_data)
            
            # Style the dataframe with colors
            def style_changes(val):
                if 'Change' in val.name and '₹' in str(val):
                    try:
                        if '+' in str(val):
                            return 'background-color: #d4edda; color: #155724'
                        elif '-' in str(val):
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
        st.error("Unable to fetch data for any stocks. Please check your internet connection and try again.")
        st.info("💡 **Troubleshooting Tips:**")
        st.info("1. Check your internet connection")
        st.info("2. Try refreshing the page")
        st.info("3. Market data might be delayed or unavailable during non-trading hours")
        st.info("4. Ensure you have installed yfinance: `pip install yfinance`")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
