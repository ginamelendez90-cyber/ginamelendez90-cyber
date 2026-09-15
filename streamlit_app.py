import streamlit as st
import statsapi
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Analizador Avanzado de MLB",
    page_icon="⚾",
    layout="wide"
)

CURRENT_YEAR = datetime.now().year

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES (RACHA RECIENTE, BvP Y ABRIDORES)
# -----------------------------------------------------------------------------

def obtener_abridores_probables(game_pk):
    """Extrae los IDs y nombres de los lanzadores abridores probables del partido."""
    away_pitcher_id = None
    away_pitcher_name = "Por determinar"
    home_pitcher_id = None
    home_pitcher_name = "Por determinar"
    try:
        g_data = statsapi.get("game", {"gamePk": game_pk})
        probables = g_data.get('gameData', {}).get('probablePitchers', {})
        
        if 'away' in probables:
            away_pitcher_id = probables['away'].get('id')
            away_pitcher_name = probables['away'].get('fullName', 'Desconocido')
            
        if 'home' in probables:
            home_pitcher_id = probables['home'].get('id')
            home_pitcher_name = probables['home'].get('fullName', 'Desconocido')
    except Exception:
        pass
    return {
        'away_id': away_pitcher_id,
        'away_name': away_pitcher_name,
        'home_id': home_pitcher_id,
        'home_name': home_pitcher_name
    }

def obtener_racha_7dias(player_id, season):
    """Consulta la racha ofensiva del bateador en los últimos 7 días."""
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
                        'hr': s.get('homeRuns', 0),
                        'ops': s.get('ops', '.000'),
                        'gp': s.get('gamesPlayed', 0)
                    }
    except Exception:
        pass
    return None

def obtener_bvp(batter_id, pitcher_id):
    """Obtiene el historial directo BvP entre un bateador y un lanzador abridor rival."""
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
                    'hits': s.get('hits', 0),
                    'hr': s.get('homeRuns', 0),
                    'so': s.get('strikeOuts', 0),
                    'ops': s.get('ops', '.000')
                }
    except Exception:
        pass
    return None

# -----------------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------

st.title("⚾ Analizador y Predictor Avanzado de Estadísticas de la MLB")
st.markdown("Panel integral con métricas de la temporada, racha reciente (7 días), BvP y abridores probables.")

# Barra lateral para navegación
st.sidebar.header("Opciones de Consulta")
opcion = st.sidebar.selectbox(
    "Selecciona una sección:",
    [
        "Equipos de la MLB", 
        "Buscar Jugador & Depuración", 
        "Partidos del Día & Análisis (Ambos Equipos + Racha + BvP)", 
        "⚾ Lanzadores Principales de Cada Equipo", 
        "🎯 Análisis de Jugadores (Hits y Ponches)"
    ]
)

if opcion == "Equipos de la MLB":
    st.header("Información de Equipos")
    
    teams_data = statsapi.get("teams", {"sportId": 1})
    
    if teams_data and 'teams' in teams_data:
        teams = teams_data['teams']
        team_names = [team['name'] for team in teams]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names)
        
        selected_team = next(t for t in teams if t['name'] == selected_team_name)
        team_id = selected_team['id']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Detalles del Equipo")
            st.write(f"**Ciudad:** {selected_team.get('locationName', 'N/A')}")
            st.write(f"**Estadio:** {selected_team.get('venue', {}).get('name', 'N/A')}")
            st.write(f"**Liga:** {selected_team.get('league', {}).get('name', 'N/A')}")
            st.write(f"**División:** {selected_team.get('division', {}).get('name', 'N/A')}")
            st.write(f"**Año de Fundación:** {selected_team.get('firstYearOfPlay', 'N/A')}")

        with col2:
            st.subheader("Plantilla Actual (Roster Directo)")
            try:
                roster_data = statsapi.get("team_roster", {"teamId": team_id})
                if roster_data and 'roster' in roster_data:
                    for m in roster_data['roster']:
                        p_name = m.get('person', {}).get('fullName', 'N/A')
                        p_pos = m.get('position', {}).get('abbreviation', 'N/A')
                        st.write(f"- **{p_name}** ({p_pos})")
                else:
                    st.info("No se pudo obtener el roster.")
            except Exception as e:
                st.error(f"Error al cargar el roster: {e}")
    else:
        st.error("No se pudieron cargar los equipos de la MLB.")

