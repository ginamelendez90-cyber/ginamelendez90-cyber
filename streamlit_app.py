import streamlit as st
import pandas as pd
import statsapi
from datetime import datetime

# Configuración de la página (Modo Ancho para mejor visualización de tablas)
st.set_page_config(page_title="MLB Sabermetrics Advanced Analytics", layout="wide", page_icon="⚾")

st.title("⚾ Sistema Avanzado de Análisis Sabermétrico MLB")
st.markdown("---")

# --- BARRA LATERAL DE CONTROL ---
st.sidebar.header("⚙️ Configuración del Análisis")
fecha_seleccionada = st.sidebar.date_input("Fecha de los partidos:", datetime.today())
Refrescar = st.sidebar.button("🔄 Actualizar Datos en Tiempo Real")

# Función con Caché para optimizar la velocidad y no saturar la API
@st.cache_data(ttl=60)
def obtener_calendario(fecha):
    fecha_str = fecha.strftime('%Y-%m-%d')
    return statsapi.schedule(date=fecha_str)

@st.cache_data(ttl=60)
def obtener_feed_en_vivo(game_pk):
    return statsapi.game_live_feed(game_pk)

@st.cache_data(ttl=300)
def obtener_stats_jugador(player_id, group):
    try:
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        return data.get('stats', [{}])[0].get('stats', {}) if data.get('stats') else {}
    except:
        return {}

