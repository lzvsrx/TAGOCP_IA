# ===============================
# TAGOCP.IA – Plataforma de Apoio Psicológico
# Versão Linux | Profissional | Arquivo Único
# ===============================

import streamlit as st
import sqlite3
import bcrypt
import jwt
import os
import datetime
import base64
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import fitz  # PyMuPDF
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI

# ===============================
# CONFIGURAÇÕES INICIAIS
# ===============================

load_dotenv()

APP_NAME = "tagocp.ia"
SECRET_KEY = os.getenv("JWT_SECRET", "changeme")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
MASTER_KEY = os.getenv("MASTER_ENCRYPTION_KEY", Fernet.generate_key().decode())

client = OpenAI(api_key=OPENAI_KEY)
fernet_master = Fernet(MASTER_KEY.encode())

# ===============================
# CSS – IDENTIDADE VISUAL
# ===============================

st.markdown("""
<style>
@font-face {
    font-family: 'Gagalin';
    src: url('https://fonts.cdnfonts.com/css/gagalin');
}
html, body, [class*="css"] {
    background-color: black;
    color: #1800ad;
    font-family: 'Gagalin', sans-serif;
}
.stButton>button {
    background-color: #1800ad;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# BANCO DE DADOS
# ===============================

conn = sqlite3.connect("tagocp.db", check_same_thread=False)
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password BLOB,
    health_focus TEXT,
    encryption_key BLOB,
    role TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    content BLOB,
    created_at TEXT
);
""")
conn.commit()

# ===============================
# UTILITÁRIOS DE SEGURANÇA
# ===============================

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def create_user_key():
    return Fernet.generate_key()

def encrypt_user_data(user_key, text):
    return Fernet(user_key).encrypt(text.encode())

def decrypt_user_data(user_key, token):
    return Fernet(user_key).decrypt(token).decode()

def generate_jwt(user_id, role):
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# ===============================
# LGPD
# ===============================

def lgpd_term():
    st.markdown("""
    ### 📜 Termo LGPD
    Esta plataforma **não substitui profissionais de saúde**.
    Os dados são criptografados individualmente.
    Em casos de crise, recomendamos buscar ajuda especializada.
    """)

# ===============================
# DETECÇÃO DE CRISE
# ===============================

CRISIS_WORDS = [
    "quero morrer", "suicídio", "me matar",
    "não aguento", "acabar com tudo"
]

def detect_crisis(text):
    return any(word in text.lower() for word in CRISIS_WORDS)

# ===============================
# RAG CIENTÍFICO (SEM FAISS)
# ===============================

def load_articles():
    texts = []
    if not os.path.exists("articles"):
        return texts

    for file in os.listdir("articles"):
        if file.endswith(".pdf"):
            doc = fitz.open(os.path.join("articles", file))
            content = "".join(page.get_text() for page in doc)
            texts.append({"title": file, "content": content})
    return texts

def search_articles(query):
    return [a for a in load_articles() if query.lower() in a["content"].lower()][:2]

# ===============================
# LLM
# ===============================

def generate_response(user_input):
    articles = search_articles(user_input)

    context = "\n".join(
        f"{a['title']}:\n{a['content'][:1200]}"
        for a in articles
    )

    prompt = f"""
Você é um assistente de apoio psicológico.
Use linguagem empática e baseada em evidências científicas.
Não faça diagnóstico.

Contexto científico:
{context}

Usuário:
{user_input}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ===============================
# INTERFACE
# ===============================

st.title("🧠 tagocp.ia")

menu = st.sidebar.selectbox("Menu", ["Login", "Cadastro", "Chat", "Admin"])

lgpd_term()

# ===============================
# CADASTRO
# ===============================

if menu == "Cadastro":
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")
    focus = st.selectbox("Foco de apoio", ["Ansiedade", "Depressão", "Estresse"])
    if st.button("Cadastrar"):
        user_key = create_user_key()
        cursor.execute(
            "INSERT INTO users VALUES (NULL,?,?,?, ?, 'user')",
            (email, hash_password(password), focus,
             fernet_master.encrypt(user_key))
        )
        conn.commit()
        st.success("Cadastro realizado")

# ===============================
# LOGIN
# ===============================

if menu == "Login":
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        user = cursor.execute(
            "SELECT id,password,role,encryption_key FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if user and verify_password(password, user[1]):
            st.session_state["user"] = {
                "id": user[0],
                "role": user[2],
                "key": fernet_master.decrypt(user[3])
            }
            st.success("Login efetuado")

# ===============================
# CHAT
# ===============================

if menu == "Chat" and "user" in st.session_state:
    msg = st.text_area("Como você está se sentindo?")
    if st.button("Enviar"):
        if detect_crisis(msg):
            st.error("""
🚨 **CRISE DETECTADA**
📞 CVV – 188 (24h)
🌐 https://www.cvv.org.br
            """)
        response = generate_response(msg)

        encrypted = encrypt_user_data(st.session_state["user"]["key"], msg)
        cursor.execute(
            "INSERT INTO messages VALUES (NULL,?,?,?)",
            (st.session_state["user"]["id"], encrypted,
             datetime.datetime.now().isoformat())
        )
        conn.commit()

        st.markdown("### 💬 Resposta")
        st.write(response)

# ===============================
# ADMIN DASHBOARD
# ===============================

if menu == "Admin" and "user" in st.session_state and st.session_state["user"]["role"] == "admin":
    df = pd.read_sql("SELECT created_at FROM messages", conn)
    df["created_at"] = pd.to_datetime(df["created_at"])
    chart = df.groupby(df["created_at"].dt.date).size()

    st.subheader("📊 Mensagens por dia")
    fig, ax = plt.subplots()
    chart.plot(ax=ax)
    st.pyplot(fig)

st.markdown("© tagocp.ia – apoio, ciência e empatia")
