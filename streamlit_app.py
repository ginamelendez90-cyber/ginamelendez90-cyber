import streamlit as st
import pandas as pd
import statsapi
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="MLB Sabermetrics Advanced Analytics", layout="wide", page_icon="⚾")

st.title("⚾ Sistema Avanzado de Análisis Sabermétrico MLB")
st.markdown("---")

# --- BARRA LATERAL DE CONTROL ---
st.sidebar.header("⚙️ Configuración del Análisis")
fecha_seleccionada = st.sidebar.date_input("Fecha de los partidos:", datetime.today())
refrescar = st.sidebar.button("🔄 Actualizar Datos en Tiempo Real")

# Funciones de consulta optimizadas
@st.cache_data(ttl=60)
def obtener_calendario(fecha):
    fecha_str = fecha.strftime('%Y-%m-%d')
    return statsapi.schedule(date=fecha_str)

@st.cache_data(ttl=60)
def obtener_feed_en_vivo(game_id):
    try:
        return statsapi.get('game', {'gamePk': game_id})
    except:
        return {}

@st.cache_data(ttl=300)
def obtener_stats_jugador(player_id, group):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        if data and 'stats' in data and len(data['stats']) > 0:
            return data['stats'][0].get('stats', {})
        return {}
    except:
        return {}

