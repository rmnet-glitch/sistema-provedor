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


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, nome, telefone, valor, vencimento_dia, status
    FROM clientes
    WHERE usuario_id=%s
    """,(session["user_id"],))

    dados = cur.fetchall()

    clientes=[]
    total=0
    recebido=0
    atrasado=0
    em_dia=0

    hoje = datetime.now().day

    for c in dados:
        id,nome,tel,valor,venc,status = c

        valor = float(valor or 0)
        total += valor

        # status automático
        if status != "pago":
            status = "atrasado" if hoje > venc else "em_dia"

        # separação financeira
        if status == "pago":
            recebido += valor
        elif status == "atrasado":
            atrasado += valor
        else:
            em_dia += valor

        clientes.append((id,nome,tel,valor,venc,status))

    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        usuario=session["usuario"],
        mensagem=session["msg"],
        total_geral=total,
        total_recebido=recebido,
        total_atrasado=atrasado,
        total_em_dia=em_dia
    )


# ================= ADD =================
@app.route("/add", methods=["POST"])
def add():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO clientes (nome, telefone, valor, vencimento_dia, usuario_id, status)
    VALUES (%s,%s,%s,%s,%s,'em_dia')
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


# ================= PAGAR =================
@app.route("/pagar/<int:id>")
def pagar(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE clientes SET status='pago' WHERE id=%s",(id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")


# ================= DESFAZER =================
@app.route("/desfazer/<int:id>")
def desfazer(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("UPDATE clientes SET status='em_dia' WHERE id=%s",(id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")


# ================= DELETE =================
@app.route("/delete/<int:id>")
def delete(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s",(id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")


# ================= RUN =================
if __name__=="__main__":
    app.run(debug=True)