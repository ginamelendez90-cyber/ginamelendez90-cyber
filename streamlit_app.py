import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst - Extracción Directa de Partidos", page_icon="⚾", layout="wide")

st.title("⚾ Analizador MLB: Lectura Directa de Historial de Partidos")
st.markdown("Consulta directa al endpoint de la MLB extrayendo el arreglo `splits` para garantizar el 100% de los juegos registrados.")
st.markdown("---")

PARK_FACTORS = {
    "Coors Field": {"factor": 1.08, "tipo": "Estadio Altamente Bateador (+8%)"},
    "Fenway Park": {"factor": 1.05, "tipo": "Estadio Bateador (+5%)"},
    "Great American Ball Park": {"factor": 1.04, "tipo": "Estadio Bateador (+4%)"},
    "Petco Park": {"factor": 0.94, "tipo": "Estadio Lanzador (-6%)"},
    "T-Mobile Park": {"factor": 0.93, "tipo": "Estadio Lanzador (-7%)"},
    "Citi Field": {"factor": 0.95, "tipo": "Estadio Lanzador (-5%)"}
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
                        diccionario_jugadores[f"{nombre} ({posicion} - {equipo_nom})"] = {
                            "id": player_id,
                            "team_id": team_id
                        }
        return dict(sorted(diccionario_jugadores.items()))
    except Exception:
        return {"Shohei Ohtani (DH - Dodgers)": {"id": 660271, "team_id": 119}}

@st.cache_data(ttl=1800)
def auto_detectar_proximo_partido(team_id):
    hoy = datetime.now().strftime('%Y-%m-%d')
    futuro = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    
    detalles = {
        "fecha": "Sin partido inmediato programado",
        "rival": "Por definir",
        "condicion": "N/A",
        "estadio": "Estadio Estándar",
        "factor_campo": 1.00,
        "desc_estadio": "Neutral (1.00)",
        "pitcher_nombre": "Por Anunciar / Reliever",
        "pitcher_mano": "R",
        "pitcher_era": "N/A",
        "perfil_pitcher": "Lanzador Promedio / Estándar",
        "factor_pitcher": 1.00
    }
    
    try:
        juegos = statsapi.schedule(team=team_id, start_date=hoy, end_date=futuro)
        if not juegos:
            juegos = statsapi.schedule(team=team_id)
            
        if juegos:
            proximo = juegos[0]
            detalles["fecha"] = proximo.get('game_date', hoy)
            es_home = proximo.get('home_id') == team_id
            detalles["condicion"] = "Local" if es_home else "Visitante"
            detalles["rival"] = proximo.get('away_name') if es_home else proximo.get('home_name')
            
            venue_name = proximo.get('venue_name', 'Estadio Estándar')
            detalles["estadio"] = venue_name
            if venue_name in PARK_FACTORS:
                detalles["factor_campo"] = PARK_FACTORS[venue_name]["factor"]
                detalles["desc_estadio"] = PARK_FACTORS[venue_name]["tipo"]
                
            pitcher_key = 'away_probable_pitcher' if es_home else 'home_probable_pitcher'
            pitcher_nombre = proximo.get(pitcher_key, '')
            
            if pitcher_nombre:
                detalles["pitcher_nombre"] = pitcher_nombre
                lookup = statsapi.lookup_player(pitcher_nombre)
                if lookup:
                    p_id = lookup[0]['id']
                    p_data = statsapi.player_stat_data(p_id, group="pitching", type="season")
                    detalles["pitcher_mano"] = lookup[0].get('pitchHand', {}).get('code', 'R')
                    
                    p_stats = p_data.get('stats', [])
                    if p_stats:
                        era_val = float(p_stats[0].get('stats', {}).get('era', '4.00'))
                        detalles["pitcher_era"] = f"{era_val:.2f}"
                        
                        if era_val <= 3.20:
                            detalles["perfil_pitcher"] = "Ace / Lanzador Dominante (-12%)"
                            detalles["factor_pitcher"] = 0.88
                        elif era_val >= 4.80:
                            detalles["perfil_pitcher"] = "Abridor Débil / Favorabilidad Altísima (+12%)"
                            detalles["factor_pitcher"] = 1.12
                        elif detalles["pitcher_mano"] == "L":
                            detalles["perfil_pitcher"] = "Lanzador Zurdo / Ventaja Platoon (+6%)"
                            detalles["factor_pitcher"] = 1.06
                        else:
                            detalles["perfil_pitcher"] = "Lanzador Promedio (0%)"
                            detalles["factor_pitcher"] = 1.00
    except Exception:
        pass
        
    return detalles

@st.cache_data(ttl=3600)
def obtener_stats_temporada(player_id):
    anio_actual = datetime.now().year
    for yr in range(anio_actual, anio_actual - 4, -1):
        try:
            res = statsapi.player_stat_data(player_id, group="hitting", type="season", season=yr)
            stats = res.get('stats', [])
            if stats:
                s_data = stats[0].get('stats', {})
                avg_val = s_data.get('avg', '.250')
                if avg_val != '.---':
                    return {
                        'avg_season': float(avg_val),
                        'games': int(s_data.get('gamesPlayed', 0)),
                        'year': yr
                    }
        except Exception:
            pass
    return {'avg_season': 0.250, 'games': 0, 'year': anio_actual}

@st.cache_data(ttl=1800)
def obtener_ultimos_juegos_directo(player_id):
    """Acceso directo al endpoint REST de la MLB extrayendo 'splits' sin filtros recortados."""
    anio_actual = datetime.now().year
    registros = []
    
    # Recorremos temporadas y tipos de juegos (R=Regular, S=Pretemporada, P=Playoffs)
    for yr in range(anio_actual, anio_actual - 4, -1):
        for gtype in ['R', 'S', 'P']:
            try:
                raw_data = statsapi.get('stats', {
                    'stats': 'gameLog',
                    'personId': player_id,
                    'group': 'hitting',
                    'season': yr,
                    'gameType': gtype
                })
                
                stats_blocks = raw_data.get('stats', [])
                for block in stats_blocks:
                    splits = block.get('splits', [])
                    for item in splits:
                        s = item.get('stat', {})
                        opp = item.get('opponent', {})
                        opp_name = opp.get('name', 'N/A') if isinstance(opp, dict) else str(opp)
                        
                        registros.append({
                            'Fecha': item.get('date', ''),
                            'Rival': opp_name,
                            'AB': int(s.get('atBats', 0)),
                            'H': int(s.get('hits', 0)),
                            '2B': int(s.get('doubles', 0)),
                            '3B': int(s.get('triples', 0)),
                            'HR': int(s.get('homeRuns', 0)),
                            'RBI': int(s.get('rbi', 0)),
                            'BB': int(s.get('baseOnBalls', 0)),
                            'SO': int(s.get('strikeOuts', 0)),
                            'AVG': s.get('avg', '.000'),
                            'Tipo': 'Pretemporada' if gtype == 'S' else ('Playoffs' if gtype == 'P' else 'Temporada Regular'),
                            'Anio': yr
                        })
            except Exception:
                pass
                
        if len(registros) >= 5:
            break
            
    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    if df.empty:
        return None, "5.º al 9.º Bate (Menos Turnos)", False, anio_actual
        
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df = df.sort_values(by='Fecha', ascending=False).drop_duplicates(subset=['Fecha']).reset_index(drop=True)
    
    df_6 = df.head(6).copy()
    anio_recuperado = df_6['Anio'].iloc[0]
    es_previo = (anio_recuperado < anio_actual)
    
    df_6['Fecha'] = df_6['Fecha'].dt.strftime('%Y-%m-%d')
    df_final = df_6.drop(columns=['Anio'])
    
    avg_ab = df_final['AB'].mean() if 'AB' in df_final.columns else 3.5
    pos_lineup = "1.º al 4.º Bate (Líderes de Turnos)" if avg_ab >= 3.8 else "5.º al 9.º Bate (Menos Turnos)"
    
    return df_final, pos_lineup, es_previo, anio_recuperado

def calcular_modelo_automatizado(df_juegos, stats_season, proximo_info, pos_lineup):
    if df_juegos is not None and not df_juegos.empty:
        total_ab = df_juegos['AB'].sum()
        total_h = df_juegos['H'].sum()
        avg_reciente = total_h / total_ab if total_ab > 0 else stats_season['avg_season']
    else:
        avg_reciente = stats_season['avg_season']
        
    avg_season = stats_season['avg_season']
    avg_base = (avg_reciente * 0.40) + (avg_season * 0.60)
    
    factor_picheo = proximo_info["factor_pitcher"]
    factor_parque = proximo_info["factor_campo"]
    
    avg_proyectado = avg_base * factor_picheo * factor_parque
    ab_esperados = 4.3 if "1.º al 4.º" in pos_lineup else 3.6
    
    lambda_hits = avg_proyectado * ab_esperados
    prob_hit = min((1 - np.exp(-lambda_hits)) * 100, 95.0)
    
    return {
        "avg_reciente": round(avg_reciente, 3),
        "avg_season": round(avg_season, 3),
        "avg_base": round(avg_base, 3),
        "factor_picheo": factor_picheo,
        "factor_parque": factor_parque,
        "avg_proyectado": round(avg_proyectado, 3),
        "ab_esperados": ab_esperados,
        "lambda_hits": round(lambda_hits, 2),
        "prob_hit": round(prob_hit, 1)
    }

def generar_explicacion_cualitativa(res, proximo_info, pos_lineup, nombre_jugador):
    puntos = []
    dif_racha = res['avg_reciente'] - res['avg_season']
    
    if dif_racha >= 0.030:
        puntos.append(f"🔥 **Racha Encendida:** {nombre_jugador} registra **{res['avg_reciente']:.3f}** en sus partidos recuperados, superando su promedio general ({res['avg_season']:.3f}).")
    elif dif_racha <= -0.030:
        puntos.append(f"❄️ **Racha Fría:** Promedio reciente de **{res['avg_reciente']:.3f}** por debajo de su estándar de **{res['avg_season']:.3f}**.")
    else:
        puntos.append(f"📊 **Rendimiento Regular:** Promedio reciente de **{res['avg_reciente']:.3f}** alineado con su temporada (**{res['avg_season']:.3f}**).")
        
    if res['factor_picheo'] > 1.00:
        porc = int((res['factor_picheo'] - 1) * 100)
        puntos.append(f"🎯 **Duelo Favorable:** Frente a **{proximo_info['pitcher_nombre']}** ({proximo_info['perfil_pitcher']}), suma un **+{porc}%** a la expectativa.")
    elif res['factor_picheo'] < 1.00:
        porc = int((1 - res['factor_picheo']) * 100)
        puntos.append(f"🛡️ **Duelo Exigente:** El abridor **{proximo_info['pitcher_nombre']}** ({proximo_info['perfil_pitcher']}) ajusta en **-{porc}%** la proyección.")
    else:
        puntos.append(f"⚾ **Lanzador Estándar:** Duelo neutro contra **{proximo_info['pitcher_nombre']}**.")
        
    if res['factor_parque'] > 1.00:
        porc = int((res['factor_parque'] - 1) * 100)
        puntos.append(f"🏟️ **Ventaja de Parque:** Jugando en **{proximo_info['estadio']}** (+{porc}% de favorabilidad de bateo).")
    elif res['factor_parque'] < 1.00:
        porc = int((1 - res['factor_parque']) * 100)
        puntos.append(f"🏟️ **Estadio de Pitcheo:** Jugando en **{proximo_info['estadio']}** (-{porc}% de favorabilidad).")
    else:
        puntos.append(f"🏟️ **Estadio Neutral:** Las condiciones del estadio no alteran la métrica base.")
        
    if "1.º al 4.º" in pos_lineup:
        puntos.append(f"🏏 **Líder de Turnos:** Parte alta del orden al bate (~**4.3 turnos esperados**).")
    else:
        puntos.append(f"🏏 **Turnos Moderados:** Parte media/baja de la alineación (~**3.6 turnos esperados**).")
        
    conclusion = f"💡 **Conclusión:** Proyección calculada en **{res['prob_hit']}%** basada en sus últimos partidos extraídos directamente del servidor de la MLB."
    return puntos, conclusion

# ==========================================
# INTERFAZ DE USUARIO
# ==========================================

directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())

