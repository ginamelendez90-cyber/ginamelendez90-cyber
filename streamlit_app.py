import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Simulador Binance", layout="wide")

st.title("⚡ Simulador de Trading Binance (Paper Trading)")

# 1. Inicializar la billetera y el historial en la sesión
if "saldo_usdt" not in st.session_state:
    st.session_state.saldo_usdt = 10000.0  # $10,000 USDT ficticios
if "posiciones" not in st.session_state:
    st.session_state.posiciones = {"BTC": 0.0, "ETH": 0.0, "SOL": 0.0}
if "historial" not in st.session_state:
    st.session_state.historial = []

# 2. Función para obtener precios reales sin API Key
def obtener_precio_binance(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    res = requests.get(url, timeout=5)
    if res.status_code == 200:
        return float(res.json()["price"])
    return 0.0

col_operaciones, col_cartera = st.columns([1, 1.2])

with col_operaciones:
    st.subheader("📊 Panel de Mercado")
    cripto = st.selectbox("Selecciona un activo", ["BTC", "ETH", "SOL"])
    
    precio_actual = obtener_precio_binance(cripto)
    st.metric(label=f"Precio Actual {cripto}/USDT", value=f"${precio_actual:,.2f}")

    st.subheader("🛒 Operar")
    tipo_orden = st.radio("Acción", ["Comprar", "Vender"], horizontal=True)
    cantidad = st.number_input(f"Cantidad de {cripto}", min_value=0.001, step=0.01, format="%.4f")
    total_usdt = cantidad * precio_actual
    
    st.info(f"Total estimado: **${total_usdt:,.2f} USDT**")
    
    if st.button("Ejecutar Orden", type="primary"):
        if tipo_orden == "Comprar":
            if st.session_state.saldo_usdt >= total_usdt:
                st.session_state.saldo_usdt -= total_usdt
                st.session_state.posiciones[cripto] += cantidad
                st.session_state.historial.append({
                    "Tipo": "COMPRA", "Cripto": cripto, "Cantidad": cantidad,
                    "Precio": precio_actual, "Total USDT": total_usdt
                })
                st.success(f"Comprados {cantidad} {cripto} con éxito.")
                st.rerun()
            else:
                st.error("Saldo insuficiente en USDT.")
        else:
            if st.session_state.posiciones[cripto] >= cantidad:
                st.session_state.saldo_usdt += total_usdt
                st.session_state.posiciones[cripto] -= cantidad
                st.session_state.historial.append({
                    "Tipo": "VENTA", "Cripto": cripto, "Cantidad": cantidad,
                    "Precio": precio_actual, "Total USDT": total_usdt
                })
                st.success(f"Vendidos {cantidad} {cripto} con éxito.")
                st.rerun()
            else:
                st.error(f"No posees suficiente {cripto} para vender.")

with col_cartera:
    st.subheader("💼 Billetera Virtual")
    
    # Calcular valor total estimado del portafolio
    valor_criptos = sum(
        cant * obtener_precio_binance(c) 
        for c, cant in st.session_state.posiciones.items() if cant > 0
    )
    patrimonio_total = st.session_state.saldo_usdt + valor_criptos

    m1, m2 = st.columns(2)
    m1.metric("Disponible USDT", f"${st.session_state.saldo_usdt:,.2f}")
    m2.metric("Patrimonio Total", f"${patrimonio_total:,.2f}")

    st.write("**Posiciones Activas:**")
    df_pos = pd.DataFrame(
        [{"Cripto": k, "Cantidad": v} for k, v in st.session_state.posiciones.items()]
    )
    st.dataframe(df_pos, use_container_width=True)

    if st.session_state.historial:
        st.write("**Historial de Registro:**")
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True)
