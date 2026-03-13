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

# --- MODULO 3: ENTRADAS (OC y GUÍA) ---
elif opcion == "Entradas (OC)":
    st.header("📥 Gestión de Ingresos (OC / Guía)")
    
    df_art = conn.read(spreadsheet=URL_DB)
    try:
        df_historial = conn.read(spreadsheet=URL_DB, worksheet="Historial_Entradas")
    except:
        df_historial = pd.DataFrame(columns=["ID", "Fecha", "Codigo", "Nombre", "Cantidad", "OC", "Guia", "Receptor", "Digitador"])

    tab1, tab2 = st.tabs(["Nuevo Ingreso", "🛠️ Editar / Corregir"])

    with tab1:
        with st.form("form_entradas_pro", clear_on_submit=True):
            st.subheader("Documentación Obligatoria")
            c_doc1, c_doc2 = st.columns(2)
            nro_oc = c_doc1.text_input("Número de OC*").upper().strip()
            nro_guia = c_doc2.text_input("Número de Guía*").upper().strip()
            
            opciones_art = ["Seleccione..."] + (df_art['Codigo'] + " - " + df_art['Nombre']).tolist()
            seleccion = st.selectbox("Buscar Artículo:", opciones_art)
            
            c_det1, c_det2 = st.columns(2)
            cant = c_det1.number_input("Cantidad", min_value=1, step=1)
            fecha_ing = c_det2.date_input("Fecha")
            
            c_resp1, c_resp2 = st.columns(2)
            p_recibe = c_resp1.text_input("Receptor").upper()
            p_digita = c_resp2.text_input("Digitador").upper()

            if st.form_submit_button("REGISTRAR"):
                if not nro_oc or not nro_guia or seleccion == "Seleccione...":
                    st.error("❌ Faltan datos obligatorios.")
                elif not df_historial.empty and nro_guia in df_historial['Guia'].astype(str).values:
                    st.error(f"⚠️ La Guía '{nro_guia}' ya fue registrada.")
                else:
                    cod_elegido = seleccion.split(" - ")[0]
                    idx = df_art.index[df_art['Codigo'] == cod_elegido][0]
                    df_art.at[idx, 'Stock_Actual'] += cant
                    
                    nuevo_mov = pd.DataFrame([{
                        "ID": str(len(df_historial) + 1), "Fecha": fecha_ing.strftime("%d/%m/%Y"),
                        "Codigo": cod_elegido, "Nombre": df_art.at[idx, 'Nombre'],
                        "Cantidad": cant, "OC": nro_oc, "Guia": nro_guia,
                        "Receptor": p_recibe, "Digitador": p_digita
                    }])

                    conn.update(spreadsheet=URL_DB, data=df_art)
                    df_hist_final = pd.concat([df_historial, nuevo_mov], ignore_index=True)
                    conn.update(spreadsheet=URL_DB, worksheet="Historial_Entradas", data=df_hist_final)
                    st.success("✅ Ingreso Exitoso.")
                    st.cache_data.clear()
                    st.rerun()

    # --- PESTAÑA 2: EDICIÓN DE ERRORES ---
    with tab2:
        if df_historial.empty:
            st.info("Aún no hay registros en el historial para editar.")
        else:
            st.subheader("Corregir Ingreso Existente")
            # Selector por Guía
            guia_a_editar = st.selectbox("Seleccione la Guía de Remisión a corregir:", df_historial['Guia'].tolist()[::-1])
            
            # Extraer datos
            datos = df_historial[df_historial['Guia'] == guia_a_editar].iloc[0]
            
            with st.container(border=True):
                st.write(f"**Artículo:** {datos['Nombre']} ({datos['Codigo']})")
                
                # --- AQUÍ ESTÁ LA CORRECCIÓN (Copia desde aquí) ---
                try:
                    # Intentamos leer la cantidad, si falla o está vacío, ponemos 0
                    val_actual = int(datos['Cantidad']) if pd.notna(datos['Cantidad']) else 0
                except:
                    val_actual = 0

                new_q = st.number_input("Cantidad Real Correcta", value=val_actual, min_value=0)
                # --- HASTA AQUÍ ---
                
                new_oc = st.text_input("Corregir N° OC", value=str(datos['OC']))
                new_p_rec = st.text_input("Corregir Receptor", value=str(datos['Receptor']))
                
                if st.button("Guardar Cambios y Ajustar Inventario"):
                    # 1. Calcular la diferencia para el Stock
                    diferencia = new_q - int(datos['Cantidad'])
                    
                    # 2. Actualizar Stock Principal
                    idx_m = df_art.index[df_art['Codigo'] == datos['Codigo']][0]
                    df_art.at[idx_m, 'Stock_Actual'] += diferencia
                    
                    # 3. Actualizar Historial
                    idx_h = df_historial.index[df_historial['Guia'] == guia_a_editar][0]
                    df_historial.at[idx_h, 'Cantidad'] = new_q
                    df_historial.at[idx_h, 'OC'] = new_oc.upper()
                    df_historial.at[idx_h, 'Receptor'] = new_p_rec.upper()
                    
                    # 4. Guardar cambios en Sheets
                    conn.update(spreadsheet=URL_DB, data=df_art)
                    conn.update(spreadsheet=URL_DB, worksheet="Historial_Entradas", data=df_historial)
                    
                    st.success("✅ Registro corregido y Stock ajustado.")
                    st.cache_data.clear()
                    st.rerun()

# --- AQUÍ EMPIEZA EL SIGUIENTE MÓDULO (Asegúrate de que esté al mismo nivel que los otros elif) ---
elif opcion == "Salidas (Vales)":
    st.header("📤 Salida de Materiales (Vales)")
    st.info("Módulo en desarrollo para el despacho de materiales.")
# --- MODULO 4: SALIDAS (RESTA) ---
elif opcion == "Salidas (Vales)":
    st.header("📋 Salida por Vale")
    df_art = conn.read(spreadsheet=URL_DB)
    df_sal = conn.read(spreadsheet=URL_DB + "&sheet=Salidas")
    with st.form("sal"):
        vale = st.text_input("Vale").upper()
        tra = st.text_input("Trabajador").upper()
        art = st.selectbox("Artículo", df_art['Nombre'].tolist())
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("Despachar"):
            idx = df_art[df_art['Nombre'] == art].index[0]
            if df_art.at[idx, 'Stock_Actual'] >= cant:
                df_art.at[idx, 'Stock_Actual'] -= cant
                nueva = pd.DataFrame([{"Fecha":"Hoy", "Vale":vale, "Trabajador":tra, "Codigo":df_art.at[idx, 'Codigo'], "Cantidad":cant, "Usuario":"SISTEMA"}])
                conn.update(spreadsheet=URL_DB, worksheet="Articulos", data=df_art)
                conn.update(spreadsheet=URL_DB, worksheet="Salidas", data=pd.concat([df_sal, nueva]))
                st.success("Despachado")
            else:
                st.error("No hay suficiente stock")
