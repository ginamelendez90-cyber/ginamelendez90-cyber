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
def obtener_stats_jugador(player_id, group):
    try:
        # Petición directa a la API por tipo de estadística de temporada
        data = statsapi.player_stat_data(player_id, group=group, type="season")
        if data and 'stats' in data and len(data['stats']) > 0:
            return data['stats'][0].get('stats', {}) # Extrae de forma segura el diccionario del primer bloque de estadísticas
        return {}
    except:
        return {}

# CORRECCIÓN CLAVE: Obtener roster en formato JSON estructurado oficial de la MLB
@st.cache_data(ttl=600)
def obtener_roster_estructurado(team_id):
    try:
        response = statsapi.get('team_roster', {'teamId': team_id})
        return response.get('roster', [])
    except:
        return []

# --- PROCESAMIENTO DE PARTIDOS ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido que deseas analizar:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    
    # Carga de IDs de los equipos
    away_id = juegos[idx_juego]['away_id']
    home_id = juegos[idx_juego]['home_id']
    
    feed = obtener_feed_en_vivo(game_id)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})
    
    probables = game_data.get('probablePitchers', {})
    away_pitcher = probables.get('away', {})
    home_pitcher = probables.get('home', {})

    # =========================================================================
    # 🗂️ CREACIÓN DE LAS VENTANAS PRINCIPALES (PESTAÑAS)
    # =========================================================================
    pestana_prepartido, pestana_en_vivo = st.tabs(["📊 ANÁLISIS PRE-PARTIDO (Proyecciones)", "📈 MONITOREO EN VIVO (Tiempo Real)"])

    # =========================================================================
    # 🏟️ VENTANA 1: ANÁLISIS PRE-PARTIDO (CORREGIDA Y OPERATIVA)
    # =========================================================================
    with pestana_prepartido:
        st.header("🔍 Análisis Predictivo y Confrontación de Históricos")
        st.write("Estudio estadístico profundo basado puramente en el rendimiento registrado en la temporada actual.")
        
        venue = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
        clima = game_data.get('weather', {})
        condiciones = f"🌡️ {clima.get('temp', 'N/A')}°F, 🌤️ {clima.get('condition', 'N/A')}, 💨 Viento: {clima.get('wind', 'N/A')}"
        
        c1, c2 = st.columns(2)
        c1.metric("🏟️ Estadio", venue)
        c2.metric("🌤️ Condiciones del Entorno", condiciones)
        
        st.markdown("### 🔮 Duelo de abridores (Datos Registrados)")
        col_p1, col_p2 = st.columns(2)
        
        stats_p_away = {}
        stats_p_home = {}
        
        with col_p1:
            st.subheader(f"Abridor Visitante: {away_pitcher.get('fullName', 'Por anunciar')}")
            if away_pitcher.get('id'):
                stats_p_away = obtener_stats_jugador(away_pitcher['id'], 'pitching')
                if stats_p_away:
                    k = stats_p_away.get('strikeOuts', 0)
                    bb = stats_p_away.get('baseOnBalls', 0)
                    k_bb = round(k / bb, 2) if bb > 0 else k
                    st.metric("Efectividad (ERA)", stats_p_away.get('era', '-'))
                    st.metric("Control (K/BB Ratio)", k_bb)
                    st.write(f"**WHIP:** {stats_p_away.get('whip', '-')} | **Promedio en contra (BAA):** .{stats_p_away.get('avg', '000')}")
                else: st.info("Estadísticas de temporada no disponibles para este lanzador.")
            else: st.info("Lanzador por definir. Se usará un promedio de la liga de .245 para las simulaciones.")
            
        with col_p2:
            st.subheader(f"Abridor Local: {home_pitcher.get('fullName', 'Por anunciar')}")
            if home_pitcher.get('id'):
                stats_p_home = obtener_stats_jugador(home_pitcher['id'], 'pitching')
                if stats_p_home:
                    k = stats_p_home.get('strikeOuts', 0)
                    bb = stats_p_home.get('baseOnBalls', 0)
                    k_bb = round(k / bb, 2) if bb > 0 else k
                    st.metric("Efectividad (ERA)", stats_p_home.get('era', '-'))
                    st.metric("Control (K/BB Ratio)", k_bb)
                    st.write(f"**WHIP:** {stats_p_home.get('whip', '-')} | **Promedio en contra (BAA):** .{stats_p_home.get('avg', '000')}")
                else: st.info("Estadísticas de temporada no disponibles para este lanzador.")
            else: st.info("Lanzador por definir. Se usará un promedio de la liga de .245 para las simulaciones.")

        st.markdown("---")
        st.markdown("### 🧮 Simulación Analítica de Bateo (Fórmula Log-5)")
        
        AVG_LEAGUE = 0.245
        
        def calcular_log5(avg_bat, baa_pitch, avg_league):
            num = (avg_bat * baa_pitch) / avg_league
            den = num + ((1 - avg_bat) * (1 - baa_pitch) / (1 - avg_league))
            return num / den if den > 0 else 0.0

        opcion_lineup = st.radio("Selecciona la ofensiva a proyectar contra el pitcher rival:", 
                                 (f"Bateadores de {juegos[idx_juego]['away_name']}", 
                                  f"Bateadores de {juegos[idx_juego]['home_name']}"))
        
        es_away = juegos[idx_juego]['away_name'] in opcion_lineup
        id_equipo_analizar = away_id if es_away else home_id
        stats_pitcher_rival = stats_p_home if es_away else stats_p_away
        
        # Obtener el roster estructurado oficial en JSON
        roster_json = obtener_roster_estructurado(id_equipo_analizar)
        
        if roster_json:
            # Obtener el promedio de bateo en contra del pitcher (BAA). Si no hay abridor asignado, por defecto es .245
            baa_rival = stats_pitcher_rival.get('avg', 0.245)
            try:
                baa_rival_float = float(baa_rival) if isinstance(baa_rival, (int, float)) else float(f"0.{str(baa_rival).split('.')[-1]}")
            except:
                baa_rival_float = 0.245
            
            lista_predicciones = []
            
            # Barra de progreso visual para indicar que Streamlit está calculando los porcentajes reales
            with st.spinner("Procesando y calculando métricas avanzadas para cada jugador..."):
                for jugador in roster_json:
                    pid = jugador.get('person', {}).get('id')
                    nombre_completo = jugador.get('person', {}).get('fullName', 'Jugador Desconocido')
                    pos = jugador.get('position', {}).get('abbreviation', 'N/A')
                    
                    if pos != 'P': # Filtrar lanzadores de la tabla de bateo
                        b_stats = obtener_stats_jugador(pid, 'batting')
                        
                        # Extraer y transformar el AVG a float de manera segura
                        avg_b = b_stats.get('avg', 0.0)
                        try:
                            avg_b_float = float(avg_b) if isinstance(avg_b, (int, float)) else float(f"0.{str(avg_b).split('.')[-1]}")
                        except:
                            avg_b_float = 0.0
                        
                        # Si el jugador no tiene turnos o estadísticas en el año, no inundar la tabla con ceros
                        if avg_b_float > 0.0:
                            prob_hit = calcular_log5(avg_b_float, baa_rival_float, AVG_LEAGUE)
                            ventaja = "🟢 Alta Ventaja Bateador" if prob_hit > 0.265 else "🟡 Duelo Neutro" if prob_hit > 0.235 else "🔴 Ventaja Lanzador"
                            
                            lista_predicciones.append({
                                "Bateador": nombre_completo,
                                "Posición": pos,
                                "AVG de Temporada": f".{str(avg_b_float).split('.')[-1][:3].ljust(3, '0')}",
                                "Probabilidad de Hit Proyectada": prob_hit,
                                "Diagnóstico Analítico": ventaja
                            })
            
            if lista_predicciones:
                df_pred = pd.DataFrame(lista_predicciones)
                # Ordenar por porcentaje y aplicar formato visual a la columna de probabilidad
                df_pred = df_pred.sort_values(by="Probabilidad de Hit Proyectada", ascending=False)
                df_pred["Probabilidad de Hit Proyectada"] = df_pred["Probabilidad de Hit Proyectada"].map(lambda x: f"{x * 100:.2f}%")
                
                st.subheader("🎯 Reporte Final de Ventajas y Porcentajes de Éxito")
                st.dataframe(df_pred, use_container_width=True, hide_index=True)
            else:
