import streamlit as st
import statsapi
import math
from datetime import datetime

st.set_page_config(
    page_title="Analizador Avanzado de MLB",
    page_icon="⚾",
    layout="wide"
)

CURRENT_YEAR = datetime.now().year

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES Y CACHÉ DE API
# -----------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def obtener_equipos():
    """Obtiene la lista oficial de equipos de la MLB."""
    try:
        data = statsapi.get("teams", {"sportId": 1})
        return data.get('teams', []) if data else []
    except Exception:
        return []

@st.cache_data(ttl=1800)
def obtener_partidos(fecha_str):
    """Obtiene los partidos programados para una fecha especificada."""
    try:
        return statsapi.schedule(date=fecha_str)
    except Exception:
        return []

@st.cache_data(ttl=1800)
def obtener_roster_equipo(team_id):
    """Obtiene el roster actual de un equipo."""
    try:
        data = statsapi.get("team_roster", {"teamId": team_id})
        return data.get('roster', []) if data else []
    except Exception:
        return []

@st.cache_data(ttl=1800)
def obtener_info_jugador(player_id, hydrate_params):
    """Obtiene la información hidratada de un jugador."""
    try:
        data = statsapi.get("people", {
            "personIds": player_id,
            "hydrate": hydrate_params
        })
        return data.get('people', [{}])[0] if data and 'people' in data else {}
    except Exception:
        return {}

@st.cache_data(ttl=1800)
def obtener_abridores_probables(game_pk):
    """Obtiene los abridores probables de un partido."""
    try:
        g_data = statsapi.get("game", {"gamePk": game_pk})
        probables = g_data.get('gameData', {}).get('probablePitchers', {})
        return {
            'away_id': probables.get('away', {}).get('id'),
            'away_name': probables.get('away', {}).get('fullName', 'Por determinar'),
            'home_id': probables.get('home', {}).get('id'),
            'home_name': probables.get('home', {}).get('fullName', 'Por determinar')
        }
    except Exception:
        return {'away_id': None, 'away_name': 'Desconocido', 'home_id': None, 'home_name': 'Desconocido'}

@st.cache_data(ttl=1800)
def obtener_racha_7dias(player_id, season):
    """Obtiene el rendimiento de un bateador en los últimos 7 días."""
    try:
        data = statsapi.get("people", {
            "personIds": player_id,
            "hydrate": f"stats(group=[hitting],type=lastXDays,limit=7,season={season})"
        })
        if data and 'people' in data:
            stats = data['people'][0].get('stats', [])
            for st_group in stats:
                splits = st_group.get('splits', [])
                if splits:
                    s = splits[0].get('stat', {})
                    return {
                        'avg': s.get('avg', '.000'),
                        'hits': s.get('hits', 0),
                        'gp': s.get('gamesPlayed', 0)
                    }
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def obtener_bvp(batter_id, pitcher_id):
    """Obtiene las estadísticas BvP entre un bateador y un lanzador."""
    if not batter_id or not pitcher_id:
        return None
    try:
        data = statsapi.get("stats", {
            "stats": "vsPlayer",
            "group": "hitting",
            "personId": batter_id,
            "opposingPlayerId": pitcher_id
        })
        if data and 'stats' in data and data['stats']:
            splits = data['stats'][0].get('splits', [])
            if splits:
                s = splits[0].get('stat', {})
                return {
                    'ab': s.get('atBats', 0),
                    'avg': s.get('avg', '.000'),
                    'hits': s.get('hits', 0)
                }
    except Exception:
        pass
    return None

def calcular_probabilidad_poisson_hits(avg_season, avg_7d=None, avg_bvp=None, ab_bvp=0, est_ab=3.8):
    """Calcula la probabilidad de hit con Poisson y proyecta a 1,000 turnos al bat (AB)."""
    try:
        avg_s = float(avg_season) if avg_season else 0.0
    except ValueError:
        avg_s = 0.0

    try:
        avg_7 = float(avg_7d) if avg_7d is not None else None
    except (ValueError, TypeError):
        avg_7 = None

    try:
        avg_b = float(avg_bvp) if avg_bvp is not None else None
    except (ValueError, TypeError):
        avg_b = None

    values, weights = [], []

    if avg_s > 0:
        values.append(avg_s)
        weights.append(0.50 if avg_7 is not None else 0.80)

    if avg_7 is not None and avg_7 >= 0:
        values.append(avg_7)
        weights.append(0.35)

    if avg_b is not None and ab_bvp >= 3:
        values.append(avg_b)
        weights.append(0.15 if ab_bvp < 8 else 0.25)

    if not values:
        return 0.0, 0.0, 0

    total_weight = sum(weights)
    avg_ponderado = sum(v * w for v, w in zip(values, weights)) / total_weight

    hits_1000 = int(round(avg_ponderado * 1000))
    lam = avg_ponderado * est_ab
    prob_hit = (1 - math.exp(-lam)) * 100

    return round(avg_ponderado, 3), round(prob_hit, 1), hits_1000

