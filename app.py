import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime
import time

# IMPORT SEGURO (não quebra deploy)
try:
    import requests
except:
    requests = None

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


# ================= CONEXÃO =================
def conectar():
    return psycopg2.connect(DATABASE_URL)


# ================= WHATSAPP =================
def enviar_whatsapp(numero, mensagem, instance=None, token=None):
    if not requests or not instance or not token:
        return

    url = f"https://api.z-api.io/instances/{instance}/token/{token}/send-text"

    try:
        payload = {
            "phone": f"55{numero}",
            "message": mensagem
        }
        requests.post(url, json=payload)
        time.sleep(2)
    except:
        pass


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


# ================= HOME =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
        SELECT id, nome, telefone, valor, vencimento_dia
        FROM clientes
        WHERE usuario_id=%s
        ORDER BY id DESC
    """, (user_id,))

    clientes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index.html",
                           clientes=clientes,
                           mes_ref=mes,
                           usuario=session["usuario"],
                           mensagem="")


# ================= USUÁRIOS =================
@app.route("/usuarios")
def usuarios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, usuario, is_admin, ativo FROM usuarios ORDER BY id DESC")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


# ================= CRIAR USUÁRIO =================
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


# ================= EDITAR USUÁRIO =================
@app.route("/editar_usuario/<int:id>", methods=["POST"])
def editar_usuario(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    usuario = request.form.get("usuario")
    senha = request.form.get("senha")
    is_admin = request.form.get("is_admin") == "true"

    if id == session["user_id"] and not is_admin:
        return "Não pode remover seu próprio admin", 400

    if senha:
        cur.execute("""
            UPDATE usuarios
            SET usuario=%s, senha=%s, is_admin=%s
            WHERE id=%s
        """, (usuario, senha, is_admin, id))
    else:
        cur.execute("""
            UPDATE usuarios
            SET usuario=%s, is_admin=%s
            WHERE id=%s
        """, (usuario, is_admin, id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= ATIVAR =================
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


# ================= DESATIVAR =================
@app.route("/desativar_usuario/<int:id>")
def desativar_usuario(id):
    if not session.get("is_admin"):
        return "Acesso negado", 403

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM usuarios WHERE id=%s", (id,))
    user = cur.fetchone()

    if user and user[0]:
        return "Não pode desativar admin", 400

    cur.execute("UPDATE usuarios SET ativo=false WHERE id=%s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= EXCLUIR =================
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
        return "Não pode excluir admin", 400

    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= START =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)