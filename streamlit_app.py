import streamlit as st
import statsapi  # Importa la librería de la API de MLB
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Analizador de MLB",
    page_icon="⚾",
    layout="wide"
)

# Definimos el año actual de análisis (2026)
CURRENT_YEAR = datetime.now().year

st.title("⚾ Analizador y Predictor de Estadísticas de la MLB")
st.markdown("Panel avanzado con `MLB-StatsAPI` para evaluar rendimiento, hits, ponches y expectativas de jugadores.")

# Barra lateral para navegación
st.sidebar.header("Opciones de Consulta")
opcion = st.sidebar.selectbox(
    "Selecciona una sección:",
    ["Equipos de la MLB", "Buscar Jugador & Depuración", "Partidos del Día & Análisis", "🎯 Análisis de Jugadores (Hits y Ponches)"]
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
            st.subheader("Plantilla Actual (Roster)")
            try:
                roster = statsapi.roster(team_id)
                st.code(str(roster), language="text")
            except Exception:
                st.info("No se pudo cargar el roster de este equipo.")
    else:
        st.error("No se pudieron cargar los equipos de la MLB.")

elif opcion == "Buscar Jugador & Depuración":
    st.header("Buscador de Jugadores & Diagnóstico de Conexión")
    player_name = st.text_input("Ingresa el nombre del jugador (ej. Shohei Ohtani):", "Shohei Ohtani")
    
    if player_name:
        players = statsapi.lookup_player(player_name)
        if players:
            player = players[0]
            player_id = player['id']
            
            st.success(f"¡Jugador encontrado: {player['fullName']} (ID: {player_id})!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Posición:** {player.get('primaryPosition', {}).get('name', 'N/A')}")
                st.write(f"**Edad:** {player.get('currentAge', 'N/A')}")
                st.write(f"**Debut en MLB:** {player.get('mlbDebutDate', 'N/A')}")
            
            with col2:
                st.subheader(f"Métricas de Rendimiento ({CURRENT_YEAR})")
                try:
                    hitting_stats = statsapi.player_stat_data(player_id, group="hitting", type="season", season=CURRENT_YEAR)
                    if hitting_stats and len(hitting_stats) > 0 and 'stats' in hitting_stats[0] and hitting_stats[0]['stats']:
                        stats_data = hitting_stats[0]['stats']
                        st.metric(label="Promedio de Bateo (AVG)", value=stats_data.get('avg', '.000'))
                        st.metric(label="Hits Conectados", value=stats_data.get('hits', 0))
                        st.metric(label="Ponches Recibidos (SO)", value=stats_data.get('strikeOuts', 0))
                    else:
                        pitching_stats = statsapi.player_stat_data(player_id, group="pitching", type="season", season=CURRENT_YEAR)
                        if pitching_stats and len(pitching_stats) > 0 and 'stats' in pitching_stats[0] and pitching_stats[0]['stats']:
                            p_data = pitching_stats[0]['stats']
                            st.info("El jugador registrado es Lanzador (Pitcher).")
                            st.metric(label="Efectividad (ERA)", value=p_data.get('era', '0.00'))
                            st.metric(label="Ponches Propinados (SO)", value=p_data.get('strikeOuts', 0))
                        else:
                            st.info("No hay estadísticas oficiales registradas para la temporada actual.")
                except Exception:
                    st.warning("No se pudieron cargar estadísticas detalladas.")

            st.markdown("---")
            st.subheader("🛠️ Diagnóstico de Conexión en Bruto")
            if st.button("Probar conexión cruda con la API"):
                try:
                    raw_data = statsapi.get("people", {"personIds": player_id, "hydrate": f"stats(group=[hitting,pitching],type=season,season={CURRENT_YEAR})"})
                    st.json(raw_data)
                except Exception as e:
                    st.error(f"Error de conexión con la API: {e}")
        else:
            st.warning("No se encontró ningún jugador con ese nombre.")

elif opcion == "Partidos del Día & Análisis":
    st.header("📅 Partidos, Boxscore y Expectativas para el Siguiente Juego")
    date_to_check = st.date_input("Selecciona una fecha para partidos:")
    
    formatted_date = date_to_check.strftime("%m/%d/%Y")
    schedule = statsapi.schedule(date=formatted_date)
    
    if schedule:
        st.write(f"Se encontraron **{len(schedule)}** encuentros para esta fecha.")
        
        for game in schedule:
            away_name = game.get('away_name', 'Visitante')
            away_id = game.get('away_id')
            away_score = game.get('away_score', 0)
            
            home_name = game.get('home_name', 'Local')
            home_id = game.get('home_id')
            home_score = game.get('home_score', 0)
            
            status = game.get('status', 'Programado')
            game_pk = game.get('game_id')
            
            with st.expander(f"⚾ {away_name} ({away_score}) vs {home_name} ({home_score}) | Estado: {status}"):
                venue_info = game.get('venue_name', game.get('venue', 'No disponible'))
                detailed_state = game.get('detailed_state', 'N/A')
                
                st.write(f"**Estadio:** {venue_info}")
                st.write(f"**Detalle del juego:** {detailed_state}")
                
                if game_pk:
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        ver_box = st.button(f"🔍 Ver Boxscore (ID: {game_pk})", key=f"box_{game_pk}")
                    with col_btn2:
                        ver_expectativa = st.button(f"🎯 Estimar Expectativas Próximo Juego", key=f"exp_{game_pk}")
                    
                    if ver_box:
                        try:
                            box = statsapi.boxscore(game_pk)
                            st.code(str(box), language="text")
                        except Exception:
                            st.warning("El boxscore detallado aún no está disponible.")
                    
                    if ver_expectativa:
                        st.markdown("---")
                        st.subheader("📈 Análisis Predictivo Basado en Datos de Temporada")
                        with st.spinner("Calculando promedios y tendencias para los jugadores..."):
                            try:
                                st.markdown(f"**Proyección ofensiva estimada para {home_name}:**")
                                
                                # Obtenemos el roster directamente con el ID seguro del equipo local
                                if home_id:
                                    h_roster = statsapi.get("team_roster", {"teamId": home_id})
                                    if h_roster and 'roster' in h_roster:
                                        count = 0
                                        for m in h_roster['roster']:
                                            if count >= 3: 
                                                break
                                            p_info = m.get('person', {})
                                            pid = p_info.get('id')
                                            pname = p_info.get('fullName')
                                            
                                            st_data = statsapi.player_stat_data(pid, group="hitting", type="season", season=CURRENT_YEAR)
                                            if st_data and len(st_data) > 0 and 'stats' in st_data[0] and st_data[0]['stats']:
                                                s = st_data[0]['stats']
                                                avg = float(s.get('avg', 0))
                                                hits_per_game = s.get('hits', 0) / max(1, s.get('gamesPlayed', 1))
                                                
                                                prob_hit = "Alto (Favorito para conectar +1 Hit)" if avg >= 0.270 else "Moderado"
                                                st.write(f"- **{pname}**: Promedio ({avg:.3f}) | **Expectativa:** {prob_hit} (Media de {hits_per_game:.1f} hits/juego).")
                                                count += 1
                                    else:
                                        st.info("No hay datos de plantilla disponibles para proyectar este equipo en este momento.")
                                else:
                                    st.warning("No se pudo identificar el ID del equipo local en el calendario.")
                                    
                                st.info(f"Nota: Proyección calculada con base en los registros oficiales acumulados en la temporada {CURRENT_YEAR}.")
                            except Exception as e:
                                st.error(f"Error al procesar la proyección: {e}")
    else:
        st.info("No hay partidos programados para esta fecha.")

elif opcion == "🎯 Análisis de Jugadores (Hits y Ponches)":
    st.header(f"🎯 Análisis de Expectativas: Hits y Ponches ({CURRENT_YEAR})")
    st.markdown("Selecciona un equipo para evaluar el acumulado de sus jugadores principales en la temporada actual.")
    
    teams_data = statsapi.get("teams", {"sportId": 1})
    
    if teams_data and 'teams' in teams_data:
        teams = teams_data['teams']
        team_names = [team['name'] for team in teams]
        selected_team_name = st.selectbox("Selecciona un equipo para analizar su plantilla:", team_names, key="analysis_team")
        
        selected_team = next(t for t in teams if t['name'] == selected_team_name)
        team_id = selected_team['id']
        
        if st.button("📊 Generar Análisis de Jugadores"):
            with st.spinner("Consultando la base de datos oficial de la MLB..."):
                try:
                    roster_data = statsapi.get("team_roster", {"teamId": team_id})
                    if roster_data and 'roster' in roster_data:
                        st.success(f"Plantilla analizada para los **{selected_team_name}**:")
                        
                        for member in roster_data['roster'][:10]:
                            player_info = member.get('person', {})
                            p_id = player_info.get('id')
                            p_name = player_info.get('fullName')
                            p_pos = member.get('position', {}).get('abbreviation', 'N/A')
                            
                            with st.expander(f"👤 {p_name} ({p_pos})"):
                                found_stats = False
                                try:
                                    h_stats = statsapi.player_stat_data(p_id, group="hitting", type="season", season=CURRENT_YEAR)
                                    if h_stats and len(h_stats) > 0 and 'stats' in h_stats[0] and h_stats[0]['stats']:
                                        s_data = h_stats[0]['stats']
                                        col_a, col_b, col_c = st.columns(3)
                                        col_a.metric("Promedio (AVG)", s_data.get('avg', '.000'))
                                        col_b.metric("Hits", s_data.get('hits', 0))
                                        col_c.metric("Ponches (SO)", s_data.get('strikeOuts', 0))
                                        found_stats = True
                                except Exception:
                                    pass
                                
                                if not found_stats:
                                    try:
                                        p_stats = statsapi.player_stat_data(p_id, group="pitching", type="season", season=CURRENT_YEAR)
                                        if p_stats and len(p_stats) > 0 and 'stats' in p_stats[0] and p_stats[0]['stats']:
                                            p_data = p_stats[0]['stats']
                                            col_a, col_b = st.columns(2)
                                            col_a.metric("Efectividad (ERA)", p_data.get('era', '0.00'))
                                            col_b.metric("Ponches (SO)", p_data.get('strikeOuts', 0))
                                            found_stats = True
                                    except Exception:
                                        pass
                                
                                if not found_stats:
                                    st.info(f"Sin estadísticas registradas para la temporada {CURRENT_YEAR}.")
                    else:
                        st.warning("No se encontró información del roster para este equipo.")
                except Exception as e:
                    st.error(f"Ocurrió un error al procesar el análisis: {e}")
    else:
        st.error("No se pudo cargar la lista de equipos.")