# -----------------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------

st.title("⚾ Analizador y Predictor Avanzado de la MLB")

st.sidebar.header("Menú de Navegación")
opcion = st.sidebar.selectbox(
    "Selecciona una sección:",
    [
        "Equipos de la MLB", 
        "Buscar Jugador & Depuración", 
        "Partidos del Día & Proyección (Poisson + 1000 AB)", 
        "⚾ Lanzadores Principales de Cada Equipo", 
        "🎯 Análisis de Jugadores (Hits y Ponches)"
    ]
)

# -----------------------------------------------------------------------------
# OPCIÓN 1: EQUIPOS DE LA MLB
# -----------------------------------------------------------------------------
if opcion == "Equipos de la MLB":
    st.header("🏢 Información General de Equipos")
    teams = obtener_equipos()
    
    if teams:
        team_names = [t['name'] for t in teams]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names)
        selected_team = next(t for t in teams if t['name'] == selected_team_name)
        team_id = selected_team['id']
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Detalles de la Franquicia")
            st.write(f"**Ciudad:** {selected_team.get('locationName', 'N/A')}")
            st.write(f"**Estadio:** {selected_team.get('venue', {}).get('name', 'N/A')}")
            st.write(f"**Liga:** {selected_team.get('league', {}).get('name', 'N/A')}")
            st.write(f"**División:** {selected_team.get('division', {}).get('name', 'N/A')}")

        with col2:
            st.subheader("Plantilla Actual (Roster Activo)")
            roster = obtener_roster_equipo(team_id)
            if roster:
                for member in roster[:15]:
                    pname = member.get('person', {}).get('fullName', 'N/A')
                    ppos = member.get('position', {}).get('abbreviation', 'N/A')
                    st.write(f"- **{pname}** ({ppos})")
            else:
                st.info("No se pudo obtener el roster del equipo.")

# -----------------------------------------------------------------------------
# OPCIÓN 2: BUSCAR JUGADOR & DEPURACIÓN
# -----------------------------------------------------------------------------
elif opcion == "Buscar Jugador & Depuración":
    st.header("🔍 Buscador de Jugadores y Métricas")
    player_name = st.text_input("Ingresa el nombre del jugador:", "Shohei Ohtani")
    
    if player_name:
        players = statsapi.lookup_player(player_name)
        if players:
            player = players[0]
            player_id = player['id']
            st.success(f"Jugador encontrado: **{player['fullName']}** (ID: {player_id})")
            
            p_info = obtener_info_jugador(player_id, f"currentTeam,stats(group=[hitting,pitching],type=season,season={CURRENT_YEAR})")
            if p_info:
                st.write(f"**Posición:** {p_info.get('primaryPosition', {}).get('name', 'N/A')}")
                st.write(f"**Edad:** {p_info.get('currentAge', 'N/A')}")
                
                stats_list = p_info.get('stats', [])
                for stat_group in stats_list:
                    g_type = stat_group.get('group', {}).get('displayName')
                    splits = stat_group.get('splits', [])
                    if splits:
                        s_stats = splits[0].get('stat', {})
                        st.subheader(f"Estadísticas de {g_type.capitalize()} ({CURRENT_YEAR})")
                        cols = st.columns(3)
                        if g_type == "hitting":
                            cols[0].metric("Promedio (AVG)", s_stats.get('avg', '.000'))
                            cols[1].metric("Hits", s_stats.get('hits', 0))
                            cols[2].metric("Ponches (SO)", s_stats.get('strikeOuts', 0))
                        else:
                            cols[0].metric("Efectividad (ERA)", s_stats.get('era', '0.00'))
                            cols[1].metric("Ponches (SO)", s_stats.get('strikeOuts', 0))
                            cols[2].metric("WHIP", s_stats.get('whip', '0.00'))
        else:
            st.warning("No se encontró ningún jugador con ese nombre.")

