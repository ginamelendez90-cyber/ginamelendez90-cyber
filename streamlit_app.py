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

# --- TABLA ESTÁTICA DE PARK FACTORS Y CONSTANTES ---
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

PA_LINEUP_WEIGHTS = {1: 4.6, 2: 4.5, 3: 4.4, 4: 4.3, 5: 4.2, 6: 4.1, 7: 4.0, 8: 3.9, 9: 3.8}
LEAGUE_K_RATE = 0.225

# --- BARRA LATERAL DE CONFIGURACIÓN ---
st.sidebar.header("⚙️ Panel de Control Sabermétrico")
fecha_seleccionada = st.sidebar.date_input("Fecha de Análisis:", datetime.today())
n_simulaciones = st.sidebar.slider("Simulaciones Monte Carlo:", min_value=1000, max_value=25000, value=10000, step=1000)
ajuste_fatiga_bp = st.sidebar.checkbox("Penalización por Fatiga de Bullpen (>1.30 WHIP)", value=True)

st.sidebar.markdown("---")
st.sidebar.header("🔄 Actualización en Vivo")
auto_refresh = st.sidebar.toggle("Auto-refresh cada 10s", value=False)

st.sidebar.markdown("---")
st.sidebar.header("🔑 Conexión a Casas de Apuestas")
odds_api_key = st.sidebar.text_input("The Odds API Key:", type="password")

