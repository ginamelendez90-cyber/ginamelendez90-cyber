import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests

# Configuración de página
st.set_page_config(page_title="Analizador Algorítmico de Fútbol", page_icon="⚽", layout="wide")

# -----------------------------------------------------------------------------
# 1. ESTADO Y CONEXIÓN A API / BASE DE DATOS
# -----------------------------------------------------------------------------
if 'datos_cargados' not in st.session_state:
    st.session_state.datos_cargados = pd.DataFrame([
        {
            "Partido": "Real Madrid vs Barcelona",
            "Local": "Real Madrid", "Visitante": "Barcelona",
            "xG_Local": 2.15, "Goles_Local": 2.0, "Tiros_Puerta_Local": 6.8,
            "xG_Vis": 1.70, "Goles_Vis": 1.5, "Tiros_Puerta_Vis": 5.2,
            "Factor_Localia": 1.12
        }
    ])

def obtener_datos_football_data(api_key, liga_code="PD"):
    if not api_key:
        st.error("Ingresa tu API Key de football-data.org en la barra lateral.")
        return st.session_state.datos_cargados

    headers = {'X-Auth-Token': api_key}
    url_partidos = f"https://api.football-data.org/v4/competitions/{liga_code}/matches?status=SCHEDULED"
    url_tabla = f"https://api.football-data.org/v4/competitions/{liga_code}/standings"

    try:
        res_tabla = requests.get(url_tabla, headers=headers)
        stats_equipos = {}
        if res_tabla.status_code == 200:
            tabla_data = res_tabla.json()
            if 'standings' in tabla_data and len(tabla_data['standings']) > 0:
                for fila in tabla_data['standings'][0]['table']:
                    nombre = fila['team']['name']
                    pj = fila['playedGames'] if fila['playedGames'] > 0 else 1
                    stats_equipos[nombre] = {
                        'gf': fila['goalsFor'] / pj,
                        'ga': fila['goalsAgainst'] / pj
                    }
        
        res_partidos = requests.get(url_partidos, headers=headers)
        if res_partidos.status_code != 200:
            st.error(f"Error API ({res_partidos.status_code}): No se pudieron obtener partidos.")
            return st.session_state.datos_cargados

        partidos = res_partidos.json().get('matches', [])
        if not partidos:
            st.warning("No hay partidos próximos programados.")
            return st.session_state.datos_cargados

        filas_procesadas = []
        for p in partidos[:15]:
            local = p['homeTeam']['name']
            visitante = p['awayTeam']['name']
            stat_loc = stats_equipos.get(local, {'gf': 1.5, 'ga': 1.0})
            stat_vis = stats_equipos.get(visitante, {'gf': 1.2, 'ga': 1.2})
            
            xg_loc = round(stat_loc['gf'], 2)
            xg_vis = round(stat_vis['gf'], 2)

            filas_procesadas.append({
                "Partido": f"{local} vs {visitante}",
                "Local": local, "Visitante": visitante,
                "xG_Local": xg_loc if xg_loc > 0 else 1.4,
                "Goles_Local": xg_loc if xg_loc > 0 else 1.4,
                "Tiros_Puerta_Local": round(xg_loc * 3.2, 1),
                "xG_Vis": xg_vis if xg_vis > 0 else 1.1,
                "Goles_Vis": xg_vis if xg_vis > 0 else 1.1,
                "Tiros_Puerta_Vis": round(xg_vis * 3.2, 1),
                "Factor_Localia": 1.10
            })

        return pd.DataFrame(filas_procesadas)
    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return st.session_state.datos_cargados

# -----------------------------------------------------------------------------
# 2. MOTOR MATEMÁTICO (POISSON Y VALOR ESPERADO)
# -----------------------------------------------------------------------------
def calcular_lambda(xg, goles, tiros, factor_localia=1.0):
    return ((xg * 0.50) + (goles * 0.35) + (tiros * 0.05)) * factor_localia

def generar_matriz_poisson(lambda_local, lambda_visitante, max_goles=7):
    prob_local = [poisson.pmf(i, lambda_local) for i in range(max_goles)]
    prob_vis = [poisson.pmf(i, lambda_visitante) for i in range(max_goles)]
    return np.outer(prob_local, prob_vis)

