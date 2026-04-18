import os
import json
from flask import Flask, render_template, request, redirect, session, Response
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")

def conectar():
    return psycopg2.connect(DATABASE_URL)


# ================= LOGIN =================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
        SELECT id, usuario, is_admin, ativo
        FROM usuarios
        WHERE usuario=%s AND senha=%s
        """,(request.form["usuario"],request.form["senha"]))

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

            return redirect("/")

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ================= USUÁRIOS (CORRIGIDO 100%) =================
@app.route("/usuarios")
def usuarios():
    if not session.get("logado"):
        return redirect("/login")

    if not session.get("is_admin"):
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, usuario, ativo FROM usuarios")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


@app.route("/add_user", methods=["POST"])
def add_user():
    if not session.get("is_admin"):
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (usuario, senha, ativo)
        VALUES (%s,%s,TRUE)
    """,(request.form["usuario"],request.form["senha"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# 🔴 EDITAR USUÁRIO (CORRIGIDO)
@app.route("/edit_user/<int:id>", methods=["POST"])
def edit_user(id):
    if not session.get("is_admin"):
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    usuario = request.form["usuario"]
    senha = request.form.get("senha","")

    if senha.strip() == "":
        cur.execute("""
            UPDATE usuarios SET usuario=%s WHERE id=%s
        """,(usuario,id))
    else:
        cur.execute("""
            UPDATE usuarios SET usuario=%s, senha=%s WHERE id=%s
        """,(usuario,senha,id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# 🔴 DESATIVAR USUÁRIO (CORRIGIDO)
@app.route("/desativar_user/<int:id>")
def desativar_user(id):
    if not session.get("logado"):
        return redirect("/login")

    if id == session["user_id"]:
        return redirect("/usuarios")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=FALSE WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# 🟢 ATIVAR USUÁRIO
@app.route("/ativar_user/<int:id>")
def ativar_user(id):
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=TRUE WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ❌ EXCLUIR USUÁRIO (CORRIGIDO)
@app.route("/del_user/<int:id>")
def del_user(id):
    if not session.get("logado"):
        return redirect("/login")

    if id == session["user_id"]:
        return redirect("/usuarios")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM usuarios WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= CLIENTES (NÃO MEXIDO) =================
@app.route("/add", methods=["POST"])
def add():
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia, usuario_id)
        VALUES (%s,%s,%s,%s,%s)
    """,(
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET nome=%s, telefone=%s, valor=%s, vencimento_dia=%s
        WHERE id=%s AND usuario_id=%s
    """,(
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        id,
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM clientes
        WHERE id=%s AND usuario_id=%s
    """,(id,session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


# ================= BACKUP =================
@app.route("/backup")
def backup():
    if not session.get("logado"):
        return redirect("/login")

    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT usuario FROM usuarios WHERE id=%s",(user_id,))
    usuario = cur.fetchone()[0]

    cur.execute("""
        SELECT id, nome, telefone, valor, vencimento_dia
        FROM clientes
        WHERE usuario_id=%s
    """,(user_id,))
    clientes = cur.fetchall()

    cur.execute("""
        SELECT cliente_id, mes_ref, status
        FROM cobrancas
        WHERE usuario_id=%s
    """,(user_id,))
    cobrancas = cur.fetchall()

    cur.close()
    conn.close()

    backup = {
        "usuario": usuario,
        "clientes": clientes,
        "cobrancas": cobrancas
    }

    json_data = json.dumps(backup, ensure_ascii=False, indent=4)

    return Response(
        json_data,
        mimetype="application/json",
        headers={"Content-Disposition":"attachment;filename=backup.json"}
    )


if __name__ == "__main__":
    app.run(debug=True)