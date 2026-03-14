import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. CONFIGURACIÓN DEL SOFTWARE
st.set_page_config(page_title="Almacén Minero Pro", layout="wide")

# 2. CONFIGURACIÓN DE URL Y CONEXIÓN
# He quitado el /edit para que sea una ruta de datos limpia
URL_DB = "https://docs.google.com/spreadsheets/d/1b0uag9fLLkDCaOMaFlNIOc3oXTwJ3KKZzWSqR9K5x98/edit"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- MENÚ LATERAL ---
st.sidebar.title("MENU PRINCIPAL")
opcion = st.sidebar.radio("Seleccione Módulo:", ["Panel de Stock", "Registrar Nuevo Artículo", "Entradas (OC)", "Salidas (Vales)"])

# --- MODULO 1: REGISTRO CON SALTO CORRELATIVO AUTOMÁTICO ---
if opcion == "Registrar Nuevo Artículo":
    st.header("📝 Catálogo de Artículos")
    
    # Leemos la base de datos
    df_art = conn.read(spreadsheet=URL_DB)
    
    # 1. Selección de Familia
    fam = st.selectbox("Seleccione Familia:", 
                      ["EPP", "HERRAMIENTAS", "EQUIPOS", "CONSUMIBLES"],
                      key="familia_selector")
    
    prefijos = {"EPP": "EPP", "HERRAMIENTAS": "HER", "EQUIPOS": "EQP", "CONSUMIBLES": "CON"}
    prefijo = prefijos[fam]

    # 2. CALCULAR EL SIGUIENTE CÓDIGO DISPONIBLE
    ultimo_num = 0
    if not df_art.empty and 'Codigo' in df_art.columns:
        # Filtramos por prefijo y extraemos el número más alto
        codigos_fam = df_art[df_art['Codigo'].str.startswith(prefijo, na=False)]
        if not codigos_fam.empty:
            numeros = codigos_fam['Codigo'].str.extract('(\d+)').astype(float).dropna()
            if not numeros.empty:
                ultimo_num = int(numeros.max())
    
    # Este es el código que toca registrar ahora
    codigo_a_usar = f"{prefijo}{ultimo_num + 1:03d}"

    # 3. FORMULARIO DE REGISTRO
    # Importante: No usamos 'value' en el text_input para el código, 
    # dejamos que el sistema lo muestre como una etiqueta informativa para que no se "chanque"
    with st.form("form_registro", clear_on_submit=True):
        st.info(f"PRÓXIMO CÓDIGO DISPONIBLE: **{codigo_a_usar}**")
        
        # El campo de código lo ponemos solo lectura o sugerido
        cod_confirmado = st.text_input("Confirmar Código para Registro", value=codigo_a_usar)
        nom_articulo = st.text_input("Nombre del Nuevo Artículo").strip().upper()
        stock_min = st.number_input("Stock Mínimo (Alerta)", min_value=0, value=5)
        
        boton_guardar = st.form_submit_button("REGISTRAR ARTÍCULO")

        if boton_guardar:
            # VALIDACIÓN DE SEGURIDAD
            if nom_articulo == "":
                st.warning("⚠️ El nombre no puede estar vacío.")
            
            elif cod_confirmado in df_art['Codigo'].astype(str).values:
                st.error(f"❌ EL CÓDIGO {cod_confirmado} YA EXISTE. El sistema generará uno nuevo ahora.")
                st.rerun() # Esto obliga a la app a refrescar y mostrar el siguiente correlativo
            
            elif nom_articulo in df_art['Nombre'].astype(str).values:
                st.error(f"❌ EL NOMBRE '{nom_articulo}' YA ESTÁ REGISTRADO.")
            
            else:
                # REGISTRO EXITOSO
                nueva_data = pd.DataFrame([{
                    "Codigo": cod_confirmado,
                    "Nombre": nom_articulo,
                    "Familia": fam,
                    "Stock_Actual": 0,
                    "Stock_Minimo": stock_min
                }])
                
                df_final = pd.concat([df_art, nueva_data], ignore_index=True)
                conn.update(spreadsheet=URL_DB, data=df_final)
                
                st.success(f"✅ ¡{nom_articulo} guardado con éxito bajo el código {cod_confirmado}!")
                
                # EL TRUCO FINAL: Forzamos el reinicio para que el código cambie al siguiente correlativo
                st.cache_data.clear() # Limpiamos caché para leer el nuevo Excel
                st.rerun()
