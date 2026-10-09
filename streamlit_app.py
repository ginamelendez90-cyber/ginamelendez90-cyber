import streamlit as st
import pandas as pd
import numpy as np
import statsapi
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(
    page_title="MLB Pro Sabermetrics & Live Tracker",
    layout="wide",
    page_icon="⚾",
    initial_sidebar_state="expanded"
)

# Sesión HTTP persistente global
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

# --- CSS INYECTADO: INTERFAZ DARK GLASSMORPHISM ---
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
    <div class="header-title">⚡ MLB Sabermetrics & Live Intelligence (Ultra-Fast Edition)</div>
    <div style="color: #64748B; font-size: 0.95rem; margin-top: 4px;">Proyección Monte Carlo, Algoritmos Log-5, Motor BvP Optimizado y Statcast en Vivo</div>
</div>
""", unsafe_allow_html=True)

# --- CONSTANTES DE LA LIGA ---
PARK_FACTORS = {
    "Coors Field": 1.15, "Fenway Park": 1.06, "Great American Ball Park": 1.05,
    "Yankee Stadium": 1.03, "Wrigley Field": 1.02, "Dodger Stadium": 1.00,
    "Busch Stadium": 0.97, "Petco Park": 0.94, "T-Mobile Park": 0.91,
    "Estadio Desconocido / Neutro": 1.00
}

PA_LINEUP_WEIGHTS = {1: 4.6, 2: 4.5, 3: 4.4, 4: 4.3, 5: 4.2, 6: 4.1, 7: 4.0, 8: 3.9, 9: 3.8}

LEAGUE_AVG = 0.245
LEAGUE_K_RATE = 0.225
LEAGUE_BB_RATE = 0.082
LEAGUE_HR_RATE = 0.031

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
odds_api_key = st.sidebar.text_input("API Key (The-Odds-API):", type="password")


# --- FUNCIONES MATEMÁTICAS Y LOG-5 ---
def parse_float(val, default=0.0):
    try:
        if val is None or val == '' or val == '-': return default
        return float(val)
    except (ValueError, TypeError):
        return default

def parse_ip(ip_val, default=0.0):
    val = parse_float(ip_val, default)
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

def calcular_log5_general(p_batter, p_pitcher, p_league):
    if p_league <= 0 or p_league >= 1: return p_batter
    num = (p_batter * p_pitcher) / p_league
    den = num + (((1.0 - p_batter) * (1.0 - p_pitcher)) / (1.0 - p_league))
    return num / den if den > 0 else p_league

def generar_campo_svg_moderno(offense_dict):
    c_1b = "#00E676" if offense_dict.get('first') else "#334155"
    c_2b = "#00E676" if offense_dict.get('second') else "#334155"
    c_3b = "#00E676" if offense_dict.get('third') else "#334155"
    
    glow_1b = 'filter="url(#glow)"' if offense_dict.get('first') else ''
    glow_2b = 'filter="url(#glow)"' if offense_dict.get('second') else ''
    glow_3b = 'filter="url(#glow)"' if offense_dict.get('third') else ''
    
    svg = (
        f'<div style="display: flex; justify-content: center; padding: 10px;">'
        f'<svg width="270" height="250" viewBox="0 0 260 240" style="background: #0F172A; border-radius: 16px; border: 1px solid #1E293B; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">'
        f'<defs>'
        f'<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" result="blur" /><feComposite in="SourceGraphic" in2="blur" operator="over" /></filter>'
        f'<linearGradient id="grassGrad" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#064E3B" /><stop offset="100%" stop-color="#022C22" /></linearGradient>'
        f'</defs>'
        f'<path d="M 130 210 L 230 110 A 130 130 0 0 0 30 110 Z" fill="url(#grassGrad)" stroke="#059669" stroke-width="2"/>'
        f'<polygon points="130,200 200,130 130,60 60,130" fill="#78350F" stroke="#9A3412" stroke-width="1.5" opacity="0.8"/>'
        f'<line x1="130" y1="200" x2="225" y2="105" stroke="#F8FAFC" stroke-width="1.5" stroke-dasharray="3,3"/>'
        f'<line x1="130" y1="200" x2="35" y2="105" stroke="#F8FAFC" stroke-width="1.5" stroke-dasharray="3,3"/>'
        f'<circle cx="130" cy="130" r="9" fill="#9A3412"/>'
        f'<rect x="126" y="128" width="8" height="4" fill="#FFFFFF"/>'
        f'<rect x="193" y="123" width="14" height="14" transform="rotate(45 200 130)" fill="{c_1b}" stroke="#FFFFFF" stroke-width="1.5" {glow_1b}/>'
        f'<rect x="123" y="53" width="14" height="14" transform="rotate(45 130 60)" fill="{c_2b}" stroke="#FFFFFF" stroke-width="1.5" {glow_2b}/>'
        f'<rect x="53" y="123" width="14" height="14" transform="rotate(45 60 130)" fill="{c_3b}" stroke="#FFFFFF" stroke-width="1.5" {glow_3b}/>'
        f'<polygon points="130,195 135,200 135,205 125,205 125,205 125,200" fill="#FFFFFF"/>'
        f'<text x="220" y="134" fill="#94A3B8" font-size="10" font-weight="700">1B</text>'
        f'<text x="130" y="42" fill="#94A3B8" font-size="10" font-weight="700" text-anchor="middle">2B</text>'
        f'<text x="32" y="134" fill="#94A3B8" font-size="10" font-weight="700">3B</text>'
        f'</svg>'
        f'</div>'
    )
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
    return prob_away, prob_home, np.mean(carreras_away), np.mean(carreras_home), np.mean(carreras_away + carreras_home), carreras_away, carreras_home

def calcular_ev_y_kelly(prob_modelo_pct, cuota_decimal):
    prob_decimal = prob_modelo_pct / 100.0
    ev_pct = round(((prob_decimal * cuota_decimal) - 1) * 100, 2)
    b = cuota_decimal - 1.0
    q = 1.0 - prob_decimal
    f_kelly = ((b * prob_decimal) - q) / b if b > 0 else 0.0
    quarter_kelly = max(0.0, (f_kelly / 4.0) * 100)
    return ev_pct, round(quarter_kelly, 2)

def generar_dictamen_partido(away_name, home_name, exp_runs_away, exp_runs_home, prob_away, prob_home, total_esperado):
    diferencia = abs(exp_runs_away - exp_runs_home)
    equipo_favorito = away_name if prob_away > prob_home else home_name
    prob_favorito = max(prob_away, prob_home)
    
    if total_esperado >= 9.5:
        perfil_juego = "🔥 Duelo Ofensivo (Alto Volumen de Carreras)"
    elif total_esperado <= 7.5:
        perfil_juego = "🛡️ Duelo de Pitcheo (Dominio de Abridores)"
    else:
        perfil_juego = "⚖️ Partido Equilibrado / Estándar"
        
    return f"""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%); 
                border: 1px solid #38BDF8; border-radius: 14px; padding: 20px; margin-top: 20px;">
        <h4 style="color: #38BDF8; margin-top: 0;">🔮 DICTAMEN INTEGRAL PROYECTIVO</h4>
        <p style="color: #E2E8F0; font-size: 1.05rem;"><b>Perfil del Juego:</b> {perfil_juego}</p>
        <ul style="color: #CBD5E1; line-height: 1.7;">
            <li><b>Ventaja Proyectada:</b> <span style="color: #00E676; font-weight: 700;">{equipo_favorito}</span> lidera la simulación con un <b>{prob_favorito:.1f}%</b> de probabilidad de victoria.</li>
            <li><b>Margen Esperado de Carreras:</b> Diferencia proyectada de <b>{diferencia:.2f} carreras</b> ({exp_runs_away:.2f} vs {exp_runs_home:.2f}).</li>
            <li><b>Línea Total Sugerida (Over/Under):</b> El modelo ubica la expectativa total en <b>{total_esperado:.2f} carreras</b>.</li>
        </ul>
    </div>
    """

def extraer_contacto_statcast(current_play):
    play_events = current_play.get('playEvents', [])
    if not play_events: return None

    pitches = [e for e in play_events if e.get('isPitch', False)]
    if not pitches: return None

    last_pitch = pitches[-1]
    details = last_pitch.get('details', {})
    code = details.get('code', '')

    hubo_contacto = False
    tipo_contacto_str = "Sin Contacto (Pelota/Strike Cantado)"
    
    if code in ['X', 'D']:
        hubo_contacto = True
        tipo_contacto_str = "💥 BATAZO EN JUEGO (Contacto Efectivo)"
    elif code in ['F', 'f', 'R', 'O', 'M']:
        hubo_contacto = True
        tipo_contacto_str = "⚾ CONTACTO FOUL"
    elif code in ['S', 'W', 'T']:
        tipo_contacto_str = "💨 ABANICADO SIN CONTACTO (Whiff)"

    hit_data = last_pitch.get('hitData', {})
    exit_vel = hit_data.get('launchSpeed')
    launch_angle = hit_data.get('launchAngle')
    distance = hit_data.get('totalDistance')
    trajectory = hit_data.get('trajectory', 'N/A')
    hardness = hit_data.get('hardness', 'N/A')

    pitch_data = last_pitch.get('pitchData', {})
    pitch_speed = pitch_data.get('startSpeed')
    pitch_type = last_pitch.get('details', {}).get('type', {}).get('description', 'Pitcheo')

    return {
        "hubo_contacto": hubo_contacto,
        "tipo_contacto": tipo_contacto_str,
        "pitch_speed": pitch_speed,
        "pitch_type": pitch_type,
        "exit_velocity": exit_vel,
        "launch_angle": launch_angle,
        "distance": distance,
        "trajectory": trajectory.replace('_', ' ').title(),
        "hardness": hardness.title()
    }

# --- CONSULTAS OPTIMIZADAS A API MLB CON FILTRO 'FIELDS' ---
@st.cache_data(ttl=300)
def obtener_calendario(fecha): 
    return statsapi.schedule(date=fecha.strftime('%Y-%m-%d'))

@st.cache_data(ttl=10)
def obtener_feed_en_vivo(game_id):
    """Petición ultraligera filtrando 'fields' para recibir ~30KB en lugar de 4MB."""
    fields_filter = (
        "gameData,status,detailedState,venue,name,probablePitchers,away,home,fullName,id,players,pitchHand,code,"
        "liveData,linescore,currentInning,isTopInning,offense,first,second,third,teams,runs,hits,errors,"
        "boxscore,players,battingOrder,person,position,abbreviation,"
        "plays,currentPlay,matchup,batter,batSide,pitcher,pitchHand,count,balls,strikes,outs,result,description,rbi,event,"
        "playEvents,isPitch,details,code,type,hitData,launchSpeed,launchAngle,totalDistance,trajectory,hardness,pitchData,startSpeed,"
        "allPlays,about,inning,halfInning"
    )
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live?fields={fields_filter}"
    try:
        res = HTTP_SESSION.get(url, timeout=2.0)
        if res.status_code == 200:
            return res.json()
    except Exception: pass
    
    try: return statsapi.get('game', {'gamePk': game_id})
    except Exception: return {}

@st.cache_data(ttl=1800)
def obtener_stats_jugador(player_id, group):
    if not player_id: return {}
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        f"?stats=season&group={group}"
        f"&fields=stats,splits,stat,avg,slg,obp,plateAppearances,strikeOuts,baseOnBalls,homeRuns,hits,era,whip,inningsPitched,battersFaced"
    )
    try:
        res = HTTP_SESSION.get(url, timeout=1.8)
        if res.status_code == 200:
            data = res.json()
            stats_list = data.get('stats', [])
            if stats_list and stats_list[0].get('splits'):
                return stats_list[0]['splits'][0].get('stat', {})
    except Exception: pass
    return {}

@st.cache_data(ttl=1800)
def obtener_bvp_detalle_completo(batter_id, pitcher_id):
    """Consulta directa optimizada de 1 solo paso con filtro de payload ultraligero."""
    if not batter_id or not pitcher_id:
        return {'at_bats': 0, 'hits': 0, 'doubles': 0, 'triples': 0, 'home_runs': 0,
                'strikeouts': 0, 'walks': 0, 'avg': 0.0, 'obp': 0.0, 'slg': 0.0, 'ops': 0.0, 'muestra_real': False}
    
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
        f"?stats=vsPlayerTotal&opposingPlayerId={pitcher_id}&group=batting"
        f"&fields=stats,splits,stat,atBats,plateAppearances,hits,doubles,triples,homeRuns,strikeOuts,baseOnBalls,avg,obp,slg,ops"
    )
    try:
        res = HTTP_SESSION.get(url, timeout=1.8)
        if res.status_code == 200:
            data = res.json()
            for s in data.get('stats', []):
                for split in s.get('splits', []):
                    st_dict = split.get('stat', {})
                    ab = parse_float(st_dict.get('atBats'), 0)
                    pa = parse_float(st_dict.get('plateAppearances'), 0)
                    if ab > 0 or pa > 0:
                        return {
                            'at_bats': int(ab),
                            'hits': int(parse_float(st_dict.get('hits'), 0)),
                            'doubles': int(parse_float(st_dict.get('doubles'), 0)),
                            'triples': int(parse_float(st_dict.get('triples'), 0)),
                            'home_runs': int(parse_float(st_dict.get('homeRuns'), 0)),
                            'strikeouts': int(parse_float(st_dict.get('strikeOuts'), 0)),
                            'walks': int(parse_float(st_dict.get('baseOnBalls'), 0)),
                            'avg': parse_float(st_dict.get('avg'), 0.000),
                            'obp': parse_float(st_dict.get('obp'), 0.000),
                            'slg': parse_float(st_dict.get('slg'), 0.000),
                            'ops': parse_float(st_dict.get('ops'), 0.000),
                            'muestra_real': True
                        }
    except Exception: pass

    return {
        'at_bats': 0, 'hits': 0, 'doubles': 0, 'triples': 0, 'home_runs': 0,
        'strikeouts': 0, 'walks': 0, 'avg': 0.0, 'obp': 0.0, 'slg': 0.0, 'ops': 0.0,
        'muestra_real': False
    }

@st.cache_data(ttl=1800)
def obtener_lineup_datos_batch(lineup_ids, pitcher_id):
    """Ejecuta descargas en paralelo en segundo plano para el lineup entero."""
    def _fetch(j_id):
        return j_id, obtener_stats_jugador(j_id, 'batting'), obtener_bvp_detalle_completo(j_id, pitcher_id)

    dict_stats, dict_bvp = {}, {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(_fetch, lineup_ids)
        for j_id, st_data, bvp_data in results:
            dict_stats[j_id] = st_data
            dict_bvp[j_id] = bvp_data

    return dict_stats, dict_bvp

@st.cache_data(ttl=1800)
def obtener_roster_estructurado(team_id):
    try:
        response = statsapi.get('team_roster', {'teamId': team_id})
        return response.get('roster', [])
    except Exception: return []

@st.cache_data(ttl=300)
def obtener_lineup_confirmado(feed, team_id, es_visitante=True):
    lineup = []
    team_key = 'away' if es_visitante else 'home'
    es_oficial = False
    
    try:
        boxscore = feed.get('liveData', {}).get('boxscore', {})
        team_data = boxscore.get('teams', {}).get(team_key, {})
        players_dict = team_data.get('players', {})
        
        order_map = {}
        for p_key, p_val in players_dict.items():
            bo = str(p_val.get('battingOrder', ''))
            if bo in ['100', '200', '300', '400', '500', '600', '700', '800', '900']:
                slot = int(bo[0])
                order_map[slot] = {
                    'slot': slot,
                    'id': p_val.get('person', {}).get('id'),
                    'name': p_val.get('person', {}).get('fullName', f'Bateador #{slot}'),
                    'pos': p_val.get('position', {}).get('abbreviation', 'DH')
                }
                
        if len(order_map) >= 9:
            lineup = [order_map[i] for i in range(1, 10)]
            es_oficial = True
    except Exception: lineup = []

    if not lineup or len(lineup) < 9:
        roster_json = obtener_roster_estructurado(team_id)
        lineup = []
        slot = 1
        for jug in roster_json:
            pos = jug.get('position', {}).get('abbreviation', 'N/A')
            if pos != 'P' and slot <= 9:
                lineup.append({
                    'slot': slot,
                    'id': jug.get('person', {}).get('id'),
                    'name': jug.get('person', {}).get('fullName', f'Jugador #{slot}'),
                    'pos': pos
                })
                slot += 1
        es_oficial = False

    return lineup, es_oficial

@st.cache_data(ttl=1800)
def obtener_whip_bullpen(team_id):
    try:
        team_stats = statsapi.get('team_stats', {'teamId': team_id, 'statType': 'season', 'group': 'pitching'})
        for stat in team_stats.get('stats', []):
            if stat.get('type', {}).get('displayName') == 'season':
                return parse_float(stat.get('splits', [{}])[0].get('stat', {}).get('whip', 1.30), 1.30)
        return 1.30
    except Exception: return 1.30

@st.cache_data(ttl=300)
def obtener_cuotas_reales(api_key, away_team, home_team):
    if not api_key: return None
    try:
        url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?apiKey={api_key}&regions=us&markets=h2h&oddsFormat=decimal"
        res = HTTP_SESSION.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            for game in data:
                home_matched = home_team.lower() in game.get('home_team', '').lower()
                away_matched = away_team.lower() in game.get('away_team', '').lower()
                if home_matched or away_matched:
                    parsed_odds = []
                    for bm in game.get('bookmakers', []):
                        bm_title = bm.get('title')
                        h2h_market = next((m for m in bm.get('markets', []) if m.get('key') == 'h2h'), None)
                        if h2h_market:
                            outcomes = h2h_market.get('outcomes', [])
                            a_odd = next((o.get('price') for o in outcomes if o.get('name') == game.get('away_team')), 2.0)
                            h_odd = next((o.get('price') for o in outcomes if o.get('name') == game.get('home_team')), 1.8)
                            parsed_odds.append({"bookmaker": bm_title, "away_odds": a_odd, "home_odds": h_odd})
                    return parsed_odds
    except Exception: return None
    return None

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

    prob_away, prob_home, sim_away, sim_home, total_esperado, arr_away_runs, arr_home_runs = simular_monte_carlo(
        exp_runs_away, exp_runs_home, n_simulaciones
    )

    col1, col2, col3 = st.columns(3)
    col1.markdown(render_kpi_card(f"Prob. {away_name}", f"{prob_away:.1f}%", f"Proyección: {sim_away:.2f} Runs"), unsafe_allow_html=True)
    col2.markdown(render_kpi_card(f"Prob. {home_name}", f"{prob_home:.1f}%", f"Proyección: {sim_home:.2f} Runs"), unsafe_allow_html=True)
    col3.markdown(render_kpi_card("Total Esperado", f"{total_esperado:.2f}", f"Park Factor: {park_factor}x"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_montecarlo, tab_lineup, tab_bvp, tab_ev, tab_vivo = st.tabs([
        "🎲 MONTE CARLO", "🧮 LOG-5 DEEP ANALYTICS", "⚔️ ENCUENTROS PASADOS (BvP)", "💰 OPORTUNIDADES +EV", "🏟️ LIVE TRACKER"
    ])

    # --- TAB 1: MONTE CARLO ---
    with tab_montecarlo:
        st.subheader("📊 Comparativo de Abridores y Bullpen")
        df_pitchers = pd.DataFrame([
            {"Equipo": away_name, "Abridor": away_pitcher.get('fullName', 'Por anunciar'), "ERA": stats_p_away.get('era', '-'), "FIP": fip_away, "WHIP": stats_p_away.get('whip', '-'), "K% Proj.": f"{k_pct_away}%", "xK": f"{xk_away_pitcher}", "WHIP Bullpen": whip_bp_away},
            {"Equipo": home_name, "Abridor": home_pitcher.get('fullName', 'Por anunciar'), "ERA": stats_p_home.get('era', '-'), "FIP": fip_home, "WHIP": stats_p_home.get('whip', '-'), "K% Proj.": f"{k_pct_home}%", "xK": f"{xk_home_pitcher}", "WHIP Bullpen": whip_bp_home}
        ])
        st.dataframe(df_pitchers, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📈 Distribución Estocástica de Carreras (Monte Carlo Simulation)")
        
        df_dist = pd.DataFrame({
            f"Carreras {away_name}": pd.Series(arr_away_runs).value_counts(normalize=True).sort_index(),
            f"Carreras {home_name}": pd.Series(arr_home_runs).value_counts(normalize=True).sort_index()
        }).fillna(0) * 100

        st.bar_chart(df_dist, height=280)
        st.markdown(generar_dictamen_partido(away_name, home_name, exp_runs_away, exp_runs_home, prob_away, prob_home, total_esperado), unsafe_allow_html=True)

    # --- TAB 2: LOG-5 DEEP ANALYTICS ---
    with tab_lineup:
        st.markdown("### 🔬 Proyección Sabermétrica Avanzada e Indicadores Internos por Bateador")
        
        oppciones_log5 = [f"Titulares de {away_name} (Visita)", f"Titulares de {home_name} (Local)"]
        opción = st.radio("Alineación:", oppciones_log5, horizontal=True, key=f"log5_radio_{game_id}")
        
        es_away = (opción == oppciones_log5[0])
        id_equipo = away_id if es_away else home_id
        
        stats_p_rival = stats_p_home if es_away else stats_p_away
        pitcher_rival_obj = home_pitcher if es_away else away_pitcher
        pitcher_rival_name = pitcher_rival_obj.get('fullName', 'Abridor Rival')
        pitcher_rival_id = pitcher_rival_obj.get('id')
        
        pitcher_hand = (game_data.get('players', {}).get(f"ID{pitcher_rival_id}", {})
                        .get('pitchHand', {}).get('code', 'R'))
        
        lineup_titular, es_oficial = obtener_lineup_confirmado(feed, id_equipo, es_visitante=es_away)
        
        if es_oficial:
            st.success(f"✅ Alineación Confirmada Oficial vs {pitcher_rival_name} ({pitcher_hand})")
        else:
            st.info(f"📋 Alineación Proyectada del Roster vs {pitcher_rival_name} ({pitcher_hand})")

        baa_rival = parse_float(stats_p_rival.get('avg'), 0.245)
        ip_p_rival = parse_ip(stats_p_rival.get('inningsPitched'), 1.0)
        bf_p_rival = parse_float(stats_p_rival.get('battersFaced'), ip_p_rival * 4.1)
        
        k_rate_p_rival = (parse_float(stats_p_rival.get('strikeOuts'), 0) / bf_p_rival) if bf_p_rival > 0 else LEAGUE_K_RATE
        bb_rate_p_rival = (parse_float(stats_p_rival.get('baseOnBalls'), 0) / bf_p_rival) if bf_p_rival > 0 else LEAGUE_BB_RATE
        hr_rate_p_rival = (parse_float(stats_p_rival.get('homeRuns'), 0) / bf_p_rival) if bf_p_rival > 0 else LEAGUE_HR_RATE
        
        if lineup_titular:
            lineup_ids = [j['id'] for j in lineup_titular]
            dict_stats_batch, dict_bvp_batch = obtener_lineup_datos_batch(tuple(lineup_ids), pitcher_rival_id)
            
            res_lineup = []
            detalles_internos_jugadores = []

            for jug in lineup_titular:
                slot = jug['slot']
                j_id = jug['id']
                b_stats = dict_stats_batch.get(j_id, {})
                bvp_data = dict_bvp_batch.get(j_id, {'at_bats':0, 'hits':0, 'avg':0.0, 'ops':0.0, 'muestra_real':False})
                
                avg_b = parse_float(b_stats.get('avg'), 0.240)
                slg_b = parse_float(b_stats.get('slg'), 0.400)
                obp_b = parse_float(b_stats.get('obp'), 0.310)
                pa_b = parse_float(b_stats.get('plateAppearances'), 100)
                
                so_b = parse_float(b_stats.get('strikeOuts'), 0)
                bb_b = parse_float(b_stats.get('baseOnBalls'), 0)
                hr_b = parse_float(b_stats.get('homeRuns'), 0)
                
                if bvp_data.get('at_bats', 0) >= 8:
                    avg_b = (avg_b * 0.7) + (bvp_data['avg'] * 0.3)

                iso_b = round(max(0.0, slg_b - avg_b), 3)
                bb_k_ratio = round(bb_b / so_b, 2) if so_b > 0 else 0.0
                hr_per_pa = round((hr_b / pa_b) * 100, 2) if pa_b > 0 else 0.0
                
                k_rate_b = (so_b / pa_b) if pa_b > 0 else LEAGUE_K_RATE
                bb_rate_b = (bb_b / pa_b) if pa_b > 0 else LEAGUE_BB_RATE
                hr_rate_b = (hr_b / pa_b) if pa_b > 0 else LEAGUE_HR_RATE
                
                avg_split = avg_b + 0.012 if pitcher_hand == 'L' else avg_b
                
                prob_hit = calcular_log5_general(avg_split, baa_rival, LEAGUE_AVG)
                prob_k = calcular_log5_general(k_rate_b, k_rate_p_rival, LEAGUE_K_RATE)
                prob_bb = calcular_log5_general(bb_rate_b, bb_rate_p_rival, LEAGUE_BB_RATE)
                prob_hr = calcular_log5_general(hr_rate_b, hr_rate_p_rival, LEAGUE_HR_RATE) * park_factor
                
                pa_exp = PA_LINEUP_WEIGHTS.get(slot, 3.8)
                xH = prob_hit * pa_exp
                xHR = prob_hr * pa_exp
                xK = prob_k * pa_exp
                xBB = prob_bb * pa_exp
                xTB = (slg_b / avg_b * xH) if avg_b > 0 else xH * 1.5
                
                score_matchup = min(99, max(1, int((prob_hit * 120) + (iso_b * 100) + (bvp_data.get('ops', 0) * 15))))

                if prob_hr > 0.045: diag = "💣 Peligro HR (+EV)"
                elif prob_hit > 0.285: diag = "🔥 Prop Over Hits"
                elif prob_k > 0.280: diag = "🎯 Target de Ponche"
                elif prob_bb > 0.110: diag = "👁️ Disciplina Elite"
                else: diag = "🟡 Perfil Neutro"

                res_lineup.append({
                    "Orden": f"#{slot}",
                    "Bateador": jug['name'],
                    "Pos": jug['pos'],
                    "xPA": round(pa_exp, 1),
                    "Prob Hit/PA": prob_hit,
                    "xH (Hits)": round(xH, 2),
                    "xHR (Jonrones)": round(xHR, 2),
                    "xK (Ponches)": round(xK, 2),
                    "xBB (Bases)": round(xBB, 2),
                    "xTB (Totales)": round(xTB, 2),
                    "Diagnóstico Pro": diag
                })
                
                detalles_internos_jugadores.append({
                    "name": jug['name'], "slot": slot, "pos": jug['pos'], "avg": avg_b, "obp": obp_b, "slg": slg_b,
                    "iso": iso_b, "bb_k": bb_k_ratio, "hr_pa": hr_per_pa, "score": score_matchup, "bvp": bvp_data,
                    "xH": xH, "xHR": xHR, "xK": xK, "diag": diag
                })
            
            st.dataframe(
                pd.DataFrame(res_lineup),
                column_config={
                    "Prob Hit/PA": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=0.45),
                    "xHR (Jonrones)": st.column_config.NumberColumn(format="%.2f 💣"),
                    "xH (Hits)": st.column_config.NumberColumn(format="%.2f 🏏"),
                    "xK (Ponches)": st.column_config.NumberColumn(format="%.2f 🛑"),
                },
                use_container_width=True,
                hide_index=True
            )

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("🔍 Desglose de Fichas Técnicas e Indicadores Internos")
            
            for d in detalles_internos_jugadores:
                with st.expander(f"📌 #{d['slot']} {d['name']} ({d['pos']}) — Matchup Score: {d['score']}/100 — {d['diag']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("ISO (Poder Aislado)", f"{d['iso']:.3f}", "SLG - AVG (> .200 Elite)")
                    c2.metric("Ratio BB/K", f"{d['bb_k']}", "Disciplina (> 0.50 Buena)")
                    c3.metric("Frecuencia HR%", f"{d['hr_pa']}%", "HR por Aparición")
                    c4.metric("Hits Esperados (xH)", f"{d['xH']:.2f}", f"{d['xHR']:.2f} xHRs")

                    bvp_info = d['bvp']
                    if bvp_info.get('muestra_real'):
                        st.markdown(f"**Histórico BvP vs {pitcher_rival_name}:** {bvp_info['hits']} Hits en {bvp_info['at_bats']} ABs ({bvp_info['avg']:.3f} AVG) | {bvp_info['home_runs']} HR | {bvp_info['strikeouts']} K")
                    else:
                        st.caption(f"ℹ️ Sin enfrentamientos previos directos contra {pitcher_rival_name}. Proyección basada en Splits de la temporada.")

    # --- TAB 3: BvP ---
    with tab_bvp:
        st.markdown("### ⚔️ Análisis Histórico BvP: Historial de Carrera Frente a Frente (REST Directo MLB)")
        
        oppciones_bvp = [f"Bateadores de {away_name} (Visita)", f"Bateadores de {home_name} (Local)"]
        opcion_bvp = st.radio("Seleccionar Lineup de Ofensa:", oppciones_bvp, horizontal=True, key=f"bvp_radio_{game_id}")
        
        es_away_bvp = (opcion_bvp == oppciones_bvp[0])
        id_eq_bvp = away_id if es_away_bvp else home_id
        
        pitcher_obj = home_pitcher if es_away_bvp else away_pitcher
        pitcher_id_bvp = pitcher_obj.get('id')
        pitcher_nombre_bvp = pitcher_obj.get('fullName', 'Lanzador Abridor')
        
        pitcher_hand_bvp = (game_data.get('players', {}).get(f"ID{pitcher_id_bvp}", {})
                            .get('pitchHand', {}).get('code', 'R'))
        
        lineup_bvp, _ = obtener_lineup_confirmado(feed, id_eq_bvp, es_visitante=es_away_bvp)
        
        st.markdown(f"**Lanzador Frente a Frente:** `<span style='color:#38BDF8; font-weight:700;'>{pitcher_nombre_bvp} ({pitcher_hand_bvp})</span>`", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if lineup_bvp and pitcher_id_bvp:
            lineup_bvp_ids = [j['id'] for j in lineup_bvp]
            _, dict_bvp_bvp_tab = obtener_lineup_datos_batch(tuple(lineup_bvp_ids), pitcher_id_bvp)
            
            lista_bvp_resumen = []
            tot_ab, tot_hits, tot_ks, tot_bbs, tot_hrs = 0, 0, 0, 0, 0
            
            for jug in lineup_bvp:
                det = dict_bvp_bvp_tab.get(jug['id'], {'at_bats':0, 'hits':0, 'strikeouts':0, 'walks':0, 'home_runs':0, 'avg':0.0})
                ab, h, k, bb, hr = det['at_bats'], det['hits'], det['strikeouts'], det['walks'], det['home_runs']
                
                tot_ab += ab
                tot_hits += h
                tot_ks += k
                tot_bbs += bb
                tot_hrs += hr
                
                if ab > 0:
                    outs = max(0, ab - h - k)
                    max_val = max(h, k, bb, outs)
                    if max_val == k and k > 0: suceso_dominante = "🛑 Ponche (K Dominante)"
                    elif max_val == h and h > 0: suceso_dominante = "🏏 Hit (Contacto Efectivo)"
                    elif max_val == bb and bb > 0: suceso_dominante = "👁️ Boleto (Disciplina)"
                    else: suceso_dominante = "⚾ Out de Contacto"
                    estado_muestra = f"{det['avg']:.3f} AVG ({ab} ABs)"
                else:
                    b_stats_gen = obtener_stats_jugador(jug['id'], 'batting')
                    avg_gen = parse_float(b_stats_gen.get('avg'), 0.245)
                    suceso_dominante = f"⚡ Proyección Splits vs Pitcher {pitcher_hand_bvp}"
                    estado_muestra = f"{avg_gen:.3f} (Temp. Gen)"

                lista_bvp_resumen.append({
                    "Bateador": jug['name'],
                    "Pos": jug['pos'],
                    "Turnos (AB)": ab if ab > 0 else "0 (Sin H2H)",
                    "Hits (H)": h,
                    "Jonrones (HR)": hr,
                    "Ponches (K)": k,
                    "Boletos (BB)": bb,
                    "AVG / Muestra": estado_muestra,
                    "Diagnóstico / Tendencia": suceso_dominante
                })
            
            df_bvp_general = pd.DataFrame(lista_bvp_resumen)
            
            c_bvp1, c_bvp2, c_bvp3, c_bvp4 = st.columns(4)
            c_bvp1.markdown(render_kpi_card("Turnos H2H Totales", f"{tot_ab}", "Muestra de carrera"), unsafe_allow_html=True)
            c_bvp2.markdown(render_kpi_card("Hits Conectados", f"{tot_hits}", f"{tot_hrs} Jonrones en H2H"), unsafe_allow_html=True)
            c_bvp3.markdown(render_kpi_card("Ponches Recibidos", f"{tot_ks}", f"K Rate: {(tot_ks/tot_ab*100):.1f}%" if tot_ab>0 else "Sin K's directos"), unsafe_allow_html=True)
            c_bvp4.markdown(render_kpi_card("Boletos Sacados", f"{tot_bbs}", "Control en H2H"), unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📋 Matriz BvP (Servidor MLB REST Concurrente)")
            st.dataframe(df_bvp_general, use_container_width=True, hide_index=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("🔍 Inspección Profunda por Jugador")
            bateador_sel_nombre = st.selectbox(
                "Selecciona un Bateador para desglosar sus partidos pasados:", 
                [j['name'] for j in lineup_bvp],
                key=f"bvp_select_player_{game_id}"
            )
            
            jug_sel = next((j for j in lineup_bvp if j['name'] == bateador_sel_nombre), None)
            if jug_sel:
                det_sel = dict_bvp_bvp_tab.get(jug_sel['id'], {})
                col_i1, col_i2 = st.columns([1, 1.2])
                with col_i1:
                    st.markdown(f"""
                    <div style="background: #1E293B; padding: 20px; border-radius: 14px; border: 1px solid #334155;">
                        <h4 style="color: #38BDF8; margin-bottom: 10px;">Perfil BvP: {jug_sel['name']}</h4>
                        <p style="margin: 4px 0;"><b>Enfrentando a:</b> {pitcher_nombre_bvp}</p>
                        <p style="margin: 4px 0;"><b>Turnos Totales (AB):</b> {det_sel.get('at_bats', 0)}</p>
                        <p style="margin: 4px 0;"><b>Promedio (AVG):</b> {det_sel.get('avg', 0.0):.3f}</p>
                        <p style="margin: 4px 0;"><b>Porcentaje Embasado (OBP):</b> {det_sel.get('obp', 0.0):.3f}</p>
                        <p style="margin: 4px 0;"><b>Slugger (SLG):</b> {det_sel.get('slg', 0.0):.3f}</p>
                        <p style="margin: 4px 0; color: #00E676;"><b>OPS Totales:</b> {det_sel.get('ops', 0.0):.3f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with col_i2:
                    if det_sel.get('at_bats', 0) > 0:
                        df_chart_jug = pd.DataFrame({
                            "Resultado": ["Hits", "Ponches (K)", "Boletos (BB)", "Outs de Campo"],
                            "Cantidad": [det_sel['hits'], det_sel['strikeouts'], det_sel['walks'], max(0, det_sel['at_bats'] - det_sel['hits'] - det_sel['strikeouts'])]
                        }).set_index("Resultado")
                        
                        st.markdown("**Distribución Visual de Sucesos:**")
                        st.bar_chart(df_chart_jug, height=220)
                    else:
                        st.info("💡 Este bateador no registra ningún turno previo oficial en su carrera contra este abridor en Grandes Ligas.")

    # --- TAB 4: DETECTOR +EV ---
    with tab_ev:
        st.markdown("##### 💰 Análisis de Valor Esperado y Criterio de Kelly (Quarter-Kelly)")
        
        cuotas_api = obtener_cuotas_reales(odds_api_key, away_name, home_name)
        
        if cuotas_api:
            st.success("🟢 Cuotas extraídas en vivo mediante The-Odds-API")
            cuotas_activas = cuotas_api
        else:
            cuotas_activas = [
                {"bookmaker": "Pinnacle", "away_odds": 2.15, "home_odds": 1.75},
                {"bookmaker": "DraftKings", "away_odds": 2.05, "home_odds": 1.80},
                {"bookmaker": "FanDuel", "away_odds": 2.10, "home_odds": 1.78}
            ]
        
        filas_ev = []
        for item in cuotas_activas:
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
            
        df_ev_table = pd.DataFrame(filas_ev)
        st.dataframe(df_ev_table, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 📥 Exportar Registro de Apuestas / Tracker")
        csv_data = df_ev_table.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar Informe de Oportunidades +EV (.CSV)",
            data=csv_data,
            file_name=f"mlb_ev_tracker_{juegos[idx_juego]['game_id']}.csv",
            mime="text/csv"
        )

    # --- TAB 5: LIVE TRACKER ---
    with tab_vivo:
        st.subheader("🏟️ Monitoreo en Tiempo Real y Cajón de Bateo")
        
        detailed_state = game_data.get('status', {}).get('detailedState', juegos[idx_juego]['status'])
        is_live = any(x in detailed_state for x in ["In Progress", "Live", "Action"])
        is_final = any(x in detailed_state for x in ["Final", "Game Over", "Completed"])
        
        linescore = live_data.get('linescore', {})
        current_play = live_data.get('plays', {}).get('currentPlay', {})
        offense = linescore.get('offense', {})
        all_plays = live_data.get('plays', {}).get('allPlays', [])
        
        current_inning_num = linescore.get('currentInning', 1)
        inning_half = linescore.get('isTopInning', True)
        half_str = "Alta" if inning_half else "Baja"
        
        if is_live:
            badge_html = f"<span style='background:#EF4444; color:white; padding:6px 16px; border-radius:20px; font-weight:800; font-size:0.9rem;'>🔴 EN VIVO — Parte {half_str} del Inning {current_inning_num}</span>"
        elif is_final:
            badge_html = f"<span style='background:#3B82F6; color:white; padding:6px 16px; border-radius:20px; font-weight:800; font-size:0.9rem;'>🏁 PARTIDO FINALIZADO</span>"
        else:
            badge_html = f"<span style='background:#F59E0B; color:white; padding:6px 16px; border-radius:20px; font-weight:800; font-size:0.9rem;'>⏰ STATUS: {detailed_state.upper()}</span>"
            
        st.markdown(f"**Estado del Encuentro:** {badge_html}", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        c_campo, c_info = st.columns([1, 1.8])
        
        with c_campo:
            st.markdown(generar_campo_svg_moderno(offense), unsafe_allow_html=True)
            
        with c_info:
            if current_play:
                matchup = current_play.get('matchup', {})
                count = current_play.get('count', {})
                
                batter_name = matchup.get('batter', {}).get('fullName', 'En espera')
                batter_side = matchup.get('batSide', {}).get('code', '-')
                pitcher_name = matchup.get('pitcher', {}).get('fullName', 'En espera')
                pitcher_hand = matchup.get('pitchHand', {}).get('code', '-')
                
                balls, strikes, outs = count.get('balls', 0), count.get('strikes', 0), count.get('outs', 0)
                ult_descripcion = current_play.get('result', {}).get('description', 'Turno en desarrollo...')
                
                bases = []
                if offense.get('first'): bases.append("1B")
                if offense.get('second'): bases.append("2B")
                if offense.get('third'): bases.append("3B")
                corredores_str = ", ".join(bases) if bases else "Bases Limpias"
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 22px; border-radius: 16px; border: 1px solid #38BDF8; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                    <div style="color: #38BDF8; font-size: 0.8rem; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px;">⚡ Cajón de Bateo Activo</div>
                    <div style="font-size: 1.35rem; font-weight: 800; color: #FFF; margin-top: 8px;">🏏 Bateando: {batter_name} <span style="color:#00E676; font-size:0.9rem;">[{batter_side}]</span></div>
                    <div style="font-size: 1.05rem; font-weight: 600; color: #CBD5E1; margin-top: 2px;">⚾ Lanzando: {pitcher_name} <span style="color:#38BDF8; font-size:0.85rem;">[{pitcher_hand}]</span></div>
                    <hr style="border-color: #334155; margin: 14px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; background: #0F172A; padding: 10px 15px; border-radius: 10px;">
                        <div style="font-size: 1.15rem; font-weight: 800; color: #00E676;">
                            Conteo: {balls}-{strikes} | {outs} Outs
                        </div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #E2E8F0;">
                            🏃 {corredores_str}
                        </div>
                    </div>
                    <div style="font-size: 0.88rem; color: #94A3B8; margin-top: 12px; font-style: italic;">
                        <b>Última Acción:</b> {ult_descripcion}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                datos_contacto = extraer_contacto_statcast(current_play)
                if datos_contacto:
                    st.markdown("<br>", unsafe_allow_html=True)
                    color_borde = "#00E676" if datos_contacto['hubo_contacto'] else "#38BDF8"
                    
                    vel_salida = f"{datos_contacto['exit_velocity']} mph" if datos_contacto['exit_velocity'] else "Procesando Statcast..."
                    angulo_despegue = f"{datos_contacto['launch_angle']}°" if datos_contacto['launch_angle'] is not None else "N/A"
                    distancia = f"{datos_contacto['distance']} ft" if datos_contacto['distance'] else "N/A"
                    
                    st.markdown(f"""
                    <div style="background: #0F172A; border: 1px solid {color_borde}; padding: 18px; border-radius: 14px;">
                        <div style="color: {color_borde}; font-size: 0.85rem; font-weight: 800; text-transform: uppercase;">🔥 Detector de Contacto (Statcast en Vivo)</div>
                        <div style="font-size: 1.1rem; font-weight: 800; color: #FFF; margin-top: 4px;">{datos_contacto['tipo_contacto']}</div>
                        <div style="display: flex; justify-content: space-between; margin-top: 10px; color: #CBD5E1; font-size: 0.9rem;">
                            <span>⚡ <b>Vel. Salida:</b> {vel_salida}</span>
                            <span>📐 <b>Ángulo:</b> {angulo_despegue}</span>
                            <span>📏 <b>Distancia:</b> {distancia}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-top: 6px; color: #CBD5E1; font-size: 0.9rem;">
                            <span>⚾ <b>Pitcheo:</b> {datos_contacto['pitch_type']} ({datos_contacto['pitch_speed']} mph)</span>
                            <span>🚀 <b>Trayectoria:</b> {datos_contacto['trajectory']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("💡 Esperando el inicio del primer turno del partido para desplegar el cajón activo.")

        if all_plays:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📜 Historial Jugada por Jugada (Play-by-Play por Inning)")
            
            innings_presentes = sorted(list(set([p.get('about', {}).get('inning', 1) for p in all_plays])))
            
            if innings_presentes:
                inn_selec_str = st.selectbox(
                    "Selecciona Inning a consultar:", 
                    [f"Inning {i}" for i in innings_presentes], 
                    index=len(innings_presentes)-1, 
                    key=f"pbp_select_inn_{game_id}"
                )
                
                num_inn_sel = int(inn_selec_str.split(" ")[1])
                jugadas_inn = [p for p in all_plays if p.get('about', {}).get('inning') == num_inn_sel]
                
                jugadas_top = [p for p in jugadas_inn if p.get('about', {}).get('halfInning') == 'top']
                jugadas_bot = [p for p in jugadas_inn if p.get('about', {}).get('halfInning') == 'bottom']
                
                col_top, col_bot = st.columns(2)
                
                with col_top:
                    st.markdown(f"##### 🔺 Alta del Inning {num_inn_sel} ({away_name} Batea)")
                    if jugadas_top:
                        for p in jugadas_top:
                            bat_p = p.get('matchup', {}).get('batter', {}).get('fullName', 'Bateador')
                            desc_p = p.get('result', {}).get('description', '')
                            evt_p = p.get('result', {}).get('event', '')
                            rbi_p = p.get('result', {}).get('rbi', 0)
                            rbi_tag = f" 🏆 +{rbi_p} RBI" if rbi_p > 0 else ""
                            
                            st.markdown(f"""
                            <div style="background:#1E293B; border-left:4px solid #38BDF8; padding:10px 14px; margin-bottom:8px; border-radius:8px;">
                                <div style="font-weight:700; color:#F8FAFC;">🏏 {bat_p} <span style="color:#00E676; font-size:0.85rem;">[{evt_p}]{rbi_tag}</span></div>
                                <div style="font-size:0.85rem; color:#CBD5E1; margin-top:3px;">{desc_p}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else: st.caption("Sin turnos registrados en la Parte Alta.")
                        
                with col_bot:
                    st.markdown(f"##### 🔻 Baja del Inning {num_inn_sel} ({home_name} Batea)")
                    if jugadas_bot:
                        for p in jugadas_bot:
                            bat_p = p.get('matchup', {}).get('batter', {}).get('fullName', 'Bateador')
                            desc_p = p.get('result', {}).get('description', '')
                            evt_p = p.get('result', {}).get('event', '')
                            rbi_p = p.get('result', {}).get('rbi', 0)
                            rbi_tag = f" 🏆 +{rbi_p} RBI" if rbi_p > 0 else ""
                            
                            st.markdown(f"""
                            <div style="background:#1E293B; border-left:4px solid #00E676; padding:10px 14px; margin-bottom:8px; border-radius:8px;">
                                <div style="font-weight:700; color:#F8FAFC;">🏏 {bat_p} <span style="color:#38BDF8; font-size:0.85rem;">[{evt_p}]{rbi_tag}</span></div>
                                <div style="font-size:0.85rem; color:#CBD5E1; margin-top:3px;">{desc_p}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else: st.caption("Sin turnos registrados en la Parte Baja.")

        entradas_lista = linescore.get('innings', [])
        if entradas_lista:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📊 Marcador de Entradas (Linescore)")
            tabla_innings = [
                {
                    "Inning": inn.get('num'),
                    f"{away_name}": inn.get('away', {}).get('runs', '-'),
                    f"{home_name}": inn.get('home', {}).get('runs', '-')
                }
                for inn in entradas_lista
            ]
            st.dataframe(pd.DataFrame(tabla_innings), use_container_width=True, hide_index=True)
            
            teams = linescore.get('teams', {})
            away_totals, home_totals = teams.get('away', {}), teams.get('home', {})
            
            c_tot1, c_tot2 = st.columns(2)
            c_tot1.metric(f"Total {away_name}", f"R: {away_totals.get('runs', 0)} | H: {away_totals.get('hits', 0)} | E: {away_totals.get('errors', 0)}")
            c_tot2.metric(f"Total {home_name}", f"R: {home_totals.get('runs', 0)} | H: {home_totals.get('hits', 0)} | E: {home_totals.get('errors', 0)}")

# AUTO-REFRESH
if auto_refresh:
    time.sleep(10)
    st.rerun()
