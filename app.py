import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from whatsapp_service import enviar_whatsapp
from datetime import datetime
from zoneinfo import ZoneInfo

def hoje_brasil():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()

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

# ================= USUARIOS SISTEMA ======


@app.route("/usuarios")
def usuarios():
    if not session.get("logado"):
        return redirect(url_for("login"))

    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, usuario, is_admin, ativo, plano_whatsapp
        FROM usuarios
        ORDER BY id DESC
    """)

    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)

# ================== ADD USER SISTEMA =======

@app.route("/add", methods=["POST"])
def add():
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        is_admin = request.form.get("is_admin") == "true"

        cur.execute("""
            INSERT INTO usuarios (usuario, senha, is_admin, ativo, plano_whatsapp)
            VALUES (%s, %s, %s, TRUE, FALSE)
        """, (usuario, senha, is_admin))

        conn.commit()

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("usuarios"))

# ================== ADD CLIENTE PROVEDOR =======

@app.route("/add_cliente", methods=["POST"])
def add_cliente():
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
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

# ================= EXCLUIR CLIENTE PROVEDOR =====

@app.route("/delete/<int:id>")
def delete_cliente(id):
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE FROM clientes
            WHERE id=%s AND usuario_id=%s
        """, (id, session["user_id"]))

        conn.commit()

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("index"))

# ================== EDIT USUARIO =======

@app.route("/editar_usuario/<int:id>", methods=["POST"])
def editar_usuario(id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()

    senha = request.form.get("senha")

    if senha:
        cur.execute("""
            UPDATE usuarios
            SET usuario=%s, senha=%s, is_admin=%s
            WHERE id=%s
        """, (
            request.form["usuario"],
            senha,
            request.form["is_admin"] == "true",
            id
        ))
    else:
        cur.execute("""
            UPDATE usuarios
            SET usuario=%s, is_admin=%s
            WHERE id=%s
        """, (
            request.form["usuario"],
            request.form["is_admin"] == "true",
            id
        ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))

# ================ DESFAZER PAGAMENTO ===========

@app.route("/desfazer/<int:id>")
def desfazer(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'em_dia')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status = 'em_dia'
    """, (id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))

# ================ DESATIVAR USUARIO =======

@app.route("/desativar_usuario/<int:id>")
def desativar_usuario(id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    # 🚫 impede desativar a si mesmo
    if id == session.get("user_id"):
        return redirect(url_for("usuarios"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE usuarios
        SET ativo = FALSE
        WHERE id = %s
    """, (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))

# ================ EXCLUIR USUARIO =========


@app.route("/delete_usuario/<int:id>")
def delete_usuario(id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))

# ================= GASTOS ======

@app.route("/gastos", methods=["GET", "POST"])
def gastos():
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
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
    """, (session["user_id"], mes))

    lista = cur.fetchall()

    return render_template("gastos.html", gastos=lista, mes_ref=mes)

# ================= EDIT CLIENTE ======= 

@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
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

# ================== ATIVAR API =============


@app.route("/ativar_api/<int:id>")
def ativar_api(id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE usuarios
        SET plano_whatsapp=TRUE
        WHERE id=%s
    """, (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))

# ================ DESATIVAR API =============

@app.route("/desativar_api/<int:id>")
def desativar_api(id):
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE usuarios
        SET plano_whatsapp=FALSE
        WHERE id=%s
    """, (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("usuarios"))

# ================= CONFIG (BLINDADO) =============
@app.route("/config", methods=["GET", "POST"])
def config():
    if not check_login():
        return redirect(url_for("login"))

    conn = get_conn()
    cur = conn.cursor()

    try:
        user_id = session.get("user_id")

      if request.method == "POST":
            # pega valores atuais do banco
         cur.execute("""
         SELECT whatsapp_msg, usar_whatsapp,    zapi_instance, zapi_token
         FROM usuarios WHERE id=%s
         """, (user_id,))

         atual = cur.fetchone()

         msg_atual = atual[0]
         usar_atual = atual[1]
         inst_atual = atual[2]
         token_atual = atual[3]

# pega o que veio do form (ou mantém o atual)
         senha = request.form.get("senha")

         mensagem = request.form.get("mensagem") or            msg_atual

         if "usar_whatsapp" in request.form:
         usar_whatsapp = True
         else:
         usar_whatsapp = usar_atual

         instance =     request.form.get("zapi_instance") or     inst_atual
         token = request.form.get("zapi_token") or        token_atual

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
        busca = request.args.get("busca", "").lower()
        filtro = request.args.get("filtro", "")

        cur.execute("""
            SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
                   cb.status
            FROM clientes c
            LEFT JOIN cobrancas cb
              ON c.id = cb.cliente_id
             AND cb.mes_ref = %s
             AND cb.usuario_id = %s
            WHERE c.usuario_id = %s
        """, (mes, user_id, user_id))

        dados = cur.fetchall()

        clientes = []
        total = recebido = atrasado = emdia = 0
        gasto = 0
        lucro = 0
        alertas = []

        hoje = datetime.now()
        mes_atual = hoje.strftime("%Y-%m")

        for c in dados:
            cid, nome, tel, valor, venc, status = c

            valor = float(valor or 0)

            try:
                venc = int(venc or 1)
            except:
                venc = 1

            if status == "pago":
                final_status = "pago"
            else:
                if mes < mes_atual:
                    final_status = "atrasado"
                elif mes == mes_atual:
                    final_status = "atrasado" if hoje.day > venc else "em_dia"
                else:
                    final_status = "em_dia"

            # busca
            if busca and busca not in (nome or "").lower():
                continue

            # filtro
            if filtro == "atrasado" and final_status != "atrasado":
                continue

            # alertas
            if final_status == "atrasado":
                alertas.append(f"🔴 {nome} está atrasado")

            elif final_status == "em_dia" and mes == mes_atual and hoje.day == venc:
                alertas.append(f"⚠️ {nome} vence hoje")

            # totais
            total += valor

            if final_status == "pago":
                recebido += valor
            elif final_status == "atrasado":
                atrasado += valor
            else:
                emdia += valor

            clientes.append((cid, nome, tel, valor, venc, final_status))

        # ✅ NOVO: buscar gastos reais do mês
        cur.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM gastos
            WHERE usuario_id = %s
            AND mes_ref = %s
        """, (user_id, mes))

        gasto = float(cur.fetchone()[0] or 0)

        # ✅ lucro real
        lucro = recebido - gasto

        clientes.sort(key=lambda x: 0 if x[5] == "atrasado" else 1 if x[5] == "em_dia" else 2)

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
            lucro=lucro,
            gasto=gasto,
            alertas=alertas,
            usuario=session.get("usuario")
        )

    finally:
        cur.close()
        conn.close()


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

        if not res:
            return "Cliente não encontrado"

        nome, tel, msg, instance, token, usar, plano = res

        print("DEBUG:", usar, plano, instance, token, tel)

        if not plano:
            return "❌ Seu plano não permite WhatsApp"

        if not usar:
            return "⚠️ WhatsApp desativado nas configurações"

        if not instance or not token:
            return "⚠️ Configure a API no painel"

        ok = enviar_whatsapp(
            tel,
            (msg or "").replace("{nome}", nome),
            instance,
            token
        )

        if ok:
            return "✅ Mensagem enviada"
        else:
            return "❌ Erro ao enviar (ver logs)"

    finally:
        cur.close()
        conn.close()

# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)