elif opcion == "Buscar Jugador & Depuración":
    st.header("Buscador de Jugadores & Diagnóstico")
    player_name = st.text_input("Ingresa el nombre del jugador (ej. Shohei Ohtani):", "Shohei Ohtani")
    
    if player_name:
        players = statsapi.lookup_player(player_name)
        if players:
            player = players[0]
            player_id = player['id']
            
            st.success(f"¡Jugador encontrado: {player['fullName']} (ID: {player_id})!")
            
            try:
                raw_data = statsapi.get("people", {
                    "personIds": player_id, 
                    "hydrate": f"currentTeam,stats(group=[hitting,pitching],type=season,season={CURRENT_YEAR})"
                })
                
                if raw_data and 'people' in raw_data:
                    p_info = raw_data['people'][0]
                    st.write(f"**Posición:** {p_info.get('primaryPosition', {}).get('name', 'N/A')}")
                    st.write(f"**Edad:** {p_info.get('currentAge', 'N/A')}")
                    
                    stats_list = p_info.get('stats', [])
                    found_data = False
                    
                    for stat_group in stats_list:
                        g_type = stat_group.get('group', {}).get('displayName')
                        splits = stat_group.get('splits', [])
                        if splits:
                            s_stats = splits[0].get('stat', {})
                            st.subheader(f"Estadísticas de {g_type} ({CURRENT_YEAR})")
                            
                            cols = st.columns(3)
                            if g_type == "hitting":
                                cols[0].metric("Promedio (AVG)", s_stats.get('avg', '.000'))
                                cols[1].metric("Hits", s_stats.get('hits', 0))
                                cols[2].metric("Ponches (SO)", s_stats.get('strikeOuts', 0))
                            else:
                                cols[0].metric("Efectividad (ERA)", s_stats.get('era', '0.00'))
                                cols[1].metric("Ponches (SO)", s_stats.get('strikeOuts', 0))
                            found_data = True
                    
                    if not found_data:
                        st.info("La API no devolvió estadísticas para este año.")
            except Exception as e:
                st.error(f"Error consultando los datos: {e}")
        else:
            st.warning("No se encontró ningún jugador con ese nombre.")

elif opcion == "Partidos del Día & Análisis (Ambos Equipos + Racha + BvP)":
    st.header("📅 Partidos y Expectativas Completas (Ambos Equipos)")
    date_to_check = st.date_input("Selecciona una fecha para partidos:")
    
    formatted_date = date_to_check.strftime("%m/%d/%Y")
    schedule = statsapi.schedule(date=formatted_date)
    
    if schedule:
        st.write(f"Se encontraron **{len(schedule)}** encuentros para esta fecha.")
        
        for game in schedule:
            away_name = game.get('away_name', 'Visitante')
            home_name = game.get('home_name', 'Local')
            away_score = game.get('away_score', 0)
            home_score = game.get('home_score', 0)
            status = game.get('status', 'Programado')
            game_pk = game.get('game_id')
            
            with st.expander(f"⚾ {away_name} ({away_score}) vs {home_name} ({home_score}) | Estado: {status}"):
                st.write(f"**Estadio:** {game.get('venue_name', 'N/A')}")
                st.write(f"**Detalle:** {game.get('detailed_state', 'N/A')}")
                
                if game_pk and st.button(f"🔍 Proyección Completa de Ambos Equipos", key=f"btn_proy_{game_pk}"):
                    with st.spinner("Buscando abridores, rachas recientes y métricas BvP..."):
                        try:
                            # 1. Obtener abridores probables
                            abridores = obtener_abridores_probables(game_pk)
                            
                            st.subheader("🥎 Lanzadores Abridores Probables")
                            c_p1, c_p2 = st.columns(2)
                            c_p1.info(f"**Visitante ({away_name}):** {abridores['away_name']}")
                            c_p2.info(f"**Local ({home_name}):** {abridores['home_name']}")
                            
                            all_teams = statsapi.get("teams", {"sportId": 1})
                            teams_dict = all_teams.get('teams', [])
                            
                            away_id = game.get('away_id') or next((t['id'] for t in teams_dict if away_name.lower() in t['name'].lower() or t['name'].lower() in away_name.lower()), None)
                            home_id = game.get('home_id') or next((t['id'] for t in teams_dict if home_name.lower() in t['name'].lower() or t['name'].lower() in home_name.lower()), None)
                            
                            col_away, col_home = st.columns(2)
                            
                            # --- PROYECCIÓN EQUIPO VISITANTE (Bateadores vs Abridor Local) ---
                            with col_away:
                                st.markdown(f"### ✈️ {away_name} (Visitante)")
                                if away_id:
                                    away_roster = statsapi.get("team_roster", {"teamId": away_id})
                                    if away_roster and 'roster' in away_roster:
                                        count_a = 0
                                        for m in away_roster['roster']:
                                            pos_abbrev = m.get('position', {}).get('abbreviation', '')
                                            if pos_abbrev == 'P': continue  # Omitir lanzadores en bateo
                                            if count_a >= 4: break
                                            
                                            pid = m.get('person', {}).get('id')
                                            pname = m.get('person', {}).get('fullName')
                                            
                                            p_data = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=hitting,type=season,season={CURRENT_YEAR})"})
                                            if p_data and 'people' in p_data:
                                                splits = p_data['people'][0].get('stats', [{}])[0].get('splits', [])
                                                if splits:
                                                    s = splits[0].get('stat', {})
                                                    avg = float(s.get('avg', 0))
                                                    hits = s.get('hits', 0)
                                                    gp = max(1, s.get('gamesPlayed', 1))
                                                    
                                                    with st.container():
                                                        st.markdown(f"**👤 {pname}** ({pos_abbrev})")
                                                        st.write(f"- Temp. {CURRENT_YEAR}: AVG `{avg:.3f}` | Hits/J `{hits/gp:.1f}`")
                                                        
                                                        # Racha 7 Días
                                                        r7 = obtener_racha_7dias(pid, CURRENT_YEAR)
                                                        if r7 and r7['gp'] > 0:
                                                            st.write(f"- 🔥 Last 7D: AVG `{r7['avg']}` | Hits `{r7['hits']}` | OPS `{r7['ops']}`")
                                                        
                                                        # BvP vs Lanzador Abridor Local
                                                        if abridores['home_id']:
                                                            bvp = obtener_bvp(pid, abridores['home_id'])
                                                            if bvp and bvp['ab'] > 0:
                                                                st.write(f"- ⚔️ vs {abridores['home_name']}: `{bvp['hits']}/{bvp['ab']}` AB (AVG `{bvp['avg']}`) | K: `{bvp['so']}`")
                                                            else:
                                                                st.write(f"- ⚔️ vs {abridores['home_name']}: Sin enfrentamientos previos")
                                                        st.divider()
                                                    count_a += 1
                                    else:
                                        st.info("Sin plantilla disponible.")
                                else:
                                    st.warning("No se pudo identificar el ID del visitante.")

                            # --- PROYECCIÓN EQUIPO LOCAL (Bateadores vs Abridor Visitante) ---
                            with col_home:
                                st.markdown(f"### 🏠 {home_name} (Local)")
                                if home_id:
                                    home_roster = statsapi.get("team_roster", {"teamId": home_id})
                                    if home_roster and 'roster' in home_roster:
                                        count_h = 0
                                        for m in home_roster['roster']:
                                            pos_abbrev = m.get('position', {}).get('abbreviation', '')
                                            if pos_abbrev == 'P': continue
                                            if count_h >= 4: break
                                            
                                            pid = m.get('person', {}).get('id')
                                            pname = m.get('person', {}).get('fullName')
                                            
                                            p_data = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=hitting,type=season,season={CURRENT_YEAR})"})
                                            if p_data and 'people' in p_data:
                                                splits = p_data['people'][0].get('stats', [{}])[0].get('splits', [])
                                                if splits:
                                                    s = splits[0].get('stat', {})
                                                    avg = float(s.get('avg', 0))
                                                    hits = s.get('hits', 0)
                                                    gp = max(1, s.get('gamesPlayed', 1))
                                                    
                                                    with st.container():
                                                        st.markdown(f"**👤 {pname}** ({pos_abbrev})")
                                                        st.write(f"- Temp. {CURRENT_YEAR}: AVG `{avg:.3f}` | Hits/J `{hits/gp:.1f}`")
                                                        
                                                        # Racha 7 Días
                                                        r7 = obtener_racha_7dias(pid, CURRENT_YEAR)
                                                        if r7 and r7['gp'] > 0:
                                                            st.write(f"- 🔥 Last 7D: AVG `{r7['avg']}` | Hits `{r7['hits']}` | OPS `{r7['ops']}`")
                                                        
                                                        # BvP vs Lanzador Abridor Visitante
                                                        if abridores['away_id']:
                                                            bvp = obtener_bvp(pid, abridores['away_id'])
                                                            if bvp and bvp['ab'] > 0:
                                                                st.write(f"- ⚔️ vs {abridores['away_name']}: `{bvp['hits']}/{bvp['ab']}` AB (AVG `{bvp['avg']}`) | K: `{bvp['so']}`")
                                                            else:
                                                                st.write(f"- ⚔️ vs {abridores['away_name']}: Sin enfrentamientos previos")
                                                        st.divider()
                                                    count_h += 1
                                    else:
                                        st.info("Sin plantilla disponible.")
                                else:
                                    st.warning("No se pudo identificar el ID del local.")
                                    
                        except Exception as e:
                            st.error(f"Error al generar la proyección de ambos equipos: {e}")
    else:
        st.info("No hay partidos programados para esta fecha.")

