import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sistema-secreto-123"

DATABASE_URL = os.getenv("DATABASE_URL")


def conectar():
    return psycopg2.connect(DATABASE_URL)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["usuario"] == "rubens" and request.form["senha"] == "Rm2412@":
            session["logado"] = True
            return redirect(url_for("index"))
        return render_template("login.html", erro="Login inválido")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def gerar_cobrancas(cur, mes_ref):
    cur.execute("SELECT id FROM clientes")
    clientes = cur.fetchall()

    for c in clientes:
        cur.execute("""
            SELECT id FROM cobrancas
            WHERE cliente_id=%s AND mes_ref=%s
        """, (c[0], mes_ref))

        if not cur.fetchone():
            cur.execute("""
                INSERT INTO cobrancas (cliente_id, mes_ref, status)
                VALUES (%s, %s, 'em_dia')
            """, (c[0], mes_ref))


@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    mes_ref = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    busca = request.args.get("busca", "").lower()

    gerar_cobrancas(cur, mes_ref)

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status, 'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id = cb.cliente_id AND cb.mes_ref=%s
    """, (mes_ref,))

    raw = cur.fetchall()

    clientes = []
    total = 0
    recebido = 0

    hoje = datetime.now()

    for c in raw:
        id, nome, tel, valor, venc, status = c

        if busca and busca not in nome.lower():
            continue

        total += float(valor)

        if status == "pago":
            recebido += float(valor)

        if mes_ref == hoje.strftime("%Y-%m"):
            if status != "pago" and hoje.day > int(venc):
                status = "atrasado"
            elif status != "pago":
                status = "em_dia"
        elif mes_ref > hoje.strftime("%Y-%m"):
            status = "em_dia"
        else:
            if status != "pago":
                status = "atrasado"

        clientes.append((id, nome, tel, valor, venc, status))

    ordem = {"atrasado": 0, "em_dia": 1, "pago": 2}
    clientes.sort(key=lambda x: ordem.get(x[5], 1))

    conn.commit()
    cur.close()
    conn.close()

    return render_template(
        "index.html",
        clientes=clientes,
        mes_ref=mes_ref,
        busca=busca,
        total_geral=total,
        total_recebido=recebido
    )


@app.route("/pago/<int:id>")
def pago(id):
    conn = conectar()
    cur = conn.cursor()
    mes_ref = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
        UPDATE cobrancas SET status='pago', pago_em=NOW()
        WHERE cliente_id=%s AND mes_ref=%s
    """, (id, mes_ref))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes_ref))


@app.route("/desfazer/<int:id>")
def desfazer(id):
    conn = conectar()
    cur = conn.cursor()
    mes_ref = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    cur.execute("""
        UPDATE cobrancas SET status='em_dia', pago_em=NULL
        WHERE cliente_id=%s AND mes_ref=%s
    """, (id, mes_ref))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes_ref))


@app.route("/add", methods=["POST"])
def add():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clientes (nome, telefone, valor, vencimento_dia)
        VALUES (%s,%s,%s,%s)
    """, (
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clientes
        SET nome=%s, telefone=%s, valor=%s, vencimento_dia=%s
        WHERE id=%s
    """, (
        request.form["nome"],
        request.form["telefone"],
        request.form["valor"],
        request.form["vencimento_dia"],
        id
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
def delete(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
