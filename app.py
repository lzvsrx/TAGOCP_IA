# ============================
# TAGOCP.IA - SISTEMA COMPLETO
# ============================

import streamlit as st
import bcrypt, uuid, os, base64, re
import psycopg2, pandas as pd
from dotenv import load_dotenv
from hashlib import sha256
from cryptography.fernet import Fernet
from openai import OpenAI
import plotly.express as px
from sentence_transformers import SentenceTransformer
import faiss, pickle
from datetime import datetime

# ============================
# CONFIGURAÇÕES
# ============================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MASTER_KEY = os.getenv("CRYPTO_MASTER_KEY")

# ============================
# ESTILO
# ============================
st.set_page_config("TAGOCP.IA", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gagalin&display=swap');
html, body {
    background-color: black;
    color: #1800ad;
    font-family: 'Gagalin', cursive;
}
</style>
""", unsafe_allow_html=True)

# ============================
# BANCO DE DADOS
# ============================
conn = psycopg2.connect(
    host=os.getenv("DATABASE_HOST"),
    dbname=os.getenv("DATABASE_NAME"),
    user=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PASSWORD"),
    port=os.getenv("DATABASE_PORT")
)
cur = conn.cursor()

# ============================
# CRIPTOGRAFIA
# ============================
def user_key(uid):
    raw = f"{uid}{MASTER_KEY}".encode()
    return Fernet(base64.urlsafe_b64encode(sha256(raw).digest()))

def encrypt(msg, uid):
    return user_key(uid).encrypt(msg.encode()).decode()

def decrypt(msg, uid):
    return user_key(uid).decrypt(msg.encode()).decode()

def hash_pass(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def check_pass(p, h): return bcrypt.checkpw(p.encode(), h.encode())

# ============================
# DETECÇÃO DE CRISE
# ============================
CRISIS_WORDS = [
    "suicídio", "me matar", "morrer", "acabar com tudo",
    "não aguento mais", "desistir da vida"
]

def detect_crisis(text):
    for w in CRISIS_WORDS:
        if re.search(w, text.lower()):
            return True

    analysis = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL"),
        messages=[{
            "role": "user",
            "content": f"Isso indica risco psicológico grave? Responda apenas SIM ou NÃO:\n{text}"
        }],
        temperature=0
    )

    return "SIM" in analysis.choices[0].message.content.upper()

# ============================
# RAG FAISS
# ============================
try:
    import faiss
    FAISS_OK = True
except Exception as e:
    FAISS_OK = False
    print("FAISS desativado:", e)
def rag_context(q):
    if not FAISS_OK:
        return "Base científica temporariamente indisponível."
    qv = embed.encode([q])
    _, idx = index.search(qv, 5)
    return "\n".join([docs[i] for i in idx[0]])


# ============================
# CHATBOT
# ============================
def chatbot_response(msg, uid):
    crisis = detect_crisis(msg)
    context = rag_context(msg)

    if crisis:
        return """
⚠️ **SINAIS DE CRISE IDENTIFICADOS**

Você não está sozinho.
📞 **CVV – Centro de Valorização da Vida**
☎️ **188 (Brasil) – 24h**
🌐 https://www.cvv.org.br/
"""

    prompt = f"""
Você é um assistente de apoio psicológico.
Use apenas base científica validada.
Contexto:
{context}

Pergunta:
{msg}
"""

    r = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return r.choices[0].message.content

# ============================
# DASHBOARD ADMIN
# ============================
def admin_panel():
    st.header("📊 Painel Administrativo")

    users = pd.read_sql("SELECT health_focus, COUNT(*) FROM users GROUP BY health_focus", conn)
    st.plotly_chart(px.pie(users, names="health_focus", values="count"))

    msgs = pd.read_sql("""
        SELECT DATE(created_at) as d, COUNT(*) FROM messages GROUP BY d
    """, conn)
    st.plotly_chart(px.line(msgs, x="d", y="count"))

# ============================
# INTERFACE
# ============================
st.image("assets/logo.png", width=160)
st.title("TAGOCP.IA – Apoio Emocional Inteligente")

if "user" not in st.session_state:
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        cur.execute("SELECT id, password_hash, role FROM users WHERE email=%s", (email,))
        u = cur.fetchone()
        if u and check_pass(password, u[1]):
            st.session_state.user = u[0]
            st.session_state.role = u[2]
            st.rerun()
else:
    if st.session_state.role == "admin":
        admin_panel()
    else:
        msg = st.text_area("Digite como você está se sentindo")
        if st.button("Enviar"):
            resp = chatbot_response(msg, st.session_state.user)
            cur.execute(
                "INSERT INTO messages (user_id, encrypted_message, is_user) VALUES (%s,%s,%s)",
                (st.session_state.user, encrypt(msg, st.session_state.user), True)
            )
            conn.commit()
            st.markdown(resp)
