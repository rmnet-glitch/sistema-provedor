from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
from urllib.parse import quote
import os

app = Flask(__name__)
app.secret_key = "chave_super_secreta"

DB_PATH = "./banco/clientes.db"


# =========================
# LOGIN FIXO
# =========================
USUARIO = "rubens"
SENHA = "Rm2412@"


# =========================
# CONEXÃO
# =========================
def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# VALOR
# =========================
def limpar_valor(v):
    if v is None:
        return 0.0
    s = str(v).replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


def formatar(v):
    v = float(v)
    if v.is_integer():
        return f"R$ {int(v):,}".replace(",", ".")
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =========================
# BANCO
# =========================
def init_db():
    os.makedirs("./banco", exist_ok=True)

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT,
        valor REAL,
        vencimento TEXT,
        ultimo_pagamento TEXT
    )
    """)

    conn.commit()
    conn.close()


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        u = request.form["usuario"]
        s = request.form["senha"]

        if u == USUARIO and s == SENHA:
            session["logado"] = True
            return redirect("/")
        else:
            return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =========================
# PROTEÇÃO
# =========================
def auth():
    return session.get("logado")


# =========================
# HOME
# =========================
@app.route("/")
def index():

    if not auth():
        return redirect("/login")

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes")
    clientes = c.fetchall()

    mes = datetime.now().strftime("%Y-%m")
    dia = datetime.now().day

    lista = []
    total_mes = 0
    total_geral = 0

    for cte in clientes:

        valor = limpar_valor(cte["valor"])
        total_geral += valor

        ultimo = cte["ultimo_pagamento"] or ""

        if ultimo == mes:
            status = "pago"
            total_mes += valor
        elif int(cte["vencimento"] or 0) < dia:
            status = "atrasado"
        else:
            status = "em_dia"

        lista.append({
            "id": cte["id"],
            "nome": cte["nome"],
            "telefone": cte["telefone"],
            "valor": formatar(valor),
            "vencimento": cte["vencimento"],
            "status": status
        })

    conn.close()

    return render_template(
        "index.html",
        clientes=lista,
        total=formatar(total_geral),
        recebido=formatar(total_mes)
    )


# =========================
# CADASTRAR
# =========================
@app.route("/cadastrar", methods=["POST"])
def cadastrar():

    if not auth():
        return redirect("/login")

    nome = request.form["nome"]
    telefone = "55" + request.form["telefone"]
    valor = limpar_valor(request.form["valor"])
    vencimento = request.form["vencimento"]

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO clientes (nome, telefone, valor, vencimento, ultimo_pagamento)
    VALUES (?, ?, ?, ?, '')
    """, (nome, telefone, valor, vencimento))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# PAGAR
# =========================
@app.route("/pagar/<int:id>")
def pagar(id):

    if not auth():
        return redirect("/login")

    mes = datetime.now().strftime("%Y-%m")

    conn = conectar()
    c = conn.cursor()

    c.execute("UPDATE clientes SET ultimo_pagamento=? WHERE id=?", (mes, id))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# DESFAZER
# =========================
@app.route("/desfazer/<int:id>")
def desfazer(id):

    if not auth():
        return redirect("/login")

    conn = conectar()
    c = conn.cursor()

    c.execute("UPDATE clientes SET ultimo_pagamento='' WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# EXCLUIR
# =========================
@app.route("/excluir/<int:id>")
def excluir(id):

    if not auth():
        return redirect("/login")

    conn = conectar()
    c = conn.cursor()

    c.execute("DELETE FROM clientes WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# COBRAR
# =========================
@app.route("/cobrar/<int:id>")
def cobrar(id):

    if not auth():
        return redirect("/login")

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes WHERE id=?", (id,))
    cli = c.fetchone()

    conn.close()

    msg = f"Olá {cli['nome']}, sua mensalidade está em aberto."
    link = f"https://wa.me/{cli['telefone']}?text={quote(msg)}"

    return redirect(link)


# =========================
# START
# =========================
if __name__ == "__main__":
    init_db()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