# -----------------------------------------------------------------------------
# OPCIÓN 3: PARTIDOS DEL DÍA & PROYECCIÓN POISSON
# -----------------------------------------------------------------------------
elif opcion == "Partidos del Día & Proyección (Poisson + 1000 AB)":
    st.header("📅 Partidos y Proyección de Hits (+0.5 Hits / 1,000 AB)")
    date_to_check = st.date_input("Selecciona la fecha:", datetime.now())
    formatted_date = date_to_check.strftime("%m/%d/%Y")
    
    schedule = obtener_partidos(formatted_date)
    
    if schedule:
        opciones_juegos = {
            f"{g['away_name']} vs {g['home_name']} ({g.get('status', 'Programado')})": g 
            for g in schedule
        }
        
        juego_sel = st.selectbox("Selecciona un partido para analizar:", list(opciones_juegos.keys()))
        game = opciones_juegos[juego_sel]
        game_pk = game.get('game_id')
        
        if game_pk:
            st.divider()
            abridores = obtener_abridores_probables(game_pk)
            
            st.subheader("🥎 Lanzadores Abridores Probables")
            c1, c2 = st.columns(2)
            c1.info(f"**Visitante ({game['away_name']}):** {abridores['away_name']}")
            c2.info(f"**Local ({game['home_name']}):** {abridores['home_name']}")
            
            away_id, home_id = game.get('away_id'), game.get('home_id')
            col_away, col_home = st.columns(2)
            
            # --- EQUIPO VISITANTE ---
            with col_away:
                st.markdown(f"### ✈️ {game['away_name']}")
                roster_away = obtener_roster_equipo(away_id) if away_id else []
                if roster_away:
                    count = 0
                    for m in roster_away:
                        pos = m.get('position', {}).get('abbreviation', '')
                        if pos == 'P': continue
                        if count >= 5: break
                        
                        pid = m.get('person', {}).get('id')
                        pname = m.get('person', {}).get('fullName')
                        
                        p_info = obtener_info_jugador(pid, f"stats(group=hitting,type=season,season={CURRENT_YEAR})")
                        splits = p_info.get('stats', [{}])[0].get('splits', []) if p_info else []
                        
                        if splits:
                            avg_season = splits[0].get('stat', {}).get('avg', '.000')
                            r7 = obtener_racha_7dias(pid, CURRENT_YEAR)
                            avg_7d = r7['avg'] if (r7 and r7['gp'] > 0) else None
                            
                            avg_bvp, ab_bvp = None, 0
                            if abridores['home_id']:
                                bvp = obtener_bvp(pid, abridores['home_id'])
                                if bvp and bvp['ab'] > 0:
                                    avg_bvp, ab_bvp = bvp['avg'], bvp['ab']
                            
                            avg_pond, prob_hit, hits_1000 = calcular_probabilidad_poisson_hits(
                                avg_season, avg_7d, avg_bvp, ab_bvp
                            )
                            
                            st.markdown(f"**👤 {pname}** ({pos})")
                            st.write(f"- Temp: `{avg_season}` | 7D: `{avg_7d or 'N/A'}` | BvP: `{avg_bvp or 'N/A'}`")
                            st.write(f"- 📈 Proyección: **{hits_1000} Hits** en 1,000 AB")
                            st.metric("Probabilidad +0.5 Hits", f"{prob_hit}%")
                            st.progress(min(int(prob_hit), 100))
                            st.divider()
                            count += 1
                else:
                    st.info("Sin plantilla disponible.")

            # --- EQUIPO LOCAL ---
            with col_home:
                st.markdown(f"### 🏠 {game['home_name']}")
                roster_home = obtener_roster_equipo(home_id) if home_id else []
                if roster_home:
                    count = 0
                    for m in roster_home:
                        pos = m.get('position', {}).get('abbreviation', '')
                        if pos == 'P': continue
                        if count >= 5: break
                        
                        pid = m.get('person', {}).get('id')
                        pname = m.get('person', {}).get('fullName')
                        
                        p_info = obtener_info_jugador(pid, f"stats(group=hitting,type=season,season={CURRENT_YEAR})")
                        splits = p_info.get('stats', [{}])[0].get('splits', []) if p_info else []
                        
                        if splits:
                            avg_season = splits[0].get('stat', {}).get('avg', '.000')
                            r7 = obtener_racha_7dias(pid, CURRENT_YEAR)
                            avg_7d = r7['avg'] if (r7 and r7['gp'] > 0) else None
                            
                            avg_bvp, ab_bvp = None, 0
                            if abridores['away_id']:
                                bvp = obtener_bvp(pid, abridores['away_id'])
                                if bvp and bvp['ab'] > 0:
                                    avg_bvp, ab_bvp = bvp['avg'], bvp['ab']
                            
                            avg_pond, prob_hit, hits_1000 = calcular_probabilidad_poisson_hits(
                                avg_season, avg_7d, avg_bvp, ab_bvp
                            )
                            
                            st.markdown(f"**👤 {pname}** ({pos})")
                            st.write(f"- Temp: `{avg_season}` | 7D: `{avg_7d or 'N/A'}` | BvP: `{avg_bvp or 'N/A'}`")
                            st.write(f"- 📈 Proyección: **{hits_1000} Hits** en 1,000 AB")
                            st.metric("Probabilidad +0.5 Hits", f"{prob_hit}%")
                            st.progress(min(int(prob_hit), 100))
                            st.divider()
                            count += 1
                else:
                    st.info("Sin plantilla disponible.")
    else:
        st.info("No hay partidos programados para esta fecha.")