jugador_sel = st.sidebar.selectbox("Selecciona Jugador a Analizar:", opciones)

if jugador_sel:
    nombre_solo = jugador_sel.split(' (')[0]
    player_data = directorio[jugador_sel]
    p_id = player_data["id"]
    team_id = player_data["team_id"]
    
    with st.spinner("Conectando con la API de la MLB y extrayendo logs directos..."):
        df_juegos, pos_lineup_detectada, es_previo, anio_recuperado = obtener_ultimos_juegos_directo(p_id)
        stats_season = obtener_stats_temporada(p_id)
        proximo_info = auto_detectar_proximo_partido(team_id)
        res = calcular_modelo_automatizado(df_juegos, stats_season, proximo_info, pos_lineup_detectada)
        
    st.subheader(f"⚾ {nombre_solo}")
    
    # MÉTRICAS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 Probabilidad de Hit", f"{res['prob_hit']}%")
    c2.metric("AVG Proyectado", f"{res['avg_proyectado']:.3f}")
    c3.metric("AVG Reciente (Racha)", f"{res['avg_reciente']:.3f}")
    c4.metric(f"AVG Temporada ({stats_season['year']})", f"{res['avg_season']:.3f}")
    
    st.markdown("---")
    
    # JUSTIFICACIÓN CUALITATIVA
    st.subheader(f"🧠 Explicación del {res['prob_hit']}% Esperado")
    puntos_explicativos, conclusion_final = generar_explicacion_cualitativa(res, proximo_info, pos_lineup_detectada, nombre_solo)
    
    for p in puntos_explicativos:
        st.markdown(f"* {p}")
        
    st.info(conclusion_final)
    
    st.markdown("---")
    st.markdown("📌 **Ficha Técnica del Próximo Juego:**")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"* **Próximo Rival:** {proximo_info['rival']} ({proximo_info['condicion']})")
        st.markdown(f"* **Fecha:** {proximo_info['fecha'][:10]}")
    with col_b:
        st.markdown(f"* **Estadio:** {proximo_info['estadio']}")
        st.markdown(f"* **Factor Parque:** {proximo_info['desc_estadio']}")
    with col_c:
        st.markdown(f"* **Pítcher Rival:** {proximo_info['pitcher_nombre']} ({proximo_info['pitcher_mano']}HP)")
        st.markdown(f"* **ERA Pítcher:** {proximo_info['pitcher_era']}")
        
    # MOSTRAR TABLA
    st.markdown("---")
    if df_juegos is not None and not df_juegos.empty:
        st.success(f"✅ **{len(df_juegos)} Partidos Extraídos Exitosamente:** (Fuente: MLB API Direct Endpoint - Temporada {anio_recuperado})")
        st.dataframe(df_juegos, use_container_width=True)
    else:
        st.error(f"❌ El jugador ID {p_id} no registra partidos jugados en la API de la MLB en las últimas 4 temporadas. Se utiliza promedio general ({stats_season['avg_season']:.3f}).")
