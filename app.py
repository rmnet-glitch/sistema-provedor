import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime
from whatsapp_service import enviar_whatsapp

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
            session["is_admin"] = True if user[2] else False

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
        return redirect(url_for("index"))

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


# ================= ATIVAR USUÁRIO =================

@app.route("/ativar_usuario/<int:id>")
def ativar_usuario(id):
    if not session.get("logado") or not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=TRUE WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))

# ================= DESATIVAR USUÁRIO =================
@app.route("/desativar_usuario/<int:id>")
def desativar_usuario(id):
    if not session.get("logado") or not session.get("is_admin"):
        return redirect(url_for("index"))

    # 🚫 BLOQUEIO: não pode desativar a si mesmo
    if id == session.get("user_id"):
        return redirect(url_for("usuarios"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=FALSE WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))


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

        usar_whatsapp = True if request.form.get("usar_whatsapp") else False
        instance = request.form.get("zapi_instance")
        token = request.form.get("zapi_token")

# 🚫 BLOQUEIO POR PLANO
cur.execute("SELECT plano_whatsapp FROM usuarios WHERE id=%s", (user_id,))
plano = cur.fetchone()[0]

if not plano:
    usar_whatsapp = False
    instance = None
    token = None
        if senha:
            cur.execute(
                "UPDATE usuarios SET senha=%s WHERE id=%s",
                (senha, user_id)
            )

        cur.execute("""
            UPDATE usuarios 
            SET whatsapp_msg=%s,
                usar_whatsapp=%s,
                zapi_instance=%s,
                zapi_token=%s
            WHERE id=%s
        """, (mensagem, usar_whatsapp, instance, token, user_id))

        conn.commit()

    # 🔽 BUSCAR DADOS ATUALIZADOS
    cur.execute("""
        SELECT usuario, whatsapp_msg, usar_whatsapp, zapi_instance, zapi_token, plano_whatsapp
        FROM usuarios
        WHERE id=%s
    """, (user_id,))

    user = cur.fetchone()

usuario = user[0]
mensagem = user[1] or ""
usar_whatsapp = user[2]
zapi_instance = user[3] or ""
zapi_token = user[4] or ""
plano_whatsapp = user[5]

    cur.close()
    conn.close()

    return render_template("config.html",
    usuario=usuario,
    mensagem=mensagem,
    usar_whatsapp=usar_whatsapp,
    zapi_instance=zapi_instance,
    zapi_token=zapi_token,
    plano_whatsapp=plano_whatsapp
)

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


# ================= ADD CLIENTE (NOVO) =================
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


# ================= ROTAS CLIENTES =================
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

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

    return redirect(url_for("index", mes=mes))


@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s AND usuario_id=%s",
                (id, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


@app.route("/pago/<int:id>")
def pago(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'pago')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='pago'
    """, (id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


@app.route("/desfazer/<int:id>")
def desfazer(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'em_dia')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='em_dia'
    """, (id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))

@app.route("/cobrar/<int:id>")
def cobrar(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    SELECT c.nome, c.telefone,
           u.whatsapp_msg, u.zapi_instance, u.zapi_token, u.usar_whatsapp, u.plano_whatsapp
    FROM clientes c
    JOIN usuarios u ON c.usuario_id = u.id
    WHERE c.id=%s AND c.usuario_id=%s
""", (id, session["user_id"]))

    res = cur.fetchone()

    if res:
        nome, tel, msg, instance, token, usar, plano = res

        if usar and plano:
            mensagem = (msg or "").replace("{nome}", nome)
            enviar_whatsapp(tel, mensagem, instance, token)

            # ⚠️ OPCIONAL: registrar envio manual (sem bloquear automático)
            cur.execute("""
                INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
                VALUES (%s,%s,%s,'manual')
                ON CONFLICT DO NOTHING
            """, (id, datetime.now().strftime("%Y-%m"), session["user_id"]))

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

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

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

        return redirect(url_for("gastos", mes=mes))

    cur.execute("""
        SELECT id, descricao, material, valor
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
        ORDER BY id DESC
    """, (session["user_id"], mes))

    lista = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
    """, (session["user_id"], mes))

    total = float(cur.fetchone()[0] or 0)

    cur.close()
    conn.close()

    return render_template("gastos.html", gastos=lista, total=total, mes_ref=mes)


@app.route("/del_gasto/<int:id>")
def del_gasto(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM gastos WHERE id=%s AND usuario_id=%s",
                (id, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("gastos", mes=mes))


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)