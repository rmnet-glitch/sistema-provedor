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
# GARANTE COBRANÇA MENSAL
# =========================
def gerar_cobrancas(cur, mes_ref):
    cur.execute("SELECT id FROM clientes")
    clientes = cur.fetchall()

    for c in clientes:
        cur.execute("""
            SELECT id FROM cobrancas
            WHERE cliente_id=%s AND mes_ref=%s
        """, (c[0], mes_ref))

        if not cur.fetchone():
            cur.execute("""
                INSERT INTO cobrancas (cliente_id, mes_ref, status)
                VALUES (%s, %s, 'em_dia')
            """, (c[0], mes_ref))


# =========================
# INDEX COM HISTÓRICO
# =========================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    # mês selecionado via query (?mes=2026-04)
    mes_ref = request.args.get("mes")

    if not mes_ref:
        mes_ref = datetime.now().strftime("%Y-%m")

    gerar_cobrancas(cur, mes_ref)

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status, 'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id = cb.cliente_id AND cb.mes_ref=%s
    """, (mes_ref,))

    raw = cur.fetchall()

    clientes = []
    total = 0
    recebido = 0

    hoje = datetime.now()

    for c in raw:
        id, nome, tel, valor, venc, status = c

        total += float(valor)

        if status == "pago":
            recebido += float(valor)

        if status != "pago":
            if hoje.day > int(venc) and mes_ref == hoje.strftime("%Y-%m"):
                status = "atrasado"
            elif mes_ref != hoje.strftime("%Y-%m") and status != "pago":
                status = "atrasado"
            else:
                status = "em_dia"

        clientes.append((id, nome, tel, valor, venc, status))

    ordem = {
        "atrasado": 0,
        "em_dia": 1,
        "pago": 2
    }

    clientes.sort(key=lambda x: ordem.get(x[5], 1))

    conn.commit()
    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        mes_ref=mes_ref,
        total_geral=total,
        total_recebido=recebido
    )


# =========================
# PAGAR
# =========================
@app.route("/pago/<int:id>")
def pago(id):
    conn = conectar()
    cur = conn.cursor()

    mes_ref = request.args.get("mes", datetime.now().strftime("%Y-%m"))

    cur.execute("""
        UPDATE cobrancas
        SET status='pago', pago_em=NOW()
        WHERE cliente_id=%s AND mes_ref=%s
    """, (id, mes_ref))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes_ref))


# =========================
# DESFAZER PAGAMENTO
# =========================
@app.route("/desfazer/<int:id>")
def desfazer(id):
    conn = conectar()
    cur = conn.cursor()

    mes_ref = request.args.get("mes", datetime.now().strftime("%Y-%m"))

    cur.execute("""
        UPDATE cobrancas
        SET status='em_dia', pago_em=NULL
        WHERE cliente_id=%s AND mes_ref=%s
    """, (id, mes_ref))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes_ref))


# =========================
# ADD CLIENTE
# =========================
@app.route("/add", methods=["POST"])
def add():
    nome = request.form["nome"]
    telefone = request.form["telefone"]
    valor = request.form["valor"]
    venc = request.form["vencimento_dia"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia)
        VALUES (%s,%s,%s,%s)
    """, (nome, telefone, valor, venc))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# EDITAR
# =========================
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    nome = request.form["nome"]
    telefone = request.form["telefone"]
    valor = request.form["valor"]
    venc = request.form["vencimento_dia"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET nome=%s, telefone=%s, valor=%s, vencimento_dia=%s
        WHERE id=%s
    """, (nome, telefone, valor, venc, id))

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
