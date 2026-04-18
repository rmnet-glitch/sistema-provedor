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
        SELECT id, usuario, is_admin, ativo, mensagem_whatsapp
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
            session["msg"] = user[4] or "Olá, seu boleto venceu."

            return redirect("/")

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ================= DEFINIÇÕES =================
@app.route("/config")
def config():
    if not session.get("logado"):
        return redirect("/login")

    return render_template("config.html")


@app.route("/salvar_config", methods=["POST"])
def salvar_config():
    conn = conectar()
    cur = conn.cursor()

    nova_senha = request.form["senha"]
    mensagem = request.form["mensagem"]

    cur.execute("""
    UPDATE usuarios 
    SET senha=%s, mensagem_whatsapp=%s
    WHERE id=%s
    """,(nova_senha, mensagem, session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/config")


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

    cur.execute("""
    SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia
    FROM clientes c
    WHERE c.usuario_id=%s
    """,(user_id,))

    dados = cur.fetchall()

    clientes=[]
    total=0

    for c in dados:
        id,nome,tel,valor,venc = c

        if busca and busca not in nome.lower():
            continue

        total += float(valor)

        clientes.append((id,nome,tel,valor,venc,"em_dia"))

    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        usuario=session["usuario"],
        mensagem=session["msg"],
        total_geral=total
    )


# ================= CLIENTES =================
@app.route("/add", methods=["POST"])
def add():
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
    return redirect("/")


# ================= USUÁRIOS =================
@app.route("/usuarios")
def usuarios():
    if not session.get("is_admin"):
        return redirect("/")

    conn=conectar()
    cur=conn.cursor()

    cur.execute("SELECT id, usuario, ativo FROM usuarios")
    lista=cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", usuarios=lista)


# ================= EXECUÇÃO =================
if __name__=="__main__":
    app.run(debug=True)