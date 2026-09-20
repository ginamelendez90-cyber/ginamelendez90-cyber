import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst Pro - Pitcher & Orden Automático", page_icon="⚾", layout="wide")

st.title("⚾ MLB Analytics Pro: Pitcher Anunciado, Orden Automático & L5")
st.markdown("---")

# --- MATRIZ DE PARK FACTORS (Ajuste de Hits por Estadio) ---
PARK_FACTORS = {
    "Coors Field": 1.14, "Fenway Park": 1.08, "Great American Ball Park": 1.07,
    "Citizens Bank Park": 1.06, "Yankee Stadium": 1.04, "Wrigley Field": 1.03,
    "Kauffman Stadium": 1.04, "Chase Field": 1.03, "Truist Park": 1.02,
    "Minute Maid Park": 1.01, "Angel Stadium": 1.01, "Rogers Centre": 1.01,
    "Guaranteed Rate Field": 1.01, "Dodger Stadium": 0.99, "Target Field": 0.99,
    "Globe Life Field": 0.98, "Progressive Field": 0.98, "Camden Yards": 0.97,
    "Comerica Park": 0.97, "PNC Park": 0.96, "Busch Stadium": 0.96,
    "Oracle Park": 0.95, "LoanDepot Park": 0.95, "Petco Park": 0.94,
    "Oakland Coliseum": 0.94, "T-Mobile Park": 0.93
}

@st.cache_data(ttl=86400)
def obtener_directorio_jugadores_activos():
    diccionario_jugadores = {}
    anio_actual = datetime.now().year
    try:
        equipos = statsapi.get('teams', {'sportId': 1, 'season': anio_actual}).get('teams', [])
        for equipo in equipos:
            team_id = equipo.get('id')
            roster = statsapi.get('team_roster', {'teamId': team_id, 'rosterType': 'active'}).get('roster', [])
            for p in roster:
                person = p.get('person', {})
                posicion = p.get('position', {}).get('abbreviation', '')
                if posicion != 'P' or person.get('fullName') == 'Shohei Ohtani':
                    nombre = person.get('fullName')
                    player_id = person.get('id')
                    equipo_nom = equipo.get('teamName', '')
                    if nombre and player_id:
                        etiqueta = f"{nombre} ({posicion} - {equipo_nom})"
                        diccionario_jugadores[etiqueta] = {
                            "player_id": player_id,
                            "team_id": team_id,
                            "nombre": nombre,
                            "equipo": equipo_nom
                        }
        return dict(sorted(diccionario_jugadores.items()))
    except Exception:
        return {
            "Shohei Ohtani (DH - Dodgers)": {"player_id": 660271, "team_id": 119, "nombre": "Shohei Ohtani", "equipo": "Dodgers"},
            "Aaron Judge (OF - Yankees)": {"player_id": 592450, "team_id": 147, "nombre": "Aaron Judge", "equipo": "Yankees"}
        }

@st.cache_data(ttl=3600)
def obtener_perfil_y_stats_temporada(player_id):
    anio_actual = datetime.now().year
    datos = {"avg_season": 0.260, "obp_season": 0.330, "slg_season": 0.430, "ops_season": 0.760, "ab_season": 200, "bat_side": "R", "xba_est": 0.260}
    try:
        person_info = statsapi.get('person', {'personId': player_id})
        if person_info and 'people' in person_info and len(person_info['people']) > 0:
            datos["bat_side"] = person_info['people'][0].get('batSide', {}).get('code', 'R')
    except Exception:
        pass

    for anio in [anio_actual, anio_actual - 1]:
        try:
            s_data = statsapi.player_stat_data(player_id, group="hitting", type="season", season=anio)
            if s_data and 'stats' in s_data and len(s_data['stats']) > 0:
                st_dict = s_data['stats'][0].get('stats', {})
                ab = st_dict.get('atBats', 0)
                if ab > 20:
                    avg = float(st_dict.get('avg', '.260').replace('.','0.')) if isinstance(st_dict.get('avg'), str) else float(st_dict.get('avg', 0.260))
                    obp = float(st_dict.get('obp', '.330').replace('.','0.')) if isinstance(st_dict.get('obp'), str) else float(st_dict.get('obp', 0.330))
                    slg = float(st_dict.get('slg', '.430').replace('.','0.')) if isinstance(st_dict.get('slg'), str) else float(st_dict.get('slg', 0.430))
                    ops = float(st_dict.get('ops', '.760').replace('.','0.')) if isinstance(st_dict.get('ops'), str) else float(st_dict.get('ops', 0.760))
                    datos["avg_season"] = avg
                    datos["obp_season"] = obp
                    datos["slg_season"] = slg
                    datos["ops_season"] = ops
                    datos["ab_season"] = ab
                    datos["xba_est"] = round(avg * (1.02 if ops > 0.850 else (0.97 if ops < 0.680 else 1.0)), 3)
                    break
        except Exception:
            pass
    return datos

