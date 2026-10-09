import streamlit as st
import pandas as pd
import numpy as np
import statsapi
import requests
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MLB Sabermetrics & Ultra-Fast Live Simulator",
    layout="wide",
    page_icon="⚾",
    initial_sidebar_state="expanded"
)

# Sesión HTTP reutilizable para reducir latencia TCP/SSL
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

# --- CSS: INTERFAZ DARK GLASSMORPHISM ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0B0F17;
        color: #F1F5F9;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1E293B;
    }

    .kpi-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        text-align: center;
    }

    .kpi-title { 
        font-size: 0.75rem; 
        text-transform: uppercase; 
        letter-spacing: 1.2px; 
        color: #94A3B8; 
        font-weight: 700; 
    }
    
    .kpi-value { 
        font-size: 2rem; 
        font-weight: 800; 
        color: #FFFFFF; 
    }
    
    .kpi-sub { 
        font-size: 0.8rem; 
        color: #38BDF8; 
        font-weight: 600; 
        margin-top: 4px; 
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px; 
        background-color: #111827; 
        padding: 6px; 
        border-radius: 12px; 
        border: 1px solid #1E293B;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        color: #94A3B8;
        font-weight: 600;
        border: none !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important; 
        color: #FFFFFF !important;
    }

    .pitch-box {
        background: #0F172A; 
        border: 1px solid #38BDF8; 
        padding: 15px; 
        border-radius: 12px; 
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES DE LIGA Y MODELO ---
PARK_FACTORS = {
    "Coors Field": 1.15, "Fenway Park": 1.06, "Great American Ball Park": 1.05,
    "Yankee Stadium": 1.03, "Wrigley Field": 1.02, "Dodger Stadium": 1.00,
    "Busch Stadium": 0.97, "Petco Park": 0.94, "T-Mobile Park": 0.91,
    "Estadio Desconocido": 1.00
}

PA_LINEUP_WEIGHTS = {1: 4.6, 2: 4.5, 3: 4.4, 4: 4.3, 5: 4.2, 6: 4.1, 7: 4.0, 8: 3.9, 9: 3.8}
LEAGUE_AVG, LEAGUE_K_RATE, LEAGUE_BB_RATE, LEAGUE_HR_RATE = 0.245, 0.225, 0.082, 0.031

# --- FUNCIONES MATEMÁTICAS Y UTILIDADES ---
def parse_float(val, default=0.0):
    try: return float(val) if val not in [None, '', '-'] else default
    except: return default

def parse_ip(ip_val, default=0.0):
    val = parse_float(ip_val, default)
    entero = int(val)
    decimal = round((val - entero) * 10)
    return entero + (decimal / 3.0)

def render_kpi_card(title, value, subtext):
    return f"""<div class="kpi-card"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{subtext}</div></div>"""

def calcular_log5_general(p_batter, p_pitcher, p_league):
    if p_league <= 0 or p_league >= 1: return p_batter
    num = (p_batter * p_pitcher) / p_league
    den = num + (((1.0 - p_batter) * (1.0 - p_pitcher)) / (1.0 - p_league))
    return num / den if den > 0 else p_league

def simular_monte_carlo(exp_away, exp_home, n_sims=10000):
    np.random.seed(42)
    carreras_away = np.random.poisson(max(0.5, exp_away), n_sims)
    carreras_home = np.random.poisson(max(0.5, exp_home), n_sims)
    
    wins_away = np.sum(carreras_away > carreras_home)
    wins_home = np.sum(carreras_home > carreras_away)
    empates = np.sum(carreras_away == carreras_home)
    
    prob_away = ((wins_away + (empates * 0.5)) / n_sims) * 100
    prob_home = ((wins_home + (empates * 0.5)) / n_sims) * 100
    return prob_away, prob_home, np.mean(carreras_away), np.mean(carreras_home), np.mean(carreras_away + carreras_home), carreras_away, carreras_home

def calcular_ev_y_kelly(prob_modelo_pct, cuota_decimal):
    prob_decimal = prob_modelo_pct / 100.0
    ev_pct = round(((prob_decimal * cuota_decimal) - 1) * 100, 2)
    b = cuota_decimal - 1.0
    q = 1.0 - prob_decimal
    f_kelly = ((b * prob_decimal) - q) / b if b > 0 else 0.0
    quarter_kelly = max(0.0, (f_kelly / 4.0) * 100)
    return ev_pct, round(quarter_kelly, 2)

def generar_campo_svg_moderno(offense_dict):
    c_1b = "#00E676" if offense_dict.get('first') else "#334155"
    c_2b = "#00E676" if offense_dict.get('second') else "#334155"
    c_3b = "#00E676" if offense_dict.get('third') else "#334155"
    
    return (
        f'<div style="display: flex; justify-content: center; padding: 10px;">'
        f'<svg width="250" height="230" viewBox="0 0 260 240" style="background: #0F172A; border-radius: 16px; border: 1px solid #1E293B;">'
        f'<path d="M 130 210 L 230 110 A 130 130 0 0 0 30 110 Z" fill="#022C22" stroke="#059669" stroke-width="2"/>'
        f'<polygon points="130,200 200,130 130,60 60,130" fill="#78350F" opacity="0.8"/>'
        f'<rect x="193" y="123" width="14" height="14" transform="rotate(45 200 130)" fill="{c_1b}" stroke="#FFFFFF"/>'
        f'<rect x="123" y="53" width="14" height="14" transform="rotate(45 130 60)" fill="{c_2b}" stroke="#FFFFFF"/>'
        f'<rect x="53" y="123" width="14" height="14" transform="rotate(45 60 130)" fill="{c_3b}" stroke="#FFFFFF"/>'
        f'<polygon points="130,195 135,200 135,205 125,205 125,200" fill="#FFFFFF"/>'
        f'</svg></div>'
    )

# --- CONSULTAS OPTIMIZADAS CON CACHÉ ---
@st.cache_data(ttl=3600)
def fetch_api_fast(url):
    try:
        r = HTTP_SESSION.get(url, timeout=1.8)
        return r.json() if r.status_code == 200 else {}
    except: return {}

@st.cache_data(ttl=1800)
def get_schedule_fast(fecha_str):
    return statsapi.schedule(date=fecha_str)

@st.cache_data(ttl=3600)
def get_player_stats_fast(player_id, group='batting'):
    if not player_id: return {}
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group={group}&fields=stats,splits,stat,avg,slg,obp,plateAppearances,strikeOuts,baseOnBalls,homeRuns,hits,era,whip,inningsPitched,battersFaced"
    data = fetch_api_fast(url)
    try: return data['stats'][0]['splits'][0]['stat']
    except: return {}

@st.cache_data(ttl=3600)
def get_bvp_fast(batter_id, pitcher_id):
    if not batter_id or not pitcher_id: return {'at_bats': 0, 'hits': 0, 'home_runs': 0, 'strikeouts': 0, 'walks': 0, 'avg': 0.0, 'ops': 0.0, 'muestra_real': False}
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsPlayerTotal&opposingPlayerId={pitcher_id}&group=batting&fields=stats,splits,stat,atBats,hits,homeRuns,strikeOuts,baseOnBalls,avg,obp,slg,ops"
    data = fetch_api_fast(url)
    try:
        st_dict = data['stats'][0]['splits'][0]['stat']
        ab = parse_float(st_dict.get('atBats'))
        return {
            'at_bats': int(ab),
            'hits': int(parse_float(st_dict.get('hits'))),
            'home_runs': int(parse_float(st_dict.get('homeRuns'))),
            'strikeouts': int(parse_float(st_dict.get('strikeOuts'))),
            'walks': int(parse_float(st_dict.get('baseOnBalls'))),
            'avg': parse_float(st_dict.get('avg')),
            'obp': parse_float(st_dict.get('obp')),
            'slg': parse_float(st_dict.get('slg')),
            'ops': parse_float(st_dict.get('ops')),
            'muestra_real': ab > 0
        }
    except: return {'at_bats': 0, 'hits': 0, 'home_runs': 0, 'strikeouts': 0, 'walks': 0, 'avg': 0.0, 'ops': 0.0, 'muestra_real': False}

def cargar_datos_partido_en_memoria(game_id, away_id, home_id, away_p_id, home_p_id):
    """Carga paralela en segundo plano con ThreadPoolExecutor."""
    feed = statsapi.get('game', {'gamePk': game_id})
    
    def extract_lineup(team_key, team_id):
        try:
            players = feed['liveData']['boxscore']['teams'][team_key]['players']
            om = {}
            for k, v in players.items():
                bo = str(v.get('battingOrder', ''))
                if bo in ['100','200','300','400','500','600','700','800','900']:
                    slot = int(bo[0])
                    om[slot] = {'slot': slot, 'id': v['person']['id'], 'name': v['person']['fullName'], 'pos': v['position']['abbreviation']}
            if len(om) >= 9: return [om[i] for i in range(1, 10)], True
        except: pass
        roster = statsapi.get('team_roster', {'teamId': team_id}).get('roster', [])
        lineup = []
        slot = 1
        for r in roster:
            if r.get('position', {}).get('abbreviation') != 'P' and slot <= 9:
                lineup.append({'slot': slot, 'id': r['person']['id'], 'name': r['person']['fullName'], 'pos': r.get('position',{}).get('abbreviation','DH')})
                slot += 1
        return lineup, False

    lineup_away, official_away = extract_lineup('away', away_id)
    lineup_home, official_home = extract_lineup('home', home_id)

    tasks = []
    for j in lineup_away: tasks.append((j['id'], home_p_id, 'away'))
    for j in lineup_home: tasks.append((j['id'], away_p_id, 'home'))

    stats_away, bvp_away = {}, {}
    stats_home, bvp_home = {}, {}

    def _worker(t):
        p_id, opp_p, side = t
        return p_id, get_player_stats_fast(p_id, 'batting'), get_bvp_fast(p_id, opp_p), side

    with ThreadPoolExecutor(max_workers=18) as ex:
        for p_id, st_d, bvp_d, side in ex.map(_worker, tasks):
            if side == 'away':
                stats_away[p_id], bvp_away[p_id] = st_d, bvp_d
            else:
                stats_home[p_id], bvp_home[p_id] = st_d, bvp_d

    return {
        'lineup_away': lineup_away, 'official_away': official_away,
        'lineup_home': lineup_home, 'official_home': official_home,
        'stats_away': stats_away, 'bvp_away': bvp_away,
        'stats_home': stats_home, 'bvp_home': bvp_home,
        'feed': feed
    }

# --- BARRA LATERAL Y CONTROLES ---
st.sidebar.markdown("<h3 style='color: #F8FAFC;'>⚙️ Panel de Control</h3>", unsafe_allow_html=True)
fecha_sel = st.sidebar.date_input("Fecha de Análisis:", datetime.today())
n_simulaciones = st.sidebar.slider("Simulaciones Monte Carlo:", 1000, 25000, 10000, step=1000)
ajuste_fatiga_bp = st.sidebar.checkbox("Penalizar Bullpen Cansado (>1.30 WHIP)", value=True)
odds_api_key = st.sidebar.text_input("API Key (The-Odds-API):", type="password")

# --- CABECERA PRINCIPAL ---
st.markdown("""
<div style="padding: 10px 0 20px 0; border-bottom: 1px solid #1E293B; margin-bottom: 20px;">
    <div style="font-size: 2.2rem; font-weight: 800; color: #FFF;">⚡ MLB Pro Intelligence & Ultra-Fast Live Simulator</div>
    <div style="color: #64748B; font-size: 0.95rem;">Master Cache en Memoria, Monte Carlo, Algoritmos Log-5 y Simulador Estocástico Pitch-by-Pitch</div>
</div>
""", unsafe_allow_html=True)

juegos = get_schedule_fast(fecha_sel.strftime('%Y-%m-%d'))

if not juegos:
    st.info("📌 No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} | {j['status']}" for j in juegos]
    juego_sel = st.selectbox("🎯 Selección de Matchup:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_sel)
    g_info = juegos[idx_juego]
    game_id = g_info['game_id']

    # GESTIÓN DE ESTADO EN SESIÓN PARA LATENCIA 0MS
    if 'current_game_id' not in st.session_state or st.session_state.current_game_id != game_id:
        with st.spinner("⚡ Cargando métricas sabermétricas en memoria interna..."):
            p_away_id = g_info.get('away_probable_id', 0)
            p_home_id = g_info.get('home_probable_id', 0)
            st.session_state.game_data_cache = cargar_datos_partido_en_memoria(game_id, g_info['away_id'], g_info['home_id'], p_away_id, p_home_id)
            st.session_state.current_game_id = game_id

    cache = st.session_state.game_data_cache
    
    stats_p_away = get_player_stats_fast(g_info.get('away_probable_id'), 'pitching')
    stats_p_home = get_player_stats_fast(g_info.get('home_probable_id'), 'pitching')
    
    fip_away = parse_float(stats_p_away.get('era'), 4.10)
    fip_home = parse_float(stats_p_home.get('era'), 4.10)
    
    venue_name = cache['feed'].get('gameData', {}).get('venue', {}).get('name', 'Estadio Desconocido')
    park_factor = PARK_FACTORS.get(venue_name, 1.00)

    exp_runs_away = round((4.5 * (fip_home / 4.10)) * park_factor, 2)
    exp_runs_home = round((4.5 * (fip_away / 4.10)) * park_factor, 2)

    prob_away, prob_home, sim_away, sim_home, total_esperado, arr_away_runs, arr_home_runs = simular_monte_carlo(
        exp_runs_away, exp_runs_home, n_simulaciones
    )

    # KPIS DESTACADOS
    c1, c2, c3 = st.columns(3)
    c1.markdown(render_kpi_card(f"Prob. {g_info['away_name']}", f"{prob_away:.1f}%", f"Proyección: {sim_away:.2f} Runs"), unsafe_allow_html=True)
    c2.markdown(render_kpi_card(f"Prob. {g_info['home_name']}", f"{prob_home:.1f}%", f"Proyección: {sim_home:.2f} Runs"), unsafe_allow_html=True)
    c3.markdown(render_kpi_card("Total Esperado", f"{total_esperado:.2f}", f"Park Factor: {park_factor}x"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # PESTAÑAS PRINCIPALES
    tab_sim_live, tab_monte, tab_log5, tab_bvp, tab_ev, tab_live = st.tabs([
        "🎮 SIMULADOR PITCH-BY-PITCH", 
        "🎲 MONTE CARLO", 
        "🧮 LOG-5 ANALYTICS", 
        "⚔️ BvP HISTÓRICO",
        "💰 DETECTOR +EV",
        "🏟️ LIVE TRACKER"
    ])

    # --- TAB 1: SIMULADOR PITCH-BY-PITCH (SUPER TIEMPO REAL) ---
    with tab_sim_live:
        st.subheader("⚡ Simulador Duelo Pitcher vs Bateador (Pitch-by-Pitch Real-Time)")
        
        col_p, col_b, col_btn = st.columns([1.2, 1.2, 1])
        with col_p:
            pitcher_nombre = st.selectbox("Lanzador Abridor:", [
                g_info.get('away_probable_name', 'Pitcher Visita'),
                g_info.get('home_probable_name', 'Pitcher Local')
            ])
            
        es_p_away = (pitcher_nombre == g_info.get('away_probable_name'))
        lineup_opciones = cache['lineup_home'] if es_p_away else cache['lineup_away']
        
        with col_b:
            bateador_sel = st.selectbox("Bateador en el Cajón:", [j['name'] for j in lineup_opciones])
            
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            iniciar_sim = st.button("🚀 Iniciar Simulación en Vivo", type="primary", use_container_width=True)

        if iniciar_sim:
            PITCH_TYPES = ["4-Seam Fastball", "Slider", "Changeup", "Curveball", "Sinker"]
            VELOCITIES = {"4-Seam Fastball": (93, 99), "Slider": (83, 89), "Changeup": (82, 87), "Curveball": (76, 82), "Sinker": (91, 96)}
            
            balls, strikes = 0, 0
            pitch_count = 0
            at_bat_over = False
            
            placeholder_zone = st.empty()
            placeholder_log = st.empty()
            log_pitches = []

            while not at_bat_over:
                pitch_count += 1
                ptype = random.choice(PITCH_TYPES)
                vel = round(random.uniform(*VELOCITIES[ptype]), 1)
                
                px = round(random.uniform(-1.1, 1.1), 2)
                py = round(random.uniform(1.2, 3.8), 2)
                
                in_zone = (-0.85 <= px <= 0.85) and (1.5 <= py <= 3.5)
                swing_prob = 0.68 if in_zone else 0.32
                swung = random.random() < swing_prob
                
                outcome = ""
                if swung:
                    contact_prob = 0.78 if in_zone else 0.45
                    if random.random() < contact_prob:
                        if random.random() < 0.60 and strikes < 2:
                            outcome = "⚾ FOUL"
                            if strikes < 2: strikes += 1
                        else:
                            at_bat_over = True
                            exit_vel = round(random.uniform(85, 108), 1)
                            launch_angle = random.randint(-10, 42)
                            
                            if exit_vel > 98 and 18 <= launch_angle <= 32:
                                outcome = f"💣 JONRÓN (HR) — Vel: {exit_vel} mph | Ángulo: {launch_angle}°"
                            elif exit_vel > 90 and -5 <= launch_angle <= 15:
                                outcome = f"🏏 HIT SENCILLO / DOBLE — Vel: {exit_vel} mph"
                            elif launch_angle > 35:
                                outcome = f"FLY OUT DE AIRE — Vel: {exit_vel} mph"
                            else:
                                outcome = f"GROUND OUT ROLETASO — Vel: {exit_vel} mph"
                    else:
                        outcome = "💨 SWING Y MISS (Abanicado)"
                        strikes += 1
                else:
                    if in_zone:
                        outcome = "🎯 STRIKE CANTADO"
                        strikes += 1
                    else:
                        outcome = "🟢 BOLA FUERA DE ZONA"
                        balls += 1

                if strikes == 3 and not at_bat_over:
                    outcome = "🛑 PONCHE (K) — Bateador Eliminado"
                    at_bat_over = True
                elif balls == 4 and not at_bat_over:
                    outcome = "👁️ BASE POR BOLAS (BB) — Bateador Embasado"
                    at_bat_over = True

                log_pitches.append(f"Lanzamiento #{pitch_count}: **{ptype}** ({vel} mph) -> {outcome} | Conteo: ({balls}-{strikes})")
                
                circle_color = "#00E676" if "HIT" in outcome or "JONRÓN" in outcome else ("#EF4444" if "STRIKE" in outcome or "PONCHE" in outcome or "SWING" in outcome else "#38BDF8")
                
                svg_zone = f"""
                <div style="display: flex; justify-content: center; align-items: center; gap: 30px; background: #0F172A; padding: 20px; border-radius: 16px; border: 1px solid #1E293B;">
                    <svg width="220" height="260" viewBox="-120 80 240 300">
                        <rect x="-70" y="150" width="140" height="180" fill="none" stroke="#64748B" stroke-width="3" stroke-dasharray="4"/>
                        <circle cx="{px*65}" cy="{400 - (py*80)}" r="10" fill="{circle_color}" stroke="#FFFFFF" stroke-width="2"/>
                        <text x="0" y="380" fill="#94A3B8" font-size="14" text-anchor="middle">Cajón de Bateo MLB</text>
                    </svg>
                    <div style="min-width: 250px;">
                        <h3 style="color: #38BDF8; margin: 0;">Conteo: {balls} - {strikes}</h3>
                        <p style="color: #F8FAFC; font-size: 1.1rem; margin-top: 5px;"><b>Último Lanzamiento:</b></p>
                        <div class="pitch-box">
                            ⚾ <b>{ptype}</b><br>
                            ⚡ <b>Velocidad:</b> {vel} mph<br>
                            📌 <b>Ubicación:</b> ({px}, {py})<br>
                            📣 <b>Dictamen:</b> {outcome}
                        </div>
                    </div>
                </div>
                """
                placeholder_zone.markdown(svg_zone, unsafe_allow_html=True)
                
                log_html = "<br>".join([f"• {l}" for l in reversed(log_pitches)])
                placeholder_log.markdown(f"#### 📜 Secuencia del Duelo:\n{log_html}")
                time.sleep(1.2)

    # --- TAB 2: MONTE CARLO ---
    with tab_monte:
        st.subheader("📊 Comparativo de Abridores y Simulación de Carreras")
        df_pitchers = pd.DataFrame([
            {"Equipo": g_info['away_name'], "Abridor": g_info.get('away_probable_name', 'TBD'), "ERA": stats_p_away.get('era', '-'), "FIP": fip_away, "WHIP": stats_p_away.get('whip', '-')},
            {"Equipo": g_info['home_name'], "Abridor": g_info.get('home_probable_name', 'TBD'), "ERA": stats_p_home.get('era', '-'), "FIP": fip_home, "WHIP": stats_p_home.get('whip', '-')}
        ])
        st.dataframe(df_pitchers, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📈 Distribución Estocástica de Carreras (Monte Carlo)")
        df_dist = pd.DataFrame({
            f"Carreras {g_info['away_name']}": pd.Series(arr_away_runs).value_counts(normalize=True).sort_index(),
            f"Carreras {g_info['home_name']}": pd.Series(arr_home_runs).value_counts(normalize=True).sort_index()
        }).fillna(0) * 100
        st.bar_chart(df_dist, height=280)

    # --- TAB 3: LOG-5 ANALYTICS ---
    with tab_log5:
        st.subheader("🔬 Proyección Sabermétrica Avanzada (Carga Instantánea)")
        sel_team = st.radio("Alineación a Proyectar:", [g_info['away_name'], g_info['home_name']], horizontal=True)
        
        es_away_tab = (sel_team == g_info['away_name'])
        lineup_tab = cache['lineup_away'] if es_away_tab else cache['lineup_home']
        stats_tab = cache['stats_away'] if es_away_tab else cache['stats_home']
        bvp_tab = cache['bvp_away'] if es_away_tab else cache['bvp_home']

        rows = []
        for jug in lineup_tab:
            st_j = stats_tab.get(jug['id'], {})
            bvp_j = bvp_tab.get(jug['id'], {})
            
            avg = parse_float(st_j.get('avg'), 0.240)
            slg = parse_float(st_j.get('slg'), 0.400)
            obp = parse_float(st_j.get('obp'), 0.310)
            
            iso = round(max(0.0, slg - avg), 3)
            pa_exp = PA_LINEUP_WEIGHTS.get(jug['slot'], 3.8)
            xH = round(avg * pa_exp, 2)
            
            rows.append({
                "Orden": f"#{jug['slot']}",
                "Bateador": jug['name'],
                "Pos": jug['pos'],
                "AVG": f"{avg:.3f}",
                "OBP": f"{obp:.3f}",
                "SLG": f"{slg:.3f}",
                "ISO": f"{iso:.3f}",
                "xH (Hits Esperados)": xH,
                "BvP Carrera": f"{bvp_j.get('avg', 0.0):.3f} ({bvp_j.get('at_bats', 0)} ABs)"
            })
            
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- TAB 4: BvP HISTÓRICO ---
    with tab_bvp:
        st.subheader("⚔️ Registro Frente a Frente Directo en Grandes Ligas")
        sel_bvp_team = st.radio("Equipo Ofensivo:", [g_info['away_name'], g_info['home_name']], horizontal=True, key="bvp_radio_tab")
        
        es_away_bvp = (sel_bvp_team == g_info['away_name'])
        lineup_bvp = cache['lineup_away'] if es_away_bvp else cache['lineup_home']
        bvp_dict = cache['bvp_away'] if es_away_bvp else cache['bvp_home']
        
        bvp_rows = []
        for j in lineup_bvp:
            det = bvp_dict.get(j['id'], {})
            bvp_rows.append({
                "Bateador": j['name'],
                "Pos": j['pos'],
                "ABs": det.get('at_bats', 0),
                "Hits": det.get('hits', 0),
                "HRs": det.get('home_runs', 0),
                "Ponches (K)": det.get('strikeouts', 0),
                "Boletos (BB)": det.get('walks', 0),
                "AVG H2H": f"{det.get('avg', 0.0):.3f}",
                "OPS H2H": f"{det.get('ops', 0.0):.3f}"
            })
            
        st.dataframe(pd.DataFrame(bvp_rows), use_container_width=True, hide_index=True)

    # --- TAB 5: DETECTOR +EV ---
    with tab_ev:
        st.subheader("💰 Cálculo de Valor Esperado (+EV) y Criterio de Kelly")
        
        cuotas_activas = [
            {"bookmaker": "Pinnacle", "away_odds": 2.15, "home_odds": 1.75},
            {"bookmaker": "DraftKings", "away_odds": 2.05, "home_odds": 1.80},
            {"bookmaker": "FanDuel", "away_odds": 2.10, "home_odds": 1.78}
        ]
        
        filas_ev = []
        for item in cuotas_activas:
            ev_away, kelly_away = calcular_ev_y_kelly(prob_away, item['away_odds'])
            ev_home, kelly_home = calcular_ev_y_kelly(prob_home, item['home_odds'])
            
            filas_ev.append({
                "Bookmaker": item['bookmaker'],
                f"Cuota {g_info['away_name']}": item['away_odds'],
                f"EV {g_info['away_name']}": f"{ev_away:+.2f}%",
                f"Kelly {g_info['away_name']}": f"{kelly_away}%",
                f"Cuota {g_info['home_name']}": item['home_odds'],
                f"EV {g_info['home_name']}": f"{ev_home:+.2f}%",
                f"Kelly {g_info['home_name']}": f"{kelly_home}%"
            })
            
        st.dataframe(pd.DataFrame(filas_ev), use_container_width=True, hide_index=True)

    # --- TAB 6: LIVE TRACKER ---
    with tab_live:
        st.subheader("Stadium Live Tracker")
        live_data = cache['feed'].get('liveData', {})
        linescore = live_data.get('linescore', {})
        offense = linescore.get('offense', {})
        
        c_campo, c_info = st.columns([1, 1.8])
        with c_campo:
            st.markdown(generar_campo_svg_moderno(offense), unsafe_allow_html=True)
            
        with c_info:
            current_play = live_data.get('plays', {}).get('currentPlay', {})
            if current_play:
                matchup = current_play.get('matchup', {})
                count = current_play.get('count', {})
                
                st.markdown(f"""
                <div style="background: #1E293B; padding: 20px; border-radius: 14px; border: 1px solid #38BDF8;">
                    <h3 style="color: #FFF; margin: 0;">🏏 Bateando: {matchup.get('batter', {}).get('fullName', 'En espera')}</h3>
                    <p style="color: #CBD5E1; margin-top: 4px;">⚾ Lanzando: {matchup.get('pitcher', {}).get('fullName', 'En espera')}</p>
                    <hr style="border-color: #334155;">
                    <h4 style="color: #00E676;">Conteo: {count.get('balls', 0)} - {count.get('strikes', 0)} | {count.get('outs', 0)} Outs</h4>
                    <p style="color: #94A3B8; font-style: italic;"><b>Última Acción:</b> {current_play.get('result', {}).get('description', 'Turno en desarrollo...')}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("💡 Esperando datos de juego activo en tiempo real.")
