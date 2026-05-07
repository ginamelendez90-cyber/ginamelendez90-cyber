import streamlit as st
import re

# Configuración de la página
st.set_page_config(page_title="Analizador de Tenis", layout="centered")

st.title("🎾 Analizador de Tenis Pro")
st.write("Pega los datos de 'Últimos Partidos' para obtener la predicción.")

# Área de texto para pegar la información
data_entrada = st.text_area("Datos de 365Scores / Flashscore:", height=200, placeholder="ÚLTIMOS PARTIDOS: JUGADOR A...")

def analizar_datos(texto_crudo):
    # (Aquí va la misma lógica del script anterior que limpia el texto)
    bloques = re.split(r'ÚLTIMOS PARTIDOS:', texto_crudo)
    resultados_finales = []
    for bloque in bloques:
        if not bloque.strip(): continue
        lineas = [l.strip() for l in bloque.strip().split('\n') if l.strip()]
        if not lineas: continue
        nombre = lineas[0]
        patron = re.findall(r'(\d)\s+(\d)\s+([GP])', bloque)
        if patron:
            victorias = sum(1 for p in patron if p[2] == 'G')
            resultados_finales.append({
                "nombre": nombre,
                "win_rate": victorias / len(patron),
                "racha": f"{victorias}-{len(patron) - victorias}"
            })
    return resultados_finales

if st.button("Analizar Partido"):
    if data_entrada:
        stats = analizar_datos(data_entrada)
        if len(stats) >= 2:
            j1, j2 = stats[0], stats[1]
            ganador = j1 if j1['win_rate'] > j2['win_rate'] else j2
            
            st.success(f"🏆 Ganador Probable: {ganador['nombre']}")
            col1, col2 = st.columns(2)
            col1.metric(j1['nombre'], j1['racha'])
            col2.metric(j2['nombre'], j2['racha'])
        else:
            st.error("Por favor, pega los datos de ambos jugadores.")
    else:
        st.warning("El área de texto está vacía.")