# --- MODULO 2: PANEL DE STOCK (MEJORADO) ---
elif opcion == "Panel de Stock":
    st.header("📊 Inventario Real")
    df = conn.read(spreadsheet=URL_DB)
    
    # Añadimos un buscador simple arriba de la tabla
    busqueda = st.text_input("🔍 Buscar por Nombre o Código:", "").strip().upper()
    
    if busqueda:
        df = df[df['Nombre'].str.contains(busqueda, na=False) | 
                df['Codigo'].str.contains(busqueda, na=False)]
    
    # Mostramos la tabla
    st.dataframe(df, use_container_width=True)
    
    # Un pequeño resumen rápido
    col1, col2 = st.columns(2)
    bajo_stock = df[df['Stock_Actual'] <= df['Stock_Minimo']].shape[0]
    col1.metric("Artículos en Alerta (Bajo Stock)", bajo_stock, delta_color="inverse")

# --- MODULO 3: ENTRADAS (OC y GUÍA) - CARGA MÚLTIPLE BLINDADA ---
elif opcion == "Entradas (OC)":
    st.header("📥 Gestión de Ingresos Multibulto")
    
    df_art = conn.read(spreadsheet=URL_DB)
    try:
        df_historial = conn.read(spreadsheet=URL_DB, worksheet="Historial_Entradas")
    except:
        df_historial = pd.DataFrame(columns=["ID", "Fecha", "Codigo", "Nombre", "Cantidad", "OC", "Guia", "Receptor", "Digitador"])

    if 'lista_temporal_ingresos' not in st.session_state:
        st.session_state.lista_temporal_ingresos = []

    tab1, tab2 = st.tabs(["Nuevo Ingreso", "🛠️ Editar / Corregir"])

    with tab1:
        st.subheader("Datos de la Guía / OC")
        c1, c2 = st.columns(2)
        
        # Forzamos mayúsculas en los inputs principales
        nro_oc = c1.text_input("Número de OC*", key="oc_main").upper().strip()
        nro_guia = c2.text_input("Número de Guía*", key="guia_main").upper().strip()
        
        # --- VALIDACIÓN DE GUÍA DUPLICADA EN TIEMPO REAL ---
        if nro_guia and not df_historial.empty:
            if nro_guia in df_historial['Guia'].astype(str).values:
                st.error(f"⚠️ BLOQUEO: La Guía '{nro_guia}' ya existe en el historial. No se permiten duplicados.")
                st.stop() # Detiene la ejecución de este módulo para evitar errores

        st.divider()
        st.subheader("Agregar Artículos a la lista")
        opciones = ["Seleccione..."] + (df_art['Codigo'] + " - " + df_art['Nombre']).tolist()
        seleccion = st.selectbox("Seleccionar Artículo:", opciones, key="sel_art")
        
        ca, cb, cc = st.columns([2, 2, 1])
        cant_temp = ca.number_input("Cantidad", min_value=1, step=1, key="cant_temp")
        fecha_ing = cb.date_input("Fecha Recepción", key="fecha_temp")
        
        if st.button("➕ AGREGAR A LA LISTA"):
            if seleccion != "Seleccione..." and nro_oc and nro_guia:
                cod = seleccion.split(" - ")[0]
                nom = seleccion.split(" - ")[1]
                st.session_state.lista_temporal_ingresos.append({
                    "Codigo": cod, 
                    "Nombre": nom.upper(), 
                    "Cantidad": cant_temp, 
                    "OC": nro_oc.upper(), 
                    "Guia": nro_guia.upper(), 
                    "Fecha": fecha_ing.strftime("%d/%m/%Y")
                })
            else:
                st.warning("⚠️ Completa los datos del documento y selecciona un artículo.")

        if st.session_state.lista_temporal_ingresos:
            st.write("### Artículos listos para procesar:")
            df_temp = pd.DataFrame(st.session_state.lista_temporal_ingresos)
            st.table(df_temp)
            
            col_rec, col_dig = st.columns(2)
            # Responsables también en mayúsculas
            p_recibe = col_rec.text_input("Recibido por (Nombre Completo):", key="p_rec").upper().strip()
            p_digita = col_dig.text_input("Registrado por:", key="p_dig").upper().strip()

            c_b1, c_b2 = st.columns([1, 4])
            if c_b1.button("✅ REGISTRAR TODO"):
                if p_recibe and p_digita:
                    # PROCESO MASIVO
                    for item in st.session_state.lista_temporal_ingresos:
                        idx = df_art.index[df_art['Codigo'] == item['Codigo']][0]
                        df_art.at[idx, 'Stock_Actual'] += item['Cantidad']
                        
                        nuevo_mov = pd.DataFrame([{
                            "ID": str(len(df_historial) + 1), 
                            "Fecha": item['Fecha'],
                            "Codigo": item['Codigo'], 
                            "Nombre": item['Nombre'],
                            "Cantidad": item['Cantidad'], 
                            "OC": item['OC'], 
                            "Guia": item['Guia'], 
                            "Receptor": p_recibe, 
                            "Digitador": p_digita
                        }])
                        df_historial = pd.concat([df_historial, nuevo_mov], ignore_index=True)

                    conn.update(spreadsheet=URL_DB, data=df_art)
                    conn.update(spreadsheet=URL_DB, worksheet="Historial_Entradas", data=df_historial)
                    
                    st.success(f"✅ Se registraron {len(st.session_state.lista_temporal_ingresos)} artículos.")
                    st.session_state.lista_temporal_ingresos = [] 
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Los nombres de los responsables son obligatorios.")

            if c_b2.button("🗑️ Limpiar Lista"):
                st.session_state.lista_temporal_ingresos = []
                st.rerun()
