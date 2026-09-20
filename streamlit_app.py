import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst - Modelo Avanzado Multi-Factor", page_icon="⚾", layout="wide")

st.title("⚾ Modelo Analítico MLB: Proyección Multi-Factor de Hit")
st.markdown("Integración de L5 + Ponderación de Temporada, Posición en Lineup, Arm del Pitcher y Factor Campo.")
st.markdown("---")

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
                        diccionario_jugadores[f"{nombre} ({posicion} - {equipo_nom})"] = player_id
        return dict(sorted(diccionario_jugadores.items()))
    except Exception:
        return {"Shohei Ohtani (DH - Dodgers)": 660271, "Aaron Judge (OF - Yankees)": 592450}

@st.cache_data(ttl=3600)
def obtener_stats_temporada(player_id):
    """Extrae las estadísticas generales de la temporada actual."""
    anio_actual = datetime.now().year
    try:
        res = statsapi.player_stat_data(player_id, group="hitting", type="season", season=anio_actual)
        stats = res.get('stats', [])
        if stats:
            s_data = stats[0].get('stats', {})
            return {
                'avg_season': float(s_data.get('avg', '.000')),
                'obp_season': float(s_data.get('obp', '.000')),
                'games': int(s_data.get('gamesPlayed', 0))
            }
    except Exception:
        pass
    return {'avg_season': 0.260, 'obp_season': 0.320, 'games': 0}

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
    for anio in [anio_actual, anio_actual - 1]:
        try:
            res = statsapi.player_game_logs(player_id, group="hitting", season=anio)
            if isinstance(res, list) and len(res) > 0:
                registros.extend(res)
                if len(registros) >= 5:
                    break
        except Exception:
            pass
            
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
    
    while (len(fechas_existentes) + len(adicionales)) < 5 and intentos < 25:
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
    columnas = {'date': 'Fecha', 'opponent': 'Rival', 'ab': 'AB', 'h': 'H', 'doubles': '2B', 'triples': '3B', 'homeRuns': 'HR', 'rbi': 'CI', 'baseOnBalls': 'BB', 'strikeOuts': 'K'}
    cols_presentes = [c for c in columnas.keys() if c in df_5.columns]
    df_final = df_5[cols_presentes].rename(columns=columnas)
    for col in ['AB', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K']:
        if col in df_final.columns:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0).astype(int)
    return df_final

def calcular_modelo_multifactor(df_5, stats_season, posicion_lineup, perfil_pitcher, factor_campo):
    """
    Combina: L5 (Inercia) + Temporada (Prior Bayesiano) + Posición Lineup (AB esperados) + Perfil Pitcher + Factor Estadio
    """
    total_ab_5 = df_5['AB'].sum()
    total_h_5 = df_5['H'].sum()
    juegos_con_hit = (df_5['H'] > 0).sum()
    
    avg_5 = total_h_5 / total_ab_5 if total_ab_5 > 0 else 0.250
    avg_season = stats_season['avg_season'] if stats_season['games'] > 10 else avg_5
    
    # 1. Ponderación Bayesiana (40% Inercia L5 / 60% Consistencia de Temporada)
    avg_proyectado = (avg_5 * 0.40) + (avg_season * 0.60)
    
    # 2. Ajuste por Brazo del Lanzador Rival
    if perfil_pitcher == "Abridor Débil / Favorabilidad Altísima":
        avg_proyectado *= 1.12
    elif perfil_pitcher == "Lanzador Zurdo (Ventaja Platoon)":
        avg_proyectado *= 1.06
    elif perfil_pitcher == "Ace / Lanzador Dominante":
        avg_proyectado *= 0.88
        
    # 3. Factor de Campo / Estadio
    avg_proyectado *= factor_campo
    
    # 4. Proyección de Turnos al Bate (AB) según lugar en la alineación
    ab_esperados = 4.3 if posicion_lineup == "1.º al 4.º Bate (Líderes de Turnos)" else 3.6
    
    # 5. Cálculo de Poisson
    lambda_hits = avg_proyectado * ab_esperados
    prob_hit = round(min((1 - np.exp(-lambda_hits)) * 100, 95.0), 1)
    
    return {
        "avg_5": round(avg_5, 3),
        "avg_season": round(avg_season, 3),
        "avg_proyectado": round(avg_proyectado, 3),
        "ab_esperados": ab_esperados,
        "prob_hit": prob_hit,
        "juegos_con_hit": f"{juegos_con_hit}/5"
    }

# ==========================================
# INTERFAZ & FILTROS AVANZADOS
# ==========================================

directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())

st.sidebar.header("⚙️ Variables del Partido Hoy")

posicion_lineup = st.sidebar.radio(
    "Orden en el Lineup:",
    ["1.º al 4.º Bate (Líderes de Turnos)", "5.º al 9.º Bate (Menos Turnos)"]
)

perfil_pitcher = st.sidebar.selectbox(
    "Perfil del Lanzador Abridor Rival:",
    [
        "Lanzador Promedio / Estándar",
        "Lanzador Zurdo (Ventaja Platoon)",
        "Abridor Débil / Favorabilidad Altísima",
        "Ace / Lanzador Dominante"
    ]
)

factor_campo_opcion = st.sidebar.selectbox(
    "Factor de Estadio / Clima:",
    ["Neutral (1.00)", "Estadio Bateador / Coors Field (+8%)", "Estadio Lanzador / Frío (-6%)"]
)

factor_campo = 1.08 if "Coors" in factor_campo_opcion else (0.94 if "Lanzador" in factor_campo_opcion else 1.00)

jugador_sel = st.sidebar.selectbox("Selecciona Jugador a Analizar:", opciones)

if jugador_sel:
    pid = directorio[jugador_sel]
    
    with st.spinner("Procesando métricas avanzadas y registros..."):
        df_5 = obtener_ultimos_5_juegos_garantizado(pid)
        stats_season = obtener_stats_temporada(pid)
        
    if df_5 is not None and not df_5.empty:
        res = calcular_modelo_multifactor(df_5, stats_season, posicion_lineup, perfil_pitcher, factor_campo)
        
        st.subheader(f"📊 Diagnóstico Analítico Completo: {jugador_sel.split(' (')[0]}")
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("🎯 Prob. Hit Ajustada", f"{res['prob_hit']}%")
        m2.metric("AVG Proyectado", f"{res['avg_proyectado']:.3f}")
        m3.metric("AVG L5 (Racha)", f"{res['avg_5']:.3f}")
        m4.metric("AVG Temporada", f"{res['avg_season']:.3f}")
        m5.metric("AB Esperados", f"~{res['ab_esperados']}")
        
        st.markdown(f"""
        > **Desglose del Algoritmo:**
        > * **Base Bayesiana:** Se ponderó el **AVG de L5 ({res['avg_5']:.3f})** con el **AVG de Temporada ({res['avg_season']:.3f})** para evitar sobre-reaccionar a rachas breves.
        > * **Oportunidad:** Asignando **~{res['ab_esperados']} AB** basados en su puesto en el lineup (**{posicion_lineup}**).
        > * **Opositor y Entorno:** Ajustado por perfil de picheo (**{perfil_pitcher}**) y factor de parque (**{factor_campo_opcion}**).
        """)
        
        st.dataframe(df_5, use_container_width=True)
