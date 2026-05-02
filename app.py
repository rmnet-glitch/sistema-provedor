import os
from flask import Flask, render_template, request, redirect, session, url_for
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

            return redirect(url_for("index"))

        return render_template("login.html", erro="Login inválido")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    # CLIENTES
    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
               COALESCE(cb.status,'em_dia')
        FROM clientes c
        LEFT JOIN cobrancas cb
        ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
        WHERE c.usuario_id=%s
    """,(mes,user_id,user_id))

    dados = cur.fetchall()

    # GASTOS
    cur.execute("""
        SELECT COALESCE(SUM(valor),0)
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
    """,(user_id,mes))

    total_gastos = float(cur.fetchone()[0])

    total=0
    recebido=0

    clientes=[]

    for c in dados:
        id,nome,tel,valor,venc,status = c
        valor=float(valor)

        total += valor
        if status == "pago":
            recebido += valor

        clientes.append((id,nome,tel,valor,venc,status))

    lucro = recebido - total_gastos

    cur.close()
    conn.close()

    return render_template("index.html",
        clientes=clientes,
        mes_ref=mes,
        total_geral=total,
        total_recebido=recebido,
        total_gastos=total_gastos,
        lucro=lucro,
        usuario=session["usuario"]
    )


# ================= CLIENTES =================
@app.route("/add", methods=["POST"])
def add():
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

    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
def delete(id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM clientes WHERE id=%s AND usuario_id=%s",(id,session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


# ================= PAGAMENTO =================
@app.route("/pago/<int:id>")
def pago(id):
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
        VALUES (%s,%s,%s,'pago')
        ON CONFLICT (cliente_id, mes_ref, usuario_id)
        DO UPDATE SET status='pago'
    """,(id,mes,session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


# ================= GASTOS =================
@app.route("/gastos")
def gastos():
    if not session.get("logado"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, descricao, material, valor, data
        FROM gastos
        WHERE usuario_id=%s AND mes_ref=%s
        ORDER BY id DESC
    """,(user_id, mes))

    lista = cur.fetchall()

    total = sum([float(g[3]) for g in lista]) if lista else 0

    cur.close()
    conn.close()

    return render_template("gastos.html",
        gastos=lista,
        total=total,
        mes_ref=mes
    )


@app.route("/add_gasto", methods=["POST"])
def add_gasto():
    conn = conectar()
    cur = conn.cursor()

    valor = request.form.get("valor")
    if not valor:
        return redirect(url_for("gastos"))

    cur.execute("""
        INSERT INTO gastos (descricao, material, valor, mes_ref, usuario_id)
        VALUES (%s,%s,%s,%s,%s)
    """,(
        request.form.get("descricao"),
        request.form.get("material"),
        valor,
        request.form.get("mes"),
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("gastos", mes=request.form.get("mes")))


@app.route("/del_gasto/<int:id>")
def del_gasto(id):
    mes = request.args.get("mes")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("DELETE FROM gastos WHERE id=%s AND usuario_id=%s",(id,session["user_id"]))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("gastos", mes=mes))


if __name__ == "__main__":
    app.run(debug=True)