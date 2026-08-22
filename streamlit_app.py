import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests

# Configuración de página
st.set_page_config(page_title="Analizador Algorítmico de Fútbol", page_icon="⚽", layout="wide")

# -----------------------------------------------------------------------------
# 1. ESTADO Y CONEXIÓN REAL A FOOTBALL-DATA.ORG
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
    """
    Conecta con la API de football-data.org para obtener los próximos partidos programados.
    Códigos de ligas populares:
    - PD: La Liga (España)
    - PL: Premier League (Inglaterra)
    - SA: Serie A (Italia)
    - BL1: Bundesliga (Alemania)
    - FL1: Ligue 1 (Francia)
    - CL: Champions League
    """
    if not api_key:
        st.error("Por favor, ingresa tu API Key de football-data.org en la barra lateral.")
        return st.session_state.datos_cargados

    headers = {'X-Auth-Token': api_key}
    url_partidos = f"https://api.football-data.org/v4/competitions/{liga_code}/matches?status=SCHEDULED"
    url_tabla = f"https://api.football-data.org/v4/competitions/{liga_code}/standings"

    try:
        # 1. Obtener tabla de posiciones para calcular estadísticas de goles por equipo
        res_tabla = requests.get(url_tabla, headers=headers)
        stats_equipos = {}
        
        if res_tabla.status_code == 200:
            tabla_data = res_tabla.json()
            if 'standings' in tabla_data and len(tabla_data['standings']) > 0:
                for fila in tabla_data['standings'][0]['table']:
                    nombre = fila['team']['name']
                    partidos_jugados = fila['playedGames'] if fila['playedGames'] > 0 else 1
                    gf_promedio = fila['goalsFor'] / partidos_jugados
                    ga_promedio = fila['goalsAgainst'] / partidos_jugados
                    stats_equipos[nombre] = {'gf': gf_promedio, 'ga': ga_promedio}
        
        # 2. Obtener próximos partidos
        res_partidos = requests.get(url_partidos, headers=headers)
        
        if res_partidos.status_code != 200:
            error_msg = res_partidos.json().get('message', 'Error al conectar con la API.')
            st.error(f"Error API ({res_partidos.status_code}): {error_msg}")
            return st.session_state.datos_cargados

        data_partidos = res_partidos.json()
        partidos = data_partidos.get('matches', [])

        if not partidos:
            st.warning(f"No se encontraron partidos próximos programados para la liga seleccionada ({liga_code}).")
            return st.session_state.datos_cargados

        filas_procesadas = []
        for p in partidos[:15]:  # Procesar los primeros 15 partidos
            local = p['homeTeam']['name']
            visitante = p['awayTeam']['name']

            # Recuperar métricas calculadas de la tabla
            stat_loc = stats_equipos.get(local, {'gf': 1.5, 'ga': 1.0})
            stat_vis = stats_equipos.get(visitante, {'gf': 1.2, 'ga': 1.2})

            # Generar métricas ajustadas
            xg_loc = round(stat_loc['gf'], 2)
            xg_vis = round(stat_vis['gf'], 2)

            filas_procesadas.append({
                "Partido": f"{local} vs {visitante}",
                "Local": local,
                "Visitante": visitante,
                "xG_Local": xg_loc if xg_loc > 0 else 1.4,
                "Goles_Local": xg_loc if xg_loc > 0 else 1.4,
                "Tiros_Puerta_Local": round(xg_loc * 3.2, 1),
                "xG_Vis": xg_vis if xg_vis > 0 else 1.1,
                "Goles_Vis": xg_vis if xg_vis > 0 else 1.1,
                "Tiros_Puerta_Vis": round(xg_vis * 3.2, 1),
                "Factor_Localia": 1.10
            })

        df_resultado = pd.DataFrame(filas_procesadas)
        st.success(f"¡Se obtuvieron {len(df_resultado)} partidos próximos de football-data.org!")
        return df_resultado

    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return st.session_state.datos_cargados

# -----------------------------------------------------------------------------
# 2. MOTOR MATEMÁTICO (POISSON)
# -----------------------------------------------------------------------------
def calcular_lambda(xg, goles, tiros, factor_localia=1.0):
    expectativa_base = (xg * 0.50) + (goles * 0.35) + (tiros * 0.05)
    return expectativa_base * factor_localia

def generar_matriz_poisson(lambda_local, lambda_visitante, max_goles=7):
    prob_local = [poisson.pmf(i, lambda_local) for i in range(max_goles)]
    prob_vis = [poisson.pmf(i, lambda_visitante) for i in range(max_goles)]
    return np.outer(prob_local, prob_vis)

# -----------------------------------------------------------------------------
# 3. INTERFAZ GRÁFICA
# -----------------------------------------------------------------------------
st.title("⚽ Analizador Estadístico de Apuestas de Fútbol")

# Barra Lateral: Configuración de API
with st.sidebar:
    st.header("🔑 Configuración API Football-Data")
    api_key = st.text_input("Ingresa tu Token de football-data.org:", type="password")
    
    liga_seleccionada = st.selectbox(
        "Selecciona la Liga:",
        options=["PD", "PL", "SA", "BL1", "FL1", "CL"],
        format_func=lambda x: {
            "PD": "La Liga (España)",
            "PL": "Premier League (Inglaterra)",
            "SA": "Serie A (Italia)",
            "BL1": "Bundesliga (Alemania)",
            "FL1": "Ligue 1 (Francia)",
            "CL": "Champions League"
        }[x]
    )
    
    if st.button("Obtener Próximos Partidos"):
        if api_key:
            st.session_state.datos_cargados = obtener_datos_football_data(api_key, liga_seleccionada)
        else:
            st.warning("Escribe tu API Key antes de hacer clic.")

    st.markdown("---")
    st.header("🎯 Selección de Partido")
    partidos_disponibles = st.session_state.datos_cargados["Partido"].tolist()
    partido_elegido = st.selectbox("Elige un encuentro cargado:", partidos_disponibles)
    
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