# -----------------------------------------------------------------------------
# OPCIÓN 4: LANZADORES PRINCIPALES DE CADA EQUIPO
# -----------------------------------------------------------------------------
elif opcion == "⚾ Lanzadores Principales de Cada Equipo":
    st.header(f"⚾ Lanzadores por Equipo ({CURRENT_YEAR})")
    teams = obtener_equipos()
    
    if teams:
        team_names = [t['name'] for t in teams]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names)
        selected_team = next(t for t in teams if t['name'] == selected_team_name)
        
        roster = obtener_roster_equipo(selected_team['id'])
        pitchers = [m for m in roster if 'P' in m.get('position', {}).get('abbreviation', '')]
        
        if pitchers:
            st.success(f"Se encontraron **{len(pitchers)}** lanzadores en la plantilla:")
            for member in pitchers[:8]:
                pid = member.get('person', {}).get('id')
                pname = member.get('person', {}).get('fullName')
                pos_code = member.get('position', {}).get('abbreviation', 'P')
                
                with st.expander(f"🥎 Lanzador: {pname} ({pos_code})"):
                    p_info = obtener_info_jugador(pid, f"stats(group=pitching,type=season,season={CURRENT_YEAR})")
                    stats_groups = p_info.get('stats', []) if p_info else []
                    
                    has_stats = False
                    for group in stats_groups:
                        splits = group.get('splits', [])
                        if splits:
                            s = splits[0].get('stat', {})
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("ERA", s.get('era', '0.00'))
                            c2.metric("Ponches (SO)", s.get('strikeOuts', 0))
                            c3.metric("Juegos", s.get('gamesPlayed', 0))
                            c4.metric("WHIP", s.get('whip', '0.00'))
                            has_stats = True
                    if not has_stats:
                        st.info("Sin estadísticas registradas para la temporada actual.")
        else:
            st.warning("No se encontraron lanzadores activos en este equipo.")

# -----------------------------------------------------------------------------
# OPCIÓN 5: ANÁLISIS DE JUGADORES (HITS Y PONCHES)
# -----------------------------------------------------------------------------
elif opcion == "🎯 Análisis de Jugadores (Hits y Ponches)":
    st.header(f"🎯 Análisis de Roster ({CURRENT_YEAR})")
    teams = obtener_equipos()
    
    if teams:
        team_names = [t['name'] for t in teams]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names)
        selected_team = next(t for t in teams if t['name'] == selected_team_name)
        
        roster = obtener_roster_equipo(selected_team['id'])
        if roster:
            st.write(f"Mostrando resumen para **{selected_team_name}**:")
            for member in roster[:8]:
                p_info_base = member.get('person', {})
                pid = p_info_base.get('id')
                pname = p_info_base.get('fullName', 'N/A')
                pos = member.get('position', {}).get('abbreviation', 'N/A')
                
                with st.expander(f"👤 {pname} ({pos})"):
                    p_info = obtener_info_jugador(pid, f"stats(group=[hitting,pitching],type=season,season={CURRENT_YEAR})")
                    stats_groups = p_info.get('stats', []) if p_info else []
                    rendered = False
                    
                    for group in stats_groups:
                        g_name = group.get('group', {}).get('displayName')
                        splits = group.get('splits', [])
                        if splits:
                            stats_val = splits[0].get('stat', {})
                            if g_name == "hitting":
                                c1, c2, c3 = st.columns(3)
                                c1.metric("AVG", stats_val.get('avg', '.000'))
                                c2.metric("Hits", stats_val.get('hits', 0))
                                c3.metric("Ponches (SO)", stats_val.get('strikeOuts', 0))
                                rendered = True
                            elif g_name == "pitching":
                                c1, c2 = st.columns(2)
                                c1.metric("ERA", stats_val.get('era', '0.00'))
                                c2.metric("Ponches (SO)", stats_val.get('strikeOuts', 0))
                                rendered = True
                    if not rendered:
                        st.info("Sin estadísticas registradas para esta temporada.")
