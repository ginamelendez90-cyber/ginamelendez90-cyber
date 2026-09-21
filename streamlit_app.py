import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="MLB Pro Sabermetrics Engine v2.0", layout="wide", page_icon="⚾")

st.title("🚀 Sistema Avanzado de Predicción Sabermétrica & Monte Carlo MLB")
st.markdown("---")

# --- TABLA ESTÁTICA DE PARK FACTORS (Factor > 1.0 favor Bateo | < 1.0 favor Pitcheo) ---
PARK_FACTORS = {
    "Coors Field": 1.15,
    "Fenway Park": 1.06,
    "Great American Ball Park": 1.05,
    "Yankee Stadium": 1.03,
    "Wrigley Field": 1.02,
    "Dodger Stadium": 1.00,
    "Busch Stadium": 0.97,
    "Petco Park": 0.94,
    "T-Mobile Park": 0.91,
    "Estadio Desconocido / Neutro": 1.00
}

# Ponderación de Apariciones al Bate (PA) según la posición en el Lineup (1º al 9º)
PA_LINEUP_WEIGHTS = {1: 4.6, 2: 4.5, 3: 4.4, 4: 4.3, 5: 4.2, 6: 4.1, 7: 4.0, 8: 3.9, 9: 3.8}

# --- BARRA LATERAL DE CONFIGURACIÓN ---
st.sidebar.header("⚙️ Panel de Control Sabermétrico")
fecha_seleccionada = st.sidebar.date_input("Fecha de Análisis:", datetime.today())
n_simulaciones = st.sidebar.slider("Simulaciones Monte Carlo:", min_value=1000, max_value=25000, value=10000, step=1000)
ajuste_fatiga_bp = st.sidebar.checkbox("Activar Penalización por Fatiga de Bullpen (>1.30 WHIP)", value=True)