@st.cache_data(ttl=1800)
def obtener_info_proximo_juego_auto(team_id):
    """Obtiene el próximo juego, estadio y el PITCHER RIVAL ANUNCIADO de la API"""
    if not team_id:
        return None
    try:
        next_game_pk = statsapi.next_game(team_id)
        if next_game_pk:
            juegos = statsapi.schedule(game_id=next_game_pk)
            if juegos and isinstance(juegos, list) and len(juegos) > 0:
                juego = juegos[0]
                es_local = (juego.get('home_id') == team_id)
                rival_nombre = juego.get('away_name') if es_local else juego.get('home_name')
                condicion = "Local 🏠" if es_local else "Visitante ✈️"
                estadio = juego.get('venue_name', 'Estadio Generico')
                fecha_juego = juego.get('game_date', juego.get('schedule_date', 'Por confirmar'))
                
                # Obtener Pitcher Probable según la localía
                pitcher_rival = juego.get('away_probable_pitcher') if es_local else juego.get('home_probable_pitcher')
                if not pitcher_rival or str(pitcher_rival).strip() == '':
                    pitcher_rival = "Por Designar / Por Confirmar"
                
                # Búsqueda de la mano del lanzador (R/L)
                pitcher_hand = "R"
                if pitcher_rival != "Por Designar / Por Confirmar":
                    try:
                        search = statsapi.lookup_player(pitcher_rival)
                        if search and len(search) > 0:
                            p_id = search[0]['id']
                            p_info = statsapi.get('person', {'personId': p_id})
                            pitcher_hand = p_info['people'][0].get('pitchHand', {}).get('code', 'R')
                    except Exception:
                        pass
                    
                return {
                    "game_id": next_game_pk, "estadio": estadio, "pitcher_rival": pitcher_rival,
                    "pitcher_hand": pitcher_hand, "rival": rival_nombre, "condicion": condicion,
                    "fecha": fecha_juego, "estado": juego.get('status', 'Programado'), "es_local": es_local, "encontrado": True
                }
    except Exception:
        pass

    return {
        "game_id": None, "estadio": "Estadio Estándar", "pitcher_rival": "Por Designar",
        "pitcher_hand": "R", "rival": "Por Definir", "condicion": "N/A",
        "fecha": "Calendario Próximo", "estado": "Programado", "es_local": True, "encontrado": False
    }

def detectar_orden_bate_automatico(player_id, info_juego, info_season):
    """Detecta el orden al bate desde la alineación oficial o aplica proyección sabermétrica"""
    if info_juego and info_juego.get('game_id'):
        try:
            box = statsapi.boxscore_data(info_juego['game_id'])
            lado = 'home' if info_juego.get('es_local') else 'away'
            batting_order = box.get(lado, {}).get('battingOrder', [])
            key_jugador = f"ID{player_id}"
            if key_jugador in batting_order:
                pos = batting_order.index(key_jugador) + 1
                return pos, "Alineación Oficial Confirmada 📋"
        except Exception:
            pass

    ops = info_season.get('ops_season', 0.750)
    obp = info_season.get('obp_season', 0.330)
    slg = info_season.get('slg_season', 0.430)

    if ops >= 0.880 and slg >= 0.500:
        return 3, "Proyección Automática (Bateador Estelar - #3) ⚡"
    elif ops >= 0.830:
        return 2, "Proyección Automática (Alto OPS - #2) ⚡"
    elif slg >= 0.480:
        return 4, "Proyección Automática (Poder / Limpieza - #4) ⚡"
    elif obp >= 0.350:
        return 1, "Proyección Automática (Leadoff / Embasado - #1) ⚡"
    elif ops >= 0.740:
        return 5, "Proyección Automática (Protección - #5) ⚡"
    elif ops >= 0.680:
        return 6, "Proyección Automática (Orden Medio - #6) ⚡"
    else:
        return 7, "Proyección Automática (Fondo de Alineación - #7) ⚡"

