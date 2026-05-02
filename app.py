import os
from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo"

DATABASE_URL = os.getenv("DATABASE_URL")


# ================= CONEXÃO =================
def conectar():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print("ERRO BANCO:", e)
        return None


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = conectar()
        if not conn:
            return "Erro ao conectar no banco"

        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT id, usuario, is_admin, ativo
                FROM usuarios 
                WHERE usuario=%s AND senha=%s
            """, (request.form["usuario"], request.form["senha"]))

            user = cur.fetchone()
        except Exception as e:
            return f"Erro SQL: {e}"

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

    conn = conectar()
    if not conn:
        return "Erro de conexão com banco"

    cur = conn.cursor()

    user_id = session["user_id"]
    usuario = session["usuario"]

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    busca = request.args.get("busca", "").lower()
    filtro = request.args.get("filtro", "")

    # CLIENTES
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
    except:
        dados = []

    # WHATSAPP MSG
    try:
        cur.execute("SELECT whatsapp_msg FROM usuarios WHERE id=%s", (user_id,))
        res = cur.fetchone()
        msg = res[0] if res and res[0] else ""
    except:
        msg = ""

    clientes = []
    total = 0
    recebido = 0
    atrasado = 0
    emdia = 0

    hoje = datetime.now()
    hoje_mes = hoje.strftime("%Y-%m")
    hoje_dia = hoje.day

    for c in dados:
        try:
            id, nome, tel, valor, venc, status = c

            if busca and busca not in (nome or "").lower():
                continue

            valor = float(valor or 0)
            venc = int(venc or 0)

            if mes < hoje_mes:
                if status != "pago":
                    status = "atrasado"

            elif mes == hoje_mes:
                if status != "pago":
                    status = "atrasado" if hoje_dia > venc else "em_dia"

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

            clientes.append((id, nome, tel, valor, venc, status))

        except:
            continue

    # FILTRO
    try:
        if filtro == "nome":
            clientes.sort(key=lambda x: (x[1] or "").lower())
        elif filtro == "status":
            ordem = {"atrasado": 0, "em_dia": 1, "pago": 2}
            clientes.sort(key=lambda x: ordem.get(x[5], 1))
        elif filtro == "valor":
            clientes.sort(key=lambda x: x[3], reverse=True)
    except:
        pass

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
        usuario=usuario,
        mensagem=msg
    )


# ================= PAGAMENTO =================
@app.route("/pago/<int:id>")
def pago(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
            VALUES (%s,%s,%s,'pago')
            ON CONFLICT (cliente_id, mes_ref, usuario_id)
            DO UPDATE SET status='pago'
        """, (id, mes, user_id))

        conn.commit()
    except Exception as e:
        print("ERRO PAGO:", e)

    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


@app.route("/desfazer/<int:id>")
def desfazer(id):
    if not session.get("logado"):
        return redirect(url_for("login"))

    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")
    user_id = session["user_id"]

    conn = conectar()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
            VALUES (%s,%s,%s,'em_dia')
            ON CONFLICT (cliente_id, mes_ref, usuario_id)
            DO UPDATE SET status='em_dia'
        """, (id, mes, user_id))

        conn.commit()
    except Exception as e:
        print("ERRO DESFAZER:", e)

    cur.close()
    conn.close()

    return redirect(url_for("index", mes=mes))


# ================= GASTOS =================
@app.route("/gastos", methods=["GET", "POST"])
def gastos():
    if not session.get("logado"):
        return redirect(url_for("login"))

    conn = conectar()
    cur = conn.cursor()

    user_id = session["user_id"]
    mes = request.args.get("mes") or datetime.now().strftime("%Y-%m")

    if request.method == "POST":
        try:
            cur.execute("""
                INSERT INTO gastos (descricao, material, valor, mes_ref, usuario_id)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                request.form.get("descricao"),
                request.form.get("material"),
                request.form.get("valor"),
                mes,
                user_id
            ))
            conn.commit()
        except:
            pass

    try:
        cur.execute("""
            SELECT id, descricao, material, valor
            FROM gastos
            WHERE usuario_id=%s AND mes_ref=%s
        """, (user_id, mes))
        lista = cur.fetchall()
    except:
        lista = []

    try:
        cur.execute("""
            SELECT COALESCE(SUM(valor),0)
            FROM gastos
            WHERE usuario_id=%s AND mes_ref=%s
        """, (user_id, mes))
        total = float(cur.fetchone()[0])
    except:
        total = 0

    cur.close()
    conn.close()

    return render_template("gastos.html",
                           gastos=lista,
                           total=total,
                           mes_ref=mes)


# ================= START =================
if __name__ == "__main__":
    app.run(debug=True)