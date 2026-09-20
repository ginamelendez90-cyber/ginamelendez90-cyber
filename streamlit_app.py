import streamlit as st
import pandas as pd
import statsapi

st.title("⚾ Análisis MLB en Tiempo Real (MLB-StatsAPI)")

# Buscador de jugadores
nombre_jugador = st.text_input("Ingresa el nombre del jugador:", "Shohei Ohtani")

if st.button("Consultar Estadísticas"):
    try:
        # 1. Buscar ID del jugador
        busqueda = statsapi.lookup_player(nombre_jugador)
        
        if not busqueda:
            st.error(f"No se encontró al jugador: {nombre_jugador}")
        else:
            player_id = busqueda[0]['id']
            st.success(f"Jugador encontrado: {busqueda[0]['fullName']} (ID: {player_id})")
            
            # 2. Obtener estadísticas de bateo de la temporada actual
            stats = statsapi.player_stat_data(player_id, group="hitting", type="season")
            
            if 'stats' in stats and len(stats['stats']) > 0:
                stat_dict = stats['stats'][0]['stats']
                
                # Mostrar métricas principales
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("AVG (Promedio)", stat_dict.get('avg', '.000'))
                col2.metric("OPS", stat_dict.get('ops', '.000'))
                col3.metric("Home Runs", stat_dict.get('homeRuns', 0))
                col4.metric("RBI (Impulsadas)", stat_dict.get('rbi', 0))
                
                # Mostrar el desglose completo
                st.subheader("Estadísticas Detalladas")
                st.json(stat_dict)
            else:
                st.warning("No se encontraron estadísticas para la temporada actual.")

    except Exception as e:
        st.error(f"Error al conectar con la API de la MLB: {e}")