def buscar_juego_por_fecha(player_id, fecha_str):
    try:
        juegos = statsapi.schedule(date=fecha_str)
        if not isinstance(juegos, list):
            return None
        key_jugador = f"ID{player_id}"
        for juego in juegos:
            if juego.get('status') in ['Final', 'Completed Early', 'In Progress', 'Game Over']:
                game_pk = juego.get('game_id')
                if not game_pk:
                    continue
                box = statsapi.boxscore_data(game_pk)
                for lado in ['home', 'away']:
                    jugadores = box.get(lado, {}).get('players', {})
                    if key_jugador in jugadores:
                        b_stats = jugadores[key_jugador].get('stats', {}).get('batting', {})
                        if b_stats and b_stats.get('atBats', 0) > 0:
                            rival = juego.get('away_name') if lado == 'home' else juego.get('home_name')
                            return {
                                'date': fecha_str, 'opponent': f"vs {rival}",
                                'ab': b_stats.get('atBats', 0), 'h': b_stats.get('hits', 0),
                                'doubles': b_stats.get('doubles', 0), 'triples': b_stats.get('triples', 0),
                                'homeRuns': b_stats.get('homeRuns', 0), 'rbi': b_stats.get('rbi', 0),
                                'baseOnBalls': b_stats.get('baseOnBalls', 0), 'strikeOuts': b_stats.get('strikeOuts', 0)
                            }
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def obtener_ultimos_5_juegos_garantizado(player_id):
    registros = []
    anio_actual = datetime.now().year
    
    for anio in range(anio_actual, anio_actual - 4, -1):
        try:
            logs = statsapi.player_game_logs(player_id, group="hitting", season=anio)
            if isinstance(logs, list) and len(logs) > 0:
                for l in logs:
                    registros.append({
                        'date': l.get('date', ''), 'opponent': l.get('opponent', 'N/A'),
                        'ab': l.get('ab', l.get('atBats', 0)), 'h': l.get('h', l.get('hits', 0)),
                        'doubles': l.get('doubles', 0), 'triples': l.get('triples', 0),
                        'homeRuns': l.get('homeRuns', 0), 'rbi': l.get('rbi', 0),
                        'baseOnBalls': l.get('baseOnBalls', l.get('bb', 0)),
                        'strikeOuts': l.get('strikeOuts', l.get('so', 0))
                    })
                if len(registros) >= 5:
                    break
        except Exception:
            pass
            
        if len(registros) < 5:
            for game_type in ['S', 'P', 'R']:
                try:
                    params = {'stats': 'gameLog', 'personId': player_id, 'group': 'hitting', 'season': anio, 'gameType': game_type}
                    res = statsapi.get('stats', params)
                    splits = res.get('stats', [])[0].get('splits', []) if res.get('stats') else []
                    for s in splits:
                        stat = s.get('stat', {})
                        fecha = s.get('date', '')
                        opp = s.get('opponent', {}).get('name', 'N/A')
                        if stat and fecha and stat.get('atBats', 0) > 0:
                            registros.append({
                                'date': fecha, 'opponent': f"vs {opp}",
                                'ab': stat.get('atBats', 0), 'h': stat.get('hits', 0),
                                'doubles': stat.get('doubles', 0), 'triples': stat.get('triples', 0),
                                'homeRuns': stat.get('homeRuns', 0), 'rbi': stat.get('rbi', 0),
                                'baseOnBalls': stat.get('baseOnBalls', 0), 'strikeOuts': stat.get('strikeOuts', 0)
                            })
                    if len(registros) >= 5:
                        break
                except Exception:
                    pass
        if len(registros) >= 5:
            break

    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=False)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        df = df.drop_duplicates(subset=['date'])

    fechas_existentes = set(df['date'].values) if not df.empty and 'date' in df.columns else set()
    dia_cursor = datetime.now()
    intentos = 0
    adicionales = []

    while (len(fechas_existentes) + len(adicionales)) < 5 and intentos < 30:
        fecha_evaluar = dia_cursor.strftime('%Y-%m-%d')
        if fecha_evaluar not in fechas_existentes:
            stat = buscar_juego_por_fecha(player_id, fecha_evaluar)
            if stat:
                adicionales.append(stat)
        dia_cursor -= timedelta(days=1)
        intentos += 1

    if adicionales:
        df_adicional = pd.DataFrame(adicionales)
        df = pd.concat([df_adicional, df], ignore_index=True) if not df.empty else df_adicional

    if df.empty:
        return None

    df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    df_5 = df.head(5).copy()

    columnas = {
        'date': 'Fecha', 'opponent': 'Rival', 'ab': 'AB', 'h': 'H',
        'doubles': '2B', 'triples': '3B', 'homeRuns': 'HR',
        'rbi': 'CI', 'baseOnBalls': 'BB', 'strikeOuts': 'K'
    }
    cols_presentes = [c for c in columnas.keys() if c in df_5.columns]
    df_final = df_5[cols_presentes].rename(columns=columnas)

    for col in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).astype(int)

    return df_final

