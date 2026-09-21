import streamlit as st
import pandas as pd
import statsapi
from datetime import datetime

# Configuración de la interfaz
st.set_page_config(page_title="MLB Pro Sabermetrics Analytics", layout="wide", page_icon="⚾")

st.title("🚀 Sistema Avanzado de Predicción Sabermétrica MLB Pro")
st.markdown("---")

# --- BARRA LATERAL DE CONFIGURACIÓN ---
st.sidebar.header("⚙️ Panel de Control")
fecha_seleccionada = st.sidebar.date_input("Fecha de Análisis:", datetime.today())

# --- FUNCIONES AUXILIARES Y DE EXTRACCIÓN OPTIMIZADAS ---
def parse_stat_float(val, default=0.0):
    """Convierte métricas de la MLB API a flotante de forma segura."""
    try:
        if val is None or val == '' or val == '-':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

@st.cache_data(ttl=120)
def obtener_calendario(fecha):
    fecha_str = fecha.strftime('%Y-%m-%d')
    return statsapi.schedule(date=fecha_str)

@st.cache_data(ttl=120)
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
                    whip_val = splits[0].get('stat', {}).get('whip', 1.30)
                    return parse_stat_float(whip_val, default=1.30)
        return 1.30
    except Exception:
        return 1.30

# --- PROCESAMIENTO E INTERFAZ ---
juegos = obtener_calendario(fecha_seleccionada)

if not juegos:
    st.warning("⚠️ No se encontraron partidos programados para la fecha seleccionada.")
