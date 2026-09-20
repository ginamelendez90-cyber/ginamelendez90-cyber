import streamlit as st
import pandas as pd
import numpy as np
import statsapi
from datetime import datetime, timedelta

st.set_page_config(page_title="MLB Analyst - Detección y Explicación de Proyección", page_icon="⚾", layout="wide")

st.title("⚾ Analizador MLB: Proyección y Justificación de Hit")
st.markdown("Análisis sabermétrico automatizado con explicación cualitativa detallada.")
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
    for yr in [anio_actual, anio_actual - 1]:
        try:
            res = statsapi.player_stat_data(player_id, group="hitting", type="season", season=yr)
            stats = res.get('stats', [])
            if stats:
                s_data = stats[0].get('stats', {})
                avg_val = s_data.get('avg', '.250')
                return {
                    'avg_season': float(avg_val) if avg_val != '.---' else 0.250,
                    'games': int(s_data.get('gamesPlayed', 0)),
                    'year': yr
                }
        except Exception:
            pass
    return {'avg_season': 0.250, 'games': 0, 'year': anio_actual}

@st.cache_data(ttl=1800)
def obtener_ultimos_juegos_detallados(player_id):
    anio_actual = datetime.now().year
    registros = []
    es_previo = False
    
    for yr in [anio_actual, anio_actual - 1]:
        try:
            data = statsapi.player_stat_data(player_id, group="hitting", type="gameLog", season=yr)
            groups = data.get('stats', [])
            
            for grp in groups:
                game_logs = grp.get('stats', [])
                for item in game_logs:
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
                        'AVG': s.get('avg', '.000')
                    })
            if registros:
                if yr < anio_actual:
                    es_previo = True
                break
        except Exception:
            pass
            
    df = pd.DataFrame(registros) if registros else pd.DataFrame()
    if df.empty:
        return None, "5.º al 9.º Bate (Menos Turnos)", False
        
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df = df.sort_values(by='Fecha', ascending=False).reset_index(drop=True)
    
    df_6 = df.head(6).copy()
    df_6['Fecha'] = df_6['Fecha'].dt.strftime('%Y-%m-%d')
    
    avg_ab = df_6['AB'].mean() if 'AB' in df_6.columns else 3.5
    pos_lineup = "1.º al 4.º Bate (Líderes de Turnos)" if avg_ab >= 3.8 else "5.º al 9.º Bate (Menos Turnos)"
    
    return df_6, pos_lineup, es_previo

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
    """Genera las razones en texto claro de por qué se espera dicho porcentaje."""
    puntos = []
    
    # 1. Analizar Racha / Forma reciente
    dif_racha = res['avg_reciente'] - res['avg_season']
    if dif_racha >= 0.030:
        puntos.append(f"🔥 **Racha Encendida:** {nombre_jugador} llega bateando para **{res['avg_reciente']:.3f}** en sus últimos juegos, superando ampliamente su promedio de temporada ({res['avg_season']:.3f}).")
    elif dif_racha <= -0.030:
        puntos.append(f"❄️ **Racha Fría:** Se encuentra por debajo de su nivel habitual en sus últimos partidos (**{res['avg_reciente']:.3f}** reciente vs **{res['avg_season']:.3f}** de temporada).")
    else:
        puntos.append(f"📊 **Rendimiento Regular:** Mantiene un nivel estable de contacto (**{res['avg_reciente']:.3f}** reciente vs **{res['avg_season']:.3f}** de temporada).")
        
    # 2. Analizar Abridor Rival
    if res['factor_picheo'] > 1.00:
        porc = int((res['factor_picheo'] - 1) * 100)
        puntos.append(f"🎯 **Duelo Favorable con el Pítcher:** Enfrenta a **{proximo_info['pitcher_nombre']}** ({proximo_info['perfil_pitcher']}), lo que incrementa su expectativa de hit en un **+{porc}%**.")
    elif res['factor_picheo'] < 1.00:
        porc = int((1 - res['factor_picheo']) * 100)
        puntos.append(f"🛡️ **Enfrentamiento Exigente:** El abridor rival **{proximo_info['pitcher_nombre']}** ({proximo_info['perfil_pitcher']}) es dominante, lo que penaliza la expectativa de hit en un **-{porc}%**.")
    else:
        puntos.append(f"⚾ **Lanzador Estándar:** El abridor **{proximo_info['pitcher_nombre']}** proyecta un escenario neutral (sin ventaja ni desventaja marcada).")
        
    # 3. Factor Estadio
    if res['factor_parque'] > 1.00:
        porc = int((res['factor_parque'] - 1) * 100)
        puntos.append(f"🏟️ **Ventaja de Parque:** El partido se jugará en **{proximo_info['estadio']}**, un estadio que favorece a los bateadores en un **+{porc}%**.")
    elif res['factor_parque'] < 1.00:
        porc = int((1 - res['factor_parque']) * 100)
        puntos.append(f"🏟️ **Estadio para Lanzadores:** Se juega en **{proximo_info['estadio']}**, un parque exigente para conectar imparables (**-{porc}%**).")
    else:
        puntos.append(f"🏟️ **Estadio Neutral:** El parque de pelota ({proximo_info['estadio']}) no altera las métricas normales de bateo.")
        
    # 4. Turnos al bate / Orden de Alineación
    if "1.º al 4.º" in pos_lineup:
        puntos.append(f"🏏 **Alto Volumen de Oportunidades:** Al batear en la parte alta del orden al bate (**{pos_lineup.split(' (')[0]}**), se estiman aproximadamente **4.3 turnos al bate**, maximizando sus probabilidades.")
    else:
        puntos.append(f"🏏 **Turnos Moderados:** Proyectado en la parte media/baja del orden al bate, con un estimado de **3.6 turnos al bate**.")
        
    # Conclusión
    if res['prob_hit'] >= 72.0:
        conclusion = f"💡 **Conclusión:** Se proyecta un alto **{res['prob_hit']}%** de probabilidad gracias a una excelente combinación de volumen de turnos, forma actual y/o condiciones muy favorables en el partido."
    elif res['prob_hit'] >= 60.0:
        conclusion = f"💡 **Conclusión:** Se obtiene un sólido **{res['prob_hit']}%**, representando una opción con probabilidad favorable bajo un escenario equilibrado."
    else:
        conclusion = f"💡 **Conclusión:** La expectativa es moderada/baja (**{res['prob_hit']}%**) debido a un duelo exigente contra el lanzador rival o una menor cantidad de turnos proyectados."
        
    return puntos, conclusion