def calcular_modelo_bayesiano_avanzado(df_5, info_season, info_juego, lineup_spot):
    total_ab_l5 = df_5['AB'].sum()
    total_h_l5 = df_5['H'].sum()
    avg_l5 = total_h_l5 / total_ab_l5 if total_ab_l5 > 0 else info_season['avg_season']

    # Regresión Bayesiana
    w_l5 = min(total_ab_l5 / (total_ab_l5 + 60), 0.35)
    w_season = 1.0 - w_l5
    avg_bayesiano = (w_l5 * avg_l5) + (w_season * info_season['avg_season'])

    # Platoon Split
    bat_side = info_season.get('bat_side', 'R')
    pitcher_hand = info_juego.get('pitcher_hand', 'R')
    
    if bat_side == 'S':
        factor_platoon = 1.05
        platoon_desc = "Ventaja Ambidiestro (+5%)"
    elif (bat_side == 'L' and pitcher_hand == 'R') or (bat_side == 'R' and pitcher_hand == 'L'):
        factor_platoon = 1.08
        platoon_desc = f"Mano Favorable ({bat_side} vs {pitcher_hand}HP: +8%)"
    else:
        factor_platoon = 0.92
        platoon_desc = f"Mano Desfavorable ({bat_side} vs {pitcher_hand}HP: -8%)"

    # Factor de Estadio
    estadio_nom = info_juego.get('estadio', 'Estadio Generico')
    factor_estadio = PARK_FACTORS.get(estadio_nom, 1.00)

    # Statcast (xBA)
    avg_real = info_season['avg_season']
    xba = info_season['xba_est']
    factor_statcast = min(max(xba / avg_real if avg_real > 0 else 1.0, 0.90), 1.10)

    # Promedio Proyectado
    avg_proyectado = avg_bayesiano * factor_platoon * factor_estadio * factor_statcast

    # Turnos según el spot en la alineación
    pa_esperados = max(4.85 - (0.15 * (lineup_spot - 1)), 3.3)
    ab_esperados = round(pa_esperados * 0.88, 2)

    # Probabilidad con Distribución Poisson
    lambda_hits = avg_proyectado * ab_esperados
    prob_hit = round(min((1 - np.exp(-lambda_hits)) * 100, 95.0), 1)

    return {
        "avg_l5": round(avg_l5, 3), "avg_season": round(info_season['avg_season'], 3),
        "avg_bayesiano": round(avg_bayesiano, 3), "avg_proyectado": round(avg_proyectado, 3),
        "prob_hit": prob_hit, "ab_esperados": ab_esperados, "pa_esperados": round(pa_esperados, 1),
        "lineup_spot": lineup_spot,
        "factor_platoon": factor_platoon, "platoon_desc": platoon_desc,
        "factor_estadio": factor_estadio, "factor_statcast": round(factor_statcast, 3),
        "w_l5_pct": round(w_l5 * 100, 1), "w_season_pct": round(w_season * 100, 1)
    }