elif opcion == "⚾ Lanzadores Principales de Cada Equipo":
    st.header(f"⚾ Seleccionados (Pitchers) por Equipo - {CURRENT_YEAR}")
    st.markdown("Selecciona un equipo de la MLB para consultar automáticamente a sus lanzadores y ver sus estadísticas de temporada.")
    
    teams_data = statsapi.get("teams", {"sportId": 1})
    if teams_data and 'teams' in teams_data:
        team_names = [t['name'] for t in teams_data['teams']]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names, key="pitcher_team_select")
        selected_team = next(t for t in teams_data['teams'] if t['name'] == selected_team_name)
        
        if st.button("📊 Consultar Lanzadores del Equipo"):
            with st.spinner("Filtrando lanzadores desde la API oficial..."):
                try:
                    roster_data = statsapi.get("team_roster", {"teamId": selected_team['id']})
                    if roster_data and 'roster' in roster_data:
                        pitchers_found = 0
                        for member in roster_data['roster']:
                            pos_code = member.get('position', {}).get('abbreviation', '')
                            if 'P' in pos_code:
                                pitchers_found += 1
                                pid = member.get('person', {}).get('id')
                                pname = member.get('person', {}).get('fullName')
                                
                                with st.expander(f"🥎 Lanzador: {pname} ({pos_code})"):
                                    p_raw = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=pitching,type=season,season={CURRENT_YEAR})"})
                                    if p_raw and 'people' in p_raw:
                                        stats_groups = p_raw['people'][0].get('stats', [])
                                        has_stats = False
                                        for group in stats_groups:
                                            splits = group.get('splits', [])
                                            if splits:
                                                s_val = splits[0].get('stat', {})
                                                c1, c2, c3, c4 = st.columns(4)
                                                c1.metric("Efectividad (ERA)", s_val.get('era', '0.00'))
                                                c2.metric("Ponches (SO)", s_val.get('strikeOuts', 0))
                                                c3.metric("Juegos Lanzados", s_val.get('gamesPlayed', 0))
                                                c4.metric("WHIP", s_val.get('whip', '0.00'))
                                                has_stats = True
                                        if not has_stats:
                                            st.info("Sin estadísticas registradas para esta temporada actual.")
                        if pitchers_found == 0:
                            st.warning("No se encontraron lanzadores activos en este roster.")
                    else:
                        st.warning("No se pudo obtener la plantilla del equipo.")
                except Exception as e:
                    st.error(f"Error al consultar los lanzadores: {e}")

elif opcion == "🎯 Análisis de Jugadores (Hits y Ponches)":
    st.header(f"🎯 Análisis Masivo de Plantilla ({CURRENT_YEAR})")
    
    teams_data = statsapi.get("teams", {"sportId": 1})
    if teams_data and 'teams' in teams_data:
        team_names = [t['name'] for t in teams_data['teams']]
        selected_team_name = st.selectbox("Selecciona un equipo:", team_names, key="masivo_team")
        selected_team = next(t for t in teams_data['teams'] if t['name'] == selected_team_name)
        
        if st.button("📊 Ejecutar Análisis Completo"):
            with st.spinner("Consultando servidores de la MLB..."):
                try:
                    roster_data = statsapi.get("team_roster", {"teamId": selected_team['id']})
                    if roster_data and 'roster' in roster_data:
                        st.success(f"Plantilla de los **{selected_team_name}**:")
                        for member in roster_data['roster'][:8]:
                            p_info = member.get('person', {})
                            pid = p_info.get('id')
                            pname = p_info.get('fullName', 'N/A')
                            pos = member.get('position', {}).get('abbreviation', 'N/A')
                            
                            with st.expander(f"👤 {pname} ({pos})"):
                                p_raw = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=[hitting,pitching],type=season,season={CURRENT_YEAR})"})
                                if p_raw and 'people' in p_raw:
                                    stats_groups = p_raw['people'][0].get('stats', [])
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
                except Exception as e:
                    st.error(f"Error procesando el análisis: {e}")