# -----------------------------------------------------------------------------
# 3. INTERFAZ GRÁFICA Y CONTROL DE SESIÓN
# -----------------------------------------------------------------------------
st.title("⚽ Analizador Estadístico y Veredicto de Apuestas")

with st.sidebar:
    st.header("🔑 API Football-Data")
    api_key = st.text_input("Ingresa tu API Key:", type="password")
    liga_seleccionada = st.selectbox(
        "Liga:", options=["PD", "PL", "SA", "BL1", "FL1", "CL"],
        format_func=lambda x: {"PD": "La Liga", "PL": "Premier League", "SA": "Serie A", "BL1": "Bundesliga", "FL1": "Ligue 1", "CL": "Champions League"}[x]
    )
    if st.button("Sincronizar Partidos"):
        st.session_state.datos_cargados = obtener_datos_football_data(api_key, liga_seleccionada)

    st.markdown("---")
    st.header("🎯 Selección de Partido")
    partidos_disponibles = st.session_state.datos_cargados["Partido"].tolist()
    partido_elegido = st.selectbox("Elige un partido:", partidos_disponibles)
    
    df_partido = st.session_state.datos_cargados[st.session_state.datos_cargados["Partido"] == partido_elegido].iloc[0]

    st.markdown("---")
    st.header("💵 Cuotas de la Casa de Apuestas")
    st.caption("Ingresa las cuotas para calcular el Valor Esperado (EV):")
    cuota_loc = st.number_input(f"Cuota {df_partido['Local']}", min_value=1.01, value=2.05, step=0.05)
    cuota_emp = st.number_input("Cuota Empate", min_value=1.01, value=3.40, step=0.05)
    cuota_vis = st.number_input(f"Cuota {df_partido['Visitante']}", min_value=1.01, value=3.60, step=0.05)
    cuota_over25 = st.number_input("Cuota Over 2.5 Goles", min_value=1.01, value=1.95, step=0.05)
    cuota_btts = st.number_input("Cuota Ambos Anotan (SÍ)", min_value=1.01, value=1.80, step=0.05)

# --- CÁLCULOS MATEMÁTICOS ---
l_local = calcular_lambda(df_partido["xG_Local"], df_partido["Goles_Local"], df_partido["Tiros_Puerta_Local"], df_partido["Factor_Localia"])
l_vis = calcular_lambda(df_partido["xG_Vis"], df_partido["Goles_Vis"], df_partido["Tiros_Puerta_Vis"])
matriz = generar_matriz_poisson(l_local, l_vis)

# Probabilidades por Mercado
p_local = np.sum(np.tril(matriz, -1))
p_empate = np.sum(np.diag(matriz))
p_vis = np.sum(np.triu(matriz, 1))

goles_matriz = np.add.outer(np.arange(matriz.shape[0]), np.arange(matriz.shape[1]))
p_over_25 = 1 - np.sum(matriz[goles_matriz <= 2])
p_under_25 = 1 - p_over_25

p_btts_si = 1 - (np.sum(matriz[0, :]) + np.sum(matriz[:, 0]) - matriz[0, 0])

# -----------------------------------------------------------------------------
# 4. MOTOR DE VEREDICTO FINAL AUTOMÁTICO
# -----------------------------------------------------------------------------
mercados_evaluados = [
    {"mercado": f"Victoria {df_partido['Local']}", "prob": p_local, "cuota": cuota_loc, "tipo": "1X2"},
    {"mercado": "Empate", "prob": p_empate, "cuota": cuota_emp, "tipo": "1X2"},
    {"mercado": f"Victoria {df_partido['Visitante']}", "prob": p_vis, "cuota": cuota_vis, "tipo": "1X2"},
    {"mercado": "Over 2.5 Goles", "prob": p_over_25, "cuota": cuota_over25, "tipo": "Goles"},
    {"mercado": "Ambos Anotan (SÍ)", "prob": p_btts_si, "cuota": cuota_btts, "tipo": "BTTS"}
]

