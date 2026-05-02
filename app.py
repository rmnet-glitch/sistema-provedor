import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


# ================= CONEXÃO =================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print("ERRO BANCO:", e)
        return None


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

        if mensagem is not None:
            cur.execute("UPDATE usuarios SET whatsapp_msg=%s WHERE id=%s", (mensagem, user_id))

        conn.commit()

    cur.execute("""
        SELECT usuario, whatsapp_msg
        FROM usuarios
        WHERE id=%s
    """, (user_id,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("config.html",
        usuario=user[0],
        mensagem=user[1] or ""
    )


# ================= USUÁRIOS =================
@app.route("/usuarios")
def usuarios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, usuario, ativo FROM usuarios")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


# ================= CLIENTES =================
@app.route("/add", methods=["POST"])
def add():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia, usuario_id)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes 
        SET nome=%s, telefone=%s, valor=%s, vencimento_dia=%s
        WHERE id=%s AND usuario_id=%s
    """, (
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

    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM clientes 
        WHERE id=%s AND usuario_id=%s
    """, (id, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# ================= PAGAMENTO =================
@app.route("/pago/<int:id>")
def pago(id):
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'pago')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='pago'
    """, (id, mes, user_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


@app.route("/desfazer/<int:id>")
def desfazer(id):
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'em_dia')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='em_dia'
    """, (id, mes, user_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


# ================= GASTOS =================
@app.route("/gastos", methods=["GET", "POST"])
def gastos():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]
    mes = request.args.get("mes") or request.form.get("mes") or datetime.now().strftime("%Y-%m")

    if request.method == "POST":
        descricao = request.form.get("descricao")
        material = request.form.get("material")
        valor = request.form.get("valor")

        if valor:
            cur.execute("""
                INSERT INTO gastos (descricao, material, valor, mes_ref, usuario_id)
                VALUES (%s,%s,%s,%s,%s)
            """, (descricao, material, valor, mes, user_id))

            conn.commit()

        return redirect(url_for("gastos", mes=mes))

    cur.execute("""
        SELECT id, descricao, material, valor
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
        ORDER BY id DESC
    """, (user_id, mes))

    lista = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
    """, (user_id, mes))

    total = float(cur.fetchone()[0])

    cur.close()
    conn.close()

    return render_template("gastos.html",
        gastos=lista,
        total=total,
        mes_ref=mes
    )


# ================= DELETE GASTO =================
@app.route("/del_gasto/<int:id>")
def del_gasto(id):
    mes = request.args.get("mes")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM gastos
        WHERE id=%s AND usuario_id=%s
    """, (id, session["user_id"]))

    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for("gastos", mes=mes))


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)