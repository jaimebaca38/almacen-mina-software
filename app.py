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

# --- MODULO 1: REGISTRO PROFESIONAL ---
if opcion == "Registrar Nuevo Artículo":
    st.header("📝 Catálogo de Artículos")
    
    # Leemos la base de datos actual
    df_art = conn.read(spreadsheet=URL_DB)
    
    # 1. Selección de Familia primero para generar el prefijo
    fam = st.selectbox("Seleccione Familia para el nuevo artículo:", 
                      ["EPP", "HERRAMIENTAS", "EQUIPOS", "CONSUMIBLES"])
    
    # Definimos el prefijo según la familia
    prefijos = {
        "EPP": "EPP",
        "HERRAMIENTAS": "HER",
        "EQUIPOS": "EQP",
        "CONSUMIBLES": "CON"
    }
    prefijo = prefijos[fam]

    # 2. Lógica de Autogeneración basada en la familia seleccionada
    ultimo_num = 0
    if not df_art.empty and 'Codigo' in df_art.columns:
        # Filtramos solo los códigos que empiecen con el prefijo de la familia actual
        codigos_familia = df_art[df_art['Codigo'].str.startswith(prefijo, na=False)]
        if not codigos_familia.empty:
            # Extraemos el número final del código
            numeros = codigos_familia['Codigo'].str.extract('(\d+)').astype(float).dropna()
            if not numeros.empty:
                ultimo_num = int(numeros.max())
    
    nuevo_cod_sugerido = f"{prefijo}{ultimo_num + 1:03d}"

    # 3. Formulario de Registro
    # Usamos 'key' en los inputs para poder limpiarlos si fuera necesario
    with st.form("reg_form", clear_on_submit=True):
        st.info(f"Sugerencia de código para {fam}: **{nuevo_cod_sugerido}**")
        
        c1, c2 = st.columns(2)
        cod = c1.text_input("Confirmar Código", value=nuevo_cod_sugerido).strip().upper()
        nom = c1.text_input("Nombre del Artículo (Ej: Casco tipo minero)").strip().upper()
        minimo = c2.number_input("Stock Mínimo de Alerta", min_value=0, value=5)
        
        enviar = st.form_submit_button("Guardar en Inventario")
        
        if enviar:
            if nom == "":
                st.warning("⚠️ Debes ingresar un nombre para el artículo.")
            
            # VALIDACIÓN ANTI-DUPLICADOS (Para no chancar información)
            elif cod in df_art['Codigo'].astype(str).values:
                st.error(f"❌ El código {cod} ya existe en el sistema. No se puede duplicar.")
            
            elif nom in df_art['Nombre'].astype(str).values:
                st.error(f"❌ Ya existe un artículo con el nombre '{nom}'.")
            
            else:
                # Si todo está bien, creamos la nueva fila
                nueva_fila = pd.DataFrame([{
                    "Codigo": cod, 
                    "Nombre": nom, 
                    "Familia": fam, 
                    "Stock_Actual": 0, 
                    "Stock_Minimo": minimo
                }])
                
                # Unimos y subimos a Google Sheets
                df_updated = pd.concat([df_art, nueva_fila], ignore_index=True)
                conn.update(spreadsheet=URL_DB, data=df_updated)
                
                st.success(f"✅ Registrado: {nom} con código {cod}")
                st.balloons()
                # Al terminar, Streamlit limpiará el formulario por el parámetro clear_on_submit=True
# --- MODULO 2: PANEL DE STOCK ---
elif opcion == "Panel de Stock":
    st.header("📊 Inventario Real")
    df = conn.read(spreadsheet=URL_DB)
    st.dataframe(df, use_container_width=True)

# --- MODULO 3: ENTRADAS (SUMA) ---
elif opcion == "Entradas (OC)":
    st.header("🚚 Ingreso por OC")
    df_art = conn.read(spreadsheet=URL_DB)
    df_ent = conn.read(spreadsheet=URL_DB + "&sheet=Entradas")
    with st.form("ent"):
        oc = st.text_input("OC").upper()
        art = st.selectbox("Artículo", df_art['Nombre'].tolist())
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("Ingresar"):
            idx = df_art[df_art['Nombre'] == art].index[0]
            df_art.at[idx, 'Stock_Actual'] += cant
            nueva = pd.DataFrame([{"Fecha": "Hoy", "OC": oc, "Codigo": df_art.at[idx, 'Codigo'], "Cantidad": cant}])
            conn.update(spreadsheet=URL_DB, worksheet="Articulos", data=df_art)
            conn.update(spreadsheet=URL_DB, worksheet="Entradas", data=pd.concat([df_ent, nueva]))
            st.success("Stock aumentado")

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
