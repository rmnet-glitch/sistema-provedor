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


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]
    usuario = session["usuario"]

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status,'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
        WHERE c.usuario_id=%s
    """, (mes, user_id, user_id))

    dados = cur.fetchall()

    clientes = []
    total = 0
    recebido = 0

    for c in dados:
        id, nome, tel, valor, venc, status = c
        valor = float(valor or 0)

        total += valor
        if status == "pago":
            recebido += valor

        clientes.append((id, nome, tel, valor, venc, status))

    cur.close()
    conn.close()

    return render_template("index.html",
                           clientes=clientes,
                           mes_ref=mes,
                           total_geral=total,
                           total_recebido=recebido,
                           usuario=usuario)


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

    # SALVAR
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

    # LISTAR
    cur.execute("""
        SELECT id, descricao, material, valor
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
        ORDER BY id DESC
    """, (user_id, mes))

    lista = cur.fetchall()

    # TOTAL
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
                           mes_ref=mes)


# ================= DELETE GASTO =================
@app.route("/del_gasto/<int:id>")
def del_gasto(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

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