from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime
from urllib.parse import quote
import os

app = Flask(__name__)

DB_PATH = "./banco/clientes.db"


# =========================
# CONEXÃO
# =========================
def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# FORMATAR MOEDA
# =========================
def formatar_moeda(valor):
    valor = float(valor)
    if valor.is_integer():
        return f"R$ {int(valor):,}".replace(",", ".")
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def limpar_valor(valor):
    if valor is None:
        return 0.0
    s = str(valor).replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


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
# HOME
# =========================
@app.route("/")
def index():

    search = request.args.get("search", "").lower()

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes")
    clientes = c.fetchall()

    hoje = datetime.now().day
    mes_atual = datetime.now().strftime("%Y-%m")

    lista = []

    for cte in clientes:

        nome = cte["nome"]
        telefone = cte["telefone"]

        if search:
            if search not in nome.lower() and search not in telefone:
                continue

        valor = limpar_valor(cte["valor"])
        vencimento = int(cte["vencimento"] or 0)
        ultimo = cte["ultimo_pagamento"] or ""

        if ultimo == mes_atual:
            status = "pago"
        elif vencimento != 0 and hoje > vencimento:
            status = "atrasado"
        else:
            status = "em_dia"

        lista.append({
            "id": cte["id"],
            "nome": nome,
            "telefone": telefone,
            "valor": formatar_moeda(valor),
            "vencimento": vencimento,
            "status": status
        })

    # =========================
    # ORDEM DE STATUS
    # atrasado -> em_dia -> pago
    # =========================
    ordem = {"atrasado": 0, "em_dia": 1, "pago": 2}
    lista.sort(key=lambda x: ordem.get(x["status"], 9))

    total = sum(limpar_valor(c["valor"]) for c in clientes)

    conn.close()

    return render_template(
        "index.html",
        clientes=lista,
        total=formatar_moeda(total),
        search=search
    )


# =========================
# CADASTRAR
# =========================
@app.route("/cadastrar", methods=["POST"])
def cadastrar():

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

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes WHERE id=?", (id,))
    cli = c.fetchone()

    conn.close()

    msg = f"Olá {cli['nome']}, sua mensalidade está pendente."
    link = f"https://wa.me/{cli['telefone']}?text={quote(msg)}"

    return redirect(link)


# =========================
# START
# =========================
if __name__ == "__main__":
    init_db()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
