import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests

# Configuración de página
st.set_page_config(page_title="Analizador Algorítmico de Fútbol", page_icon="⚽", layout="wide")

# -----------------------------------------------------------------------------
# 1. ESTADO Y SIMULADOR DE API / BASE DE DATOS
# -----------------------------------------------------------------------------
if 'partido_seleccionado' not in st.session_state:
    st.session_state.partido_seleccionado = None

if 'datos_cargados' not in st.session_state:
    # Datos iniciales de demostración con métricas avanzadas (xG, tiros, fuerza defensiva)
    st.session_state.datos_cargados = pd.DataFrame([
        {
            "Partido": "Real Madrid vs Barcelona",
            "Local": "Real Madrid", "Visitante": "Barcelona",
            "xG_Local": 2.15, "Goles_Local": 2.0, "Tiros_Puerta_Local": 6.8,
            "xG_Vis": 1.70, "Goles_Vis": 1.5, "Tiros_Puerta_Vis": 5.2,
            "Factor_Localia": 1.12
        },
        {
            "Partido": "Arsenal vs Manchester City",
            "Local": "Arsenal", "Visitante": "Manchester City",
            "xG_Local": 1.80, "Goles_Local": 1.6, "Tiros_Puerta_Local": 5.0,
            "xG_Vis": 2.10, "Goles_Vis": 1.9, "Tiros_Puerta_Vis": 6.1,
            "Factor_Localia": 1.10
        }
    ])

def obtener_datos_api_online(api_key):
    """
    Función lista para conectar con API-Football o similar.
    Sustituir la URL con el endpoint real al activar tu plan.
    """
    if not api_key:
        return st.session_state.datos_cargados
    # Ejemplo de estructura de llamada API:
    # headers = {'x-apisports-key': api_key}
    # response = requests.get('https://v3.football.api-sports.io/fixtures?league=140&season=2025', headers=headers)
    return st.session_state.datos_cargados

# -----------------------------------------------------------------------------
# 2. MOTOR MATEMÁTICO (POISSON CON PONDERACIÓN AVANZADA)
# -----------------------------------------------------------------------------
def calcular_lambda(xg, goles, tiros, factor_localia=1.0):
    """Calcula la expectativa de goles (Lambda) usando xG (50%), Goles (35%) y Tiros (15%)."""
    expectativa_base = (xg * 0.50) + (goles * 0.35) + (tiros * 0.05)
    return expectativa_base * factor_localia

def generar_matriz_poisson(lambda_local, lambda_visitante, max_goles=7):
    """Genera la matriz de probabilidades cuadradas para los resultados de un partido."""
    prob_local = [poisson.pmf(i, lambda_local) for i in range(max_goles)]
    prob_vis = [poisson.pmf(i, lambda_visitante) for i in range(max_goles)]
    return np.outer(prob_local, prob_vis)

# -----------------------------------------------------------------------------
# 3. INTERFAZ GRÁFICA Y CONTROL DE MERCADOS
# -----------------------------------------------------------------------------
st.title("⚽ Analizador Estadístico de Apuestas de Fútbol")

# Barra Lateral: Configuración de Datos y API
with st.sidebar:
    st.header("🔑 Conexión a API Online")
    api_key = st.text_input("API Key (API-Football / RapidAPI)", type="password")
    if st.button("Sincronizar / Cargar Datos"):
        st.session_state.datos_cargados = obtener_datos_api_online(api_key)
        st.success("Base de datos actualizada.")
    
    st.markdown("---")
    st.header("🎯 Selección de Partido")
    partidos_disponibles = st.session_state.datos_cargados["Partido"].tolist()
    partido_elegido = st.selectbox("Elige un encuentro:", partidos_disponibles)
    
    # Extraer fila seleccionada
    df_partido = st.session_state.datos_cargados[
        st.session_state.datos_cargados["Partido"] == partido_elegido
    ].iloc[0]

# --- CÁLCULOS MATEMÁTICOS ---
l_local = calcular_lambda(df_partido["xG_Local"], df_partido["Goles_Local"], df_partido["Tiros_Puerta_Local"], df_partido["Factor_Localia"])
l_vis = calcular_lambda(df_partido["xG_Vis"], df_partido["Goles_Vis"], df_partido["Tiros_Puerta_Vis"])

matriz = generar_matriz_poisson(l_local, l_vis)

# Probabilidades Mercado 1X2
p_local = np.sum(np.tril(matriz, -1))
p_empate = np.sum(np.diag(matriz))
p_vis = np.sum(np.triu(matriz, 1))

# Probabilidades Mercado Goles Totales (Over/Under)
goles_matriz = np.add.outer(np.arange(matriz.shape[0]), np.arange(matriz.shape[1]))
p_under_15 = np.sum(matriz[goles_matriz <= 1])
p_over_15 = 1 - p_under_15
p_under_25 = np.sum(matriz[goles_matriz <= 2])
p_over_25 = 1 - p_under_25
p_under_35 = np.sum(matriz[goles_matriz <= 3])
p_over_35 = 1 - p_under_35

