import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Configuración de página y Estilos CSS Tema Binance Dark
st.set_page_config(page_title="Binance Pro Clone", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0b0e11; color: #eaecef; }
    header, footer { visibility: hidden; }
    
    div[data-testid="stVerticalBlock"] > div {
        background-color: #181a20;
        border-radius: 4px;
        padding: 6px;
    }
    
    .stButton > button {
        font-weight: bold;
        border-radius: 4px;
        border: none;
        width: 100%;
        height: 42px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #181a20; }
    .stTabs [data-baseweb="tab"] { color: #848e9c; }
    .stTabs [aria-selected="true"] { color: #f0b90b !important; }
</style>
""", unsafe_allow_html=True)

# 2. Inicialización de Session State
if "saldo_usdt" not in st.session_state:
    st.session_state.saldo_usdt = 10000.0
if "posiciones" not in st.session_state:
    st.session_state.posiciones = {"BTC": 0.5, "ETH": 2.0}
if "historial" not in st.session_state:
    st.session_state.historial = []

# 3. Función auxiliar resiliente para consultas HTTP
def peticion_binance_segura(endpoint, params):
    urls = [
        f"https://api.binance.com/api/v3/{endpoint}",
        f"https://api.binance.us/api/v3/{endpoint}"
    ]
    for url in urls:
        try:
            res = requests.get(url, params=params, timeout=3)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict) and "code" in data:
                    continue
                return data
        except Exception:
            continue
    return None

# 4. Funciones API protegidas con datos de respaldo
@st.cache_data(ttl=5)
def obtener_ticker_24h(symbol):
    data = peticion_binance_segura("ticker/24hr", {"symbol": symbol})
    if data and "lastPrice" in data:
        return data
    return {
        "lastPrice": "65000.00",
        "priceChangePercent": "0.00",
        "highPrice": "66000.00",
        "lowPrice": "64000.00",
        "volume": "1000.00"
    }

@st.cache_data(ttl=10)
def obtener_klines(symbol, interval="1h", limit=100):
    data = peticion_binance_segura("klines", {"symbol": symbol, "interval": interval, "limit": limit})
    if data and isinstance(data, list):
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "num_trades", "tbb", "tbq", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df

    dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="1h")
    precios = 65000.0 + np.cumsum(np.random.randn(limit) * 80)
    return pd.DataFrame({
        "time": dates,
        "open": precios,
        "high": precios + 40,
        "low": precios - 40,
        "close": precios + 10,
        "volume": np.random.randint(20, 150, size=limit)
    })

@st.cache_data(ttl=2)
def obtener_libro_ordenes(symbol, limit=10):
    data = peticion_binance_segura("depth", {"symbol": symbol, "limit": limit})
    if data and "bids" in data and "asks" in data:
        bids = pd.DataFrame(data["bids"], columns=["Precio", "Cantidad"]).astype(float)
        asks = pd.DataFrame(data["asks"], columns=["Precio", "Cantidad"]).astype(float)
        return bids, asks

    px = 65000.0
    bids = pd.DataFrame([[px - i * 12, 0.2 + i * 0.05] for i in range(1, limit + 1)], columns=["Precio", "Cantidad"])
    asks = pd.DataFrame([[px + i * 12, 0.2 + i * 0.05] for i in range(1, limit + 1)], columns=["Precio", "Cantidad"])
    return bids, asks

# 5. Header Superior
par_seleccionado = st.selectbox("Seleccionar Par", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], index=0)
ticker = obtener_ticker_24h(par_seleccionado)
cripto_base = par_seleccionado.replace("USDT", "")

precio_actual = float(ticker.get("lastPrice", 0))
cambio_pct = float(ticker.get("priceChangePercent", 0))

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Precio Actual", f"${precio_actual:,.2f}", f"{cambio_pct:.2f}%")
m2.metric("Máximo 24h", f"${float(ticker.get('highPrice', 0)):,.2f}")
m3.metric("Mínimo 24h", f"${float(ticker.get('lowPrice', 0)):,.2f}")
m4.metric("Volumen 24h", f"{float(ticker.get('volume', 0)):,.2f} {cripto_base}")
m5.metric("Saldo USDT", f"${st.session_state.saldo_usdt:,.2f}")

st.divider()

# 6. Layout Principal
col_grafico, col_orderbook, col_trade = st.columns([2.5, 1, 1.2])

# --- Gráfico ---
with col_grafico:
    st.subheader(f"📈 {par_seleccionado} - Gráfico K-Line")
    temporalidad = st.radio("Intervalo", ["15m", "1h", "4h", "1d"], horizontal=True, index=1)
    df_klines = obtener_klines(par_seleccionado, interval=temporalidad)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=df_klines['time'], open=df_klines['open'], high=df_klines['high'],
        low=df_klines['low'], close=df_klines['close'],
        increasing_line_color='#0ecb81', decreasing_line_color='#f6465d', name="Precio"
    ), row=1, col=1)
    
    colors = ['#0ecb81' if c >= o else '#f6465d' for c, o in zip(df_klines['close'], df_klines['open'])]
    fig.add_trace(go.Bar(x=df_klines['time'], y=df_klines['volume'], marker_color=colors, name="Volumen"), row=2, col=1)

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#181a20", plot_bgcolor="#181a20",
        margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False, height=500
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Libro de Órdenes ---
with col_orderbook:
    st.subheader("📖 Order Book")
    bids, asks = obtener_libro_ordenes(par_seleccionado)

    st.caption("🔴 Ventas (Asks)")
    st.dataframe(
        asks.sort_values(by="Precio", ascending=False).style.format({"Precio": "${:,.2f}", "Cantidad": "{:.4f}"}),
        height=180, use_container_width=True
    )
    st.markdown(f"### **${precio_actual:,.2f}**")
    st.caption("🟢 Compras (Bids)")
    st.dataframe(
        bids.style.format({"Precio": "${:,.2f}", "Cantidad": "{:.4f}"}),
        height=180, use_container_width=True
    )

# --- Panel de Trading ---
with col_trade:
    st.subheader("⚡ Spot Trading")
    tab_buy, tab_sell = st.tabs(["Comprar", "Vender"])

    with tab_buy:
        tipo_orden = st.selectbox("Tipo de Orden", ["Market", "Limit"], key="buy_type")
        px_compra = precio_actual if tipo_orden == "Market" else st.number_input("Precio USDT", value=precio_actual)
        cantidad_compra = st.number_input("Cantidad", min_value=0.0001, step=0.01, key="buy_qty")
        total_usdt = px_compra * cantidad_compra

        st.caption(f"Total: **${total_usdt:,.2f} USDT**")
        if st.button("Comprar " + cripto_base, type="primary"):
            if st.session_state.saldo_usdt >= total_usdt:
                st.session_state.saldo_usdt -= total_usdt
                st.session_state.posiciones[cripto_base] = st.session_state.posiciones.get(cripto_base, 0.0) + cantidad_compra
                st.session_state.historial.append({"Tipo": "COMPRA", "Par": par_seleccionado, "Precio": px_compra, "Cantidad": cantidad_compra})
                st.success("Orden Ejecutada")
                st.rerun()
            else:
                st.error("Saldo insuficiente")

    with tab_sell:
        tipo_orden_s = st.selectbox("Tipo de Orden", ["Market", "Limit"], key="sell_type")
        px_venta = precio_actual if tipo_orden_s == "Market" else st.number_input("Precio USDT", value=precio_actual, key="spx")
        cantidad_venta = st.number_input("Cantidad", min_value=0.0001, step=0.01, key="sell_qty")
        posicion_actual = st.session_state.posiciones.get(cripto_base, 0.0)

        st.caption(f"Disponible: {posicion_actual:.4f} {cripto_base}")
        if st.button("Vender " + cripto_base):
            if posicion_actual >= cantidad_venta:
                total_recibido = px_venta * cantidad_venta
                st.session_state.saldo_usdt += total_recibido
                st.session_state.posiciones[cripto_base] -= cantidad_venta
                st.session_state.historial.append({"Tipo": "VENTA", "Par": par_seleccionado, "Precio": px_venta, "Cantidad": cantidad_venta})
                st.success("Orden Ejecutada")
                st.rerun()
            else:
                st.error("Balance insuficiente")

# 7. Portafolio e Historial
st.divider()
col_portafolio, col_historial = st.columns([1, 1])

with col_portafolio:
    st.subheader("💼 Balances de Cuenta")
    df_pos = pd.DataFrame([{"Activo": k, "Cantidad": v} for k, v in st.session_state.posiciones.items() if v > 0])
    st.dataframe(df_pos, use_container_width=True)

with col_historial:
    st.subheader("📜 Historial de Órdenes")
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
    else:
        st.info("Sin transacciones registradas.")
