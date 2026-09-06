import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Configuración de página y Estilos CSS Tema Binance Dark
st.set_page_config(page_title="Binance Pro Clone", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Estilo oscuro general */
    .stApp { background-color: #0b0e11; color: #eaecef; }
    header, footer { visibility: hidden; }
    
    /* Contenedores estilo Binance */
    div[data-testid="stVerticalBlock"] > div {
        background-color: #181a20;
        border-radius: 4px;
        padding: 6px;
    }
    
    /* Botones de Operación */
    .stButton > button {
        font-weight: bold;
        border-radius: 4px;
        border: none;
        width: 100%;
        height: 42px;
    }
    /* Estilizado personalizado de pestañas */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #181a20; }
    .stTabs [data-baseweb="tab"] { color: #848e9c; }
    .stTabs [aria-selected="true"] { color: #f0b90b !important; }
</style>
""", unsafe_allow_html=True)

# 2. Inicialización de Session State (Billetera e Historial)
if "saldo_usdt" not in st.session_state:
    st.session_state.saldo_usdt = 10000.0
if "posiciones" not in st.session_state:
    st.session_state.posiciones = {"BTC": 0.5, "ETH": 2.0}
if "historial" not in st.session_state:
    st.session_state.historial = []

# 3. Funciones API de Binance
@st.cache_data(ttl=5)
def obtener_ticker_24h(symbol):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    return requests.get(url).json()

@st.cache_data(ttl=10)
def obtener_klines(symbol, interval="1h", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "num_trades", "tbb", "tbq", "ignore"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df

@st.cache_data(ttl=2)
def obtener_libro_ordenes(symbol, limit=10):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}"
    res = requests.get(url).json()
    bids = pd.DataFrame(res["bids"], columns=["Precio", "Cantidad"]).astype(float)
    asks = pd.DataFrame(res["asks"], columns=["Precio", "Cantidad"]).astype(float)
    return bids, asks

# 4. Header Superior (Métricas de Ticker)
par_seleccionado = st.selectbox("Seleccionar Par", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], index=0)
ticker = obtener_ticker_24h(par_seleccionado)
cripto_base = par_seleccionado.replace("USDT", "")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Precio Actual", f"${float(ticker['lastPrice']):,.2f}", f"{float(ticker['priceChangePercent']):.2f}%")
m2.metric("Máximo 24h", f"${float(ticker['highPrice']):,.2f}")
m3.metric("Mínimo 24h", f"${float(ticker['lowPrice']):,.2f}")
m4.metric("Volumen 24h", f"{float(ticker['volume']):,.2f} {cripto_base}")
m5.metric("Saldo USDT", f"${st.session_state.saldo_usdt:,.2f}")

st.divider()

# 5. Dashboard Principal Layout
col_grafico, col_orderbook, col_trade = st.columns([2.5, 1, 1.2])

# --- COLUMNA 1: Gráficos de Velas + Volumen ---
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

# --- COLUMNA 2: Libro de Órdenes (Order Book) ---
with col_orderbook:
    st.subheader("📖 Order Book")
    bids, asks = obtener_libro_ordenes(par_seleccionado)
    precio_actual = float(ticker['lastPrice'])

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

# --- COLUMNA 3: Panel de Ejecución de Órdenes ---
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

# 6. Panel Inferior: Portafolio e Historial
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
