import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sistema-secreto-123"

DATABASE_URL = os.getenv("DATABASE_URL")


def conectar():
    return psycopg2.connect(DATABASE_URL)


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["usuario"] == "rubens" and request.form["senha"] == "Rm2412@":
            session["logado"] = True
            return redirect(url_for("index"))
        return render_template("login.html", erro="Login inválido")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# GARANTE COBRANÇA DO MÊS
# =========================
def gerar_cobrancas_mes(cur, mes_ref):
    cur.execute("SELECT id, valor, vencimento_dia FROM clientes")
    clientes = cur.fetchall()

    for c in clientes:
        cliente_id = c[0]

        cur.execute("""
            SELECT id FROM cobrancas
            WHERE cliente_id=%s AND mes_ref=%s
        """, (cliente_id, mes_ref))

        existe = cur.fetchone()

        if not existe:
            cur.execute("""
                INSERT INTO cobrancas (cliente_id, mes_ref, status)
                VALUES (%s, %s, 'em_dia')
            """, (cliente_id, mes_ref))


# =========================
# INDEX
# =========================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    hoje = datetime.now()
    mes_ref = hoje.strftime("%Y-%m")

    gerar_cobrancas_mes(cur, mes_ref)

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status, 'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id = cb.cliente_id AND cb.mes_ref=%s
    """, (mes_ref,))

    clientes_raw = cur.fetchall()

    clientes = []
    total = 0
    recebidos = 0

    for c in clientes_raw:
        id, nome, tel, valor, venc, status = c

        total += float(valor)

        if status == "pago":
            recebidos += float(valor)

        if status != "pago":
            if hoje.day > int(venc):
                status = "atrasado"
            else:
                status = "em_dia"

        clientes.append((id, nome, tel, valor, venc, status))

    conn.commit()
    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        total_geral=total,
        total_recebido=recebidos
    )


# =========================
# PAGAMENTO
# =========================
@app.route("/pago/<int:id>")
def pago(id):
    conn = conectar()
    cur = conn.cursor()

    mes_ref = datetime.now().strftime("%Y-%m")

    cur.execute("""
        UPDATE cobrancas
        SET status='pago', pago_em=NOW()
        WHERE cliente_id=%s AND mes_ref=%s
    """, (id, mes_ref))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# ADD CLIENTE
# =========================
@app.route("/add", methods=["POST"])
def add():
    nome = request.form["nome"]
    telefone = request.form["telefone"]
    valor = request.form["valor"]
    vencimento = request.form["vencimento_dia"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia)
        VALUES (%s,%s,%s,%s)
    """, (nome, telefone, valor, vencimento))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# EDITAR CLIENTE
# =========================
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    nome = request.form["nome"]
    telefone = request.form["telefone"]
    valor = request.form["valor"]
    vencimento = request.form["vencimento_dia"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET nome=%s, telefone=%s, valor=%s, vencimento_dia=%s
        WHERE id=%s
    """, (nome, telefone, valor, vencimento, id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# DELETE
# =========================
@app.route("/delete/<int:id>")
def delete(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
