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
# LIMPAR VALOR
# =========================
def limpar_valor(valor):
    if valor is None:
        return 0.0

    s = str(valor).strip()
    s = s.replace("R$", "").replace(" ", "")

    if "," in s:
        s = s.replace(".", "")
        s = s.replace(",", ".")

    try:
        return float(s)
    except:
        return 0.0


# =========================
# FORMATAR MOEDA
# =========================
def formatar_moeda(valor):
    valor = float(valor)

    if valor.is_integer():
        return f"R$ {int(valor):,}".replace(",", ".")
    else:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =========================
# BANCO (AUTO CRIA + MIGRAÇÃO)
# =========================
def atualizar_banco():
    os.makedirs("./banco", exist_ok=True)

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT,
        valor REAL,
        vencimento TEXT
    )
    """)

    try:
        c.execute("ALTER TABLE clientes ADD COLUMN ultimo_pagamento TEXT")
    except:
        pass

    conn.commit()
    conn.close()


def corrigir_banco():
    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT id, valor FROM clientes")
    clientes = c.fetchall()

    for cliente in clientes:
        valor = limpar_valor(cliente["valor"])
        c.execute("UPDATE clientes SET valor=? WHERE id=?", (valor, cliente["id"]))

    conn.commit()
    conn.close()


# =========================
# HOME
# =========================
@app.route("/")
def index():

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes")
    clientes = c.fetchall()

    hoje = datetime.now().day
    mes_atual = datetime.now().strftime("%Y-%m")

    lista = []
    total = 0

    for cliente in clientes:

        valor = limpar_valor(cliente["valor"])

        try:
            vencimento = int(cliente["vencimento"])
        except:
            vencimento = 0

        ultimo_pagamento = cliente["ultimo_pagamento"] or ""

        # =========================
        # LÓGICA MENSAL
        # =========================
        if ultimo_pagamento == mes_atual:
            status = "pago"
        elif vencimento != 0 and hoje > vencimento:
            status = "atrasado"
        else:
            status = "em_dia"

        total += valor

        lista.append({
            "id": cliente["id"],
            "nome": cliente["nome"],
            "telefone": cliente["telefone"],
            "valor": formatar_moeda(valor),
            "vencimento": vencimento,
            "status": status
        })

    conn.close()

    return render_template("index.html", clientes=lista, total=formatar_moeda(total))


# =========================
# CADASTRAR
# =========================
@app.route("/cadastrar", methods=["POST"])
def cadastrar():

    nome = request.form.get("nome", "").strip()
    telefone = request.form.get("telefone", "").strip()
    valor = limpar_valor(request.form.get("valor", "0"))
    vencimento = request.form.get("vencimento", "").strip()

    if not telefone.isdigit():
        return redirect("/")

    if not vencimento.isdigit():
        vencimento = "0"

    telefone = "55" + telefone

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO clientes (nome, telefone, valor, vencimento, ultimo_pagamento)
    VALUES (?, ?, ?, ?, ?)
    """, (nome, telefone, valor, vencimento, ""))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# EDITAR
# =========================
@app.route("/editar/<int:id>", methods=["POST"])
def editar(id):

    nome = request.form.get("nome", "").strip()
    telefone = request.form.get("telefone", "").strip()
    valor = limpar_valor(request.form.get("valor", "0"))
    vencimento = request.form.get("vencimento", "").strip()

    if not telefone.isdigit():
        return redirect("/")

    if not vencimento.isdigit():
        vencimento = "0"

    telefone = "55" + telefone

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    UPDATE clientes
    SET nome=?, telefone=?, valor=?, vencimento=?
    WHERE id=?
    """, (nome, telefone, valor, vencimento, id))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# PAGAR (MÊS ATUAL)
# =========================
@app.route("/pagar/<int:id>")
def pagar(id):

    mes_atual = datetime.now().strftime("%Y-%m")

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    UPDATE clientes
    SET ultimo_pagamento=?
    WHERE id=?
    """, (mes_atual, id))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# DESFAZER PAGAMENTO DO MÊS
# =========================
@app.route("/desfazer/<int:id>")
def desfazer(id):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    UPDATE clientes
    SET ultimo_pagamento=''
    WHERE id=?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# COBRAR WHATSAPP
# =========================
@app.route("/cobrar/<int:id>")
def cobrar(id):

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes WHERE id=?", (id,))
    cliente = c.fetchone()

    conn.close()

    mensagem = f"Olá {cliente['nome']}, sua mensalidade de {formatar_moeda(cliente['valor'])} está pendente."
    mensagem = quote(mensagem)

    link = f"https://wa.me/{cliente['telefone']}?text={mensagem}"

    return redirect(link)


# =========================
# START (NUVEM RENDER)
# =========================
if __name__ == "__main__":
    atualizar_banco()
    corrigir_banco()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)