# Probabilidades Mercado Goles Totales
goles_matriz = np.add.outer(np.arange(matriz.shape[0]), np.arange(matriz.shape[1]))
p_under_15 = np.sum(matriz[goles_matriz <= 1])
p_over_15 = 1 - p_under_15
p_under_25 = np.sum(matriz[goles_matriz <= 2])
p_over_25 = 1 - p_under_25
p_under_35 = np.sum(matriz[goles_matriz <= 3])
p_over_35 = 1 - p_under_35

# Mercado Both Teams To Score (BTTS)
p_btts_si = 1 - (np.sum(matriz[0, :]) + np.sum(matriz[:, 0]) - matriz[0, 0])
p_btts_no = 1 - p_btts_si

# --- VISUALIZACIÓN ---
st.subheader(f"📊 Análisis: {df_partido['Local']} vs {df_partido['Visitante']}")
col_a, col_b, col_c = st.columns(3)
col_a.metric(f"Promedio Gol/xG {df_partido['Local']}", f"{df_partido['xG_Local']}")
col_b.metric(f"Promedio Gol/xG {df_partido['Visitante']}", f"{df_partido['xG_Vis']}")
col_c.metric("Factor Localía Aplicado", f"+{int((df_partido['Factor_Localia']-1)*100)}%")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["🏆 Mercado 1X2", "⚽ Goles (Over/Under)", "🥊 Ambos Anotan (BTTS)", "🤖 Prompt para Gemini"])

with tab1:
    st.subheader("Predicción 1X2 y Calculadora de EV")
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Gana {df_partido['Local']}", f"{p_local*100:.1f}%", help=f"Cuota Justa: {round(1/p_local, 2)}")
    c2.metric("Empate", f"{p_empate*100:.1f}%", help=f"Cuota Justa: {round(1/p_empate, 2)}")
    c3.metric(f"Gana {df_partido['Visitante']}", f"{p_vis*100:.1f}%", help=f"Cuota Justa: {round(1/p_vis, 2)}")
    
    st.markdown("#### Calculadora de Valor Esperado (EV)")
    col_ev1, col_ev2 = st.columns(2)
    opcion_apuesta = col_ev1.selectbox("Opción a evaluar:", [df_partido['Local'], "Empate", df_partido['Visitante']])
    cuota_casa = col_ev2.number_input("Cuota de la Casa de Apuestas:", min_value=1.01, value=2.00, step=0.05)
    
    prob_map = {df_partido['Local']: p_local, "Empate": p_empate, df_partido['Visitante']: p_vis}
    prob_elegida = prob_map[opcion_apuesta]
    ev = (prob_elegida * cuota_casa) - 1
    
    if ev > 0:
        st.success(f"**¡Apuesta de Valor (EV Positivo)!** Ventaja estadística: **+{ev*100:.2f}%**")
    else:
        st.error(f"**Sin Valor (EV Negativo):** Ventaja de la casa: **{ev*100:.2f}%**")

with tab2:
    st.subheader("Mercado de Total de Goles")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.markdown("**Línea 1.5 Goles**")
        st.write(f"Over 1.5: **{p_over_15*100:.1f}%**")
        st.write(f"Under 1.5: **{p_under_15*100:.1f}%**")
    with g2:
        st.markdown("**Línea 2.5 Goles**")
        st.write(f"Over 2.5: **{p_over_25*100:.1f}%**")
        st.write(f"Under 2.5: **{p_under_25*100:.1f}%**")
    with g3:
        st.markdown("**Línea 3.5 Goles**")
        st.write(f"Over 3.5: **{p_over_35*100:.1f}%**")
        st.write(f"Under 3.5: **{p_under_35*100:.1f}%**")

with tab3:
    st.subheader("Ambos Equipos Anotan")
    b1, b2 = st.columns(2)
    b1.metric("Ambos Anotan: SÍ", f"{p_btts_si*100:.1f}%", help=f"Cuota Justa: {round(1/p_btts_si, 2)}")
    b2.metric("Ambos Anotan: NO", f"{p_btts_no*100:.1f}%", help=f"Cuota Justa: {round(1/p_btts_no, 2)}")

with tab4:
    st.subheader("Prompt de Análisis para Gemini")
    prompt_texto = f"""
Actúa como un analista profesional de fútbol. Analiza el siguiente partido cargado mediante API:
Partido: {df_partido['Local']} vs {df_partido['Visitante']}
- Probabilidades Poisson 1X2: Local ({p_local*100:.1f}%), Empate ({p_empate*100:.1f}%), Visitante ({p_vis*100:.1f}%)
- Mercado Over/Under 2.5: Over 2.5 ({p_over_25*100:.1f}%), Under 2.5 ({p_under_25*100:.1f}%)
- Ambos Anotan: Sí ({p_btts_si*100:.1f}%)
¿Qué variables cualitativas (lesiones, calendario, clima) pueden alterar este modelo?
"""
    st.text_area("Prompt listo para copiar:", value=prompt_texto, height=200)