# --- MODULO 4: SALIDAS (VALES) - VERSIÓN OPTIMIZADA Y SEGURA ---
elif opcion == "Salidas (Vales)":
    st.header("📤 Despacho de Materiales (Vales)")
    
    # 1. INTENTO DE LECTURA CON MANEJO DE ERRORES (API SAFETY)
    try:
        # Solo usamos ttl=0 aquí para asegurar datos frescos al entrar al módulo
        df_art = conn.read(spreadsheet=URL_DB, ttl=0)
        df_historial = conn.read(spreadsheet=URL_DB, worksheet="Historial_Salidas", ttl=0)
    except Exception as e:
        st.error("⚠️ Google Sheets está temporalmente saturado. Por favor, espera 5 segundos y presiona F5.")
        st.stop()

    if 'lista_salidas' not in st.session_state:
        st.session_state.lista_salidas = []
    if 'reset_form' not in st.session_state:
        st.session_state.reset_form = 0

    rf = st.session_state.reset_form

    # 2. INFORMACIÓN DEL DESPACHO
    st.subheader("1. Información del Despacho")
    col_f, col_v = st.columns(2)
    fecha_vale = col_f.date_input("Fecha del Vale", value=pd.to_datetime("today"), key=f"f_v_{rf}")
    nro_vale = col_v.text_input("N° de Vale*", key=f"v_nro_{rf}").upper().strip()

    c1, c2, c3 = st.columns(3)
    # VALIDACIÓN DNI: Máximo 8 caracteres y solo números
    dni_input = c1.text_input("DNI (8 números)*", key=f"v_dni_{rf}", max_chars=8).strip()
    nom_trab = c2.text_input("Nombre del Trabajador*", key=f"v_nom_{rf}").upper().strip()
    area_trab = c3.selectbox("Área:", ["OPERACIONES", "MANTENIMIENTO", "SEGURIDAD", "LOGÍSTICA", "MINA"], key=f"v_area_{rf}")

    st.divider()

    # 3. CARGA DE ARTÍCULOS
    st.subheader("2. Artículos a Entregar")
    opciones = ["Seleccione..."] + (df_art['Codigo'] + " - " + df_art['Nombre'] + " (Stock: " + df_art['Stock_Actual'].astype(str) + ")").tolist()
    
    seleccion = st.selectbox("Buscar Artículo:", opciones, key=f"art_sel_{rf}")
    cant_salida = st.number_input("Cantidad", min_value=1, step=1, key=f"cant_val_{rf}")

    if st.button("➕ AGREGAR AL VALE"):
        # RESTRICCIÓN DE DNI Y CAMPOS VACÍOS
        dni_es_valido = dni_input.isdigit() and len(dni_input) == 8
        vales_usados = df_historial['Vale'].astype(str).str.strip().values

        if not nro_vale or not nom_trab:
            st.error("❌ El Número de Vale y Nombre son obligatorios.")
        elif not dni_es_valido:
            st.error("❌ El DNI debe ser de exactamente 8 números.")
        elif nro_vale in vales_usados:
            st.error(f"❌ El Vale {nro_vale} ya existe en el historial. Use un número distinto.")
        elif seleccion == "Seleccione...":
            st.error("❌ Seleccione un artículo válido.")
        else:
            # Si pasa las pruebas, agregar a la lista
            cod = seleccion.split(" - ")[0]
            nom = seleccion.split(" - ")[1].split(" (")[0]
            stock_disp = int(df_art.loc[df_art['Codigo'] == cod, 'Stock_Actual'].values[0])
            
            if cant_salida > stock_disp:
                st.error(f"❌ Stock insuficiente. Solo hay {stock_disp} unidades.")
            else:
                st.session_state.lista_salidas.append({
                    "Codigo": cod, "Nombre": nom, "Cantidad": cant_salida,
                    "Vale": nro_vale, "DNI": dni_input, "Trabajador": nom_trab,
                    "Area": area_trab, "Fecha": fecha_vale.strftime("%d/%m/%Y")
                })
                st.rerun()

    # 4. REGISTRO FINAL EN EXCEL
    if st.session_state.lista_salidas:
        st.write("### Resumen del Vale:")
        st.table(pd.DataFrame(st.session_state.lista_salidas)[["Codigo", "Nombre", "Cantidad"]])
        
        p_digita = st.text_input("Digitador (Firma)*:", key=f"v_dig_{rf}").upper().strip()

        if st.button("🚀 FINALIZAR Y GUARDAR TODO"):
            if not p_digita:
                st.error("❌ Ingrese el nombre del digitador responsable.")
            else:
                try:
                    # Una última lectura rápida para evitar choques entre usuarios
                    df_final = conn.read(spreadsheet=URL_DB, worksheet="Historial_Salidas", ttl=0)
                    
                    if nro_vale in df_final['Vale'].astype(str).values:
                        st.error("❌ ERROR: Alguien más acaba de registrar este número de vale.")
                    else:
                        with st.spinner("Registrando en Google Sheets..."):
                            for item in st.session_state.lista_salidas:
                                # Descontar Stock
                                idx = df_art.index[df_art['Codigo'] == item['Codigo']][0]
                                df_art.at[idx, 'Stock_Actual'] -= item['Cantidad']
                                
                                # Nuevo registro
                                nuevo = pd.DataFrame([{
                                    "ID": str(len(df_final) + 1), "Fecha": item['Fecha'], 
                                    "Codigo": item['Codigo'], "Nombre": item['Nombre'],
                                    "Cantidad": item['Cantidad'], "Vale": item['Vale'],
                                    "DNI": item['DNI'], "Trabajador": item['Trabajador'],
                                    "Area": item['Area'], "Digitador": p_digita
                                }])
                                df_final = pd.concat([df_final, nuevo], ignore_index=True)

                            # Actualización física del Excel
                            conn.update(spreadsheet=URL_DB, data=df_art)
                            conn.update(spreadsheet=URL_DB, worksheet="Historial_Salidas", data=df_final)
                            
                            st.success(f"✅ Vale {nro_vale} guardado con éxito.")
                            st.session_state.lista_salidas = []
                            st.session_state.reset_form += 1
                            st.cache_data.clear()
                            st.rerun()
                except Exception as api_err:
                    st.error("❌ Error al conectar con el servidor de Google. Reintente en unos segundos.")
