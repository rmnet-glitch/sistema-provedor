import os
import json
from flask import Flask, render_template, request, redirect, session, Response
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


# ================= BACKUP MANUAL =================
@app.route("/backup")
def backup():
    if not session.get("logado"):
        return redirect("/login")

    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT usuario FROM usuarios WHERE id=%s",(user_id,))
    usuario = cur.fetchone()[0]

    cur.execute("""
        SELECT id, nome, telefone, valor, vencimento_dia
        FROM clientes
        WHERE usuario_id=%s
    """,(user_id,))
    clientes = cur.fetchall()

    cur.execute("""
        SELECT cliente_id, mes_ref, status
        FROM cobrancas
        WHERE usuario_id=%s
    """,(user_id,))
    cobrancas = cur.fetchall()

    cur.close()
    conn.close()

    backup_data = {
        "usuario": usuario,
        "clientes": clientes,
        "cobrancas": cobrancas
    }

    json_data = json.dumps(backup_data, ensure_ascii=False, indent=4)

    return Response(
        json_data,
        mimetype="application/json",
        headers={"Content-Disposition":"attachment;filename=backup.json"}
    )


# ================= RESTORE =================
@app.route("/restore", methods=["POST"])
def restore():
    if not session.get("logado"):
        return redirect("/login")

    file = request.files.get("backup_file")

    if not file:
        return redirect("/config")

    data = json.load(file)

    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    # limpa dados do usuário
    cur.execute("DELETE FROM clientes WHERE usuario_id=%s",(user_id,))
    cur.execute("DELETE FROM cobrancas WHERE usuario_id=%s",(user_id,))

    # restaura clientes
    for c in data.get("clientes", []):
        cur.execute("""
            INSERT INTO clientes (id, nome, telefone, valor, vencimento_dia, usuario_id)
            VALUES (%s,%s,%s,%s,%s,%s)
        """,(c[0],c[1],c[2],c[3],c[4],user_id))

    # restaura cobranças
    for cb in data.get("cobrancas", []):
        cur.execute("""
            INSERT INTO cobrancas (cliente_id, mes_ref, status, usuario_id)
            VALUES (%s,%s,%s,%s)
        """,(cb[0],cb[1],cb[2],user_id))

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
    busca = request.args.get("busca","")

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status,'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
        WHERE c.usuario_id=%s
    """,(mes,user_id,user_id))

    dados = cur.fetchall()

    clientes=[]
    total=0
    recebido=0
    atrasado=0
    emdia=0

    hoje = datetime.now()
    hoje_mes = hoje.strftime("%Y-%m")
    hoje_dia = hoje.day

    for c in dados:
        id,nome,tel,valor,venc,status = c

        if busca and busca.lower() not in nome.lower():
            continue

        valor = float(valor)

        if mes < hoje_mes:
            if status != "pago":
                status = "atrasado"

        elif mes == hoje_mes:
            if status != "pago":
                status = "atrasado" if hoje_dia > int(venc) else "em_dia"

        else:
            if status != "pago":
                status = "em_dia"

        total += valor

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
        usuario=session["usuario"]
    )


if __name__ == "__main__":
    app.run(debug=True)