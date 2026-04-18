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


# ================= CONFIG =================
@app.route("/config", methods=["GET", "POST"])
def config():
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()
    user_id = session["user_id"]

    # 🔐 SALVAR SENHA
    if request.method == "POST" and "senha_btn" in request.form:
        senha = request.form.get("senha")

        if senha:
            cur.execute("""
                UPDATE usuarios
                SET senha=%s
                WHERE id=%s
            """, (senha, user_id))

    # 💬 SALVAR MENSAGEM
    if request.method == "POST" and "msg_btn" in request.form:
        mensagem = request.form.get("mensagem")

        cur.execute("""
            UPDATE usuarios
            SET whatsapp_msg=%s
            WHERE id=%s
        """, (mensagem, user_id))

    conn.commit()

    cur.execute("""
        SELECT usuario, whatsapp_msg
        FROM usuarios
        WHERE id=%s
    """, (user_id,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "config.html",
        usuario=user[0],
        mensagem=user[1] or ""
    )


# ================= GERAR COBRANÇAS =================
def gerar_cobrancas(cur, mes, user_id):
    cur.execute("SELECT id FROM clientes WHERE usuario_id=%s",(user_id,))
    clientes = cur.fetchall()

    for c in clientes:
        cur.execute("""
        SELECT id FROM cobrancas
        WHERE cliente_id=%s AND mes_ref=%s AND usuario_id=%s
        """,(c[0], mes, user_id))

        if not cur.fetchone():
            cur.execute("""
            INSERT INTO cobrancas (cliente_id, mes_ref, status, usuario_id)
            VALUES (%s,%s,'em_dia',%s)
            """,(c[0], mes, user_id))


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect("/login")

    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    busca = request.args.get("busca","").lower()

    gerar_cobrancas(cur, mes, user_id)

    cur.execute("""
    SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
           COALESCE(cb.status,'em_dia')
    FROM clientes c
    LEFT JOIN cobrancas cb
    ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
    WHERE c.usuario_id=%s
    """,(mes, user_id, user_id))

    dados = cur.fetchall()

    # 💬 BUSCAR MENSAGEM DO USUÁRIO
    cur.execute("""
    SELECT whatsapp_msg FROM usuarios WHERE id=%s
    """,(user_id,))
    msg = cur.fetchone()[0]

    clientes=[]
    total=recebido=atrasado=emdia=0
    total_clientes=0

    hoje = datetime.now()
    hoje_mes = hoje.strftime("%Y-%m")
    hoje_dia = hoje.day

    for c in dados:
        id,nome,tel,valor,venc,status = c

        if busca and busca not in nome.lower():
            continue

        total_clientes+=1
        valor=float(valor)
        total+=valor

        if mes > hoje_mes:
            status="em_dia"
        elif mes == hoje_mes:
            if status!="pago" and hoje_dia>int(venc):
                status="atrasado"
            elif status!="pago":
                status="em_dia"
        else:
            if status!="pago":
                status="atrasado"

        if status=="pago":
            recebido+=valor
        elif status=="atrasado":
            atrasado+=valor
        else:
            emdia+=valor

        clientes.append((id,nome,tel,valor,venc,status))

    ordem={"atrasado":0,"em_dia":1,"pago":2}
    clientes.sort(key=lambda x:ordem.get(x[5],1))

    conn.commit()
    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        mes_ref=mes,
        busca=busca,
        total_geral=total,
        total_recebido=recebido,
        total_atrasado=atrasado,
        total_em_dia=emdia,
        total_clientes=total_clientes,
        usuario=session["usuario"],
        mensagem=msg
    )


if __name__=="__main__":
    app.run(debug=True)