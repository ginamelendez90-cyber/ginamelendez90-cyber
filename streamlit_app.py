import streamlit as st
import pandas as pd
import datetime

# 1. Configuración principal
st.set_page_config(page_title="Gestión de Cartera", layout="wide")

# 2. Inicialización de la base de datos temporal
if 'clientes' not in st.session_state:
    st.session_state.clientes = pd.DataFrame(columns=['ID_Cliente', 'Nombre', 'Teléfono'])
if 'prestamos' not in st.session_state:
    st.session_state.prestamos = pd.DataFrame(columns=['ID_Prestamo', 'Cliente', 'Monto_Inicial', 'Saldo_Actual'])
if 'abonos' not in st.session_state:
    st.session_state.abonos = pd.DataFrame(columns=['ID_Abono', 'ID_Prestamo', 'Monto_Abonado', 'Fecha'])

st.title("Sistema de Préstamos y Abonos")

# 3. Menú de Navegación
menu = st.sidebar.radio("Navegación", ["📊 Dashboard", "👤 Ingresar Cliente", "💰 Registrar Préstamo", "💵 Registrar Abono"])

# --- VISTA: INGRESAR CLIENTE ---
if menu == "👤 Ingresar Cliente":
    st.header("Registrar Nuevo Cliente")
    with st.form("form_cliente", clear_on_submit=True):
        nombre = st.text_input("Nombre completo")
        telefono = st.text_input("Número de teléfono")
        submit_cliente = st.form_submit_button("Guardar Cliente")

        if submit_cliente and nombre:
            nuevo_id = len(st.session_state.clientes) + 1
            nuevo_cliente = pd.DataFrame({'ID_Cliente': [nuevo_id], 'Nombre': [nombre], 'Teléfono': [telefono]})
            st.session_state.clientes = pd.concat([st.session_state.clientes, nuevo_cliente], ignore_index=True)
            st.success(f"Cliente '{nombre}' guardado exitosamente.")

# --- VISTA: REGISTRAR PRÉSTAMO ---
elif menu == "💰 Registrar Préstamo":
    st.header("Asignar Nuevo Préstamo")
    if not st.session_state.clientes.empty:
        with st.form("form_prestamo", clear_on_submit=True):
            cliente_sel = st.selectbox("Seleccionar Cliente", st.session_state.clientes['Nombre'].tolist())
            monto = st.number_input("Monto del Préstamo", min_value=1.0, step=10.0)
            submit_prestamo = st.form_submit_button("Registrar Préstamo")

            if submit_prestamo:
                nuevo_id_prestamo = len(st.session_state.prestamos) + 1
                nuevo_prestamo = pd.DataFrame({
                    'ID_Prestamo': [nuevo_id_prestamo],
                    'Cliente': [cliente_sel],
                    'Monto_Inicial': [monto],
                    'Saldo_Actual': [monto]
                })
                st.session_state.prestamos = pd.concat([st.session_state.prestamos, nuevo_prestamo], ignore_index=True)
                st.success("Préstamo registrado correctamente.")
    else:
        st.warning("Debes ingresar al menos un cliente en el sistema primero.")

# --- VISTA: REGISTRAR ABONO ---
elif menu == "💵 Registrar Abono":
    st.header("Aplicar Abono a un Crédito Activo")
    # Aislar solo los créditos que aún tienen saldo
    prestamos_activos = st.session_state.prestamos[st.session_state.prestamos['Saldo_Actual'] > 0]

    if not prestamos_activos.empty:
        with st.form("form_abono", clear_on_submit=True):
            opciones = prestamos_activos.apply(
                lambda x: f"Préstamo #{x['ID_Prestamo']} | {x['Cliente']} | Saldo: ${x['Saldo_Actual']:.2f}", axis=1
            ).tolist()
            
            seleccion = st.selectbox("Seleccionar Crédito", opciones)
            monto_abono = st.number_input("Monto a abonar", min_value=1.0, step=10.0)
            submit_abono = st.form_submit_button("Procesar Abono")

            if submit_abono:
                id_prestamo = int(seleccion.split("#")[1].split(" |")[0])
                fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

                idx = st.session_state.prestamos.index[st.session_state.prestamos['ID_Prestamo'] == id_prestamo][0]
                saldo_previo = st.session_state.prestamos.at[idx, 'Saldo_Actual']

                if monto_abono <= saldo_previo:
                    st.session_state.prestamos.at[idx, 'Saldo_Actual'] -= monto_abono
                    
                    nuevo_abono = pd.DataFrame({
                        'ID_Abono': [len(st.session_state.abonos) + 1],
                        'ID_Prestamo': [id_prestamo],
                        'Monto_Abonado': [monto_abono],
                        'Fecha': [fecha_hoy]
                    })
                    st.session_state.abonos = pd.concat([st.session_state.abonos, nuevo_abono], ignore_index=True)
                    st.success(f"Abono procesado. Nuevo saldo pendiente: ${saldo_previo - monto_abono:.2f}")
                else:
                    st.error("El monto del abono no puede ser mayor al saldo pendiente.")
    else:
        st.info("No hay créditos activos pendientes de pago en este momento.")

# --- VISTA: DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("Resumen de Flujo de Caja y Cartera")

    # Métricas principales
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Clientes", len(st.session_state.clientes))
    total_prestado = st.session_state.prestamos['Monto_Inicial'].sum() if not st.session_state.prestamos.empty else 0
    col2.metric("Capital Prestado", f"${total_prestado:.2f}")
    total_pendiente = st.session_state.prestamos['Saldo_Actual'].sum() if not st.session_state.prestamos.empty else 0
    col3.metric("Capital en la Calle (Pendiente)", f"${total_pendiente:.2f}")

    st.divider()

    # Tabla de Créditos Activos
    st.subheader("Créditos Activos")
    activos = st.session_state.prestamos[st.session_state.prestamos['Saldo_Actual'] > 0]
    st.dataframe(activos, use_container_width=True, hide_index=True)

    st.divider()

    # Tabla de Historial de Abonos con Filtro de Fechas
    st.subheader("Historial de Abonos")
    
    if not st.session_state.abonos.empty:
        df_abonos = st.session_state.abonos.copy()
        df_abonos['Fecha_Filtro'] = pd.to_datetime(df_abonos['Fecha']).dt.date
        
        col_f1, col_f2 = st.columns(2)
        fecha_inicio = col_f1.date_input("Desde", datetime.date.today())
        fecha_fin = col_f2.date_input("Hasta", datetime.date.today())
        
        mask = (df_abonos['Fecha_Filtro'] >= fecha_inicio) & (df_abonos['Fecha_Filtro'] <= fecha_fin)
        abonos_filtrados = df_abonos.loc[mask].drop(columns=['Fecha_Filtro'])
        
        st.dataframe(abonos_filtrados, use_container_width=True, hide_index=True)
        
        if not abonos_filtrados.empty:
            total_rango = abonos_filtrados['Monto_Abonado'].sum()
            st.success(f"Total recaudado en el periodo seleccionado: ${total_rango:.2f}")
        else:
            st.warning("No se encontraron abonos en este rango de fechas.")
    else:
        st.info("Aún no hay abonos registrados en el sistema.")
