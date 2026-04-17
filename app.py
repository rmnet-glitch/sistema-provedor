import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2

app = Flask(__name__)
app.secret_key = "sistema-secreto-123"

DATABASE_URL = os.getenv("DATABASE_URL")


def conectar():
    return psycopg2.connect(DATABASE_URL)


# ======================
# LOGIN
# ======================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["usuario"] == "rubens" and request.form["senha"] == "Rm2412@!@!":
            session["logado"] = True
            return redirect(url_for("index"))
        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ======================
# HOME
# ======================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nome, telefone, valor, vencimento, status
        FROM clientes
        ORDER BY CASE WHEN status='atrasado' THEN 0 ELSE 1 END, vencimento ASC
    """)

    clientes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index.html", clientes=clientes)


# ======================
# CADASTRO
# ======================
@app.route("/add", methods=["POST"])
def add():
    nome = request.form["nome"]
    telefone = request.form["telefone"]
    valor = request.form["valor"]
    vencimento = request.form["vencimento"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento, status)
        VALUES (%s, %s, %s, %s, 'atrasado')
    """, (nome, telefone, valor, vencimento))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# ======================
# STATUS
# ======================
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


# ======================
# DELETE
# ======================
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
