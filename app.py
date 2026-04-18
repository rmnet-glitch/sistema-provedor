from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "123"

def conectar():
    return sqlite3.connect("clientes.db")


# 🔐 LOGIN
@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        user=request.form["usuario"]
        senha=request.form["senha"]

        con=conectar()
        cur=con.cursor()

        cur.execute("SELECT * FROM usuarios WHERE usuario=? AND senha=? AND ativo=1",(user,senha))
        u=cur.fetchone()

        if u:
            session["user_id"]=u[0]
            session["usuario"]=u[1]
            session["is_admin"]=u[3]
            return redirect("/index")

    return render_template("login.html")


# 🏠 INDEX
@app.route("/index")
def index():
    if "usuario" not in session:
        return redirect("/")

    con=conectar()
    cur=con.cursor()

    # 📅 MÊS ATUAL
    hoje=datetime.now()
    mes_atual=hoje.strftime("%Y-%m")

    mes_ref=request.args.get("mes",mes_atual)
    busca=request.args.get("busca","")

    # CLIENTES DO USUÁRIO
    cur.execute("""
    SELECT * FROM clientes 
    WHERE user_id=? AND nome LIKE ?
    """,(session["user_id"],f"%{busca}%"))

    clientes=cur.fetchall()

    lista=[]
    total_geral=0
    total_recebido=0
    total_atrasado=0
    total_em_dia=0

    for c in clientes:
        id,nome,tel,valor,vencimento=user_id=c

        valor=float(valor)
        total_geral+=valor

        # VERIFICA PAGAMENTO NO MÊS
        cur.execute("""
        SELECT * FROM pagamentos 
        WHERE cliente_id=? AND mes=?
        """,(id,mes_ref))

        pago=cur.fetchone()

        # 🔥 LÓGICA CORRIGIDA
        dia_hoje=hoje.day

        if pago:
            status="pago"
            total_recebido+=valor
        else:
            if dia_hoje > int(vencimento):
                status="atrasado"
                total_atrasado+=valor
            else:
                status="em_dia"
                total_em_dia+=valor

        lista.append((id,nome,tel,valor,vencimento,status))

    # 📩 MENSAGEM WHATSAPP
    cur.execute("SELECT mensagem FROM usuarios WHERE id=?",(session["user_id"],))
    msg=cur.fetchone()
    mensagem=msg[0] if msg and msg[0] else "Olá, tudo bem?"

    return render_template("index.html",
        clientes=lista,
        total_geral=total_geral,
        total_recebido=total_recebido,
        total_atrasado=total_atrasado,
        total_em_dia=total_em_dia,
        total_clientes=len(lista),
        usuario=session["usuario"],
        mes_ref=mes_ref,
        busca=busca,
        mensagem=mensagem
    )


# ➕ ADICIONAR
@app.route("/add", methods=["POST"])
def add():
    con=conectar()
    cur=con.cursor()

    cur.execute("""
    INSERT INTO clientes(nome,telefone,valor,vencimento,user_id)
    VALUES(?,?,?,?,?)
    """,(
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        session["user_id"]
    ))

    con.commit()
    return redirect("/index")


# ✏ EDITAR
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    con=conectar()
    cur=con.cursor()

    cur.execute("""
    UPDATE clientes 
    SET nome=?, telefone=?, valor=?, vencimento=?
    WHERE id=? AND user_id=?
    """,(
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        id,
        session["user_id"]
    ))

    con.commit()
    return redirect("/index")


# 🗑 EXCLUIR
@app.route("/delete/<int:id>")
def delete(id):
    con=conectar()
    cur=con.cursor()

    cur.execute("DELETE FROM clientes WHERE id=? AND user_id=?",(id,session["user_id"]))
    con.commit()

    return redirect("/index")


# ✅ MARCAR PAGO
@app.route("/pago/<int:id>")
def pago(id):
    mes=request.args.get("mes")

    con=conectar()
    cur=con.cursor()

    cur.execute("""
    INSERT INTO pagamentos(cliente_id,mes)
    VALUES(?,?)
    """,(id,mes))

    con.commit()
    return redirect(f"/index?mes={mes}")


# ↩ DESFAZER
@app.route("/desfazer/<int:id>")
def desfazer(id):
    mes=request.args.get("mes")

    con=conectar()
    cur=con.cursor()

    cur.execute("""
    DELETE FROM pagamentos 
    WHERE cliente_id=? AND mes=?
    """,(id,mes))

    con.commit()
    return redirect(f"/index?mes={mes}")


# ⚙ CONFIG
@app.route("/config", methods=["GET","POST"])
def config():
    if "usuario" not in session:
        return redirect("/")

    con=conectar()
    cur=con.cursor()

    if request.method=="POST":
        senha=request.form.get("senha")
        mensagem=request.form.get("mensagem")

        if senha:
            cur.execute("UPDATE usuarios SET senha=? WHERE id=?",(senha,session["user_id"]))

        cur.execute("UPDATE usuarios SET mensagem=? WHERE id=?",(mensagem,session["user_id"]))

        con.commit()

    cur.execute("SELECT mensagem FROM usuarios WHERE id=?",(session["user_id"],))
    msg=cur.fetchone()

    return render_template("config.html",mensagem=msg[0] if msg else "")


# 🚪 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


app.run(debug=True)