else:
    lista_juegos = [f"{j['away_name']} @ {j['home_name']} - Estado: {j['status']}" for j in juegos]
    juego_elegido = st.selectbox("🎯 Selecciona el partido para el Deep-Dive Analítico:", lista_juegos)
    
    idx_juego = lista_juegos.index(juego_elegido)
    game_id = juegos[idx_juego]['game_id']
    away_id = juegos[idx_juego]['away_id']
    home_id = juegos[idx_juego]['home_id']
    away_name = juegos[idx_juego]['away_name']
    home_name = juegos[idx_juego]['home_name']
    
    feed = obtener_feed_en_vivo(game_id)
    game_data = feed.get('gameData', {})
    live_data = feed.get('liveData', {})
    
    probables = game_data.get('probablePitchers', {})
    away_pitcher = probables.get('away', {})
    home_pitcher = probables.get('home', {})

    # Crear Ventanas
    pestana_prepartido, pestana_en_vivo = st.tabs(["📊 ANÁLISIS PRE-PARTIDO (Proyecciones)", "📈 MONITOREO EN VIVO (Tiempo Real)"])

    # VENTANA PRE-PARTIDO COMPLETA
    with pestana_prepartido:
        st.header("⚡ 1. Ventaja por Entorno y Clima")
        venue = game_data.get('venue', {}).get('name', 'Estadio Desconocido')
        clima = game_data.get('weather', {})
        temp = clima.get('temp', '70')
        viento = clima.get('wind', '0 mph, Calm')
        
        try:
            temp_int = int(temp)
            impacto_clima = "🔥 Favorable al Bateo (Alta temperatura)" if temp_int > 80 else "🥶 Favorable al Pitcheo (Aire denso/frío)" if temp_int < 60 else "😐 Condición Neutra"
        except (ValueError, TypeError):
            impacto_clima = "😐 Condición Neutra"

        c1, c2, c3 = st.columns(3)
        c1.metric("Estadio", venue)
        c2.metric("Condiciones", f"🌡️ {temp}°F | 💨 {viento}")
        c3.metric("Impacto Proyectado", impacto_clima)

        st.markdown("---")
        st.header("🔮 2. Duelo de Abridores y Relevos (Bullpen)")
        
        col_p1, col_p2 = st.columns(2)
        stats_p_away = {}
        stats_p_home = {}
        
        with col_p1:
            st.subheader(f"Visiting Starter: {away_pitcher.get('fullName', 'Por anunciar')}")
            if away_pitcher.get('id'):
                stats_p_away = obtener_stats_jugador(away_pitcher['id'], 'pitching')
                pitcher_info = game_data.get('players', {}).get(f"ID{away_pitcher.get('id')}", {})
                hand = pitcher_info.get('pitchHand', {}).get('code', 'R')
                if stats_p_away:
                    st.metric("Efectividad (ERA)", stats_p_away.get('era', '-'))
                    st.write(f"**WHIP:** {stats_p_away.get('whip', '-')} | **Mano:** {hand}")
            
            whip_bp_away = obtener_whip_bullpen(away_id)
            st.metric("WHIP Promedio del Bullpen", whip_bp_away, help="Menor a 1.20 es un bullpen de élite.")

        with col_p2:
            st.subheader(f"Home Starter: {home_pitcher.get('fullName', 'Por anunciar')}")
            if home_pitcher.get('id'):
                stats_p_home = obtener_stats_jugador(home_pitcher['id'], 'pitching')
                pitcher_info = game_data.get('players', {}).get(f"ID{home_pitcher.get('id')}", {})
                hand = pitcher_info.get('pitchHand', {}).get('code', 'R')
                if stats_p_home:
                    st.metric("Efectividad (ERA)", stats_p_home.get('era', '-'))
                    st.write(f"**WHIP:** {stats_p_home.get('whip', '-')} | **Mano:** {hand}")
            
            whip_bp_home = obtener_whip_bullpen(home_id)
            st.metric("WHIP Promedio del Bullpen", whip_bp_home, help="Menor a 1.20 es un bullpen de élite.")

        st.markdown("---")
        st.header("🧮 3. Algoritmo Predictivo Log-5 Ajustado")
        
        opcion_lineup = st.radio("Selecciona la ofensiva a proyectar:", 
                                 (f"Bateadores de {away_name}", 
                                  f"Bateadores de {home_name}"))
        
        es_away = away_name in opcion_lineup
        id_equipo_analizar = away_id if es_away else home_id
        stats_pitcher_rival = stats_p_home if es_away else stats_p_away
        whip_bullpen_rival = whip_bp_home if es_away else whip_bp_away
        
        roster_json = obtener_roster_estructurado(id_equipo_analizar)
        
        if roster_json:
            baa_rival_float = parse_stat_float(stats_pitcher_rival.get('avg'), default=0.245)
            lista_predicciones = []
            
            for jugador in roster_json:
                pid = jugador.get('person', {}).get('id')
                nombre_completo = jugador.get('person', {}).get('fullName', 'Jugador')
                pos = jugador.get('position', {}).get('abbreviation', 'N/A')
                
                if pos != 'P':
                    b_stats = obtener_stats_jugador(pid, 'batting')
                    avg_b_float = parse_stat_float(b_stats.get('avg'), default=0.0)
                    
                    if avg_b_float > 0.0:
                        # FÓRMULA LOG-5 COMPUESTA: Evalúa el éxito ante el abridor
                        num = (avg_b_float * baa_rival_float) / 0.245
                        den = num + ((1 - avg_b_float) * (1 - baa_rival_float) / (1 - 0.245))
                        prob_hit = num / den if den > 0 else 0.0
                        
                        # AJUSTE PRO: Si el Bullpen rival es malo (WHIP alto), la probabilidad sube
                        if whip_bullpen_rival > 1.35:
                            prob_hit += 0.015
                        elif whip_bullpen_rival < 1.15:
                            prob_hit -= 0.015
                        
                        ventaja = "🟢 Alta Ventaja" if prob_hit > 0.270 else "🟡 Neutro" if prob_hit > 0.240 else "🔴 Desventaja"
                        
                        lista_predicciones.append({
                            "Bateador": nombre_completo,
                            "Posición": pos,
                            "AVG Temporada": f".{int(round(avg_b_float * 1000)):03d}",
                            "Probabilidad Hit Proyectada": prob_hit,
                            "Diagnóstico Pro": ventaja
                        })
            
            if lista_predicciones:
                df_pred = pd.DataFrame(lista_predicciones).sort_values(by="Probabilidad Hit Proyectada", ascending=False)
                df_pred["Probabilidad Hit Proyectada"] = df_pred["Probabilidad Hit Proyectada"].map(lambda x: f"{x * 100:.2f}%")
                st.dataframe(df_pred, use_container_width=True, hide_index=True)
            else:
                st.info("No hay suficientes datos registrados de turnos al bate para este equipo.")
        else:
            st.error("No se pudo cargar el Roster.")

    # VENTANA EN VIVO
    with pestana_en_vivo:
        st.header("🏟️ Transmisión en Tiempo Real")
        st.metric("Estado del Juego", juegos[idx_juego]['status'])
        
        linescore = live_data.get('linescore', {})
        entradas_lista = linescore.get('innings', [])
        
        if entradas_lista:
            tabla_innings = []
            for inn in entradas_lista:
                tabla_innings.append({
                    "Inning": inn.get('num'),
                    f"{away_name} (Vis)": inn.get('away', {}).get('runs', '-'),
                    f"{home_name} (Loc)": inn.get('home', {}).get('runs', '-')
                })
            df_linescore = pd.DataFrame(tabla_innings)
            st.subheader("Tablero por Entradas (Linescore)")
            st.dataframe(df_linescore, use_container_width=True, hide_index=True)
            
            # Resumen Total R / H / E
            teams = linescore.get('teams', {})
            away_totals = teams.get('away', {})
            home_totals = teams.get('home', {})
            
            c_tot1, c_tot2 = st.columns(2)
            c_tot1.metric(f"Total {away_name}", f"R: {away_totals.get('runs', 0)} | H: {away_totals.get('hits', 0)} | E: {away_totals.get('errors', 0)}")
            c_tot2.metric(f"Total {home_name}", f"R: {home_totals.get('runs', 0)} | H: {home_totals.get('hits', 0)} | E: {home_totals.get('errors', 0)}")
        else:
            st.info("El partido seleccionado aún no inicia o no hay datos en vivo registrados.")
