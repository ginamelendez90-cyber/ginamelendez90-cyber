import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst - Automatización Total de Próximo Juego", page_icon="⚾", layout="wide")

st.title("⚾ Analizador MLB: Detección Automática del Próximo Partido")
st.markdown("Extrae de la API oficial el rival, pitcher abridor anunciado, estadio y alineación estimada sin selección manual.")
st.markdown("---")

# Diccionario de estadios con factores de parque conocidos
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
def auto_detectar_proximo_partido(player_id, team_id):
    hoy = datetime.now().strftime('%Y-%m-%d')
    futuro = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    detalles = {
        "fecha": "Sin juego programado en 7 días",
        "rival": "N/A",
        "condicion": "N/A",
        "estadio": "Estadio Estándar",
        "factor_campo": 1.00,
        "desc_estadio": "Neutral (1.00)",
        "pitcher_nombre": "Por Anunciar / Reliever",
        "pitcher_mano": "R",
        "pitcher_era": "N/A",
        "perfil_pitcher": "Lanzador Promedio / Estándar"
    }
    
    try:
        juegos = statsapi.schedule(team=team_id, start_date=hoy, end_date=futuro)
        if not juegos:
            return detalles
            
        proximo = juegos[0]
        detalles["fecha"] = proximo.get('game_date', hoy)
        es_home = proximo.get('home_id') == team_id
        detalles["condicion"] = "Local" if es_home else "Visitante"
        detalles["rival"] = proximo.get('away_name') if es_home else proximo.get('home_name')
        
        # Estadio y Park Factor
        venue_name = proximo.get('venue_name', 'Estadio Estándar')
        detalles["estadio"] = venue_name
        if venue_name in PARK_FACTORS:
            detalles["factor_campo"] = PARK_FACTORS[venue_name]["factor"]
            detalles["desc_estadio"] = PARK_FACTORS[venue_name]["tipo"]
            
        # Pitcher Abridor Rival
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
                        detalles["perfil_pitcher"] = "Ace / Lanzador Dominante"
                    elif era_val >= 4.80:
                        detalles["perfil_pitcher"] = "Abridor Débil / Favorabilidad Altísima"
                    elif detalles["pitcher_mano"] == "L":
                        detalles["perfil_pitcher"] = "Lanzador Zurdo (Ventaja Platoon)"
                    else:
                        detalles["perfil_pitcher"] = "Lanzador Promedio / Estándar"
    except Exception:
        pass
        
    return detalles

@st.cache_data(ttl=3600)
def obtener_stats_temporada(player_id):
    anio_actual = datetime.now().year
    try:
        res = statsapi.player_stat_data(player_id, group="hitting", type="season", season=anio_actual)
        stats = res.get('stats', [])
        if stats:
            s_data = stats[0].get('stats', {})
            return {
                'avg_season': float(s_data.get('avg', '.000')),
                'games': int(s_data.get('gamesPlayed', 0))
            }
    except Exception:
        pass
    return {'avg_season': 0.260, 'games': 0}

@st.cache_data(ttl=1800)
def obtener_ultimos_5_juegos(player_id):
    registros = []
    anio_actual = datetime.now().year
    try:
        res = statsapi.player_game_logs(player_id, group="hitting", season=anio_actual)
        if isinstance(res, list):
            registros = res
    except Exception:
        pass
        
    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    if df.empty:
        return None, "5.º al 9.º Bate (Menos Turnos)"
        
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date', ascending=False).reset_index(drop=True)
    df_5 = df.head(5).copy()
    
    cols = {'date': 'Fecha', 'opponent': 'Rival', 'ab': 'AB', 'h': 'H', 'homeRuns': 'HR'}
    df_final = df_5[[c for c in cols.keys() if c in df_5.columns]].rename(columns=cols)
    
    avg_ab = df_5['ab'].mean() if 'ab' in df_5.columns else 3.5
    pos_lineup = "1.º al 4.º Bate (Líderes de Turnos)" if avg_ab >= 3.8 else "5.º al 9.º Bate (Menos Turnos)"
    
    return df_final, pos_lineup

