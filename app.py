from flask import Flask, render_template, request, redirect, session
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rm_net_2026'


# ---------------- CONEXÃO NEON ----------------
def get_db():
    return psycopg2.connect(os.environ['DATABASE_URL'])


# ---------------- CRIAR TABELA ----------------
def criar_tabelas():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS clientes (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        telefone TEXT,
        valor NUMERIC,
        vencimento INTEGER,
        status TEXT,
        ultimo_pagamento TEXT,
        usuario TEXT
    )
    ''')

    conn.commit()
    conn.close()


criar_tabelas()


# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']

        if usuario == 'RM_NET' and senha == 'Rm2412@':
            session['user'] = usuario
            return redirect('/index')

    return render_template('login.html')


# ---------------- INDEX ----------------
@app.route('/index')
def index():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM clientes WHERE usuario=%s", (session['user'],))
    clientes = c.fetchall()

    hoje = datetime.now().day

    total = 0
    recebido = 0

    clientes_tratados = []

    for cte in clientes:
        valor = float(cte[3] or 0)
        vencimento = cte[4]
        status = cte[5]

        # 🔥 CORRIGE STATUS AUTOMATICAMENTE
        if status != 'pago':
            if hoje > vencimento:
                status = 'atrasado'
            else:
                status = 'em_dia'

        if status == 'pago':
            recebido += valor

        total += valor

        clientes_tratados.append((
            cte[0],
            cte[1],
            cte[2],
            valor,
            vencimento,
            status,
            cte[6]
        ))

    conn.close()

    return render_template('index.html',
                           clientes=clientes_tratados,
                           total=total,
                           recebido=recebido)


# ---------------- ADD CLIENTE ----------------
@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session:
        return redirect('/')

    nome = request.form['nome']
    telefone = request.form['telefone']
    valor = float(request.form['valor'])
    vencimento = int(request.form['vencimento'])

    hoje = datetime.now().day

    status = 'em_dia'
    if hoje > vencimento:
        status = 'atrasado'

    conn = get_db()
    c = conn.cursor()

    c.execute('''
    INSERT INTO clientes (nome, telefone, valor, vencimento, status, ultimo_pagamento, usuario)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (nome, telefone, valor, vencimento, status, '', session['user']))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- PAGAR ----------------
@app.route('/pagar/<int:id>')
def pagar(id):
    conn = get_db()
    c = conn.cursor()

    data_pagamento = datetime.now().strftime('%d/%m/%Y')

    c.execute("""
        UPDATE clientes 
        SET status='pago', ultimo_pagamento=%s 
        WHERE id=%s
    """, (data_pagamento, id))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- DESFAZER PAGAMENTO ----------------
@app.route('/desfazer/<int:id>')
def desfazer(id):
    conn = get_db()
    c = conn.cursor()

    hoje = datetime.now().day

    c.execute("SELECT vencimento FROM clientes WHERE id=%s", (id,))
    vencimento = c.fetchone()[0]

    status = 'em_dia'
    if hoje > vencimento:
        status = 'atrasado'

    c.execute("""
        UPDATE clientes 
        SET status=%s, ultimo_pagamento='' 
        WHERE id=%s
    """, (status, id))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- DELETE ----------------
@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM clientes WHERE id=%s", (id,))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)