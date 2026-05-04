import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


# ================= CONEXÃO =================
def conectar():
    return psycopg2.connect(DATABASE_URL)


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, usuario, is_admin, ativo
            FROM usuarios
            WHERE usuario=%s AND senha=%s
        """, (request.form["usuario"], request.form["senha"]))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            if not user[3]:
                return render_template("login.html", erro="Usuário desativado!")

            session["logado"] = True
            session["user_id"] = user[0]
            session["usuario"] = user[1]
            session["is_admin"] = user[2]

            return redirect(url_for("index"))

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= USUÁRIOS =================
@app.route("/usuarios")
def usuarios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, usuario, is_admin, ativo
        FROM usuarios
        ORDER BY id DESC
    """)
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


# ================= USUÁRIOS - CRUD =================

@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (usuario, senha, is_admin, ativo)
        VALUES (%s,%s,%s,true)
    """, (
        request.form.get("usuario"),
        request.form.get("senha"),
        request.form.get("is_admin") == "true"
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/editar_usuario/<int:id>", methods=["POST"])
def editar_usuario(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE usuarios
        SET usuario=%s,
            is_admin=%s
        WHERE id=%s
    """, (
        request.form.get("usuario"),
        request.form.get("is_admin") == "true",
        id
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/reset_senha/<int:id>")
def reset_senha(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE usuarios
        SET senha=%s
        WHERE id=%s
    """, ("123456", id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= USUÁRIOS - AÇÕES =================

@app.route("/ativar_usuario/<int:id>")
def ativar_usuario(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=true WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/desativar_usuario/<int:id>")
def desativar_usuario(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM usuarios WHERE id=%s", (id,))
    user = cur.fetchone()

    if user and user[0]:
        cur.close()
        conn.close()
        return "Não pode desativar o admin principal", 400

    cur.execute("UPDATE usuarios SET ativo=false WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/delete_usuario/<int:id>")
def delete_usuario(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    if id == session["user_id"]:
        return "Não pode excluir seu próprio usuário", 400

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM usuarios WHERE id=%s", (id,))
    user = cur.fetchone()

    if user and user[0]:
        cur.close()
        conn.close()
        return "Não pode excluir o admin principal", 400

    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= CONFIG =================
@app.route("/config", methods=["GET", "POST"])
def config():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]

    if request.method == "POST":
        senha = request.form.get("senha")
        mensagem = request.form.get("mensagem")

        if senha:
            cur.execute("UPDATE usuarios SET senha=%s WHERE id=%s", (senha, user_id))

        try:
            cur.execute("UPDATE usuarios SET whatsapp_msg=%s WHERE id=%s", (mensagem, user_id))
        except:
            pass

        conn.commit()

    cur.execute("SELECT usuario, whatsapp_msg FROM usuarios WHERE id=%s", (user_id,))
    user = cur.fetchone()

    usuario = user[0]
    mensagem = user[1] if user and user[1] else ""

    cur.close()
    conn.close()

    return render_template("config.html", usuario=usuario, mensagem=mensagem)


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)