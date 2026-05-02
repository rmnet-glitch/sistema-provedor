import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


# ================= CONEXÃO SEGURA =================
def conectar():
    try:
        if not DATABASE_URL:
            print("ERRO: DATABASE_URL não definida")
            return None
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print("ERRO CONEXÃO:", e)
        return None


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        conn = conectar()
        if not conn:
            return "Erro de conexão com banco"

        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT id, usuario, is_admin, ativo
                FROM usuarios
                WHERE usuario=%s AND senha=%s
            """, (request.form["usuario"], request.form["senha"]))

            user = cur.fetchone()

            if user:
                if not user[3]:
                    erro = "Usuário desativado"
                else:
                    session["logado"] = True
                    session["user_id"] = user[0]
                    session["usuario"] = user[1]
                    session["is_admin"] = user[2]
                    return redirect(url_for("index"))
            else:
                erro = "Login inválido"

        except Exception as e:
            return f"Erro SQL: {e}"

        finally:
            cur.close()
            conn.close()

    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= INDEX =================
@app.route("/")
def index():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    if not conn:
        return "Erro ao conectar no banco"

    cur = conn.cursor()

    user_id = session["user_id"]
    usuario = session["usuario"]
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    try:
        cur.execute("""
            SELECT c.id, c.nome, c.telefone, c.valor, c.vencimento_dia,
                   COALESCE(cb.status,'em_dia')
            FROM clientes c
            LEFT JOIN cobrancas cb
            ON c.id=cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=%s
            WHERE c.usuario_id=%s
        """, (mes, user_id, user_id))

        dados = cur.fetchall()

    except Exception as e:
        return f"Erro clientes: {e}"

    # GASTOS
    try:
        cur.execute("""
            SELECT COALESCE(SUM(valor),0)
            FROM gastos
            WHERE usuario_id=%s AND mes_ref=%s
        """, (user_id, mes))

        total_gastos = float(cur.fetchone()[0])
    except:
        total_gastos = 0

    total = 0
    recebido = 0
    clientes = []

    for c in dados:
        id,nome,tel,valor,venc,status = c
        valor = float(valor or 0)

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
        usuario=usuario
    )


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)