def generar_analisis_detallado_texto(res_m, info_juego, info_season, df_5, nombre_jugador, modo_lineup):
    prob = res_m['prob_hit']
    pitcher_nom = info_juego['pitcher_rival']
    pitcher_mano = f"({info_juego['pitcher_hand']}HP)"
    
    if res_m['avg_l5'] > res_m['avg_season']:
        texto_bayes = f"**Racha Reciente:** Batea para `{res_m['avg_l5']:.3f}` en sus últimos 5 juegos, superando su línea base de temporada (`{res_m['avg_season']:.3f}`). AVG Bayesiano: `{res_m['avg_bayesiano']:.3f}`."
    else:
        texto_bayes = f"**Ajuste Bayesiano:** Viene en bajón corto en L5 (`{res_m['avg_l5']:.3f}`), pero la ponderación a la temporada completa (`{res_m['avg_season']:.3f}`) sostiene un promedio base de `{res_m['avg_bayesiano']:.3f}`."

    if res_m['factor_platoon'] > 1.0:
        texto_platoon = f"✅ **Enfrentamiento Favorable:** Enfrenta al pitcher anunciado **{pitcher_nom}** {pitcher_mano}. La ventaja de mano ({info_season['bat_side']} vs {info_juego['pitcher_hand']}) incrementa la proyección **+{int((res_m['factor_platoon']-1)*100)}%**."
    else:
        texto_platoon = f"⚠️ **Cruce de Misma Mano:** Se mide ante el pitcher **{pitcher_nom}** {pitcher_mano}, aplicando una ligera desventaja al perfil bateador ({info_season['bat_side']}) de **-{int((1-res_m['factor_platoon'])*100)}%**."

    texto_spot = f"🎯 **Orden al Bate Detectado (# {res_m['lineup_spot']}):** Ubicado en el lugar **#{res_m['lineup_spot']}** ({modo_lineup}). Proyección de **{res_m['ab_esperados']} turnos oficiales (AB)**."

    estadio = info_juego['estadio']
    texto_estadio = f"🏛️ **Estadio ({estadio}):** Factor de parque asignado en **{res_m['factor_estadio']}x**."

    return f"""
    ### 📝 Análisis del Pronóstico ({prob}% Hit)
    
    1. {texto_bayes}
    2. {texto_platoon}
    3. {texto_spot}
    4. {texto_estadio}
    """

# --- INTERFAZ STREAMLIT ---
directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())
predet = [o for o in opciones if "Ohtani" in o or "Judge" in o][:2]

st.sidebar.header("⚙️ Configuración")
seleccionados = st.sidebar.multiselect("Selecciona Jugador(es):", options=opciones, default=predet if predet else opciones[:1])

if seleccionados:
    for etiqueta in seleccionados:
        datos_jugador = directorio[etiqueta]
        pid = datos_jugador["player_id"]
        tid = datos_jugador["team_id"]
        nombre_solo = etiqueta.split(' (')[0]

        st.subheader(f"⚾ {nombre_solo}")

        info_juego = obtener_info_proximo_juego_auto(tid)
        info_season = obtener_perfil_y_stats_temporada(pid)
        df_5 = obtener_ultimos_5_juegos_garantizado(pid)

        # Selección automática del spot en la alineación
        lineup_spot, modo_lineup = detectar_orden_bate_automatico(pid, info_juego, info_season)

        if df_5 is not None and not df_5.empty:
            res_m = calcular_modelo_bayesiano_avanzado(df_5, info_season, info_juego, lineup_spot)

            # Tarjetas Principales
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("🎯 Prob. Hit", f"{res_m['prob_hit']}%")
            with c2:
                st.metric("⚾ Pitcher Anunciado", f"{info_juego['pitcher_rival']}")
            with c3:
                st.metric("📋 Spot en Orden", f"#{lineup_spot} ({res_m['ab_esperados']} AB)")
            with c4:
                st.metric("📊 AVG L5 vs Temp.", f"{res_m['avg_l5']:.3f} / {res_m['avg_season']:.3f}")

            # Análisis explicativo
            analisis_texto = generar_analisis_detallado_texto(res_m, info_juego, info_season, df_5, nombre_solo, modo_lineup)
            st.info(analisis_texto)

            # Desglose Técnico
            with st.expander("🔍 Ver Contexto del Partido y Pitcher Rival", expanded=True):
                f1, f2, f3 = st.columns(3)
                with f1:
                    st.markdown(f"**🎯 Pitcher Rival:** `{info_juego['pitcher_rival']}` ({info_juego['pitcher_hand']}HP)")
                with f2:
                    st.markdown(f"**🏟️ Estadio:** `{info_juego['estadio']}`")
                with f3:
                    st.markdown(f"**⚔️ Partido:** `{info_juego['condicion']}` vs `{info_juego['rival']}`")

            # Tabla de L5
            st.markdown("##### 📊 Historial de los Últimos 5 Partidos (Garantizado)")
            st.dataframe(df_5, use_container_width=True)
            st.markdown("---")
