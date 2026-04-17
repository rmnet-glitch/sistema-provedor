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
    for c in cur.fetchall():
        cur.execute("""
            SELECT id FROM cobrancas
            WHERE cliente_id=%s AND mes_ref=%s
        """, (c[0], mes_ref))

        if not cur.fetchone():
            cur.execute("""
                INSERT INTO cobrancas (cliente_id, mes_ref, status)
                VALUES (%s,%s,'em_dia')
            """, (c[0], mes_ref))


@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    mes_ref = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    busca = request.args.get("busca", "").lower()
    hoje = datetime.now().strftime("%Y-%m")

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

    total_geral = 0
    total_recebido = 0
    total_atrasado = 0
    total_em_dia = 0

    hoje_dia = datetime.now().day

    for c in raw:
        id, nome, tel, valor, venc, status = c

        if busca and busca not in nome.lower():
            continue

        valor = float(valor)
        total_geral += valor

        if status == "pago":
            total_recebido += valor

        if mes_ref > hoje:
            status = "em_dia"
        elif mes_ref == hoje:
            if status != "pago" and hoje_dia > int(venc):
                status = "atrasado"
            elif status != "pago":
                status = "em_dia"
        else:
            if status != "pago":
                status = "atrasado"

        if status == "atrasado":
            total_atrasado += valor
        elif status == "em_dia":
            total_em_dia += valor

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
        total_geral=total_geral,
        total_recebido=total_recebido,
        total_atrasado=total_atrasado,
        total_em_dia=total_em_dia
    )


if __name__ == "__main__":
    app.run(debug=True)