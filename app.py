from flask import Flask, render_template, request, redirect, session
import psycopg2
import os
from datetime import datetime
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = "sistema_provedor_secret"

# =========================
# SUPABASE (POSTGRES)
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")


def conectar():
    return psycopg2.connect(DATABASE_URL)


# =========================
# LOGIN FIXO
# =========================
USUARIO = "rubens"
SENHA = "Rm2412@"


# =========================
# FORMATAÇÃO
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
    return f"R$ {v:,.2f}".replace(".", ",")


def auth():
    return session.get("logado")


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        if request.form["usuario"] == USUARIO and request.form["senha"] == SENHA:
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
# HOME
# =========================
@app.route("/")
def index():

    if not auth():
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT * FROM clientes")
    clientes = cur.fetchall()

    mes = datetime.now().strftime("%Y-%m")
    dia = datetime.now().day

    lista = []
    total = 0
    recebido = 0

    for c in clientes:

        valor = float(c[3])
        total += valor

        ultimo = c[5] or ""

        if ultimo == mes:
            status = "pago"
            recebido += valor
        elif int(c[4] or 0) < dia:
            status = "atrasado"
        else:
            status = "em_dia"

        lista.append({
            "id": c[0],
            "nome": c[1],
            "telefone": c[2],
            "valor": formatar(valor),
            "vencimento": c[4],
            "status": status
        })

    conn.close()

    return render_template(
        "index.html",
        clientes=lista,
        total=formatar(total),
        recebido=formatar(recebido),
        search=""
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
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento, ultimo_pagamento)
        VALUES (%s, %s, %s, %s, %s)
    """, (nome, telefone, valor, vencimento, ""))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# EDITAR
# =========================
@app.route("/editar/<int:id>", methods=["POST"])
def editar(id):

    if not auth():
        return redirect("/login")

    nome = request.form["nome"]
    telefone = request.form["telefone"]
    valor = limpar_valor(request.form["valor"])
    vencimento = request.form["vencimento"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET nome=%s, telefone=%s, valor=%s, vencimento=%s
        WHERE id=%s
    """, (nome, telefone, valor, vencimento, id))

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
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET ultimo_pagamento=%s
        WHERE id=%s
    """, (mes, id))

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
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET ultimo_pagamento=''
        WHERE id=%s
    """, (id,))

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
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s", (id,))

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
    cur = conn.cursor()

    cur.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    c = cur.fetchone()

    conn.close()

    msg = f"Olá {c[1]}, sua mensalidade está em aberto."
    link = f"https://wa.me/{c[2]}?text={quote(msg)}"

    return redirect(link)


# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