def calcular_modelo_automatizado(df_5, stats_season, proximo_info, pos_lineup):
    total_ab_5 = df_5['AB'].sum()
    total_h_5 = df_5['H'].sum()
    juegos_con_hit = (df_5['H'] > 0).sum()
    
    avg_5 = total_h_5 / total_ab_5 if total_ab_5 > 0 else 0.250
    avg_season = stats_season['avg_season'] if stats_season['games'] > 10 else avg_5
    
    avg_proyectado = (avg_5 * 0.40) + (avg_season * 0.60)
    
    perfil = proximo_info["perfil_pitcher"]
    if perfil == "Abridor Débil / Favorabilidad Altísima":
        avg_proyectado *= 1.12
    elif perfil == "Lanzador Zurdo (Ventaja Platoon)":
        avg_proyectado *= 1.06
    elif perfil == "Ace / Lanzador Dominante":
        avg_proyectado *= 0.88
        
    avg_proyectado *= proximo_info["factor_campo"]
    
    ab_esperados = 4.3 if "1.º al 4.º" in pos_lineup else 3.6
    
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
# DESPLIEGUE EN INTERFAZ
# ==========================================

directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())

jugador_sel = st.sidebar.selectbox("Selecciona Jugador a Analizar:", opciones)

if jugador_sel:
    player_data = directorio[jugador_sel]
    p_id = player_data["id"]
    team_id = player_data["team_id"]
    
    with st.spinner("Conectando con MLB StatsAPI para extraer métricas y próximo partido..."):
        df_5, pos_lineup_detectada = obtener_ultimos_5_juegos(p_id)
        stats_season = obtener_stats_temporada(p_id)
        proximo_info = auto_detectar_proximo_partido(p_id, team_id)
        
    if df_5 is not None and not df_5.empty:
        res = calcular_modelo_automatizado(df_5, stats_season, proximo_info, pos_lineup_detectada)
        
        st.subheader(f"⚾ {jugador_sel.split(' (')[0]}")
        
        # MÉTRICAS PRINCIPALES
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🎯 Probabilidad de Hit", f"{res['prob_hit']}%")
        c2.metric("AVG Proyectado", f"{res['avg_proyectado']:.3f}")
        c3.metric("AVG L5 (Racha)", f"{res['avg_5']:.3f}")
        c4.metric("AVG Temporada", f"{res['avg_season']:.3f}")
        
        # DESGLOSE TÉCNICO AUTOMÁTICO
        st.info("📌 **Ficha Técnica Extraída Automáticamente de la MLB:**")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f"* **Próximo Rival:** {proximo_info['rival']} ({proximo_info['condicion']})")
            st.markdown(f"* **Fecha del Partido:** {proximo_info['fecha'][:10]}")
        with col_b:
            st.markdown(f"* **Estadio:** {proximo_info['estadio']}")
            st.markdown(f"* **Factor de Parque:** {proximo_info['desc_estadio']}")
        with col_c:
            st.markdown(f"* **Abridor Rival:** {proximo_info['pitcher_nombre']} ({proximo_info['pitcher_mano']}HP)")
            st.markdown(f"* **Ajuste de Picheo:** {proximo_info['perfil_pitcher']} (ERA: {proximo_info['pitcher_era']})")
            
        st.caption(f"🏏 **Alineación Estimada:** {pos_lineup_detectada} (~{res['ab_esperados']} turnos al bate proyectados).")
        
        st.markdown("---")
        st.markdown("**Historial Base L5:**")
        st.dataframe(df_5, use_container_width=True)
    else:
        st.warning(f"⚠️ No se encontraron registros de partidos oficiales de la MLB esta temporada para **{jugador_sel.split(' (')[0]}** (puede ser un prospecto de ligas menores, estar en lista de lesionados o no haber debutado). Prueba seleccionando un bateador titular habitual como **Shohei Ohtani**, **Aaron Judge**, **Mookie Betts**, etc.")
