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

    if request.method == "POST":

        if "senha_btn" in request.form:
            senha = request.form.get("senha")
            if senha:
                cur.execute("""
                    UPDATE usuarios
                    SET senha=%s
                    WHERE id=%s
                """, (senha, user_id))

        if "msg_btn" in request.form:
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

    return render_template("config.html",
        usuario=user[0],
        mensagem=user[1] or ""
    )


# ================= USUÁRIOS =================
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
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (usuario, senha, ativo)
        VALUES (%s,%s,TRUE)
    """, (request.form["usuario"], request.form["senha"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= EDITAR USUÁRIO (CORRIGIDO) =================
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
            UPDATE usuarios
            SET usuario=%s
            WHERE id=%s
        """, (usuario, id))
    else:
        cur.execute("""
            UPDATE usuarios
            SET usuario=%s, senha=%s
            WHERE id=%s
        """, (usuario, senha, id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/desativar_user/<int:id>")
def desativar_user(id):
    if id == session["user_id"]:
        return redirect("/usuarios")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=FALSE WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/ativar_user/<int:id>")
def ativar_user(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=TRUE WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/del_user/<int:id>")
def del_user(id):
    if id == session["user_id"]:
        return redirect("/usuarios")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM usuarios WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


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
    filtro = request.args.get("filtro","")

    cur.execute("""
    SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
           COALESCE(cb.status,'em_dia')
    FROM clientes c
    LEFT JOIN cobrancas cb
    ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
    WHERE c.usuario_id=%s
    """,(mes, user_id, user_id))

    dados = cur.fetchall()

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

    if filtro == "nome":
        clientes.sort(key=lambda x: x[1].lower())

    elif filtro == "status":
        ordem={"atrasado":0,"em_dia":1,"pago":2}
        clientes.sort(key=lambda x: ordem.get(x[5],1))

    elif filtro == "valor":
        clientes.sort(key=lambda x: float(x[3]), reverse=True)

    conn.commit()
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
        total_clientes=total_clientes,
        usuario=session["usuario"],
        mensagem=msg
    )


# ================= PAGAMENTO =================
@app.route("/pago/<int:id>")
def pago(id):
    if not session.get("logado"):
        return redirect("/login")

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE cobrancas 
        SET status='pago'
        WHERE cliente_id=%s AND mes_ref=%s AND usuario_id=%s
    """,(id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(f"/?mes={mes}")


@app.route("/desfazer/<int:id>")
def desfazer(id):
    if not session.get("logado"):
        return redirect("/login")

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE cobrancas 
        SET status='em_dia'
        WHERE cliente_id=%s AND mes_ref=%s AND usuario_id=%s
    """,(id, mes, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(f"/?mes={mes}")


if __name__ == "__main__":
    app.run(debug=True)