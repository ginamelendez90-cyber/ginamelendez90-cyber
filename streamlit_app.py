import streamlit as st
import pandas as pd
import statsapi
from datetime import datetime

# Configuración de la página en modo ancho
st.set_page_config(page_title="MLB Sabermetrics Advanced Analytics", layout="wide", page_icon="⚾")

st.title("⚾ Sistema Avanzado de Análisis Sabermétrico MLB")
st.markdown("---")

# --- BARRA LATERAL DE CONTROL ---
st.sidebar.header("⚙️ Configuración Global")
fecha_seleccionada = st.sidebar.date_input("Fecha de los partidos:", datetime.today())

# Funciones de consulta optimizadas con caché
@st.cache_data(ttl=120)
def obtener_calendario(fecha):
    fecha_str = fecha.strftime('%Y-%m-%d')
    return statsapi.schedule(date=fecha_str)

@st.cache_data(ttl=120)
def obtener_feed_en_vivo(game_id):
    try:
        return statsapi.get('game', {'gamePk': game_id})
    except:
        return {}

@st.cache_data(ttl=600)
def obtener_stats_jugador(player_id, group, stat_type="season"):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type=stat_type)
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
    # Selector único de partidos
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido que deseas analizar:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    
    # Carga de datos base de la API
    feed = obtener_feed_en_vivo(game_id)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})
    
    # Extraer IDs de lanzadores abridores confirmados o probables
    probables = game_data.get('probablePitchers', {})
    away_pitcher = probables.get('away', {})
    home_pitcher = probables.get('home', {})

    # =========================================================================
    # 🗂️ CREACIÓN DE LAS VENTANAS PRINCIPALES (PESTAÑAS)
    # =========================================================================
    pestana_prepartido, pestana_en_vivo = st.tabs(["📊 ANÁLISIS PRE-PARTIDO (Proyecciones)", "📈 MONITOREO EN VIVO (Tiempo Real)"])

    # =========================================================================
    # 🏟️ VENTANA 1: ANÁLISIS PRE-PARTIDO (Métricas Históricas y Pronósticos)
    # =========================================================================
    with pestana_prepartido:
        st.header("🔍 Análisis Predictivo y Confrontación de Históricos")
        st.write("Estudio estadístico profundo basado puramente en el rendimiento registrado en la temporada actual.")
        
        # Sub-bloque 1: Estadio y Clima
        venue = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
        clima = game_data.get('weather', {})
        condiciones = f"🌡️ {clima.get('temp', 'N/A')}°F, 🌤️ {clima.get('condition', 'N/A')}, 💨 Viento: {clima.get('wind', 'N/A')}"
        
        c1, c2 = st.columns(2)
        c1.metric("🏟️ Estadio (Park Factor)", venue)
        c2.metric("🌤️ Condiciones del Entorno", condiciones)
        
        st.markdown("### 🔮 Duelo de abridores (Datos Registrados)")
        col_p1, col_p2 = st.columns(2)
        
        stats_p_away = {}
        stats_p_home = {}
        
        with col_p1:
            st.subheader(f"Abridor Visitante: {away_pitcher.get('fullName', 'Por anunciar')}")
            if away_pitcher.get('id'):
                stats_p_away = obtener_stats_jugador(away_pitcher['id'], 'pitching', 'season')
                if stats_p_away:
                    k = stats_p_away.get('strikeOuts', 0)
                    bb = stats_p_away.get('baseOnBalls', 0)
                    k_bb = round(k / bb, 2) if bb > 0 else k
                    
                    st.metric("Efectividad (ERA)", stats_p_away.get('era', '-'))
                    st.metric("Control (K/BB Ratio)", k_bb)
                    st.write(f"**WHIP:** {stats_p_away.get('whip', '-')} | **Gana/Pierde:** {stats_p_away.get('wins', 0)}-{stats_p_away.get('losses', 0)}")
                    st.write(f"**Promedio en contra (BAA):** .{stats_p_away.get('avg', '000')}")
                else: st.info("Datos de temporada no disponibles.")
            else: st.info("Lanzador por definir.")
            
        with col_p2:
            st.subheader(f"Abridor Local: {home_pitcher.get('fullName', 'Por anunciar')}")
            if home_pitcher.get('id'):
                stats_p_home = obtener_stats_jugador(home_pitcher['id'], 'pitching', 'season')
                if stats_p_home:
                    k = stats_p_home.get('strikeOuts', 0)
                    bb = stats_p_home.get('baseOnBalls', 0)
                    k_bb = round(k / bb, 2) if bb > 0 else k
                    
                    st.metric("Efectividad (ERA)", stats_p_home.get('era', '-'))
                    st.metric("Control (K/BB Ratio)", k_bb)
                    st.write(f"**WHIP:** {stats_p_home.get('whip', '-')} | **Gana/Pierde:** {stats_p_home.get('wins', 0)}-{stats_p_home.get('losses', 0)}")
                    st.write(f"**Promedio en contra (BAA):** .{stats_p_home.get('avg', '000')}")
                else: st.info("Datos de temporada no disponibles.")
            else: st.info("Lanzador por definir.")

        st.markdown("---")
        st.markdown("### 🧮 Simulación Analítica de Bateo (Fórmula Log-5)")
        
        # Cargar rosters/lineups registrados históricos si el juego no ha empezado
        boxscore = live_data.get('boxscore', {})
        teams_box = boxscore.get('teams', {})
        
        AVG_LEAGUE = 0.245
        
        def calcular_log5(avg_bat, baa_pitch, avg_league):
            num = (avg_bat * baa_pitch) / avg_league
            den = num + ((1 - avg_bat) * (1 - baa_pitch) / (1 - avg_league))
            return num / den if den > 0 else 0.0

        opcion_lineup = st.radio("Selecciona la ofensiva a proyectar contra el pitcher rival:", 
                                 (f"Bateadores de {juegos[idx_juego]['away_name']}", 
                                  f"Bateadores de {juegos[idx_juego]['home_name']}"))
        
        es_away = juegos[idx_juego]['away_name'] in opcion_lineup
        players_dict = teams_box.get('away', {}).get('players', {}) if es_away else teams_box.get('home', {}).get('players', {})
        stats_pitcher_rival = stats_p_home if es_away else stats_p_away

        if players_dict and stats_pitcher_rival:
            baa_rival = stats_pitcher_rival.get('avg', '.245')
            try: baa_rival_float = float(f"0.{baa_rival.split('.')[-1]}") if '.' in str(baa_rival) else 0.245
            except: baa_rival_float = 0.245
            
            lista_predicciones = []
            for pid, pinfo in players_dict.items():
                if pinfo.get('position', {}).get('code') != '1':
                    b_stats = pinfo.get('seasonStats', {}).get('batting', {})
                    avg_b_str = b_stats.get('avg', '.000')
                    try: avg_b_float = float(f"0.{avg_b_str.split('.')[-1]}") if '.' in str(avg_b_str) else 0.0
                    except: avg_b_float = 0.0
                    
                    prob_hit = calcular_log5(avg_b_float, baa_rival_float, AVG_LEAGUE)
                    ventaja = "🟢 Alta Ventaja Bateador" if prob_hit > 0.270 else "🟡 Duelo Neutro" if prob_hit > 0.240 else "🔴 Ventaja Lanzador"
                    
                    lista_predicciones.append({
                        "Bateador": pinfo.get('person', {}).get('fullName'),
                        "AVG Acumulado": avg_b_float,
                        "Probabilidad de Hit Hoy": f"{prob_hit * 100:.2f}%",
                        "Diagnóstico Analítico": ventaja
                    })
            
            if lista_predicciones:
                df_pred = pd.DataFrame(lista_predicciones)
                st.dataframe(df_pred.sort_values(by="Probabilidad de Hit Hoy", ascending=False), use_container_width=True)
            else: st.info("Los datos de las líneas de bateo acumuladas no están disponibles.")
        else:
            st.info("⚠️ Para partidos de fechas futuras, los rosters o los abridores probables aún no se encuentran registrados en la base de datos de la API.")

    # =========================================================================
    # 📈 VENTANA 2: MONITOREO EN VIVO (Se activa solo si el partido inició)
    # =========================================================================
    with pestana_en_vivo:
        st.header("🏟️ Panel de Eventos en Tiempo Real")
        st.write("Estado actual del marcador y las bases una vez que se efectúa el primer lanzamiento.")
        
        st.metric("Estado del Juego", juegos[idx_juego]['status'])
        linescore = live_data.get('linescore', {})
        
        if linescore and linescore.get('innings'):
            st.subheader("Tablero de Anotaciones (Linescore)")
            innings = linescore.get('innings', [])
            score_data = {"Equipo": [juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']]}
            for inn in innings:
                num_inn = inn.get('num')
                score_data[f"Inning {num_inn}"] = [inn.get('away', {}).get('runs', 0), inn.get('home', {}).get('runs', 0)]
            
            st.table(pd.DataFrame(score_data))
            
            st.subheader("🏃 Estado de las Almohadillas")
            offense = linescore.get('offense', {})
            cb1, cb2, cb3 = st.columns(3)
            cb1.checkbox("Primera Base ocupada", value='first' in offense, disabled=True)
            cb2.checkbox("Segunda Base ocupada", value='second' in offense, disabled=True)
