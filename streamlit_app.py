import streamlit as st
import statsapi
import pandas as pd
import numpy as np
from scipy.stats import binom, poisson
from datetime import datetime

st.set_page_config(page_title="Radar Player Props MLB", layout="wide")

# Promedios de referencia de la MLB
BA_LIGA = 0.243
K_RATE_LIGA = 0.225

@st.cache_data(ttl=3600)
def obtener_equipos():
    teams = statsapi.get('teams', {'sportId': 1})['teams']
    return {t['name']: t['id'] for t in teams}

@st.cache_data(ttl=3600)
def obtener_roster(team_id):
    roster = statsapi.roster(team_id)
    # Extraer pares (ID, Nombre)
    lineas = roster.split('\n')
    jugadores = []
    for linea in lineas:
        if linea.strip():
            partes = linea.split()
            player_id = partes[0]
            nombre = " ".join(partes[1:])
            jugadores.append({'id': player_id, 'nombre': nombre})
    return pd.DataFrame(jugadores)

@st.cache_data(ttl=3600)
def obtener_stats_jugador(player_id, group):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        stats = data.get('stats', [])
        if stats:
            return stats[0]['stats']
    except Exception:
        pass
    return None

# --- INTERFAZ DE STREAMLIT ---
st.title("🎯 Radar de Jugadores: Hits & Ponches (Player Props)")
st.markdown("Herramienta analítica para proyección de líneas individuales mediante probabilidades ajustadas.")

equipos_dict = obtener_equipos()
tab1, tab2 = st.tabs(["⚾ Proyección de Hits (Bateadores)", "🔥 Proyección de Ponches (Lanzadores)"])

# ---------------------------------------------------------
# TAB 1: PROYECTAR HITS
# ---------------------------------------------------------
with tab1:
    st.subheader("Análisis de Hit para Bateador")
    col1, col2 = st.columns(2)
    
    with col1:
        equipo_bat = st.selectbox("Equipo Bateador", list(equipos_dict.keys()), key="bat_team")
        roster_bat = obtener_roster(equipos_dict[equipo_bat])
        bateador_sel = st.selectbox("Seleccionar Bateador", roster_bat['nombre'].tolist())
        id_bateador = roster_bat[roster_bat['nombre'] == bateador_sel]['id'].values[0]
        
        orden_al_bate = st.slider("Posición en el Lineup", 1, 9, 3)
        # Asignación de AB esperados
        ab_esperados = 4.2 if orden_al_bate <= 3 else (3.9 if orden_al_bate <= 6 else 3.5)

    with col2:
        equipo_pit = st.selectbox("Equipo Rival (Lanzador)", list(equipos_dict.keys()), key="pit_team_1")
        roster_pit = obtener_roster(equipos_dict[equipo_pit])
        lanzador_sel = st.selectbox("Lanzador Abridor Rival", roster_pit['nombre'].tolist(), key="pitcher_1")
        id_lanzador = roster_pit[roster_pit['nombre'] == lanzador_sel]['id'].values[0]

    if st.button("📊 Analizar Probabilidad de Hit"):
        stats_bat = obtener_stats_jugador(id_bateador, group="hitting")
        stats_pit = obtener_stats_jugador(id_lanzador, group="pitching")
        
        if stats_bat and stats_pit:
            ba_bateador = float(stats_bat.get('avg', BA_LIGA))
            baa_lanzador = float(stats_pit.get('avg', BA_LIGA))
            
            # Ajuste p_adj
            p_adj = (ba_bateador * baa_lanzador) / BA_LIGA
            p_adj = min(max(p_adj, 0.05), 0.60) # Límites lógicos
            
            # Probabilidad de al menos 1 hit
            prob_1plus_hit = 1 - binom.pmf(0, n=int(np.round(ab_esperados)), p=p_adj)
            fair_odd_hit = 1 / prob_1plus_hit if prob_1plus_hit > 0 else 0
            
            # Mostrar métricas
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("AVG Bateador", f"{ba_bateador:.3f}")
            m2.metric("BAA Lanzador Rival", f"{baa_lanzador:.3f}")
            m3.metric("Probabilidad ≥ 1 Hit", f"{prob_1plus_hit * 100:.1f}%")
            m4.metric("Fair Odd (Cuota Justa)", f"{fair_odd_hit:.2f}")
            
            st.info(f"💡 **Criterio de Apuesta**: Si la casa de apuestas paga el Over 0.5 Hits a una cuota mayor a **{fair_odd_hit:.2f}**, la apuesta tiene **Valor Positivo (+EV)**.")
        else:
            st.warning("No se encontraron suficientes estadísticas de la temporada para estos jugadores.")

# ---------------------------------------------------------
# TAB 2: PROYECTAR PONCHES (STRIKEOUTS)
# ---------------------------------------------------------
with tab2:
    st.subheader("Análisis de Ponches para Lanzadores (Over/Under K's)")
    col1_k, col2_k = st.columns(2)
    
    with col1_k:
        equipo_pitcher = st.selectbox("Equipo del Lanzador", list(equipos_dict.keys()), key="pit_team_2")
        roster_p = obtener_roster(equipos_dict[equipo_pitcher])
        pitcher_k_sel = st.selectbox("Lanzador Abridor", roster_p['nombre'].tolist(), key="pitcher_2")
        id_pitcher_k = roster_p[roster_p['nombre'] == pitcher_k_sel]['id'].values[0]
        
        ip_esperados = st.slider("Innings Proyectados (IP)", 3.0, 8.0, 5.2, step=0.1)

    with col2_k:
        equipo_rival_k = st.selectbox("Equipo Rival (Ofensiva)", list(equipos_dict.keys()), key="bat_team_2")
        k_linea_casas = st.number_input("Línea de la Casa de Apuestas (ej. 5.5)", value=5.5, step=0.5)

    if st.button("🔥 Analizar Línea de Ponches"):
        stats_p = obtener_stats_jugador(id_pitcher_k, group="pitching")
        
        if stats_p:
            so = float(stats_p.get('strikeOuts', 0))
            ip = float(stats_p.get('inningsPitched', 1.0))
            k_per_ip = so / ip if ip > 0 else 1.0
            
            # Estimación de Ponches Esperados (Lambda)
            lambda_k = k_per_ip * ip_esperados
            
            # Probabilidades Over / Under
            k_corte = int(np.floor(k_linea_casas))
            prob_under = poisson.cdf(k_corte, lambda_k)
            prob_over = 1 - prob_under
            
            fair_odd_over = 1 / prob_over if prob_over > 0 else 0
            fair_odd_under = 1 / prob_under if prob_under > 0 else 0
            
            # Métricas
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("K/IP del Lanzador", f"{k_per_ip:.2f}")
            c2.metric("Ponches Proyectados (xK)", f"{lambda_k:.2f}")
            c3.metric(f"Prob. Over {k_linea_casas}", f"{prob_over * 100:.1f}%")
            c4.metric("Fair Odd Over", f"{fair_odd_over:.2f}")
            
            st.markdown("---")
            col_o, col_u = st.columns(2)
            with col_o:
                st.success(f"**Línea OVER {k_linea_casas}** | Probabilidad: {prob_over*100:.1f}% | Cuota Mínima rentable: **{fair_odd_over:.2f}**")
            with col_u:
                st.error(f"**Línea UNDER {k_linea_casas}** | Probabilidad: {prob_under*100:.1f}% | Cuota Mínima rentable: **{fair_odd_under:.2f}**")
        else:
            st.warning("No se encontraron datos de pitcheo para este jugador.")
