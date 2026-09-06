import streamlit as st
import pandas as pd
import plotly.express as px
from langchain_community.chat_models import ChatOllama

st.title("Analizador Local con Gráficos Interactivos")

archivo = st.file_uploader("Carga tu archivo CSV", type=["csv"])

if archivo:
    df = pd.read_csv(archivo)
    st.write("### Vista previa de los datos", df.head(3))
    
    # Modelo local con Ollama
    llm = ChatOllama(
        model="llama3",
        temperature=0,
        base_url="http://localhost:11434"
    )
    
    pregunta = st.text_input("Pide un gráfico o consulta (ej: 'Genera un gráfico de barras del promedio de ventas por categoría')")
    
    if pregunta:
        # Prompt enfocado en generación de código Plotly ejecutable
        prompt = f"""
Eres un asistente de ciencia de datos. Tienes un DataFrame de Pandas llamado `df` con las siguientes columnas: {list(df.columns)}.

El usuario te solicita: "{pregunta}"

Instrucciones de respuesta:
1. Genera código Python utilizando `plotly.express` (importado como `px`) o `pandas`.
2. Si la solicitud implica un gráfico, asigna la figura de Plotly a una variable llamada `fig`.
3. Si la solicitud implica un dato o resumen de texto, asigna la respuesta a una variable llamada `resultado`.
4. Devuelve ÚNICAMENTE el código Python dentro de un bloque de código markdown ```python ... ```. No agregues saludos ni explicaciones de texto fuera del bloque de código.
"""
        with st.spinner("Generando gráfico/análisis localmente..."):
            try:
                respuesta = llm.invoke(prompt).content
                
                # Extraer el código Python limpio
                if "```python" in respuesta:
                    codigo = respuesta.split("```python")[1].split("```")[0].strip()
                elif "```" in respuesta:
                    codigo = respuesta.split("```")[1].split("```")[0].strip()
                else:
                    codigo = respuesta.strip()
                
                # Espacio de nombres para ejecutar el código de forma segura en memoria
                entorno_local = {"df": df, "px": px, "pd": pd}
                
                # Ejecutar el código generado por Ollama
                exec(codigo, entorno_local)
                
                # Renderizar el gráfico interactivo si el modelo creó la variable 'fig'
                if "fig" in entorno_local:
                    st.plotly_chart(entorno_local["fig"], use_container_width=True)
                
                # Mostrar el resultado numérico/texto si el modelo creó la variable 'resultado'
                if "resultado" in entorno_local:
                    st.write("**Resultado:**", entorno_local["resultado"])
                
                # Mostrar el código generado para auditoría
                with st.expander("Ver código Python generado por el modelo"):
                    st.code(codigo, language="python")
                    
            except Exception as e:
                st.error(f"Error procesando o ejecutando el gráfico: {e}")
