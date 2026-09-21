import streamlit as st
import pandas as pd
import numpy as np
import statsapi
import requests
import time
from datetime import datetime

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="MLB Pro Sabermetrics & Live Tracker", layout="wide", page_icon="⚾")

st.title("🚀 Sistema Avanzado Sabermétrico, Monte Carlo & Live Tracker MLB")
st.markdown("---")

# --- CONSTANTES Y FACTORES ---
PARK_FACTORS = {
    "Coors Field": 1.15, "Fenway Park": 1.06, "Great American Ball Park": 1.05,
    "Yankee Stadium": 1.03, "Wrigley Field": 1.02, "Dodger Stadium": 1.00,
    "Busch Stadium": 0.97, "Petco Park": 0.94, "T-Mobile Park": 0.91,
    "Estadio Desconocido / Neutro": 1.00
}
PA_LINEUP_WEIGHTS = {1: 4.6, 2: 4.5, 3: 4.4, 4: 4.3, 5: 4.2, 6: 4.1, 7: 4.0, 8: 3.9, 9: 3.8}
LEAGUE_K_RATE = 0.225

# --- PANEL LATERAL ---
st.sidebar.header("⚙️ Panel de Control Sabermétrico")
fecha_seleccionada = st.sidebar.date_input("Fecha de Análisis:", datetime.today())
n_simulaciones = st.sidebar.slider("Simulaciones Monte Carlo:", 1000, 25000, 10000, 1000)
ajuste_fatiga_bp = st.sidebar.checkbox("Penalización por Fatiga de Bullpen (>1.30 WHIP)", value=True)

st.sidebar.markdown("---")
auto_refresh = st.sidebar.toggle("Auto-refresh cada 10s", value=False)
odds_api_key = st.sidebar.text_input("The Odds API Key:", type="password")

# --- DIBUJO DEL CAMPO EN SVG CON BATEADOR ---
def parse_float(val, default=0.0):
    try:
        return float(val) if val not in [None, '', '-'] else default
    except (ValueError, TypeError):
        return default