# --- PROCESAMIENTO DE PARTIDOS ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido que deseas analizar en profundidad:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    
    feed = obtener_feed_en_vivo(game_id)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})

    # ==========================================
    # BLOQUE 1: CONTEXTO GENERAL DEL PARTIDO
    # ==========================================
    st.header("🏟️ 1. Entorno del Encuencer")
    venue = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
    clima = game_data.get('weather', {})
    condiciones = f"🌡️ {clima.get('temp', 'N/A')}°F, 🌤️ {clima.get('condition', 'N/A')}, 💨 Viento: {clima.get('wind', 'N/A')}"
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Estadio", venue)
    c2.metric("Condiciones Climáticas", condiciones)
    c3.metric("Estado Actual", juegos[idx_juego]['status'])
    
    st.markdown("---")

    # Variables globales para almacenar estadísticas de lanzadores para el módulo predictivo
    stats_pitcher_away = {}
    stats_pitcher_home = {}

    # ==========================================
    # BLOQUE 2: DUELO DE LANZADORES
    # ==========================================
    st.header("🔮 2. Análisis Deep-Dive: Lanzadores Abridores")
    probables = game_data.get('probablePitchers', {})
    away_pitcher = probables.get('away', {})
    home_pitcher = probables.get('home', {})
    
    col_pitcher1, col_pitcher2 = st.columns(2)
    
    with col_pitcher1:
        st.subheader(f"Visiting Starter: {away_pitcher.get('fullName', 'Por anunciar')}")
        if away_pitcher.get('id'):
            stats_pitcher_away = obtener_stats_jugador(away_pitcher['id'], 'pitching')
            if stats_pitcher_away:
                k = stats_pitcher_away.get('strikeOuts', 0)
                bb = stats_pitcher_away.get('baseOnBalls', 0)
                k_bb_ratio = round(k / bb, 2) if bb > 0 else k
                st.metric("Efectividad (ERA)", stats_pitcher_away.get('era', '-'))
                st.metric("Ponches / Boletos (K/BB Ratio)", k_bb_ratio)
                st.write(f"**WHIP:** {stats_pitcher_away.get('whip', '-')} | **AVG en contra:** .{stats_pitcher_away.get('avg', '-')}")
            else: st.info("Estadísticas no disponibles.")
        else: st.info("Lanzador no definido.")
    
    with col_pitcher2:
        st.subheader(f"Home Starter: {home_pitcher.get('fullName', 'Por anunciar')}")
        if home_pitcher.get('id'):
            stats_pitcher_home = obtener_stats_jugador(home_pitcher['id'], 'pitching')
            if stats_pitcher_home:
                k = stats_pitcher_home.get('strikeOuts', 0)
                bb = stats_pitcher_home.get('baseOnBalls', 0)
                k_bb_ratio = round(k / bb, 2) if bb > 0 else k
                st.metric("Efectividad (ERA)", stats_pitcher_home.get('era', '-'))
                st.metric("Ponches / Boletos (K/BB Ratio)", k_bb_ratio)
                st.write(f"**WHIP:** {stats_pitcher_home.get('whip', '-')} | **AVG en contra:** .{stats_pitcher_home.get('avg', '-')}")
            else: st.info("Estadísticas no disponibles.")
        else: st.info("Lanzador no definido.")

    st.markdown("---")

    # ==========================================
    # BLOQUE 3: LÍNEAS DE BATEO Y ALINEACIONES
    # ==========================================
    st.header("⚡ 3. Poder Ofensivo y Alineaciones (Lineups)")
    boxscore = live_data.get('boxscore', {})
    teams_box = boxscore.get('teams', {})
    
    tab_away, tab_home = st.tabs([juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']])
    
    df_batters_away = pd.DataFrame()
    df_batters_home = pd.DataFrame()

    with tab_away:
        st.subheader(f"Lineup de {juegos[idx_juego]['away_name']}")
        away_players = teams_box.get('away', {}).get('players', {})
        if away_players:
            lista_bateadores = []
            for pid, pinfo in away_players.items():
                if pinfo.get('position', {}).get('code') != '1': 
                    b_stats = pinfo.get('seasonStats', {}).get('batting', {})
                    lista_bateadores.append({
                        "ID": pinfo.get('person', {}).get('id'),
                        "Jugador": pinfo.get('person', {}).get('fullName'),
                        "Posición": pinfo.get('position', {}).get('abbreviation'),
                        "AVG": float(b_stats.get('avg', '.000').replace('.','0.')),
                        "OPS": float(b_stats.get('ops', '.000').replace('.','0.') if b_stats.get('ops') else 0.0),
                        "HR": b_stats.get('homeRuns', 0)
                    })
            df_batters_away = pd.DataFrame(lista_bateadores)
            if not df_batters_away.empty:
                st.dataframe(df_batters_away.sort_values(by="OPS", ascending=False), use_container_width=True)
        else: st.info("Datos de alineación no disponibles.")
                
    with tab_home:
        st.subheader(f"Lineup de {juegos[idx_juego]['home_name']}")
        home_players = teams_box.get('home', {}).get('players', {})
        if home_players:
            lista_bateadores_home = []
            for pid, pinfo in home_players.items():
                if pinfo.get('position', {}).get('code') != '1':
                    b_stats = pinfo.get('seasonStats', {}).get('batting', {})
                    lista_bateadores_home.append({
                        "ID": pinfo.get('person', {}).get('id'),
                        "Jugador": pinfo.get('person', {}).get('fullName'),
                        "Posición": pinfo.get('position', {}).get('abbreviation'),
                        "AVG": float(b_stats.get('avg', '.000').replace('.','0.')),
                        "OPS": float(b_stats.get('ops', '.000').replace('.','0.') if b_stats.get('ops') else 0.0),
                        "HR": b_stats.get('homeRuns', 0)
                    })
            df_batters_home = pd.DataFrame(lista_bateadores_home)
            if not df_batters_home.empty:
                st.dataframe(df_batters_home.sort_values(by="OPS", ascending=False), use_container_width=True)
        else: st.info("Datos de alineación no disponibles.")

    st.markdown("---")

    # ==========================================
    # BLOQUE 4: ESTADO SITUACIONAL EN TIEMPO REAL
    # ==========================================
    st.header("📈 4. Estado Situacional en Tiempo Real")
    linescore = live_data.get('linescore', {})
    if linescore:
        innings = linescore.get('innings', [])
        if innings:
            score_data = {"Equipo": [juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']]}
            for i, inn in enumerate(innings):
                num_inn = inn.get('num')
                score_data[f"Inning {num_inn}"] = [inn.get('away', {}).get('runs', 0), inn.get('home', {}).get('runs', 0)]
            df_score = pd.DataFrame(score_data)
            st.table(df_score)
        else: st.info("El partido aún no ha comenzado.")
    else: st.info("Información no disponible.")

    st.markdown("---")

    # ==========================================
    # NUEVO BLOQUE 5: PREDICCIÓN ANALÍTICA (Fórmula Log-5 Sabermetrics)
    # ==========================================
    st.header("🧮 5. Módulo Predictivo Inteligente (Duelos Individuales)")
    st.write("Este módulo calcula la probabilidad matemática de que un bateador obtenga un hit basándose en su promedio de bateo contra el promedio de bateo en contra (BAA) del lanzador rival.")
    
    # Promedio histórico de bateo de la MLB (Línea base)
    AVG_LEAGUE = 0.245

    def calcular_log5(avg_bateador, baa_lanzador, avg_liga):
        # Fórmula Log-5 Sabermétrica de Bill James
        numerador = (avg_bateador * baa_lanzador) / avg_liga
        denominador = numerador + ((1 - avg_bateador) * (1 - baa_lanzador) / (1 - avg_liga))
        return numerador / denominador if denominador > 0 else 0.0

    # Determinar qué lineup analizar según la selección
    opcion_lineup = st.radio("Selecciona qué ofensiva deseas proyectar contra el lanzador rival:", 
                             (f"Bateadores de {juegos[idx_juego]['away_name']} vs {home_pitcher.get('fullName', 'Abridor Local')}", 
                              f"Bateadores de {juegos[idx_juego]['home_name']} vs {away_pitcher.get('fullName', 'Abridor Visitante')}"))

    df_analizar = df_batters_away if "away_name" in opcion_lineup else df_batters_home