# ==========================================
# DESPLIEGUE EN INTERFAZ
# ==========================================

directorio = obtener_directorio_jugadores_activos()
opciones = list(directorio.keys())

jugador_sel = st.sidebar.selectbox("Selecciona Jugador a Analizar:", opciones)

if jugador_sel:
    nombre_solo = jugador_sel.split(' (')[0]
    player_data = directorio[jugador_sel]
    p_id = player_data["id"]
    team_id = player_data["team_id"]
    
    with st.spinner("Extrayendo estadísticas e información del próximo partido..."):
        df_juegos, pos_lineup_detectada, es_previo = obtener_ultimos_juegos_detallados(p_id)
        stats_season = obtener_stats_temporada(p_id)
        proximo_info = auto_detectar_proximo_partido(team_id)
        res = calcular_modelo_automatizado(df_juegos, stats_season, proximo_info, pos_lineup_detectada)
        
    st.subheader(f"⚾ {nombre_solo}")
    
    # MÉTRICAS PRINCIPALES
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 Probabilidad de Hit", f"{res['prob_hit']}%")
    c2.metric("AVG Proyectado", f"{res['avg_proyectado']:.3f}")
    c3.metric("AVG Reciente (Racha)", f"{res['avg_reciente']:.3f}")
    c4.metric("AVG Temporada", f"{res['avg_season']:.3f}")
    
    st.markdown("---")
    
    # JUSTIFICACIÓN CUALITATIVA DEL RESULTADO
    st.subheader(f"🧠 ¿Por qué se espera un {res['prob_hit']}% de probabilidad?")
    puntos_explicativos, conclusion_final = generar_explicacion_cualitativa(res, proximo_info, pos_lineup_detectada, nombre_solo)
    
    for p in puntos_explicativos:
        st.markdown(f"* {p}")
        
    st.info(conclusion_final)
    
    # FICHA TÉCNICA
    st.markdown("---")
    st.markdown("📌 **Ficha Técnica Extraída Automáticamente:**")
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
    
    # EXPLICACIÓN MATEMÁTICA
    with st.expander("🧮 Ver Desglose de Fórmulas Matemáticas"):
        st.markdown(f"""
        1. **Promedio Ponderado Base:** 40% Racha (`{res['avg_reciente']:.3f}`) + 60% Temporada (`{res['avg_season']:.3f}`) = **`{res['avg_base']:.3f}`**
        2. **Multiplicadores:** Base (`{res['avg_base']:.3f}`) × Picheo (`{res['factor_picheo']:.2f}`) × Parque (`{res['factor_parque']:.2f}`) = **`{res['avg_proyectado']:.3f}`**
        3. **Poisson:** `{res['avg_proyectado']:.3f}` × `{res['ab_esperados']}` AB = `{res['lambda_hits']}` hits esperados $\rightarrow$ **`{res['prob_hit']}%`**.
        """)

    st.markdown("---")
    
    # TABLA DE HISTORIAL COMPLETA
    if df_juegos is not None and not df_juegos.empty:
        if es_previo:
            st.warning("⚠️ Sin partidos en la temporada actual. Mostrando historial de la temporada anterior.")
        st.markdown("**📊 Historial Detallado de Partidos Recientes:**")
        st.dataframe(df_juegos, use_container_width=True)
    else:
        st.warning(f"⚠️ El jugador no registra partidos oficiales. Proyección basada en promedio general ({stats_season['avg_season']:.3f}).")