def generar_campo_svg(offense_dict, batter_side='R'):
    """Genera un gráfico SVG del diamante con corredores y cajón de bateo iluminado"""
    c_1b = "#ECC94B" if offense_dict.get('first') else "#CBD5E0"
    c_2b = "#ECC94B" if offense_dict.get('second') else "#CBD5E0"
    c_3b = "#ECC94B" if offense_dict.get('third') else "#CBD5E0"
    
    # Ilumina el cajón activo (R: Lado 3B / L: Lado 1B)
    box_r_color = "#3182CE" if batter_side == 'R' else "#4A5568"
    box_l_color = "#3182CE" if batter_side == 'L' else "#4A5568"
    
    return f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 10px;">
        <svg width="280" height="250" viewBox="0 0 280 250" style="background-color: #1A202C; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <!-- Grama exterior -->
            <path d="M 140 220 L 240 120 A 140 140 0 0 0 40 120 Z" fill="#2F855A" stroke="#276749" stroke-width="3"/>
            <!-- Cuadro interior -->
            <polygon points="140,210 210,140 140,70 70,140" fill="#9C4221" stroke="#FFFFFF" stroke-width="1.5"/>
            <!-- Líneas de Cal -->
            <line x1="140" y1="210" x2="235" y2="115" stroke="#FFFFFF" stroke-width="2"/>
            <line x1="140" y1="210" x2="45" y2="115" stroke="#FFFFFF" stroke-width="2"/>
            <!-- Loma del Pitcher -->
            <circle cx="140" cy="140" r="10" fill="#C05621" stroke="#FFFFFF" stroke-width="1"/>
            <rect x="136" y="138" width="8" height="4" fill="#FFFFFF"/>
            <!-- Bases -->
            <rect x="203" y="133" width="14" height="14" transform="rotate(45 210 140)" fill="{c_1b}" stroke="#FFFFFF" stroke-width="2"/>
            <rect x="133" y="63" width="14" height="14" transform="rotate(45 140 70)" fill="{c_2b}" stroke="#FFFFFF" stroke-width="2"/>
            <rect x="63" y="133" width="14" height="14" transform="rotate(45 70 140)" fill="{c_3b}" stroke="#FFFFFF" stroke-width="2"/>
            <!-- Home Plate -->
            <polygon points="140,205 145,210 145,215 135,215 135,210" fill="#FFFFFF"/>
            
            <!-- Cajones de Bateo -->
            <!-- Derecha (R) -->
            <rect x="120" y="198" width="10" height="18" fill="{box_r_color}" stroke="#FFFFFF" stroke-width="1" rx="2"/>
            <!-- Izquierda (L) -->
            <rect x="150" y="198" width="10" height="18" fill="{box_l_color}" stroke="#FFFFFF" stroke-width="1" rx="2"/>
            
            <!-- Etiquetas -->
            <text x="228" y="145" fill="#FFFFFF" font-size="11" font-weight="bold">1B</text>
            <text x="140" y="55" fill="#FFFFFF" font-size="11" font-weight="bold" text-anchor="middle">2B</text>
            <text x="45" y="145" fill="#FFFFFF" font-size="11" font-weight="bold">3B</text>
            <text x="140" y="238" fill="#A0AEC0" font-size="10" text-anchor="middle">Lado Bateador: {batter_side}</text>
        </svg>
    </div>
    """

def calcular_fip(stats):
    if not stats: return 4.20
    ip = parse_float(stats.get('inningsPitched'), 0.0)
    if ip <= 0: return parse_float(stats.get('era'), 4.20)
    hr, bb, hbp, k = parse_float(stats.get('homeRuns')), parse_float(stats.get('baseOnBalls')), parse_float(stats.get('hitByPitch')), parse_float(stats.get('strikeOuts'))
    return round((((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / ip) + 3.10, 2)

def calcular_xk_pitcher(stats_pitcher, team_k_rate=0.225, projected_bf=22):
    if not stats_pitcher: return 4.5, 22.5
    k, bf = parse_float(stats_pitcher.get('strikeOuts')), parse_float(stats_pitcher.get('battersFaced'))
    k_rate_p = (k / bf) if bf > 0 else (parse_float(stats_pitcher.get('strikeOutsPer9Innings'), 8.5) / 9.0) / 4.0
    num = (k_rate_p * team_k_rate) / LEAGUE_K_RATE
    den = num + ((1 - k_rate_p) * (1 - team_k_rate) / (1 - LEAGUE_K_RATE))
    k_rate_proj = num / den if den > 0 else LEAGUE_K_RATE
    return round(projected_bf * k_rate_proj, 1), round(k_rate_proj * 100, 1)

def simular_monte_carlo(exp_away, exp_home, n_sims=10000):
    np.random.seed(42)
    c_away, c_home = np.random.poisson(max(0.5, exp_away), n_sims), np.random.poisson(max(0.5, exp_home), n_sims)
    w_away, w_home, emp = np.sum(c_away > c_home), np.sum(c_home > c_away), np.sum(c_away == c_home)
    return ((w_away + emp*0.5)/n_sims)*100, ((w_home + emp*0.5)/n_sims)*100, np.mean(c_away), np.mean(c_home), np.mean(c_away + c_home)

# --- APIS ---
@st.cache_data(ttl=120)
def obtener_calendario(fecha): return statsapi.schedule(date=fecha.strftime('%Y-%m-%d'))

@st.cache_data(ttl=10)
def obtener_feed_en_vivo(game_id): return statsapi.get('game', {'gamePk': game_id})

@st.cache_data(ttl=600)
def obtener_stats_jugador(player_id, group):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        return data['stats'][0].get('stats', {}) if data and 'stats' in data and len(data['stats']) > 0 else {}
    except Exception: return {}

@st.cache_data(ttl=600)
def obtener_roster_estructurado(team_id): return statsapi.get('team_roster', {'teamId': team_id}).get('roster', [])

@st.cache_data(ttl=600)
def obtener_whip_bullpen(team_id):
    try:
        splits = statsapi.get('team_stats', {'teamId': team_id, 'statType': 'season', 'group': 'pitching'}).get('stats', [{}])[0].get('splits', [{}])
        return parse_float(splits[0].get('stat', {}).get('whip', 1.30), 1.30)
    except Exception: return 1.30

# --- LÓGICA PRINCIPAL ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    away_id, home_id = juegos[idx_juego]['away_id'], juegos[idx_juego]['home_id']
    away_name, home_name = juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']
    
    feed = obtener_feed_en_vivo(game_id)
    game_data, live_data = feed.get('gameData', {}), feed.get('liveData', {})
    probables = game_data.get('probablePitchers', {})
    away_pitcher, home_pitcher = probables.get('away', {}), probables.get('home', {})

    stats_p_away = obtener_stats_jugador(away_pitcher.get('id'), 'pitching') if away_pitcher.get('id') else {}
    stats_p_home = obtener_stats_jugador(home_pitcher.get('id'), 'pitching') if home_pitcher.get('id') else {}
    
    fip_away, fip_home = calcular_fip(stats_p_away), calcular_fip(stats_p_home)
    xk_away_pitcher, k_pct_away = calcular_xk_pitcher(stats_p_away)
    xk_home_pitcher, k_pct_home = calcular_xk_pitcher(stats_p_home)
    whip_bp_away, whip_bp_home = obtener_whip_bullpen(away_id), obtener_whip_bullpen(home_id)
    park_factor = PARK_FACTORS.get(game_data.get('venue', {}).get('name', ''), 1.00)

    tab_montecarlo, tab_lineup, tab_ev, tab_vivo = st.tabs([
        "🎲 SIMULACIÓN MONTE CARLO", "🧮 LOG-5 & PLATOON SPLITS", "💰 DETECTOR +EV", "📈 TRANSMISIÓN EN VIVO"
    ])

    exp_runs_away = round((4.5 * (fip_home / 4.10)) * park_factor, 2)
    exp_runs_home = round((4.5 * (fip_away / 4.10)) * park_factor, 2)
    if ajuste_fatiga_bp:
        if whip_bp_home > 1.30: exp_runs_away += 0.25
        if whip_bp_away > 1.30: exp_runs_home += 0.25

    prob_away, prob_home, sim_away, sim_home, total_esperado = simular_monte_carlo(exp_runs_away, exp_runs_home, n_simulaciones)

    with tab_montecarlo:
        st.header("🎰 Proyección y Simulación Monte Carlo")
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Victoria {away_name}", f"{prob_away:.1f}%", f"Proj: {sim_away:.2f} R")
        c2.metric(f"Victoria {home_name}", f"{prob_home:.1f}%", f"Proj: {sim_home:.2f} R")
        c3.metric("Línea Total", f"{total_esperado:.2f} R", f"PF: {park_factor}x")

    with tab_vivo:
        st.header("🏟️ Transmisión y Monitor con Posición del Bateador")
        linescore, plays = live_data.get('linescore', {}), live_data.get('plays', {})
        current_play = plays.get('currentPlay', {})
        offense = linescore.get('offense', {})
        matchup = current_play.get('matchup', {}) if current_play else {}
        
        batter_side = matchup.get('batSide', {}).get('code', 'R')
        batter_name = matchup.get('batter', {}).get('fullName', 'En espera')
        batter_id = matchup.get('batter', {}).get('id')
        
        col_campo, col_datos = st.columns([1, 2])
        
        with col_campo:
            # Muestra el SVG con el cajón de bateo iluminado en azul
            st.markdown(generar_campo_svg(offense, batter_side), unsafe_allow_html=True)
            
        with col_datos:
            if current_play:
                count = current_play.get('count', {})
                pitcher_name = matchup.get('pitcher', {}).get('fullName', 'En espera')
                pitcher_hand = matchup.get('pitchHand', {}).get('code', '-')
                
                # Cargar stats del bateador actual
                b_stats = obtener_stats_jugador(batter_id, 'batting') if batter_id else {}
                avg_b = b_stats.get('avg', '.000')
                hr_b = b_stats.get('homeRuns', '0')
                rbi_b = b_stats.get('rbi', '0')
                ops_b = b_stats.get('ops', '.000')

                st.markdown(f"### ⚡ Bateador en Turno: **{batter_name}**")
                st.caption(f"Lado al bate: **{'Derecho' if batter_side=='R' else 'Zurdo'}** | AVG: **{avg_b}** | HR: **{hr_b}** | RBI: **{rbi_b}** | OPS: **{ops_b}**")
                
                st.markdown("---")
                c_d1, c_d2 = st.columns(2)
                c_d1.metric("Pitcher en la Loma", pitcher_name, f"Mano: {pitcher_hand}")
                c_d2.metric("Conteo y Outs", f"⚽ {count.get('balls',0)}-{count.get('strikes',0)} | 🛑 {count.get('outs',0)} Outs")

if auto_refresh:
    time.sleep(10)
    st.rerun()
