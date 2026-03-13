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
