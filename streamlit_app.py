import streamlit as st
import pandas as pd
import requests
import zipfile
import io

# 1. URL de descarga directa (usando /raw/ en lugar de /blob/)
GITHUB_ZIP_URL = "https://github.com/ginamelendez90-cyber/ginamelendez90-cyber/raw/main/MLB-StatsAPI-master.zip"

@st.cache_data
def cargar_datos_desde_zip(url):
    try:
        # Descargar el ZIP desde GitHub
        response = requests.get(url)
        response.raise_for_status() # Verifica que no haya error 404
        
        # Abrir el ZIP en la memoria de Streamlit
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            
            # Buscar todos los archivos que terminen en .csv dentro del ZIP
            archivos_csv = [f for f in z.namelist() if f.endswith('.csv')]
            
            if not archivos_csv:
                st.error("No se encontraron archivos CSV dentro del archivo ZIP.")
                return None
                
            # Por defecto, abrimos el primer CSV que encuentre. 
            # (Si sabes el nombre exacto, cámbialo aquí)
            archivo_objetivo = archivos_csv[0] 
            
            # Leer el CSV con Pandas
            with z.open(archivo_objetivo) as f:
                df = pd.read_csv(f)
                
            return df, archivo_objetivo # Retornamos los datos y el nombre del archivo
            
    except Exception as e:
        st.error(f"Ocurrió un error al procesar el ZIP: {e}")
        return None, None

# ==========================================
# INTERFAZ DE STREAMLIT
# ==========================================
st.title("⚾ Análisis MLB desde GitHub ZIP")

if st.button("Cargar Datos Actuales"):
    with st.spinner('Descargando y extrayendo ZIP desde GitHub...'):
        df, nombre_archivo = cargar_datos_desde_zip(GITHUB_ZIP_URL)
        
        if df is not None:
            st.success(f"¡Datos cargados exitosamente desde: {nombre_archivo}!")
            
            # Mostrar las primeras filas y columnas del dataset
            st.subheader("Vista previa de los datos")
            st.dataframe(df.head(10))
            
            # Mostrar qué columnas detectó para que sepas cómo armar tu algoritmo después
            st.write("Columnas disponibles para el análisis:", df.columns.tolist())
