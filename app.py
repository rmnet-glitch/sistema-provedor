import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2

app = Flask(__name__)
app.secret_key = "sistema-secreto-123"

# 🔐 URL do banco vem do Render (Environment Variable)
DATABASE_URL = os.getenv("DATABASE_URL")


# =========================
# CONEXÃO COM BANCO
# =========================
def conectar():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL não definida no Render")

    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        # login simples (você pode melhorar depois)
        if usuario == "rubens" and senha == "Rm2412@!@!":
            session["logado"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", erro="Usuário ou senha inválidos")

    return render_template("login.html")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# HOME (LISTA CLIENTES)
# =========================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    try:
        conn = conectar()
        cur = conn.cursor()

        cur.execute("SELECT id, nome, valor, status FROM clientes ORDER BY id DESC")
        clientes = cur.fetchall()

        cur.close()
        conn.close()

        return render_template("index.html", clientes=clientes)

    except Exception as e:
        return f"""
        <h3>Erro ao conectar no banco</h3>
        <pre>{e}</pre>
        """


# =========================
# ADICIONAR CLIENTE
# =========================
@app.route("/add", methods=["POST"])
def add():
    if not session.get("logado"):
        return redirect(url_for("login"))

    nome = request.form["nome"]
    valor = request.form["valor"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO clientes (nome, valor, status) VALUES (%s, %s, %s)",
        (nome, valor, "atrasado")
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# MARCAR COMO PAGO
# =========================
@app.route("/pago/<int:id>")
def pago(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE clientes SET status='pago' WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# CANCELAR PAGAMENTO
# =========================
@app.route("/cancelar/<int:id>")
def cancelar(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE clientes SET status='atrasado' WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# DELETAR CLIENTE
# =========================
@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================
# RODAR LOCAL
# =========================
if __name__ == "__main__":
    app.run(debug=True)
