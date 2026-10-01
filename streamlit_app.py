import streamlit as st
import pandas as pd
import numpy as np
import statsapi
import requests
import time
from datetime import datetime

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(
    page_title="MLB Pro Sabermetrics & Live Tracker",
    layout="wide",
    page_icon="⚾",
    initial_sidebar_state="expanded"
)

# --- CSS INYECTADO: INTERFAZ MÁS MODERNA (DARK GLASSMORPHISM) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Fondo Principal */
    .stApp {
        background-color: #0B0F17;
        color: #F1F5F9;
    }

    /* Ocultar elementos sobrantes de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Panel Lateral (Sidebar) */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1E293B;
    }

    /* Tarjetas KPI Glassmorphism */
    .kpi-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .kpi-card:hover {
        border-color: rgba(56, 189, 248, 0.4);
        transform: translateY(-2px);
    }

    .kpi-title {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #94A3B8;
        font-weight: 700;
        margin-bottom: 6px;
    }

    .kpi-value {
        font-size: 2.1rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1.1;
    }

    .kpi-sub {
        font-size: 0.82rem;
        color: #38BDF8;
        font-weight: 600;
        margin-top: 8px;
    }

    /* Pestañas Estilizadas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #111827;
        padding: 8px;
        border-radius: 14px;
        border: 1px solid #1E293B;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 20px;
        color: #94A3B8;
        font-weight: 600;
        border: none !important;
        transition: all 0.2s ease;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }

    /* Badges de Estado */
    .badge-status {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    .badge-live { background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #EF4444; }
    .badge-final { background: rgba(100, 116, 139, 0.2); color: #94A3B8; border: 1px solid #64748B; }
    .badge-scheduled { background: rgba(56, 189, 248, 0.2); color: #38BDF8; border: 1px solid #38BDF8; }

    /* Encabezado Principal */
    .header-container {
        padding: 15px 0 25px 0;
        border-bottom: 1px solid #1E293B;
        margin-bottom: 25px;
    }
    
    .header-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFFFF 0%, #94A3B8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER PRINCIPAL ---
st.markdown("""
<div class="header-container">
    <div class="header-title">⚡ MLB Sabermetrics & Live Intelligence</div>
    <div style="color: #64748B; font-size: 0.95rem; margin-top: 4px;">Sistema Proyectivo Monte Carlo, Algoritmos Log-5 y Rastreador de Apuestas +EV</div>
</div>
""", unsafe_allow_html=True)

# --- CONSTANTES ---
PARK_FACTORS = {
    "Coors Field": 1.15, "Fenway Park": 1.06, "Great American Ball Park": 1.05,
    "Yankee Stadium": 1.03, "Wrigley Field": 1.02, "Dodger Stadium": 1.00,
    "Busch Stadium": 0.97, "Petco Park": 0.94, "T-Mobile Park": 0.91,
    "Estadio Desconocido / Neutro": 1.00
}

PA_LINEUP_WEIGHTS = {1: 4.6, 2: 4.5, 3: 4.4, 4: 4.3, 5: 4.2, 6: 4.1, 7: 4.0, 8: 3.9, 9: 3.8}
LEAGUE_K_RATE = 0.225

# --- BARRA LATERAL ---
st.sidebar.markdown("<h3 style='color: #F8FAFC; font-size: 1.1rem;'>⚙️ Panel de Control</h3>", unsafe_allow_html=True)
fecha_seleccionada = st.sidebar.date_input("Fecha de Análisis:", datetime.today())
n_simulaciones = st.sidebar.slider("Simulaciones Monte Carlo:", 1000, 25000, 10000, step=1000)
ajuste_fatiga_bp = st.sidebar.checkbox("Penalizar Bullpen Cansado (>1.30 WHIP)", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("<h3 style='color: #F8FAFC; font-size: 1.1rem;'>🔄 Live Sync</h3>", unsafe_allow_html=True)
auto_refresh = st.sidebar.toggle("Auto-refresh (10s)", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("<h3 style='color: #F8FAFC; font-size: 1.1rem;'>🔑 Odds API</h3>", unsafe_allow_html=True)
odds_api_key = st.sidebar.text_input("API Key:", type="password")


# --- FUNCIONES CORE Y DIBUJO DE CAMPO NEÓN SVG ---
def parse_float(val, default=0.0):
    try:
        if val is None or val == '' or val == '-': return default
        return float(val)
    except (ValueError, TypeError):
        return default

def parse_ip(ip_val):
    val = parse_float(ip_val, 0.0)
    entero = int(val)
    decimal = round((val - entero) * 10)
    return entero + (decimal / 3.0)

def render_kpi_card(title, value, subtext):
    return f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{subtext}</div>
    </div>
    """

def generar_campo_svg_moderno(offense_dict):
    """Genera un diamante estilizado Cyber-Neon con filtros de brillo"""
    c_1b = "#00E676" if offense_dict.get('first') else "#334155"
    c_2b = "#00E676" if offense_dict.get('second') else "#334155"
    c_3b = "#00E676" if offense_dict.get('third') else "#334155"
    
    glow_1b = 'filter="url(#glow)"' if offense_dict.get('first') else ''
    glow_2b = 'filter="url(#glow)"' if offense_dict.get('second') else ''
    glow_3b = 'filter="url(#glow)"' if offense_dict.get('third') else ''
    
    svg = f"""
    <div style="display: flex; justify-content: center; padding: 10px;">
        <svg width="270" height="250" viewBox="0 0 260 240" style="background: #0F172A; border-radius: 16px; border: 1px solid #1E293B; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            <defs>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <linearGradient id="grassGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#064E3B" />
                    <stop offset="100%" stop-color="#022C22" />
                </linearGradient>
            </defs>
            
            <!-- Campo Exterior -->
            <path d="M 130 210 L 230 110 A 130 130 0 0 0 30 110 Z" fill="url(#grassGrad)" stroke="#059669" stroke-width="2"/>
            
            <!-- Cuadro Interior -->
            <polygon points="130,200 200,130 130,60 60,130" fill="#78350F" stroke="#9A3412" stroke-width="1.5" opacity="0.8"/>
            <line x1="130" y1="200" x2="225" y2="105" stroke="#F8FAFC" stroke-width="1.5" stroke-dasharray="3,3"/>
            <line x1="130" y1="200" x2="35" y2="105" stroke="#F8FAFC" stroke-width="1.5" stroke-dasharray="3,3"/>
            
            <!-- Loma Lanzador -->
            <circle cx="130" cy="130" r="9" fill="#9A3412"/>
            <rect x="126" y="128" width="8" height="4" fill="#FFFFFF"/>
            
            <!-- Bases (1B, 2B, 3B) -->
            <rect x="193" y="123" width="14" height="14" transform="rotate(45 200 130)" fill="{c_1b}" stroke="#FFFFFF" stroke-width="1.5" {glow_1b}/>
            <rect x="123" y="53" width="14" height="14" transform="rotate(45 130 60)" fill="{c_2b}" stroke="#FFFFFF" stroke-width="1.5" {glow_2b}/>
            <rect x="53" y="123" width="14" height="14" transform="rotate(45 60 130)" fill="{c_3b}" stroke="#FFFFFF" stroke-width="1.5" {glow_3b}/>
            
            <!-- Home Plate -->
            <polygon points="130,195 135,200 135,205 125,205 125,200" fill="#FFFFFF"/>
            
            <!-- Etiquetas -->
            <text x="220" y="134" fill="#94A3B8" font-size="10" font-weight="700">1B</text>
            <text x="130" y="42" fill="#94A3B8" font-size="10" font-weight="700" text-anchor="middle">2B</text>
            <text x="32" y="134" fill="#94A3B8" font-size="10" font-weight="700">3B</text>
        </svg>
    </div>
    """
    return svg

def calcular_fip(stats):
    if not stats: return 4.20
    ip = parse_ip(stats.get('inningsPitched', 0.0))
    if ip <= 0: return parse_float(stats.get('era'), 4.20)
    
    hr, bb, hbp, k = [parse_float(stats.get(x), 0) for x in ['homeRuns', 'baseOnBalls', 'hitByPitch', 'strikeOuts']]
    return round((((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / ip) + 3.10, 2)

def calcular_xk_pitcher(stats_pitcher, team_k_rate=0.225, projected_bf=22):
    if not stats_pitcher: return 4.5, 22.5
    k = parse_float(stats_pitcher.get('strikeOuts'), 0)
    bf = parse_float(stats_pitcher.get('battersFaced'), 0)
    k_rate_pitcher = (k / bf) if bf > 0 else 0.225

    num = (k_rate_pitcher * team_k_rate) / LEAGUE_K_RATE
    den = num + ((1 - k_rate_pitcher) * (1 - team_k_rate) / (1 - LEAGUE_K_RATE))
    k_rate_proj = num / den if den > 0 else LEAGUE_K_RATE
    return round(projected_bf * k_rate_proj, 1), round(k_rate_proj * 100, 1)

def simular_monte_carlo(exp_away, exp_home, n_sims=10000):
    np.random.seed(42)
    carreras_away = np.random.poisson(max(0.5, exp_away), n_sims)
    carreras_home = np.random.poisson(max(0.5, exp_home), n_sims)
    
    wins_away = np.sum(carreras_away > carreras_home)
    wins_home = np.sum(carreras_home > carreras_away)
    empates = np.sum(carreras_away == carreras_home)
    
    prob_away = ((wins_away + (empates * 0.5)) / n_sims) * 100
    prob_home = ((wins_home + (empates * 0.5)) / n_sims) * 100
    return prob_away, prob_home, np.mean(carreras_away), np.mean(carreras_home), np.mean(carreras_away + carreras_home)

def calcular_ev_y_kelly(prob_modelo_pct, cuota_decimal):
    prob_decimal = prob_modelo_pct / 100.0
    ev_pct = round(((prob_decimal * cuota_decimal) - 1) * 100, 2)
    b = cuota_decimal - 1.0
    q = 1.0 - prob_decimal
    f_kelly = ((b * prob_decimal) - q) / b if b > 0 else 0.0
    quarter_kelly = max(0.0, (f_kelly / 4.0) * 100)
    return ev_pct, round(quarter_kelly, 2)

# --- CONSULTAS API CACHEADAS ---
@st.cache_data(ttl=120)
def obtener_calendario(fecha): return statsapi.schedule(date=fecha.strftime('%Y-%m-%d'))

@st.cache_data(ttl=10)
def obtener_feed_en_vivo(game_id):
    try: return statsapi.get('game', {'gamePk': game_id})
    except Exception: return {}

@st.cache_data(ttl=600)
def obtener_stats_jugador(player_id, group):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        return data['stats'][0].get('stats', {}) if data.get('stats') else {}
    except Exception: return {}

@st.cache_data(ttl=300)
def obtener_lineup_confirmado(game_id, es_visitante=True):
    try:
        box = statsapi.get('game_boxscore', {'gamePk': game_id})
        team_key = 'away' if es_visitante else 'home'
        team_data = box.get('teams', {}).get(team_key, {})
        batting_order = team_data.get('battingOrder', [])
        players = team_data.get('players', {})
        
        lineup = []
        for idx, pid in enumerate(batting_order[:9], start=1):
            p_info = players.get(f"ID{pid}", {})
            lineup.append({
                'slot': idx, 'id': pid,
                'name': p_info.get('person', {}).get('fullName', f'Bateador #{idx}'),
                'pos': p_info.get('position', {}).get('abbreviation', 'DH')
            })
        return lineup
    except Exception: return []

@st.cache_data(ttl=600)
def obtener_whip_bullpen(team_id):
    try:
        team_stats = statsapi.get('team_stats', {'teamId': team_id, 'statType': 'season', 'group': 'pitching'})
        for stat in team_stats.get('stats', []):
            if stat.get('type', {}).get('displayName') == 'season':
                return parse_float(stat.get('splits', [{}])[0].get('stat', {}).get('whip', 1.30), 1.30)
        return 1.30
    except Exception: return 1.30

# --- PROCESAMIENTO Y RENDERIZADO ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.info("📌 No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} | {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selección de Matchup:", lista_juegos)
    
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
    venue_name = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
    park_factor = PARK_FACTORS.get(venue_name, 1.00)

    exp_runs_away = round((4.5 * (fip_home / 4.10)) * park_factor, 2)
    exp_runs_home = round((4.5 * (fip_away / 4.10)) * park_factor, 2)

    if ajuste_fatiga_bp:
        if whip_bp_home > 1.30: exp_runs_away += 0.25
        if whip_bp_away > 1.30: exp_runs_home += 0.25

    prob_away, prob_home, sim_away, sim_home, total_esperado = simular_monte_carlo(
        exp_runs_away, exp_runs_home, n_simulaciones
    )

    # TARJETAS KPI DE CABECERA
    col1, col2, col3 = st.columns(3)
    col1.markdown(render_kpi_card(f"Prob. {away_name}", f"{prob_away:.1f}%", f"Proyección: {sim_away:.2f} Runs"), unsafe_allow_html=True)
    col2.markdown(render_kpi_card(f"Prob. {home_name}", f"{prob_home:.1f}%", f"Proyección: {sim_home:.2f} Runs"), unsafe_allow_html=True)
    col3.markdown(render_kpi_card("Total Esperado", f"{total_esperado:.2f}", f"Park Factor: {park_factor}x"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # PESTAÑAS PRINCIPALES
    tab_montecarlo, tab_lineup, tab_ev, tab_vivo = st.tabs([
        "🎲 MONTE CARLO", "🧮 LOG-5 & TITULARES", "💰 OPORTUNIDADES +EV", "🏟️ LIVE TRACKER"
    ])

    # --- TAB 1: MONTE CARLO ---
    with tab_montecarlo:
        st.subheader("📊 Comparativo de Abridores y Bullpen")
        df_pitchers = pd.DataFrame([
            {"Equipo": away_name, "Abridor": away_pitcher.get('fullName', 'Por anunciar'), "ERA": stats_p_away.get('era', '-'), "FIP": fip_away, "WHIP": stats_p_away.get('whip', '-'), "K% Proj.": f"{k_pct_away}%", "xK": f"{xk_away_pitcher}", "WHIP Bullpen": whip_bp_away},
            {"Equipo": home_name, "Abridor": home_pitcher.get('fullName', 'Por anunciar'), "ERA": stats_p_home.get('era', '-'), "FIP": fip_home, "WHIP": stats_p_home.get('whip', '-'), "K% Proj.": f"{k_pct_home}%", "xK": f"{xk_home_pitcher}", "WHIP Bullpen": whip_bp_home}
        ])
        st.dataframe(df_pitchers, use_container_width=True, hide_index=True)

    # --- TAB 2: LOG-5 ---
    with tab_lineup:
        opción = st.radio("Alineación:", (f"Titulares de {away_name}", f"Titulares de {home_name}"), horizontal=True)
        es_away = away_name in opción
        
        stats_p_rival = stats_p_home if es_away else stats_p_away
        pitcher_hand = (game_data.get('players', {}).get(f"ID{home_pitcher.get('id') if es_away else away_pitcher.get('id')}", {}).get('pitchHand', {}).get('code', 'R'))
        lineup_titular = obtener_lineup_confirmado(game_id, es_visitante=es_away)
        
        baa_rival = parse_float(stats_p_rival.get('avg'), 0.245)
        bf_p_rival = parse_float(stats_p_rival.get('battersFaced'), 1)
        k_rate_p_rival = (parse_float(stats_p_rival.get('strikeOuts'), 0) / bf_p_rival) if bf_p_rival > 0 else 0.225
        
        if lineup_titular:
            res_lineup = []
            for jug in lineup_titular:
                b_stats = obtener_stats_jugador(jug['id'], 'batting')
                avg_b = parse_float(b_stats.get('avg'), 0.0)
                pa_b = parse_float(b_stats.get('plateAppearances'), 1)
                k_rate_b = (parse_float(b_stats.get('strikeOuts'), 0) / pa_b) if pa_b > 0 else 0.225
                
                avg_split = avg_b + 0.012 if pitcher_hand == 'L' else avg_b
                num_h = (avg_split * baa_rival) / 0.245
                prob_hit = num_h / (num_h + ((1 - avg_split) * (1 - baa_rival) / 0.755)) if num_h > 0 else 0.0
                
                pa_exp = PA_LINEUP_WEIGHTS.get(jug['slot'], 3.8)
                res_lineup.append({
                    "Orden": f"#{jug['slot']}", "Bateador": jug['name'], "Pos": jug['pos'],
                    "AVG": avg_b, "Prob Hit": prob_hit, "Hits Proj (xH)": round(prob_hit * pa_exp, 2),
                    "Diagnóstico": "🟢 Ventaja" if prob_hit > 0.270 else "🟡 Neutro" if prob_hit > 0.240 else "🔴 Desventaja"
                })
            
            st.dataframe(
                pd.DataFrame(res_lineup),
                column_config={
                    "AVG": st.column_config.NumberColumn(format="%.3f"),
                    "Prob Hit": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=0.5),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Alineación confirmada aún no disponible.")

        # --- TAB 3: DETECTOR +EV ---
    with tab_ev:
        st.markdown("##### 💰 Análisis de Valor Esperado y Criterio de Kelly (Quarter-Kelly)")
        cuotas_demo = [
            {"bookmaker": "Pinnacle", "away_odds": 2.15, "home_odds": 1.75},
            {"bookmaker": "DraftKings", "away_odds": 2.05, "home_odds": 1.80},
            {"bookmaker": "FanDuel", "away_odds": 2.10, "home_odds": 1.78}
        ]
        
        filas_ev = []
        for item in cuotas_demo:
            ev_away, kelly_away = calcular_ev_y_kelly(prob_away, item['away_odds'])
            ev_home, kelly_home = calcular_ev_y_kelly(prob_home, item['home_odds'])
            
            row = {
                "Bookmaker": item['bookmaker'],
                f"Cuota {away_name}": item['away_odds'],
                f"EV {away_name}": f"{ev_away:+.2f}%",
                f"Kelly {away_name}": f"{kelly_away}%",
                f"Cuota {home_name}": item['home_odds'],
                f"EV {home_name}": f"{ev_home:+.2f}%",
                f"Kelly {home_name}": f"{kelly_home}%"
            }
            filas_ev.append(row)
            
        st.dataframe(pd.DataFrame(filas_ev), use_container_width=True, hide_index=True)

    # --- TAB 4: LIVE TRACKER ---
    with tab_vivo:
        linescore = live_data.get('linescore', {})
        current_play = live_data.get('plays', {}).get('currentPlay', {})
        offense = linescore.get('offense', {})
        
        c_campo, c_info = st.columns([1, 1.8])
        
        with c_campo:
            st.markdown(generar_campo_svg_moderno(offense), unsafe_allow_html=True)
            
        with c_info:
            if current_play:
                matchup = current_play.get('matchup', {})
                count = current_play.get('count', {})
                
                st.markdown(f"""
                <div style="background: #1E293B; padding: 18px; border-radius: 12px; border: 1px solid #334155;">
                    <div style="color: #38BDF8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase;">Turno Actual</div>
                    <div style="font-size: 1.3rem; font-weight: 800; color: #FFF;">🏏 {matchup.get('batter', {}).get('fullName', 'En Espera')}</div>
                    <div style="color: #94A3B8; font-size: 0.9rem;">vs. ⚾ {matchup.get('pitcher', {}).get('fullName', 'En Espera')}</div>
                    <hr style="border-color: #334155; margin: 10px 0;">
                    <div style="font-size: 1.1rem; font-weight: 700; color: #00E676;">
                        Conteo: {count.get('balls', 0)}B - {count.get('strikes', 0)}S | {count.get('outs', 0)} Outs
                    </div>
                </div>
                """, unsafe_allow_html=True)

# AUTO-REFRESH
if auto_refresh:
    time.sleep(10)
    st.rerun()
