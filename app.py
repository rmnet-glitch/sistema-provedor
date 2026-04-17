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


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# RESET MENSAL
# =========================
def reset_mensal(cur):
    hoje = datetime.now()
    if hoje.day == 1:
        cur.execute("""
            UPDATE clientes
            SET status='atrasado'
            WHERE status='pago'
        """)


# =========================
# INDEX
# =========================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    hoje = datetime.now().day
    reset_mensal(cur)

    cur.execute("""
        SELECT id, nome, telefone, valor, vencimento_dia, status
        FROM clientes
    """)

    clientes_raw = cur.fetchall()

    clientes = []
    total_geral = 0
    total_recebido = 0

    for c in clientes_raw:
        id, nome, telefone, valor, vencimento, status = c

        total_geral += float(valor)

        if status == "pago":
            final_status = "pago"
            total_recebido += float(valor)
        else:
            if hoje > int(vencimento):
                final_status = "atrasado"
            else:
                final_status = "em_dia"

        clientes.append((id, nome, telefone, valor, vencimento, final_status))

    conn.commit()
    cur.close()
    conn.close()

    return render_template(
        "index.html",
        clientes=clientes,
        total_geral=total_geral,
        total_recebido=total_recebido
    )


# =========================
# ADD
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
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia, status)
        VALUES (%s,%s,%s,%s,'em_dia')
    """, (nome, telefone, valor, vencimento))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# EDIT
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
# STATUS
# =========================
@app.route("/pago/<int:id>")
def pago(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE clientes SET status='pago' WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/atrasado/<int:id>")
def atrasado(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE clientes SET status='atrasado' WHERE id=%s", (id,))

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