# --- FUNCIONES AUXILIARES Y DIBUJO DE CAMPO EN SVG ---
def parse_float(val, default=0.0):
    try:
        if val is None or val == '' or val == '-':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def generar_campo_svg(offense_dict):
    """Genera un gráfico dinámico SVG del diamante de béisbol con corredores en base"""
    c_1b = "#ECC94B" if offense_dict.get('first') else "#CBD5E0"  # Amarillo si ocupada, gris si vacía
    c_2b = "#ECC94B" if offense_dict.get('second') else "#CBD5E0"
    c_3b = "#ECC94B" if offense_dict.get('third') else "#CBD5E0"
    
    svg = f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 10px;">
        <svg width="260" height="240" viewBox="0 0 260 240" style="background-color: #1A202C; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <!-- Grama exterior -->
            <path d="M 130 210 L 230 110 A 130 130 0 0 0 30 110 Z" fill="#2F855A" stroke="#276749" stroke-width="3"/>
            <!-- Tierra del cuadro interior -->
            <polygon points="130,200 200,130 130,60 60,130" fill="#9C4221" stroke="#FFFFFF" stroke-width="1.5"/>
            <!-- Líneas de Cal -->
            <line x1="130" y1="200" x2="225" y2="105" stroke="#FFFFFF" stroke-width="2"/>
            <line x1="130" y1="200" x2="35" y2="105" stroke="#FFFFFF" stroke-width="2"/>
            <!-- Malla / Loma del Pitcher -->
            <circle cx="130" cy="130" r="10" fill="#C05621" stroke="#FFFFFF" stroke-width="1"/>
            <rect x="126" y="128" width="8" height="4" fill="#FFFFFF"/>
            <!-- Bases (1B, 2B, 3B) -->
            <!-- 1B -->
            <rect x="193" y="123" width="14" height="14" transform="rotate(45 200 130)" fill="{c_1b}" stroke="#FFFFFF" stroke-width="2"/>
            <!-- 2B -->
            <rect x="123" y="53" width="14" height="14" transform="rotate(45 130 60)" fill="{c_2b}" stroke="#FFFFFF" stroke-width="2"/>
            <!-- 3B -->
            <rect x="53" y="123" width="14" height="14" transform="rotate(45 60 130)" fill="{c_3b}" stroke="#FFFFFF" stroke-width="2"/>
            <!-- Home Plate -->
            <polygon points="130,195 135,200 135,205 125,205 125,200" fill="#FFFFFF"/>
            <!-- Etiquetas -->
            <text x="218" y="135" fill="#FFFFFF" font-size="11" font-weight="bold">1B</text>
            <text x="130" y="45" fill="#FFFFFF" font-size="11" font-weight="bold" text-anchor="middle">2B</text>
            <text x="35" y="135" fill="#FFFFFF" font-size="11" font-weight="bold">3B</text>
        </svg>
    </div>
    """
    return svg

def calcular_fip(stats):
    if not stats:
        return 4.20
    ip = parse_float(stats.get('inningsPitched'), 0.0)
    if ip <= 0:
        return parse_float(stats.get('era'), 4.20)
    
    hr = parse_float(stats.get('homeRuns'), 0)
    bb = parse_float(stats.get('baseOnBalls'), 0)
    hbp = parse_float(stats.get('hitByPitch'), 0)
    k = parse_float(stats.get('strikeOuts'), 0)
    
    return round((((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / ip) + 3.10, 2)

def calcular_xk_pitcher(stats_pitcher, team_k_rate=0.225, projected_bf=22):
    if not stats_pitcher:
        return 4.5, 22.5
    
    k = parse_float(stats_pitcher.get('strikeOuts'), 0)
    bf = parse_float(stats_pitcher.get('battersFaced'), 0)
    
    if bf > 0:
        k_rate_pitcher = k / bf
    else:
        ip = parse_float(stats_pitcher.get('inningsPitched'), 0)
        k9 = parse_float(stats_pitcher.get('strikeOutsPer9Innings'), 8.5)
        k_rate_pitcher = (k9 / 9.0) / 4.0 if ip > 0 else 0.225

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

def calcular_ev(prob_modelo_pct, cuota_decimal):
    prob_decimal = prob_modelo_pct / 100.0
    return round(((prob_decimal * cuota_decimal) - 1) * 100, 2)

# --- CACHÉ Y CONSULTAS DE APIS ---
@st.cache_data(ttl=120)
def obtener_calendario(fecha):
    return statsapi.schedule(date=fecha.strftime('%Y-%m-%d'))

@st.cache_data(ttl=10)
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

@st.cache_data(ttl=900)
def obtener_cuotas_mlb_api(api_key, region="us"):
    if not api_key:
        return None
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {'apiKey': api_key, 'regions': region, 'markets': 'h2h', 'oddsFormat': 'decimal'}
    try:
        res = requests.get(url, params=params)
        return res.json() if res.status_code == 200 else None
    except Exception:
        return None

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

    stats_p_away = obtener_stats_jugador(away_pitcher.get('id'), 'pitching') if away_pitcher.get('id') else {}
    stats_p_home = obtener_stats_jugador(home_pitcher.get('id'), 'pitching') if home_pitcher.get('id') else {}
    
    fip_away = calcular_fip(stats_p_away)
    fip_home = calcular_fip(stats_p_home)
    
    xk_away_pitcher, k_pct_away = calcular_xk_pitcher(stats_p_away)
    xk_home_pitcher, k_pct_home = calcular_xk_pitcher(stats_p_home)

    whip_bp_away = obtener_whip_bullpen(away_id)
    whip_bp_home = obtener_whip_bullpen(home_id)

    venue_name = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
    park_factor = PARK_FACTORS.get(venue_name, 1.00)

    # CREACIÓN DE PESTAÑAS
    tab_montecarlo, tab_lineup, tab_ev, tab_vivo = st.tabs([
        "🎲 SIMULACIÓN MONTE CARLO", 
        "🧮 LOG-5 & PLATOON SPLITS", 
        "💰 DETECTOR +EV (APUESTAS)",
        "📈 TRANSMISIÓN EN VIVO"
    ])

    exp_runs_away = round((4.5 * (fip_home / 4.10)) * park_factor, 2)
    exp_runs_home = round((4.5 * (fip_away / 4.10)) * park_factor, 2)

    if ajuste_fatiga_bp:
        if whip_bp_home > 1.30: exp_runs_away += 0.25
        if whip_bp_away > 1.30: exp_runs_home += 0.25

    prob_away, prob_home, sim_away, sim_home, total_esperado = simular_monte_carlo(
        exp_runs_away, exp_runs_home, n_simulaciones
    )

    # --- TAB 1: MONTE CARLO ---
    with tab_montecarlo:
        st.header("🎰 Proyección del Partido y Simulación Estocástica")
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Prob. Victoria {away_name}", f"{prob_away:.1f}%", f"Proj: {sim_away:.2f} R")
        c2.metric(f"Prob. Victoria {home_name}", f"{prob_home:.1f}%", f"Proj: {sim_home:.2f} R")
        c3.metric("Línea Total de Carreras", f"{total_esperado:.2f} Carreras", f"Park Factor: {park_factor}x")

        st.markdown("---")
        st.subheader("📊 Comparativo de Pitcheo y Ponches Esperados (xK)")
        
        df_pitchers = pd.DataFrame([
            {
                "Equipo": away_name,
                "Abridor": away_pitcher.get('fullName', 'Por anunciar'),
                "ERA": stats_p_away.get('era', '-'),
                "FIP": fip_away,
                "WHIP Abridor": stats_p_away.get('whip', '-'),
                "K% Proyectado": f"{k_pct_away}%",
                "Ponches Esperados (xK)": f"🔥 {xk_away_pitcher} Ks",
                "WHIP Bullpen": whip_bp_away
            },
            {
                "Equipo": home_name,
                "Abridor": home_pitcher.get('fullName', 'Por anunciar'),
                "ERA": stats_p_home.get('era', '-'),
                "FIP": fip_home,
                "WHIP Abridor": stats_p_home.get('whip', '-'),
                "K% Proyectado": f"{k_pct_home}%",
                "Ponches Esperados (xK)": f"🔥 {xk_home_pitcher} Ks",
                "WHIP Bullpen": whip_bp_home
            }
        ])
        st.table(df_pitchers)

    # --- TAB 2: LOG-5 & LINEUP ---
    with tab_lineup:
        st.header("🧮 Algoritmo Log-5 con Platoon Splits y Proyección por Bateador")
        
        opcion_lineup = st.radio("Selecciona Ofensiva a Proyectar:", (f"Bateadores de {away_name}", f"Bateadores de {home_name}"))
        es_away = away_name in opcion_lineup
        
        id_equipo = away_id if es_away else home_id
        stats_pitcher_rival = stats_p_home if es_away else stats_p_away
        pitcher_hand = (game_data.get('players', {}).get(f"ID{home_pitcher.get('id') if es_away else away_pitcher.get('id')}", {})
                        .get('pitchHand', {}).get('code', 'R'))
        
        roster_json = obtener_roster_estructurado(id_equipo)
        baa_rival = parse_float(stats_pitcher_rival.get('avg'), 0.245)
        
        k_pitcher_rival = parse_float(stats_pitcher_rival.get('strikeOuts'), 0)
        bf_pitcher_rival = parse_float(stats_pitcher_rival.get('battersFaced'), 1)
        k_rate_p_rival = (k_pitcher_rival / bf_pitcher_rival) if bf_pitcher_rival > 0 else 0.225
        
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
                    so_b = parse_float(b_stats.get('strikeOuts'), 0)
                    pa_b = parse_float(b_stats.get('plateAppearances'), 1)
                    k_rate_b = (so_b / pa_b) if pa_b > 0 else 0.225
                    
                    if avg_b > 0.0:
                        avg_b_split = avg_b + 0.012 if pitcher_hand == 'L' else avg_b
                        num_h = (avg_b_split * baa_rival) / 0.245
                        den_h = num_h + ((1 - avg_b_split) * (1 - baa_rival) / (1 - 0.245))
                        prob_hit = num_h / den_h if den_h > 0 else 0.0
                        
                        num_k = (k_rate_b * k_rate_p_rival) / LEAGUE_K_RATE
                        den_k = num_k + ((1 - k_rate_b) * (1 - k_rate_p_rival) / (1 - LEAGUE_K_RATE))
                        prob_k = num_k / den_k if den_k > 0 else 0.225
                        
                        pa_esperadas = PA_LINEUP_WEIGHTS.get(slot, 3.8)
                        hits_esperados = prob_hit * pa_esperadas
                        ks_esperados = prob_k * pa_esperadas
                        
                        lista_predicciones.append({
                            "Lineup Spot": f"#{slot}" if slot <= 9 else "Banca",
                            "Bateador": nombre,
                            "Pos": pos,
                            "AVG Base": f".{int(round(avg_b * 1000)):03d}",
                            "Prob Hit/PA": f"{prob_hit * 100:.1f}%",
                            "Hits Esperados (xH)": round(hits_esperados, 2),
                            "Prob K/PA": f"{prob_k * 100:.1f}%",
                            "Ponches Esperados (xK)": round(ks_esperados, 2),
                            "Diagnóstico Pro": "🟢 Alta Ventaja" if prob_hit > 0.270 else "🟡 Neutro" if prob_hit > 0.240 else "🔴 Desventaja"
                        })
                        slot += 1
            
            if lista_predicciones:
                st.dataframe(pd.DataFrame(lista_predicciones), use_container_width=True, hide_index=True)
            else:
                st.info("No hay suficientes datos registrados de turnos al bate.")
        else:
            st.error("No se pudo cargar el Roster.")

    # --- TAB 3: DETECTOR DE APUESTAS +EV ---
    with tab_ev:
        st.header("💰 Detector de Apuestas con Valor Esperado (+EV)")
        st.markdown("Compara las probabilidades del algoritmo Monte Carlo contra las cuotas automáticas en tiempo real.")

        cuotas_raw = obtener_cuotas_mlb_api(odds_api_key) if odds_api_key else None
        
        if not cuotas_raw:
            st.info("💡 **Modo Demo**: Ingresa tu *Odds API Key* en el panel lateral para conectar las casas de apuestas en tiempo real. Mostrando datos proyectados de demostración:")
            cuotas_lista = [
                {"bookmaker": "Pinnacle", "away_odds": 2.15, "home_odds": 1.75},
                {"bookmaker": "DraftKings", "away_odds": 2.05, "home_odds": 1.80},
                {"bookmaker": "FanDuel", "away_odds": 2.10, "home_odds": 1.78},
                {"bookmaker": "BetMGM", "away_odds": 2.00, "home_odds": 1.85}
            ]
        else:
            cuotas_lista = []
            for juego in cuotas_raw:
                if away_name.lower() in juego.get('away_team', '').lower() or home_name.lower() in juego.get('home_team', '').lower():
                    for bm in juego.get('bookmakers', []):
                        odds_h2h = {}
                        for m in bm.get('markets', []):
                            if m.get('key') == 'h2h':
                                for out in m.get('outcomes', []):
                                    if away_name.lower() in out.get('name', '').lower():
                                        odds_h2h['away'] = out.get('price')
                                    else:
                                        odds_h2h['home'] = out.get('price')
                        if 'away' in odds_h2h and 'home' in odds_h2h:
                            cuotas_lista.append({
                                "bookmaker": bm.get('title'),
                                "away_odds": odds_h2h['away'],
                                "home_odds": odds_h2h['home']
                            })

        if cuotas_lista:
            filas_ev = []
            for item in cuotas_lista:
                ev_away = calcular_ev(prob_away, item['away_odds'])
                ev_home = calcular_ev(prob_home, item['home_odds'])
                
                filas_ev.append({
                    "Casa de Apuestas": item['bookmaker'],
                    f"Cuota {away_name}": item['away_odds'],
                    f"EV {away_name}": f"{ev_away:+.2f}%",
                    f"Diagnóstico {away_name}": f"🚀 +EV (+{ev_away:.1f}%)" if ev_away > 2.0 else "❌ Sin Valor",
                    f"Cuota {home_name}": item['home_odds'],
                    f"EV {home_name}": f"{ev_home:+.2f}%",
                    f"Diagnóstico {home_name}": f"🚀 +EV (+{ev_home:.1f}%)" if ev_home > 2.0 else "❌ Sin Valor"
                })

            st.dataframe(pd.DataFrame(filas_ev), use_container_width=True, hide_index=True)
        else:
            st.warning("No se encontraron cuotas disponibles en la API para este encuentro en este momento.")

        # --- TAB 4: TRANSMISIÓN Y MONITOR EN VIVO CON DIAGRAMA DE CAMPO ---
    with tab_vivo:
        st.header("🏟️ Transmisión y Monitoreo en Tiempo Real")
        st.metric("Estado del Partido", juegos[idx_juego]['status'])
        
        linescore = live_data.get('linescore', {})
        plays = live_data.get('plays', {})
        current_play = plays.get('currentPlay', {})
        offense = linescore.get('offense', {})
        
        # 1. SIMULACIÓN VISUAL DEL CAMPO DE BÉISBOL (DIAMANTE DINÁMICO SVG)
        st.subheader("📌 Ubicación en el Campo de Juego (Live Diamond)")
        col_campo, col_datos = st.columns([1, 2])
        
        with col_campo:
            # Dibuja el gráfico SVG con las bases encendidas en amarillo si hay corredor
            st.markdown(generar_campo_svg(offense), unsafe_allow_html=True)
            
        with col_datos:
            if current_play:
                matchup = current_play.get('matchup', {})
                count = current_play.get('count', {})
                
                batter_name = matchup.get('batter', {}).get('fullName', 'En espera')
                batter_side = matchup.get('batSide', {}).get('code', '-')
                pitcher_name = matchup.get('pitcher', {}).get('fullName', 'En espera')
                pitcher_hand = matchup.get('pitchHand', {}).get('code', '-')
                
                balls, strikes, outs = count.get('balls', 0), count.get('strikes', 0), count.get('outs', 0)
                
                bases = []
                if offense.get('first'): bases.append("1B")
                if offense.get('second'): bases.append("2B")
                if offense.get('third'): bases.append("3B")
                corredores_str = ", ".join(bases) if bases else "Bases Limpias"
                
                st.markdown("### ⚡ Duelo Actual en el Cajón")
                c_d1, c_d2 = st.columns(2)
                c_d1.metric("Bateador en Turno", batter_name, f"Lado: {batter_side}")
                c_d2.metric("Pitcher en la Loma", pitcher_name, f"Mano: {pitcher_hand}")
                
                c_d3, c_d4 = st.columns(2)
                c_d3.metric("Conteo y Outs", f"⚾ {balls}-{strikes} | 🛑 {outs} Outs")
                c_d4.metric("Corredores en Base", corredores_str)

        st.markdown("---")

        # 2. LINESCORE (MARCADOR POR ENTRADAS)
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
            st.subheader("📊 Tablero por Entradas (Linescore)")
            st.dataframe(pd.DataFrame(tabla_innings), use_container_width=True, hide_index=True)
            
            teams = linescore.get('teams', {})
            away_totals, home_totals = teams.get('away', {}), teams.get('home', {})
            
            c_tot1, c_tot2 = st.columns(2)
            c_tot1.metric(f"Total {away_name}", f"R: {away_totals.get('runs', 0)} | H: {away_totals.get('hits', 0)} | E: {away_totals.get('errors', 0)}")
            c_tot2.metric(f"Total {home_name}", f"R: {home_totals.get('runs', 0)} | H: {home_totals.get('hits', 0)} | E: {home_totals.get('errors', 0)}")
            
            # 3. RESUMEN DE ACTUACIÓN POR JUGADOR (NUEVA SECCIÓN)
            all_plays = plays.get('allPlays', [])
            if all_plays:
                st.markdown("---")
                st.subheader("🎯 Rendimiento Detallado de Jugadores")
                
                resumen_bateadores = {}
                resumen_pitchers = {}
                
                # Iterar sobre las jugadas para extraer el historial individual
                for p in all_plays:
                    match = p.get('matchup', {})
                    res = p.get('result', {})
                    about = p.get('about', {})
                    
                    evento = res.get('event')
                    # Solo tomamos eventos que registraron un resultado final en el turno
                    if not evento:
                        continue
                        
                    batter = match.get('batter', {}).get('fullName', 'N/A')
                    pitcher = match.get('pitcher', {}).get('fullName', 'N/A')
                    inning = about.get('inning', '-')
                    
                    # Agrupar historial de bateo
                    if batter != 'N/A':
                        if batter not in resumen_bateadores:
                            resumen_bateadores[batter] = []
                        resumen_bateadores[batter].append(f"In{inning}: {evento}")
                        
                    # Agrupar historial de pitcheo
                    if pitcher != 'N/A':
                        if pitcher not in resumen_pitchers:
                            resumen_pitchers[pitcher] = []
                        # Para el pitcher, agregamos qué bateador enfrentó y el resultado
                        resumen_pitchers[pitcher].append(f"In{inning} vs {batter}: {evento}")

                # Mostrar las tablas lado a lado
                col_bat, col_pit = st.columns(2)
                
                with col_bat:
                    st.markdown("#### 🏏 Bateadores")
                    if resumen_bateadores:
                        df_batters = pd.DataFrame([
                            {"Bateador": b, "Apariciones": len(evs), "Secuencia de Eventos": " ➔ ".join(evs)}
                            for b, evs in resumen_bateadores.items()
                        ])
                        st.dataframe(df_batters, use_container_width=True, hide_index=True)
                    else:
                        st.info("Aún no hay registros de bateo.")
                        
                with col_pit:
                    st.markdown("#### ⚾ Lanzadores")
                    if resumen_pitchers:
                        df_pitchers = pd.DataFrame([
                            {"Lanzador": p, "Bateadores Enfrentados": len(evs), "Resultados Provocados": " ➔ ".join(evs)}
                            for p, evs in resumen_pitchers.items()
                        ])
                        st.dataframe(df_pitchers, use_container_width=True, hide_index=True)
                    else:
                        st.info("Aún no hay registros de pitcheo.")

                # 4. BITÁCORA PLAY-BY-PLAY (Movida al final)
                st.markdown("---")
                st.subheader("📜 Registro Jugada por Jugada (Play-by-Play)")
                
                lista_pbp = []
                for p in reversed(all_plays):
                    about = p.get('about', {})
                    res = p.get('result', {})
                    match = p.get('matchup', {})
                    
                    inning_num = about.get('inning', '')
                    half = "Alta" if about.get('halfInning') == 'top' else "Baja"
                    
                    lista_pbp.append({
                        "Entrada": f"{half} {inning_num}",
                        "Bateador": match.get('batter', {}).get('fullName', 'N/A'),
                        "Pitcher": match.get('pitcher', {}).get('fullName', 'N/A'),
                        "Resultado": res.get('event', 'N/A'),
                        "Descripción Completa": res.get('description', '')
                    })
                
                st.dataframe(pd.DataFrame(lista_pbp), use_container_width=True, hide_index=True)
        else:
            st.info("El partido seleccionado aún no inicia o no hay datos de jugadas registrados.")


# --- BUCLE DE AUTO-REFRESH (10 SEGUNDOS) ---
if auto_refresh:
    time.sleep(10)
    st.rerun()