# --- FUNCIONES AUXILIARES Y CÁLCULOS SABERMÉTRICOS ---
def parse_float(val, default=0.0):
    try:
        if val is None or val == '' or val == '-':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def calcular_fip(stats):
    """Calcula el Fielding Independent Pitching (FIP) a partir de las estadísticas acumuladas."""
    if not stats:
        return 4.20
    ip = parse_float(stats.get('inningsPitched'), 0.0)
    if ip <= 0:
        return parse_float(stats.get('era'), 4.20)
    
    hr = parse_float(stats.get('homeRuns'), 0)
    bb = parse_float(stats.get('baseOnBalls'), 0)
    hbp = parse_float(stats.get('hitByPitch'), 0)
    k = parse_float(stats.get('strikeOuts'), 0)
    
    fip_constant = 3.10  # Constante de ajuste promedio MLB
    fip = (((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / ip) + fip_constant
    return round(fip, 2)

def simular_monte_carlo(exp_away, exp_home, n_sims=10000):
    """Ejecuta una simulación Monte Carlo utilizando distribuciones de Poisson para cada equipo."""
    np.random.seed(42)
    carreras_away = np.random.poisson(max(0.5, exp_away), n_sims)
    carreras_home = np.random.poisson(max(0.5, exp_home), n_sims)
    
    wins_away = np.sum(carreras_away > carreras_home)
    wins_home = np.sum(carreras_home > carreras_away)
    empates = np.sum(carreras_away == carreras_home)
    
    # Repartición de extra-innings (50/50 para resolver empates)
    prob_away = ((wins_away + (empates * 0.5)) / n_sims) * 100
    prob_home = ((wins_home + (empates * 0.5)) / n_sims) * 100
    
    return prob_away, prob_home, np.mean(carreras_away), np.mean(carreras_home), np.mean(carreras_away + carreras_home)

# --- CACHÉ DE API MLB ---
@st.cache_data(ttl=120)
def obtener_calendario(fecha):
    return statsapi.schedule(date=fecha.strftime('%Y-%m-%d'))

@st.cache_data(ttl=120)
def obtener_feed_en_vivo(game_id):
    try:
        return statsapi.get('game', {'gamePk': game_id})
    except Exception:
        return {}

@st.cache_data(ttl=600)
def obtener_stats_jugador(player_id, group):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        if data and 'stats' in data and len(data['stats']) > 0:
            return data['stats'][0].get('stats', {})
        return {}
    except Exception:
        return {}

@st.cache_data(ttl=600)
def obtener_roster_estructurado(team_id):
    try:
        response = statsapi.get('team_roster', {'teamId': team_id})
        return response.get('roster', [])
    except Exception:
        return []

@st.cache_data(ttl=600)
def obtener_whip_bullpen(team_id):
    try:
        team_stats = statsapi.get('team_stats', {'teamId': team_id, 'statType': 'season', 'group': 'pitching'})
        for stat in team_stats.get('stats', []):
            if stat.get('type', {}).get('displayName') == 'season':
                splits = stat.get('splits', [{}])
                if splits:
                    return parse_float(splits[0].get('stat', {}).get('whip', 1.30), 1.30)
        return 1.30
    except Exception:
        return 1.30

# --- PROCESAMIENTO PRINCIPAL ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido para el Deep-Dive Analítico:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    away_id, home_id = juegos[idx_juego]['away_id'], juegos[idx_juego]['home_id']
    away_name, home_name = juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']
    
    feed = obtener_feed_en_vivo(game_id)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})
    
    probables = game_data.get('probablePitchers', {})
    away_pitcher, home_pitcher = probables.get('away', {}), probables.get('home', {})

    # Extracción de Métricas de Abridores
    stats_p_away = obtener_stats_jugador(away_pitcher.get('id'), 'pitching') if away_pitcher.get('id') else {}
    stats_p_home = obtener_stats_jugador(home_pitcher.get('id'), 'pitching') if home_pitcher.get('id') else {}
    
    fip_away = calcular_fip(stats_p_away)
    fip_home = calcular_fip(stats_p_home)
    
    whip_bp_away = obtener_whip_bullpen(away_id)
    whip_bp_home = obtener_whip_bullpen(home_id)

    # Detalle de Estadio y Park Factor
    venue_name = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
    park_factor = PARK_FACTORS.get(venue_name, 1.00)

    # TABS PRINCIPALES
    tab_montecarlo, tab_lineup, tab_vivo = st.tabs([
        "🎲 SIMULACIÓN MONTE CARLO", 
        "🧮 LOG-5 & PLATOON SPLITS", 
        "📈 TRANSMISIÓN EN VIVO"
    ])

    # --- TAB 1: MONTE CARLO & PROYECCIÓN ---
    with tab_montecarlo:
        st.header("🎰 Proyección del Partido y Simulación Estocástica")
        
        # Expectativa de Carreras Base (Ponderado por FIP del rival y Park Factor)
        # MLB promedio de carreras por equipo ≈ 4.5
        exp_runs_away = round((4.5 * (fip_home / 4.10)) * park_factor, 2)
        exp_runs_home = round((4.5 * (fip_away / 4.10)) * park_factor, 2)

        # Ajuste por fatiga/calidad de bullpen
        if ajuste_fatiga_bp:
            if whip_bp_home > 1.30: exp_runs_away += 0.25
            if whip_bp_away > 1.30: exp_runs_home += 0.25

        prob_away, prob_home, sim_carreras_away, sim_carreras_home, total_esperado = simular_monte_carlo(
            exp_runs_away, exp_runs_home, n_simulaciones
        )

        # Despliegue de Resultados
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(f"Prob. Victoria {away_name}", f"{prob_away:.1f}%", f"Proj: {sim_carreras_away:.2f} R")
        col_m2.metric(f"Prob. Victoria {home_name}", f"{prob_home:.1f}%", f"Proj: {sim_carreras_home:.2f} R")
        col_m3.metric("Línea Total de Carreras (Over/Under)", f"{total_esperado:.2f} Carreras", f"Park Factor: {park_factor}x")

        st.markdown("---")
        st.subheader("📊 Comparativo de Métricas del Pitcheo (ERA vs. FIP)")
        
        df_pitchers = pd.DataFrame([
            {
                "Equipo": away_name,
                "Abridor": away_pitcher.get('fullName', 'Por anunciar'),
                "ERA": stats_p_away.get('era', '-'),
                "FIP (Métrica Real)": fip_away,
                "WHIP Abridor": stats_p_away.get('whip', '-'),
                "WHIP Bullpen": whip_bp_away
            },
            {
                "Equipo": home_name,
                "Abridor": home_pitcher.get('fullName', 'Por anunciar'),
                "ERA": stats_p_home.get('era', '-'),
                "FIP (Métrica Real)": fip_home,
                "WHIP Abridor": stats_p_home.get('whip', '-'),
                "WHIP Bullpen": whip_bp_home
            }
        ])
        st.table(df_pitchers)

    # --- TAB 2: LOG-5 Y LINEUP SPLITS ---
    with tab_lineup:
        st.header("🧮 Algoritmo Log-5 con Platoon Splits y Ponderación por Posición")
        
        opcion_lineup = st.radio("Selecciona Ofensiva a Proyectar:", (f"Bateadores de {away_name}", f"Bateadores de {home_name}"))
        es_away = away_name in opcion_lineup
        
        id_equipo = away_id if es_away else home_id
        stats_pitcher_rival = stats_p_home if es_away else stats_p_away
        pitcher_hand = (game_data.get('players', {}).get(f"ID{home_pitcher.get('id') if es_away else away_pitcher.get('id')}", {})
                        .get('pitchHand', {}).get('code', 'R'))
        
        roster_json = obtener_roster_estructurado(id_equipo)
        baa_rival = parse_float(stats_pitcher_rival.get('avg'), 0.245)
        
        if roster_json:
            lista_predicciones = []
            slot = 1
            
            for jugador in roster_json:
                pid = jugador.get('person', {}).get('id')
                nombre = jugador.get('person', {}).get('fullName', 'Jugador')
                pos = jugador.get('position', {}).get('abbreviation', 'N/A')
                
                if pos != 'P':
                    b_stats = obtener_stats_jugador(pid, 'batting')
                    avg_b = parse_float(b_stats.get('avg'), 0.0)
                    
                    if avg_b > 0.0:
                        # Platoon Split Ajuste: Si el bateador enfrenta mano opuesta, recibe un bono +0.012 en AVG
                        # (Ajuste conceptual de split zurdo/diestro)
                        avg_b_split = avg_b + 0.012 if pitcher_hand == 'L' else avg_b
                        
                        # Cálculo Log-5 vs Abridor
                        num = (avg_b_split * baa_rival) / 0.245
                        den = num + ((1 - avg_b_split) * (1 - baa_rival) / (1 - 0.245))
                        prob_hit = num / den if den > 0 else 0.0
                        
                        # Ponderación por Turnos Esperados (PA Weight)
                        pa_esperadas = PA_LINEUP_WEIGHTS.get(slot, 3.8)
                        hits_esperados = prob_hit * pa_esperadas
                        
                        lista_predicciones.append({
                            "Lineup Spot": f"#{slot}" if slot <= 9 else "Banca",
                            "Bateador": nombre,
                            "Pos": pos,
                            "AVG Base": f".{int(round(avg_b * 1000)):03d}",
                            "Probabilidad Hit/PA": f"{prob_hit * 100:.2f}%",
                            "PA Proyectadas": pa_esperadas,
                            "Hits Esperados (xH)": round(hits_esperados, 2),
                            "Diagnóstico Pro": "🟢 Alta Ventaja" if prob_hit > 0.270 else "🟡 Neutro" if prob_hit > 0.240 else "🔴 Desventaja"
                        })
                        slot += 1
            
            if lista_predicciones:
                df_pred = pd.DataFrame(lista_predicciones)
                st.dataframe(df_pred, use_container_width=True, hide_index=True)
            else:
                st.info("No hay suficientes datos registrados de turnos al bate para este equipo.")

    # --- TAB 3: MONITOREO EN VIVO ---
    with tab_vivo:
        st.header("🏟️ Marcador en Tiempo Real")
        st.metric("Estado del Partido", juegos[idx_juego]['status'])
        
        linescore = live_data.get('linescore', {})
        entradas_lista = linescore.get('innings', [])
        
        if entradas_lista:
            tabla_innings = [
                {
                    "Inning": inn.get('num'),
                    f"{away_name} (Vis)": inn.get('away', {}).get('runs', '-'),
                    f"{home_name} (Loc)": inn.get('home', {}).get('runs', '-')
                }
                for inn in entradas_lista
            ]
            st.subheader("Tablero por Entradas (Linescore)")
            st.dataframe(pd.DataFrame(tabla_innings), use_container_width=True, hide_index=True)
            
            teams = linescore.get('teams', {})
            away_totals, home_totals = teams.get('away', {}), teams.get('home', {})
            
            c_tot1, c_tot2 = st.columns(2)
            c_tot1.metric(f"Total {away_name}", f"R: {away_totals.get('runs', 0)} | H: {away_totals.get('hits', 0)} | E: {away_totals.get('errors', 0)}")
            c_tot2.metric(f"Total {home_name}", f"R: {home_totals.get('runs', 0)} | H: {home_totals.get('hits', 0)} | E: {home_totals.get('errors', 0)}")
        else:
            st.info("El partido seleccionado aún no inicia o no hay datos registrados.")
