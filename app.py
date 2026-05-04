import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime
from whatsapp_service import enviar_whatsapp

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


# ================= BANCO =================
def conectar():
    return psycopg2.connect(DATABASE_URL)


def get_conn():
    return conectar()


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_conn()
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
            session["is_admin"] = bool(user[2])

            return redirect(url_for("index"))

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= PROTEÇÃO BASE =================
def check_login():
    return session.get("logado") and session.get("user_id")


# ================= CONFIG (BLINDADO) =================
@app.route("/config", methods=["GET", "POST"])
def config():
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        user_id = session.get("user_id")

        if request.method == "POST":
            senha = request.form.get("senha")
            mensagem = request.form.get("mensagem")
            usar_whatsapp = bool(request.form.get("usar_whatsapp"))
            instance = request.form.get("zapi_instance")
            token = request.form.get("zapi_token")

            # plano seguro
            cur.execute("SELECT plano_whatsapp FROM usuarios WHERE id=%s", (user_id,))
            res = cur.fetchone()
            plano = res[0] if res else False

            if not plano:
                usar_whatsapp = False
                instance = None
                token = None

            if senha:
                cur.execute("UPDATE usuarios SET senha=%s WHERE id=%s", (senha, user_id))

            cur.execute("""
                UPDATE usuarios 
                SET whatsapp_msg=%s,
                    usar_whatsapp=%s,
                    zapi_instance=%s,
                    zapi_token=%s
                WHERE id=%s
            """, (mensagem, usar_whatsapp, instance, token, user_id))

            conn.commit()

        cur.execute("""
            SELECT usuario, whatsapp_msg, usar_whatsapp,
                   zapi_instance, zapi_token, plano_whatsapp
            FROM usuarios
            WHERE id=%s
        """, (user_id,))

        user = cur.fetchone()

        if not user:
            return redirect(url_for("logout"))

        return render_template(
            "config.html",
            usuario=user[0],
            mensagem=user[1] or "",
            usar_whatsapp=user[2],
            zapi_instance=user[3] or "",
            zapi_token=user[4] or "",
            plano_whatsapp=user[5]
        )

    except Exception as e:
        print("ERRO CONFIG:", str(e))
        return f"Erro real: {str(e)}", 500

    finally:
        cur.close()
        conn.close()


# ================= INDEX =================
@app.route("/")
def index():
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        user_id = session["user_id"]
        mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
        busca = request.args.get("busca", "")
        filtro = request.args.get("filtro", "")

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
        total = recebido = atrasado = emdia = 0
        alertas = []

        for c in dados:
            cid, nome, tel, valor, venc, status = c

            valor = float(valor or 0)

            total += valor

            if status == "pago":
                recebido += valor
            elif status == "atrasado":
                atrasado += valor
            else:
                emdia += valor

            clientes.append((cid, nome, tel, valor, venc, status))

        cur.execute("""
            SELECT COALESCE(SUM(valor),0)
            FROM gastos
            WHERE usuario_id=%s AND mes_ref=%s
        """, (user_id, mes))

        total_gastos = float(cur.fetchone()[0] or 0)
        lucro = recebido - total_gastos

        cur.execute("SELECT whatsapp_msg FROM usuarios WHERE id=%s", (user_id,))
        res = cur.fetchone()
        mensagem = res[0] if res else ""

        return render_template(
            "index.html",
            clientes=clientes,
            mes_ref=mes,
            busca=busca,
            filtro=filtro,
            total_geral=total,
            total_recebido=recebido,
            total_atrasado=atrasado,
            total_em_dia=emdia,
            total_gastos=total_gastos,
            lucro=lucro,
            alertas=alertas,
            usuario=session.get("usuario"),
            mensagem=mensagem,
            session=session
        )

    finally:
        cur.close()
        conn.close()

# ================= CLIENTES =================
@app.route("/add", methods=["POST"])
def add():
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
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

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("index"))


# ================= PAGO =================
@app.route("/pago/<int:id>")
def pago(id):
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        mes = datetime.now().strftime("%Y-%m")

        cur.execute("""
            INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
            VALUES (%s,%s,%s,'pago')
            ON CONFLICT (cliente_id, mes_ref, usuario_id)
            DO UPDATE SET status='pago'
        """, (id, mes, session["user_id"]))

        conn.commit()

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("index"))


# ================= COBRAR =================
@app.route("/cobrar/<int:id>")
def cobrar(id):
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT c.nome, c.telefone,
                   u.whatsapp_msg, u.zapi_instance, u.zapi_token,
                   u.usar_whatsapp, u.plano_whatsapp
            FROM clientes c
            JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.id=%s AND c.usuario_id=%s
        """, (id, session["user_id"]))

        res = cur.fetchone()

        if res:
            nome, tel, msg, instance, token, usar, plano = res

            if usar and plano:
                try:
                    enviar_whatsapp(tel, (msg or "").replace("{nome}", nome), instance, token)
                except:
                    pass

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("index"))


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)