# Mercado Ambos Anotan (BTTS)
p_btts_si = 1 - (np.sum(matriz[0, :]) + np.sum(matriz[:, 0]) - matriz[0, 0])
p_btts_no = 1 - p_btts_si

# --- MOSTRAR DATOS TÁCTICOS EN CABECERA ---
st.subheader(f"📊 Análisis: {df_partido['Local']} vs {df_partido['Visitante']}")
col_a, col_b, col_c = st.columns(3)
col_a.metric(f"xG Promedio {df_partido['Local']}", f"{df_partido['xG_Local']} goles")
col_b.metric(f"xG Promedio {df_partido['Visitante']}", f"{df_partido['xG_Vis']} goles")
col_c.metric("Factor Localía Aplicado", f"+{int((df_partido['Factor_Localia']-1)*100)}%")

st.markdown("---")

# -----------------------------------------------------------------------------
# 4. PESTAÑAS DE MERCADOS MÚLTIPLES (SIN PERDER DATOS)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Mercado 1X2 (Match Odds)", "⚽ Goles (Over/Under)", "🥊 Ambos Anotan (BTTS)", "🤖 Prompt para Gemini"])

with tab1:
    st.subheader("Predicción de Resultado Final y Valor Esperado (EV)")
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Gana {df_partido['Local']}", f"{p_local*100:.1f}%", help="Cuota Justa: " + str(round(1/p_local, 2)))
    c2.metric("Empate", f"{p_empate*100:.1f}%", help="Cuota Justa: " + str(round(1/p_empate, 2)))
    c3.metric(f"Gana {df_partido['Visitante']}", f"{p_vis*100:.1f}%", help="Cuota Justa: " + str(round(1/p_vis, 2)))
    
    st.markdown("#### 📐 Calculadora de Valor Esperado (EV)")
    col_ev1, col_ev2 = st.columns(2)
    opcion_apuesta = col_ev1.selectbox("Selecciona la opción a evaluar:", [df_partido['Local'], "Empate", df_partido['Visitante']])
    cuota_casa = col_ev2.number_input("Cuota que ofrece la Casa de Apuestas:", min_value=1.01, value=2.10, step=0.05)
    
    prob_map = {df_partido['Local']: p_local, "Empate": p_empate, df_partido['Visitante']: p_vis}
    prob_elegida = prob_map[opcion_apuesta]
    ev = (prob_elegida * cuota_casa) - 1
    
    if ev > 0:
        st.success(f"**¡Apuesta de Valor Detectada (EV Positivo)!** El valor es de **+{ev*100:.2f}%**")
    else:
        st.error(f"**Sin Valor (EV Negativo):** La apuesta no tiene ventaja estadística (**{ev*100:.2f}%**)")

with tab2:
    st.subheader("Mercado de Total de Goles")
    g1, g2, g3 = st.columns(3)
    
    with g1:
        st.markdown("**Línea 1.5 Goles**")
        st.write(f"Over 1.5: **{p_over_15*100:.1f}%**")
        st.write(f"Under 1.5: **{p_under_15*100:.1f}%**")
    with g2:
        st.markdown("**Línea 2.5 Goles (Estándar)**")
        st.write(f"Over 2.5: **{p_over_25*100:.1f}%**")
        st.write(f"Under 2.5: **{p_under_25*100:.1f}%**")
    with g3:
        st.markdown("**Línea 3.5 Goles**")
        st.write(f"Over 3.5: **{p_over_35*100:.1f}%**")
        st.write(f"Under 3.5: **{p_under_35*100:.1f}%**")

with tab3:
    st.subheader("Mercado de Ambos Equipos Anotan")
    b1, b2 = st.columns(2)
    b1.metric("Ambos Anotan: SÍ", f"{p_btts_si*100:.1f}%", help=f"Cuota Justa: {round(1/p_btts_si, 2)}")
    b2.metric("Ambos Anotan: NO", f"{p_btts_no*100:.1f}%", help=f"Cuota Justa: {round(1/p_btts_no, 2)}")

with tab4:
    st.subheader("Copia este Prompt para un Análisis Cualitativo en Gemini")
    prompt_texto = f"""
Actúa como un analista profesional de apuestas deportivas. He corrido un modelo de Poisson con ponderación de xG, goles reales y tiros a puerta para el siguiente partido:

Partido: {df_partido['Local']} vs {df_partido['Visitante']}
- Probabilidades 1X2: Local ({p_local*100:.1f}%), Empate ({p_empate*100:.1f}%), Visitante ({p_vis*100:.1f}%)
- Mercado Over/Under 2.5: Over 2.5 ({p_over_25*100:.1f}%), Under 2.5 ({p_under_25*100:.1f}%)
- Ambos Anotan (BTTS): Sí ({p_btts_si*100:.1f}%)
- xG promedio ajustado: {df_partido['Local']} ({df_partido['xG_Local']}) - {df_partido['Visitante']} ({df_partido['xG_Vis']})

Considerando la forma reciente, calendario de competiciones o bajas de jugadores clave, ¿encuentras algún factor cualitativo que altere este modelo numérico?
"""
    st.text_area("Texto listo para copiar:", value=prompt_texto, height=250)