# --- PROCESAMIENTO DE PARTIDOS ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    # Selector de partidos
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido que deseas analizar en profundidad:", lista_juegos)
    
    # Extraer el ID único del juego seleccionado
    idx_juego = lista_juegos.index(juego_elegido)
    game_pk = juegos[idx_juego]['game_pk']
    
    # Obtener la data detallada del feed en vivo de la MLB
    feed = obtener_feed_en_vivo(game_pk)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})

    # ==========================================
    # BLOQUE 1: CONTEXTO GENERAL DEL PARTIDO
    # ==========================================
    st.header("🏟️ 1. Entorno del Encuentro")
    venue = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
    clima = game_data.get('weather', {})
    condiciones = f"🌡️ {clima.get('temp', 'N/A')}°F, 🌤️ {clima.get('condition', 'N/A')}, 💨 Viento: {clima.get('wind', 'N/A')}"
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Estadio (Park Factor)", venue)
    c2.metric("Condiciones Climáticas", condiciones)
    c3.metric("Estado Actual", juegos[idx_juego]['status'])
    
    st.markdown("---")

    # ==========================================
    # BLOQUE 2: DUELO DE LANZADORES (PITCHING PROP)
    # ==========================================
    st.header("🔮 2. Análisis Deep-Dive: Lanzadores Abridores")
    
    probables = game_data.get('probablePitchers', {})
    away_pitcher = probables.get('away', {})
    home_pitcher = probables.get('home', {})
    
    col_pitcher1, col_pitcher2 = st.columns(2)
    
    with col_pitcher1:
        st.subheader(f"Visiting Starter: {away_pitcher.get('fullName', 'Por anunciar')}")
        if away_pitcher.get('id'):
            p_stats = obtener_stats_jugador(away_pitcher['id'], 'pitching')
            if p_stats:
                # Cálculos de métricas de control avanzado
                k = p_stats.get('strikeOuts', 0)
                bb = p_stats.get('baseOnBalls', 0)
                k_bb_ratio = round(k / bb, 2) if bb > 0 else k
                
                st.metric("Efectividad (ERA)", p_stats.get('era', '-'))
                st.metric("Lanzadores / Boletos (K/BB Ratio)", k_bb_ratio, help="Mayor a 3.00 indica excelente control.")
                st.write(f"**WHIP:** {p_stats.get('whip', '-')} | **Jonrones Permitidos:** {p_stats.get('homeRuns', '-')}")
                st.write(f"**Promedio de bateo en contra (BAA):** .{p_stats.get('avg', '-')}")
    
    with col_pitcher2:
        st.subheader(f"Home Starter: {home_pitcher.get('fullName', 'Por anunciar')}")
        if home_pitcher.get('id'):
            p_stats = obtener_stats_jugador(home_pitcher['id'], 'pitching')
            if p_stats:
                k = p_stats.get('strikeOuts', 0)
                bb = p_stats.get('baseOnBalls', 0)
                k_bb_ratio = round(k / bb, 2) if bb > 0 else k
                
                st.metric("Efectividad (ERA)", p_stats.get('era', '-'))
                st.metric("Lanzadores / Boletos (K/BB Ratio)", k_bb_ratio)
                st.write(f"**WHIP:** {p_stats.get('whip', '-')} | **Jonrones Permitidos:** {p_stats.get('homeRuns', '-')}")
                st.write(f"**Promedio de bateo en contra (BAA):** .{p_stats.get('avg', '-')}")

    st.markdown("---")

    # ==========================================
    # BLOQUE 3: LÍNEAS DE BATEO Y ALINEACIONES
    # ==========================================
    st.header("⚡ 3. Poder Ofensivo y Alineaciones (*Lineups*)")
    
    # Intentar extraer el Lineup actual del Boxscore si el juego ya inició o está confirmado
    boxscore = live_data.get('boxscore', {})
    teams_box = boxscore.get('teams', {})
    
    tab_away, tab_home = st.tabs([juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']])
    
    with tab_away:
        st.subheader(f"Métricas del Lineup de {juegos[idx_juego]['away_name']}")
        away_players = teams_box.get('away', {}).get('players', {})
        if away_players:
            lista_bateadores = []
            for pid, pinfo in away_players.items():
                if pinfo.get('position', {}).get('code') != '1': # Excluir pitchers del bateo
                    b_stats = pinfo.get('seasonStats', {}).get('batting', {})
                    lista_bateadores.append({
                        "Jugador": pinfo.get('person', {}).get('fullName'),
                        "Posición": pinfo.get('position', {}).get('abbreviation'),
                        "AVG": b_stats.get('avg', '.000'),
                        "OBP": b_stats.get('obp', '.000'),
                        "SLG": b_stats.get('slg', '.000'),
                        "OPS": b_stats.get('ops', '.000'),
                        "HR": b_stats.get('homeRuns', 0),
                        "RBI": b_stats.get('rbi', 0)
                    })
            df_away = pd.DataFrame(lista_bateadores)
            if not df_away.empty:
                st.dataframe(df_away.sort_values(by="OPS", ascending=False), use_container_width=True)
            else:
                st.info("Lineup detallado no disponible aún para este juego.")
                
    with tab_home:
        st.subheader(f"Métricas del Lineup de {juegos[idx_juego]['home_name']}")
        home_players = teams_box.get('home', {}).get('players', {})
        if home_players:
            lista_bateadores_home = []
            for pid, pinfo in home_players.items():
                if pinfo.get('position', {}).get('code') != '1':
                    b_stats = pinfo.get('seasonStats', {}).get('batting', {})
                    lista_bateadores_home.append({
                        "Jugador": pinfo.get('person', {}).get('fullName'),
                        "Posición": pinfo.get('position', {}).get('abbreviation'),
                        "AVG": b_stats.get('avg', '.000'),
                        "OBP": b_stats.get('obp', '.000'),
                        "SLG": b_stats.get('slg', '.000'),
                        "OPS": b_stats.get('ops', '.000'),
                        "HR": b_stats.get('homeRuns', 0),
                        "RBI": b_stats.get('rbi', 0)
                    })
            df_home = pd.DataFrame(lista_bateadores_home)
            if not df_home.empty:
                st.dataframe(df_home.sort_values(by="OPS", ascending=False), use_container_width=True)
            else:
                st.info("Lineup detallado no disponible aún para este juego.")

    st.markdown("---")

    # ==========================================
    # BLOQUE 4: ANÁLISIS EN VIVO Y SITUACIONAL
    # ==========================================
    st.header("📈 4. Estado Situacional en Tiempo Real")
    
    linescore = live_data.get('linescore', {})
    
    if linescore:
        # Puntuación por entradas (Inning by Inning)
        st.subheader("Tablero de Anotaciones (Linescore)")
        innings = linescore.get('innings', [])
        
        if innings:
            score_data = {"Equipo": [juegos[idx_juego]['away_name'], juegos[idx_juego]['home_name']]}
            for i, inn in enumerate(innings):
                num_inn = inn.get('num')
                score_data[f"Inning {num_inn}"] = [
                    inn.get('away', {}).get('runs', 0),
                    inn.get('home', {}).get('runs', 0)
                ]
            
            # Añadir Totales de Carreras, Hits y Errores (R-H-E)
            score_data["C (Runs)"] = [linescore.get('teams', {}).get('away', {}).get('runs', 0), linescore.get('teams', {}).get('home', {}).get('runs', 0)]
            score_data["H (Hits)"] = [linescore.get('teams', {}).get('away', {}).get('hits', 0), linescore.get('teams', {}).get('home', {}).get('hits', 0)]
            score_data["E (Errors)"] = [linescore.get('teams', {}).get('away', {}).get('errors', 0), linescore.get('teams', {}).get('home', {}).get('errors', 0)]
            
            df_score = pd.DataFrame(score_data)
            st.table(df_score)
            
            # Situación de las Bases (Si el juego está en vivo)
            st.subheader("🏃 Corredores en Base actualmente")
            offense = linescore.get('offense', {})
            c_base1, c_base2, c_base3 = st.columns(3)
            c_base1.checkbox("Primera Base", value='first' in offense)
            c_base2.checkbox("Segunda Base", value='second' in offense)
            c_base3.checkbox("Tercera Base", value='third' in offense)
        else:
