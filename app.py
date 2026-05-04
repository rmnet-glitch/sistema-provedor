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
            session["is_admin"] = True if user[2] else False  # 🔥 FIX

            return redirect(url_for("index"))

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= USUÁRIOS (🔥 CORREÇÃO AQUI) =================
@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if not session.get("is_admin"):
        return redirect(url_for("index"))

    return render_template("usuarios.html")


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

    return render_template("config.html",
                           usuario=usuario,
                           mensagem=mensagem)


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    busca = request.args.get("busca", "").lower()
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

    cur.execute("SELECT whatsapp_msg FROM usuarios WHERE id=%s", (user_id,))
    res = cur.fetchone()
    mensagem = res[0] if res and res[0] else ""

    clientes = []
    total = recebido = atrasado = emdia = 0
    alertas = []

    hoje = datetime.now()
    hoje_mes = hoje.strftime("%Y-%m")
    hoje_dia = hoje.day

    for c in dados:
        id, nome, tel, valor, venc, status = c

        valor = float(valor or 0)
        venc = int(venc or 1)

        if busca and busca not in (nome or "").lower():
            continue

        if status != "pago":
            if mes < hoje_mes:
                status = "atrasado"
            elif mes == hoje_mes:
                if hoje_dia > venc:
                    status = "atrasado"
                elif hoje_dia == venc:
                    alertas.append(f"⚠️ {nome} vence hoje")
                    status = "em_dia"
                else:
                    status = "em_dia"

        if status == "atrasado":
            alertas.append(f"🔴 {nome} atrasado")

        total += valor

        if status == "pago":
            recebido += valor
        elif status == "atrasado":
            atrasado += valor
        else:
            emdia += valor

        clientes.append((id, nome, tel, valor, venc, status))

    cur.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
    """, (user_id, mes))

    total_gastos = float(cur.fetchone()[0] or 0)
    lucro = recebido - total_gastos

    ordem = {"atrasado": 0, "em_dia": 1, "pago": 2}

    if filtro == "nome":
        clientes.sort(key=lambda x: (x[1] or "").lower())
    elif filtro == "valor":
        clientes.sort(key=lambda x: x[3], reverse=True)
    else:
        clientes.sort(key=lambda x: ordem.get(x[5], 1))

    cur.close()
    conn.close()

    return render_template("index.html",
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
                           usuario=session["usuario"],
                           mensagem=mensagem)


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)