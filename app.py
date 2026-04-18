import os
from flask import Flask, render_template, request, redirect, session
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


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
    SELECT id, nome, telefone, valor, vencimento_dia
    FROM clientes
    WHERE usuario_id=%s
    """,(user_id,))

    clientes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        usuario=session["usuario"]
    )


# ================= USUÁRIOS =================
@app.route("/usuarios")
def usuarios():
    if not session.get("is_admin"):
        return redirect("/")

    conn=conectar()
    cur=conn.cursor()

    cur.execute("SELECT id, usuario, ativo FROM usuarios")
    lista=cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


@app.route("/add_user", methods=["POST"])
def add_user():
    conn=conectar()
    cur=conn.cursor()

    cur.execute("""
    INSERT INTO usuarios (usuario, senha, ativo)
    VALUES (%s,%s,TRUE)
    """,(request.form["usuario"],request.form["senha"]))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/usuarios")


# 🔴 DESATIVAR
@app.route("/desativar_user/<int:id>")
def desativar_user(id):
    conn=conectar()
    cur=conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=FALSE WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/usuarios")


# 🟢 ATIVAR
@app.route("/ativar_user/<int:id>")
def ativar_user(id):
    conn=conectar()
    cur=conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=TRUE WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/usuarios")


# ❌ EXCLUIR
@app.route("/del_user/<int:id>")
def del_user(id):
    conn=conectar()
    cur=conn.cursor()

    cur.execute("DELETE FROM usuarios WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/usuarios")


if __name__=="__main__":
    app.run(debug=True)