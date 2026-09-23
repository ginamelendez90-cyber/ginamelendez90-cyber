import streamlit as st
import pandas as pd
import numpy as np
import statsapi
import requests
import time
from datetime import datetime

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="MLB Pro Match Odds & Live Tracker", layout="wide", page_icon="⚾")

# Inicializar el historial de apuestas de partido en la sesión de Streamlit
if 'mis_apuestas' not in st.session_state:
    st.session_state.mis_apuestas = []

st.title("🚀 Tracker y Analizador de Apuestas de Partido MLB")
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

# --- FUNCIONES AUXILIARES Y EVALUACIÓN EXCLUSIVA DE APUESTAS DE PARTIDO ---
def parse_float(val, default=0.0):
    try:
        if val is None or val == '' or val == '-':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def generar_campo_svg(offense_dict, hit_x=None, hit_y=None):
    """Genera un gráfico dinámico SVG del diamante de béisbol con corredores y punto de caída del batazo"""
    c_1b = "#ECC94B" if offense_dict.get('first') else "#CBD5E0"
    c_2b = "#ECC94B" if offense_dict.get('second') else "#CBD5E0"
    c_3b = "#ECC94B" if offense_dict.get('third') else "#CBD5E0"
    
    marcador_batazo = ""
    if hit_x is not None and hit_y is not None:
        try:
            svg_x = (float(hit_x) / 250.0) * 260.0
            svg_y = (float(hit_y) / 250.0) * 240.0
            marcador_batazo = f"""
            <circle cx="{svg_x}" cy="{svg_y}" r="4" fill="#E53E3E" stroke="#FFFFFF" stroke-width="1.5">
                <animate attributeName="r" values="3;6;3" dur="1.5s" repeatCount="indefinite" />
            </circle>
            """
        except (ValueError, TypeError):
            pass

    return f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 10px;">
        <svg width="260" height="240" viewBox="0 0 260 240" style="background-color: #1A202C; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
            <path d="M 130 210 L 230 110 A 130 130 0 0 0 30 110 Z" fill="#2F855A" stroke="#276749" stroke-width="3"/>
            <polygon points="130,200 200,130 130,60 60,130" fill="#9C4221" stroke="#FFFFFF" stroke-width="1.5"/>
            <line x1="130" y1="200" x2="225" y2="105" stroke="#FFFFFF" stroke-width="2"/>
            <line x1="130" y1="200" x2="35" y2="105" stroke="#FFFFFF" stroke-width="2"/>
            <circle cx="130" cy="130" r="10" fill="#C05621" stroke="#FFFFFF" stroke-width="1"/>
            <rect x="126" y="128" width="8" height="4" fill="#FFFFFF"/>
            <rect x="193" y="123" width="14" height="14" transform="rotate(45 200 130)" fill="{c_1b}" stroke="#FFFFFF" stroke-width="2"/>
            <rect x="123" y="53" width="14" height="14" transform="rotate(45 130 60)" fill="{c_2b}" stroke="#FFFFFF" stroke-width="2"/>
            <rect x="53" y="123" width="14" height="14" transform="rotate(45 60 130)" fill="{c_3b}" stroke="#FFFFFF" stroke-width="2"/>
            <polygon points="130,195 135,200 135,205 125,205 125,200" fill="#FFFFFF"/>
            <text x="218" y="135" fill="#FFFFFF" font-size="11" font-weight="bold">1B</text>
            <text x="130" y="45" fill="#FFFFFF" font-size="11" font-weight="bold" text-anchor="middle">2B</text>
            <text x="35" y="135" fill="#FFFFFF" font-size="11" font-weight="bold">3B</text>
            {marcador_batazo}
        </svg>
    </div>
    """

def evaluar_apuesta_partido(apuesta, live_data, status_juego):
    """Evalúa exclusivamente líneas de PARTIDO (Moneyline, Run Line, Over/Under, F5)"""
    linescore = live_data.get('linescore', {})
    teams = linescore.get('teams', {})
    innings = linescore.get('innings', [])
    
    carreras_away = parse_float(teams.get('away', {}).get('runs', 0))
    carreras_home = parse_float(teams.get('home', {}).get('runs', 0))
    total_carreras = carreras_away + carreras_home
    
    # Datos de 5 Primeras Entradas (F5)
    f5_away = sum([parse_float(inn.get('away', {}).get('runs', 0)) for inn in innings[:5]])
    f5_home = sum([parse_float(inn.get('home', {}).get('runs', 0)) for inn in innings[:5]])
    f5_total = f5_away + f5_home
    f5_completado = len(innings) >= 5 and (linescore.get('currentInning', 0) > 5 or "Final" in str(status_juego))
    
    es_final = "Final" in str(status_juego) or "Game Over" in str(status_juego)
    tipo = apuesta['tipo']
    
    # 1. GANADOR DEL PARTIDO (MONEYLINE)
    if tipo == "Victoria (Moneyline)":
        es_away = apuesta['seleccion'] == apuesta['away_name']
        mi_score = carreras_away if es_away else carreras_home
        rival_score = carreras_home if es_away else carreras_away
        
        if mi_score > rival_score:
            return ("✅ GANADA" if es_final else "🟢 GANANDO", f"{int(mi_score)} - {int(rival_score)}")
        elif mi_score < rival_score:
            return ("❌ PERDIDA" if es_final else "🔴 PERDIENDO", f"{int(mi_score)} - {int(rival_score)}")
        else:
            return ("🟡 EMPATE TEMPORAL", f"{int(mi_score)} - {int(rival_score)}")

    # 2. RUN LINE / HÁNDICAP DEL PARTIDO (Ej. -1.5 o +1.5)
    elif tipo == "Run Line / Hándicap":
        es_away = apuesta['seleccion'] == apuesta['away_name']
        mi_score = carreras_away if es_away else carreras_home
        rival_score = carreras_home if es_away else carreras_away
        handicap = apuesta['linea']
        score_con_handicap = mi_score + handicap
        
        if score_con_handicap > rival_score:
            return ("✅ GANADA" if es_final else "🟢 CUBRIENDO", f"Con Hándicap: {score_con_handicap:.1f} vs {int(rival_score)}")
        elif score_con_handicap < rival_score:
            return ("❌ PERDIDA" if es_final else "🔴 SIN CUBRIR", f"Con Hándicap: {score_con_handicap:.1f} vs {int(rival_score)}")
        else:
            return ("🟡 EMPATE", f"{score_con_handicap:.1f} vs {int(rival_score)}")

    # 3. TOTAL DE CARRERAS DEL PARTIDO (OVER / UNDER)
    elif tipo in ["Total: OVER (Altas)", "Total: UNDER (Bajas)"]:
        linea = apuesta['linea']
        if tipo == "Total: OVER (Altas)":
            if total_carreras > linea:
                return ("✅ GANADA" if es_final else "🟢 CUBIERTA", f"{int(total_carreras)} carreras (Línea: {linea})")
            else:
                faltan = linea - total_carreras
                return ("❌ PERDIDA" if es_final else "🔴 EN PROGRESO", f"Llevan {int(total_carreras)} | Faltan {faltan:.1f}")
        else:
            if total_carreras < linea:
                return ("✅ GANADA" if es_final else "🟢 CUBIERTA", f"{int(total_carreras)} carreras (Línea: {linea})")
            else:
                return ("❌ PERDIDA" if es_final else "🔴 SUPERADA", f"Llevan {int(total_carreras)} | Máximo: {linea}")

    # 4. MERCADOS DE PRIMERAS 5 ENTRADAS (F5)
    elif tipo == "F5 Victoria (5 Entradas)":
        es_away = apuesta['seleccion'] == apuesta['away_name']
        mi_f5 = f5_away if es_away else f5_home
        rival_f5 = f5_home if es_away else f5_away
        
        if mi_f5 > rival_f5:
            return ("✅ GANADA" if f5_completado else "🟢 GANANDO F5", f"F5: {int(mi_f5)} - {int(rival_f5)}")
        elif mi_f5 < rival_f5:
            return ("❌ PERDIDA" if f5_completado else "🔴 PERDIENDO F5", f"F5: {int(mi_f5)} - {int(rival_f5)}")
        else:
            return ("🟡 EMPATE F5", f"F5: {int(mi_f5)} - {int(rival_f5)}")

    elif tipo in ["F5 Total: OVER (Altas)", "F5 Total: UNDER (Bajas)"]:
        linea = apuesta['linea']
        if tipo == "F5 Total: OVER (Altas)":
            if f5_total > linea:
                return ("✅ GANADA" if f5_completado else "🟢 CUBIERTA F5", f"F5: {int(f5_total)} carreras (Línea: {linea})")
            else:
                return ("❌ PERDIDA" if f5_completado else "🔴 EN PROGRESO F5", f"F5 Llevan {int(f5_total)} | Línea: {linea}")
        else:
            if f5_total < linea:
                return ("✅ GANADA" if f5_completado else "🟢 CUBIERTA F5", f"F5: {int(f5_total)} carreras (Línea: {linea})")
            else:
                return ("❌ PERDIDA" if f5_completado else "🔴 SUPERADA F5", f"F5 Llevan {int(f5_total)} | Línea: {linea}")

    return ("⚪ PENDIENTE", "Esperando datos")

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

# --- CONSULTAS Y CACHÉ ---
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
    params = {'apiKey': api_key, 'regions': region, 'markets': 'h2h,spreads,totals', 'oddsFormat': 'decimal'}
    try:
        res = requests.get(url, params=params)
        return res.json() if res.status_code == 200 else None
    except Exception:
        return None

# --- EJECUCIÓN PRINCIPAL ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido a monitorear:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    away_id, home_id = juegos[idx_juego]['away_id'], juegos[idx_juego]['home_id']
    away_name, home_name = juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']
    
    # --- FORMULARIO SIDEBAR: APUESTAS DE PARTIDO ---
    st.sidebar.markdown("---")
    st.sidebar.header("🎟️ Registrar Apuesta de Partido")
    with st.sidebar.form("form_apuesta_partido"):
        tipo_apuesta = st.selectbox(
            "Mercado del Partido:", 
            [
                "Victoria (Moneyline)", 
                "Run Line / Hándicap", 
                "Total: OVER (Altas)", 
                "Total: UNDER (Bajas)",
                "F5 Victoria (5 Entradas)",
                "F5 Total: OVER (Altas)",
                "F5 Total: UNDER (Bajas)"
            ]
        )
        
        seleccion_equipo = st.selectbox("Equipo Seleccionado:", [away_name, home_name])
        linea_valor = st.number_input("Línea / Hándicap (Ej. -1.5, +1.5, 8.5):", value=8.5, step=0.5)
        monto_apostado = st.number_input("Monto ($):", value=10.0, step=5.0)
        cuota_apostada = st.number_input("Cuota / Odds (Decimal):", value=1.90, step=0.05)
        
        btn_guardar = st.form_submit_button("➕ Añadir Apuesta de Partido")
        
        if btn_guardar:
            # Construcción de la descripción según el tipo de apuesta de partido
            if "Victoria" in tipo_apuesta:
                desc_sel = f"Ganador: {seleccion_equipo}"
            elif "Run Line" in tipo_apuesta:
                desc_sel = f"{seleccion_equipo} ({linea_valor:+.1f})"
            else:
                desc_sel = f"{tipo_apuesta} {linea_valor}"

            nueva_apuesta = {
                "game_id": game_id,
                "partido": f"{away_name} @ {home_name}",
                "tipo": tipo_apuesta,
                "seleccion": seleccion_equipo if ("Victoria" in tipo_apuesta or "Run Line" in tipo_apuesta) else desc_sel,
                "linea": linea_valor,
                "monto": monto_apostado,
                "cuota": cuota_apostada,
                "ganancia_potencial": round(monto_apostado * cuota_apostada, 2),
                "away_name": away_name,
                "home_name": home_name
            }
            st.session_state.mis_apuestas.append(nueva_apuesta)
            st.sidebar.success("¡Apuesta de partido agregada!")

    feed = obtener_feed_en_vivo(game_id)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})
    
    probables = game_data.get('probablePitchers', {})
    away_pitcher, home_pitcher = probables.get('away', {}), probables.get('home', {})

    stats_p_away = obtener_stats_jugador(away_pitcher.get('id'), 'pitching') if away_pitcher.get('id') else {}
    stats_p_home = obtener_stats_jugador(home_pitcher.get('id'), 'pitching') if home_pitcher.get('id') else {}
    
    fip_away, fip_home = calcular_fip(stats_p_away), calcular_fip(stats_p_home)
    whip_bp_away, whip_bp_home = obtener_whip_bullpen(away_id), obtener_whip_bullpen(home_id)

    venue_name = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
    park_factor = PARK_FACTORS.get(venue_name, 1.00)

    # CÁLCULOS Y SIMULACIÓN
    exp_runs_away = round((4.5 * (fip_home / 4.10)) * park_factor, 2)
    exp_runs_home = round((4.5 * (fip_away / 4.10)) * park_factor, 2)

    if ajuste_fatiga_bp:
        if whip_bp_home > 1.30: exp_runs_away += 0.25
        if whip_bp_away > 1.30: exp_runs_home += 0.25

    prob_away, prob_home, sim_away, sim_home, total_esperado = simular_monte_carlo(
        exp_runs_away, exp_runs_home, n_simulaciones
    )

    # PESTAÑAS PRINCIPALES DE ANÁLISIS
    tab_montecarlo, tab_ev, tab_vivo = st.tabs([
        "🎲 SIMULACIÓN MONTE CARLO (PARTIDO)", 
        "💰 DETECTOR +EV EN CASAS",
        "📈 MARCADOR Y TRACKER EN VIVO"
    ])

    # --- TAB 1: MONTE CARLO ---
    with tab_montecarlo:
        st.header("🎰 Proyección General del Partido")
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Prob. Victoria {away_name}", f"{prob_away:.1f}%", f"Proj: {sim_away:.2f} R")
        c2.metric(f"Prob. Victoria {home_name}", f"{prob_home:.1f}%", f"Proj: {sim_home:.2f} R")
        c3.metric("Total Proyectado del Partido", f"{total_esperado:.2f} Carreras", f"Park Factor: {park_factor}x")

        st.markdown("---")
        st.subheader("📊 Métricas Clave de Pitcheo Colectivo / Abridores")
        df_pitchers = pd.DataFrame([
            {"Equipo": away_name, "Abridor": away_pitcher.get('fullName', 'Por anunciar'), "ERA": stats_p_away.get('era', '-'), "FIP": fip_away, "WHIP Bullpen": whip_bp_away},
            {"Equipo": home_name, "Abridor": home_pitcher.get('fullName', 'Por anunciar'), "ERA": stats_p_home.get('era', '-'), "FIP": fip_home, "WHIP Bullpen": whip_bp_home}
        ])
        st.table(df_pitchers)

    # --- TAB 2: VALOR ESPERADO DE MERCADOS DEL PARTIDO ---
    with tab_ev:
        st.header("💰 Detector de Valor (+EV) en Mercados de Partido")
        cuotas_raw = obtener_cuotas_mlb_api(odds_api_key) if odds_api_key else None
        
        if not cuotas_raw:
            st.info("💡 **Modo Demo**: Se muestran cuotas simuladas. Añade tu API Key para datos en vivo de Pinnacle, DraftKings, etc.")
            cuotas_lista = [
                {"bookmaker": "Pinnacle", "away_odds": 2.15, "home_odds": 1.75},
                {"bookmaker": "DraftKings", "away_odds": 2.05, "home_odds": 1.80},
                {"bookmaker": "FanDuel", "away_odds": 2.10, "home_odds": 1.78}
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
                            cuotas_lista.append({"bookmaker": bm.get('title'), "away_odds": odds_h2h['away'], "home_odds": odds_h2h['home']})

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

    # --- TAB 3: TRANSMISIÓN Y TRACKER EN VIVO DE APUESTAS ---
    with tab_vivo:
        st.header("🏟️ Tracker en Vivo: Estado del Partido y Tickets")
        st.metric("Estado del Encuentro", juegos[idx_juego]['status'])
        
        linescore = live_data.get('linescore', {})
        plays = live_data.get('plays', {})
        current_play = plays.get('currentPlay', {})
        offense = linescore.get('offense', {})

        # --- SECCIÓN: TRACKER DE APUESTAS DE PARTIDO REGISTRADAS ---
        if st.session_state.mis_apuestas:
            st.subheader("🎯 Tus Apuestas de Partido en Seguimiento")
            apuestas_del_partido = [a for a in st.session_state.mis_apuestas if a.get('game_id') == game_id]
            
            if apuestas_del_partido:
                columnas_cards = st.columns(min(len(apuestas_del_partido), 4))
                for idx, ap in enumerate(apuestas_del_partido):
                    estado, detalle = evaluar_apuesta_partido(ap, live_data, juegos[idx_juego]['status'])
                    
                    with columnas_cards[idx % len(columnas_cards)]:
                        st.markdown(f"""
                        <div style="background-color: #2D3748; padding: 12px; border-radius: 8px; border-left: 4px solid #3182CE; margin-bottom:10px;">
                            <b style="color:#F7FAFC;">{ap['tipo']}</b><br>
                            <span style="color:#CBD5E0; font-size:14px;">{ap['seleccion']}</span><br>
                            <b style="font-size: 18px;">{estado}</b><br>
                            <small style="color:#A0AEC0;">{detalle}</small><br><hr style="margin:6px 0;">
                            <small>Monto: <b>${ap['monto']}</b> | Retorno: <b>${ap['ganancia_potencial']}</b></small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No tienes apuestas de partido registradas para este encuentro.")
            
            if st.button("🗑️ Limpiar Historial de Apuestas"):
                st.session_state.mis_apuestas = []
                st.rerun()
                
            st.markdown("---")

        # SPRAY CHART Y VISTA DEL CAMPO EN VIVO
        hit_x, hit_y = None, None
        if current_play:
            for evento in reversed(current_play.get('playEvents', [])):
                if 'hitData' in evento and 'coordinates' in evento['hitData']:
                    coords = evento['hitData']['coordinates']
                    hit_x, hit_y = coords.get('coordX'), coords.get('coordY')
                    break

        st.subheader("📌 Diamante y Duelo en Vivo")
        col_campo, col_datos = st.columns([1, 2])
        
        with col_campo:
            st.markdown(generar_campo_svg(offense, hit_x, hit_y), unsafe_allow_html=True)
            
        with col_datos:
            if current_play:
                matchup = current_play.get('matchup', {})
                count = current_play.get('count', {})
                
                batter_name = matchup.get('batter', {}).get('fullName', 'En espera')
                pitcher_name = matchup.get('pitcher', {}).get('fullName', 'En espera')
                balls, strikes, outs = count.get('balls', 0), count.get('strikes', 0), count.get('outs', 0)
                
                bases = []
                if offense.get('first'): bases.append("1B")
                if offense.get('second'): bases.append("2B")
                if offense.get('third'): bases.append("3B")
                corredores_str = ", ".join(bases) if bases else "Bases Limpias"
                
                st.markdown("### ⚡ Situación de Juego")
                c_d1, c_d2 = st.columns(2)
                c_d1.metric("Bateador", batter_name)
                c_d2.metric("Pitcher", pitcher_name)
                
                c_d3, c_d4 = st.columns(2)
                c_d3.metric("Conteo / Outs", f"⚽ {balls}-{strikes} | 🛑 {outs} Outs")
                c_d4.metric("Corredores", corredores_str)

        st.markdown("---")

        # LINESCORE DEL PARTIDO
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
            st.subheader("📊 Marcador por Entradas (Linescore)")
            st.dataframe(pd.DataFrame(tabla_innings), use_container_width=True, hide_index=True)
            
            teams = linescore.get('teams', {})
            away_totals, home_totals = teams.get('away', {}), teams.get('home', {})
            
            c_tot1, c_tot2 = st.columns(2)
            c_tot1.metric(f"Total {away_name}", f"R: {away_totals.get('runs', 0)} | H: {away_totals.get('hits', 0)} | E: {away_totals.get('errors', 0)}")
            c_tot2.metric(f"Total {home_name}", f"R: {home_totals.get('runs', 0)} | H: {home_totals.get('hits', 0)} | E: {home_totals.get('errors', 0)}")
        else:
            st.info("Esperando inicio del partido para mostrar marcador por entradas.")

# --- BUCLE DE AUTO-REFRESH (10 SEGUNDOS) ---
if auto_refresh:
    time.sleep(10)
    st.rerun()