# Calcular EV para cada opción
for m in mercados_evaluados:
    m["ev"] = (m["prob"] * m["cuota"]) - 1
    m["cuota_justa"] = 1 / m["prob"] if m["prob"] > 0 else 99.0

# Ordenar por el mayor Valor Esperado (EV)
mercados_ordenados = sorted(mercados_evaluados, key=lambda x: x["ev"], reverse=True)
mejor_opcion = mercados_ordenados[0]

# --- CABECERA Y VEREDICTO ---
st.subheader(f"📊 {df_partido['Local']} vs {df_partido['Visitante']}")

st.markdown("### 🏆 Veredicto Final del Algoritmo")

if mejor_opcion["ev"] > 0.03: # Si hay más de 3% de ventaja estadística
    st.success(f"""
    **RECOMENDACIÓN PRINCIPAL:** Apoyar **{mejor_opcion['mercado']}**
    * **Valor Esperado (EV):** `+{mejor_opcion['ev']*100:.2f}%` (Ventaja sobre la casa de apuestas)
    * **Probabilidad Calculada:** `{mejor_opcion['prob']*100:.1f}%`
    * **Cuota Mínima Aceptable (Cuota Justa):** `{mejor_opcion['cuota_justa']:.2f}` (Cuota actual: `{mejor_opcion['cuota']}`)
    * **Nivel de Riesgo:** {'Bajo' if mejor_opcion['prob'] > 0.55 else 'Moderado' if mejor_opcion['prob'] > 0.40 else 'Alto'}
    """)
elif mejor_opcion["ev"] > 0:
    st.warning(f"""
    **RECOMENDACIÓN MODERADA:** **{mejor_opcion['mercado']}** tiene un valor marginal (`+{mejor_opcion['ev']*100:.2f}%`).
    * Se sugiere una apuesta pequeña o esperar a que la cuota suba en vivo.
    """)
else:
    st.error("""
    **SIN APUESTA DE VALOR DETECTADA (NO BET)**
    Todas las cuotas ingresadas ofrecen un **EV Negativo**. La casa de apuestas mantiene el margen a su favor en este encuentro. 
    """)

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. PESTAÑAS DETALLADAS
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Mercado 1X2", "⚽ Over / Under", "🥊 Both Teams To Score", "🤖 Prompt IA"])

with tab1:
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Gana {df_partido['Local']}", f"{p_local*100:.1f}%", f"Cuota Justa: {1/p_local:.2f}")
    c2.metric("Empate", f"{p_empate*100:.1f}%", f"Cuota Justa: {1/p_empate:.2f}")
    c3.metric(f"Gana {df_partido['Visitante']}", f"{p_vis*100:.1f}%", f"Cuota Justa: {1/p_vis:.2f}")

with tab2:
    g1, g2 = st.columns(2)
    g1.metric("Over 2.5 Goles", f"{p_over_25*100:.1f}%", f"Cuota Justa: {1/p_over_25:.2f}")
    g2.metric("Under 2.5 Goles", f"{p_under_25*100:.1f}%", f"Cuota Justa: {1/p_under_25:.2f}")

with tab3:
    b1, b2 = st.columns(2)
    b1.metric("Ambos Anotan: SÍ", f"{p_btts_si*100:.1f}%", f"Cuota Justa: {1/p_btts_si:.2f}")
    b2.metric("Ambos Anotan: NO", f"{(1-p_btts_si)*100:.1f}%", f"Cuota Justa: {1/(1-p_btts_si):.2f}")

with tab4:
    prompt_texto = f"""
Actúa como analista senior de apuestas. Revisa la recomendación del modelo para {df_partido['Local']} vs {df_partido['Visitante']}:
- Selección sugerida: {mejor_opcion['mercado']} (EV: {mejor_opcion['ev']*100:.2f}%)
- Probabilidad estimada: {mejor_opcion['prob']*100:.1f}% vs Cuota ofrecida: {mejor_opcion['cuota']}
¿Ves factores externos (alineaciones, clima, motivación) que aconsejen no tomar este veredicto numérico?
"""
    st.text_area("Copiar Prompt para Gemini:", value=prompt_texto, height=180)
