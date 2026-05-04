import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


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


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status,'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
        WHERE c.usuario_id=%s
    """, (mes, user_id, user_id))

    clientes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index.html",
                           clientes=clientes,
                           mes_ref=mes,
                           usuario=session["usuario"],
                           mensagem="")


# ================= CLIENTES =================
@app.route("/add", methods=["POST"])
def add():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia, usuario_id)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        request.form.get("nome"),
        request.form.get("telefone"),
        request.form.get("valor"),
        request.form.get("vencimento_dia"),
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET nome=%s, telefone=%s, valor=%s, vencimento_dia=%s
        WHERE id=%s AND usuario_id=%s
    """, (
        request.form.get("nome"),
        request.form.get("telefone"),
        request.form.get("valor"),
        request.form.get("vencimento_dia"),
        id,
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
def delete(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s AND usuario_id=%s",
                (id, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/pago/<int:id>")
def pago(id):
    conn = conectar()
    cur = conn.cursor()

    mes = datetime.now().strftime("%Y-%m")

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'pago')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='pago'
    """, (id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/desfazer/<int:id>")
def desfazer(id):
    conn = conectar()
    cur = conn.cursor()

    mes = datetime.now().strftime("%Y-%m")

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'em_dia')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='em_dia'
    """, (id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# ================= GASTOS =================
@app.route("/gastos", methods=["GET", "POST"])
def gastos():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    mes = datetime.now().strftime("%Y-%m")

    if request.method == "POST":
        cur.execute("""
            INSERT INTO gastos (descricao, material, valor, mes_ref, usuario_id)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            request.form.get("descricao"),
            request.form.get("material"),
            request.form.get("valor"),
            mes,
            session["user_id"]
        ))
        conn.commit()

    cur.execute("""
        SELECT id, descricao, material, valor
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
    """, (session["user_id"], mes))

    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("gastos.html", gastos=lista)


@app.route("/del_gasto/<int:id>")
def del_gasto(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM gastos WHERE id=%s AND usuario_id=%s",
                (id, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("gastos"))


# ================= USUÁRIOS =================
@app.route("/usuarios")
def usuarios():
    if not session.get("is_admin"):
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, usuario, is_admin, ativo FROM usuarios")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


@app.route("/add_usuario", methods=["POST"])
def add_usuario():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (usuario, senha, is_admin, ativo)
        VALUES (%s,%s,%s,TRUE)
    """, (
        request.form.get("usuario"),
        request.form.get("senha"),
        True if request.form.get("is_admin") else False
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))


@app.route("/toggle_usuario/<int:id>")
def toggle_usuario(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE usuarios
        SET ativo = NOT ativo
        WHERE id=%s
    """, (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))


@app.route("/delete_usuario/<int:id>")
def delete_usuario(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))


# ================= CONFIG =================
@app.route("/config")
def config():
    return render_template("config.html")


# ================= START =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)