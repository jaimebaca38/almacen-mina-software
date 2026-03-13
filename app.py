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

# --- MODULO 1: REGISTRO (EVITA DUPLICADOS) ---
if opcion == "Registrar Nuevo Artículo":
    st.header("📝 Catálogo de Artículos")
    df_art = conn.read(spreadsheet=URL_DB)
    with st.form("reg"):
        c1, c2 = st.columns(2)
        cod = c1.text_input("Código").strip().upper()
        nom = c1.text_input("Nombre").strip().upper()
        fam = c2.selectbox("Familia", ["EPP", "HERRAMIENTAS", "EQUIPOS"])
        minimo = c2.number_input("Mínimo", 0)
        if st.form_submit_button("Guardar"):
            if nom in df_art['Nombre'].values:
                st.error("Ese nombre ya existe")
            else:
                nueva = pd.DataFrame([{"Codigo":cod, "Nombre":nom, "Familia":fam, "Stock_Actual":0, "Stock_Minimo":minimo}])
                conn.update(spreadsheet=URL_DB, worksheet="Articulos", data=pd.concat([df_art, nueva]))
                st.success("Registrado")

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
