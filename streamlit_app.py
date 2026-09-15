import streamlit as st
import statsapi
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Analizador de MLB",
    page_icon="⚾",
    layout="wide"
)

CURRENT_YEAR = datetime.now().year

st.title("⚾ Analizador y Predictor de Estadísticas de la MLB")
st.markdown("Panel avanzado con peticiones directas a la API oficial para evitar bloqueos de la librería.")

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
            
            # Petición directa para asegurar datos de temporada
            try:
                raw_data = statsapi.get("people", {
                    "personIds": player_id, 
                    "hydrate": f"currentTeam,stats(group=[hitting,pitching],type=season,season={CURRENT_YEAR})"
                })
                
                if raw_data and 'people' in raw_data:
                    p_info = raw_data['people'][0]
                    st.write(f"**Posición:** {p_info.get('primaryPosition', {}).get('name', 'N/A')}")
                    st.write(f"**Edad:** {p_info.get('currentAge', 'N/A')}")
                    
                    # Intentar extraer estadísticas de la respuesta cruda
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
                        st.info("La API no devolvió estadísticas para este año (es posible que el jugador esté inactivo o lesionado).")
            except Exception as e:
                st.error(f"Error consultando los datos del jugador: {e}")
        else:
            st.warning("No se encontró ningún jugador con ese nombre.")

elif opcion == "Partidos del Día & Análisis":
    st.header("📅 Partidos y Expectativas")
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
                
                if game_pk and st.button(f"🔍 Cargar Proyección de Bateadores ({home_name})", key=f"btn_proy_{game_pk}"):
                    with st.spinner("Buscando datos recientes..."):
                        try:
                            all_teams = statsapi.get("teams", {"sportId": 1})
                            target_id = next((t['id'] for t in all_teams['teams'] if home_name.lower() in t['name'].lower() or t['name'].lower() in home_name.lower()), None)
                            
                            if target_id:
                                roster_res = statsapi.get("team_roster", {"teamId": target_id})
                                if roster_res and 'roster' in roster_res:
                                    st.markdown(f"**Jugadores clave analizados para {home_name}:**")
                                    count = 0
                                    for m in roster_res['roster']:
                                        if count >= 3: break
                                        pid = m.get('person', {}).get('id')
                                        pname = m.get('person', {}).get('fullName')
                                        
                                        # Consulta directa de rendimiento
                                        p_data = statsapi.get("people", {"personIds": pid, "hydrate": f"stats(group=hitting,type=season,season={CURRENT_YEAR})"})
                                        if p_data and 'people' in p_data:
                                            splits = p_data['people'][0].get('stats', [{}])[0].get('splits', [])
                                            if splits:
                                                s = splits[0].get('stat', {})
                                                avg = float(s.get('avg', 0))
                                                hits = s.get('hits', 0)
                                                gp = max(1, s.get('gamesPlayed', 1))
                                                st.write(f"- **{pname}**: AVG: {avg:.3f} | Promedio de hits/juego: {hits/gp:.1f}")
                                                count += 1
                                else:
                                    st.warning("No hay plantilla disponible.")
                            else:
                                st.warning("No se pudo mapear el ID del equipo local.")
                        except Exception as e:
                            st.error(f"Error al generar la proyección: {e}")
    else:
        st.info("No hay partidos programados para esta fecha.")

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
                            pname = p_info.get('fullName')
                            pos = member.get('position', {}).get('abbreviation', 'N/A')
                            
                            with st.expander(f"👤 {p_name} ({pos})"):
                                # Petición limpia por jugador
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
