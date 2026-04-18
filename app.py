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
@app.route("/config", methods=["GET","POST"])
def config():
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]

    if request.method == "POST":

        senha = request.form.get("senha")
        mensagem = request.form.get("mensagem")

        if senha:
            cur.execute("""
                UPDATE usuarios SET senha=%s WHERE id=%s
            """,(senha,user_id))

        if mensagem is not None:
            cur.execute("""
                UPDATE usuarios SET whatsapp_msg=%s WHERE id=%s
            """,(mensagem,user_id))

        conn.commit()

    cur.execute("""
        SELECT usuario, whatsapp_msg
        FROM usuarios
        WHERE id=%s
    """,(user_id,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "config.html",
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
    if not session.get("is_admin"):
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO usuarios (usuario, senha, ativo)
        VALUES (%s,%s,TRUE)
    """,(request.form["usuario"], request.form["senha"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


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
            UPDATE usuarios SET usuario=%s WHERE id=%s
        """,(usuario,id))
    else:
        cur.execute("""
            UPDATE usuarios SET usuario=%s, senha=%s WHERE id=%s
        """,(usuario,senha,id))

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

    cur.execute("UPDATE usuarios SET ativo=FALSE WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


@app.route("/ativar_user/<int:id>")
def ativar_user(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE usuarios SET ativo=TRUE WHERE id=%s",(id,))

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

    cur.execute("DELETE FROM usuarios WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/usuarios")


# ================= CLIENTES =================
@app.route("/add", methods=["POST"])
def add():
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia, usuario_id)
        VALUES (%s,%s,%s,%s,%s)
    """,(
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes 
        SET nome=%s,
            telefone=%s,
            valor=%s,
            vencimento_dia=%s
        WHERE id=%s AND usuario_id=%s
    """,(
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

    return redirect("/")


@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM clientes 
        WHERE id=%s AND usuario_id=%s
    """,(id,session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")


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
    """,(id,mes,session["user_id"]))

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
    """,(id,mes,session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(f"/?mes={mes}")


# ================= INDEX (CORRIGIDO TOTALMENTE) =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect("/login")

    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    busca = request.args.get("busca","").lower()

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status,'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
        WHERE c.usuario_id=%s
    """,(mes,user_id,user_id))

    dados = cur.fetchall()

    cur.execute("SELECT whatsapp_msg FROM usuarios WHERE id=%s",(user_id,))
    msg = cur.fetchone()[0]

    clientes = []

    total = 0
    recebido = 0
    atrasado = 0
    emdia = 0
    total_clientes = 0

    hoje = datetime.now()
    hoje_mes = hoje.strftime("%Y-%m")
    hoje_dia = hoje.day

    for c in dados:
        id,nome,tel,valor,venc,status = c

        if busca and busca not in nome.lower():
            continue

        valor = float(valor)

        # STATUS CORRETO
        if mes < hoje_mes:
            if status != "pago":
                status = "atrasado"

        elif mes == hoje_mes:
            if status != "pago":
                if hoje_dia > int(venc):
                    status = "atrasado"
                else:
                    status = "em_dia"

        else:
            if status != "pago":
                status = "em_dia"

        # SOMAS CORRETAS
        total += valor
        total_clientes += 1

        if status == "pago":
            recebido += valor
        elif status == "atrasado":
            atrasado += valor
        else:
            emdia += valor

        clientes.append((id,nome,tel,valor,venc,status))

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


if __name__ == "__main__":
    app.run(debug=True)