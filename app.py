from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'rm_net_2026'

DB = 'clientes.db'


# ---------------- BANCO ----------------
def get_db():
    return sqlite3.connect(DB)


def criar_tabelas():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT,
        valor REAL,
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

        # 🔥 MANTÉM SEU LOGIN ORIGINAL
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

    c.execute("SELECT * FROM clientes WHERE usuario=?", (session['user'],))
    clientes = c.fetchall()

    # 🔥 CORREÇÃO VALORES
    total = sum([float(c[3] or 0) for c in clientes])
    recebido = sum([float(c[3] or 0) for c in clientes if c[5] == 'pago'])

    conn.close()

    return render_template('index.html',
                           clientes=clientes,
                           total=total,
                           recebido=recebido)


# ---------------- ADD CLIENTE ----------------
@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session:
        return redirect('/')

    nome = request.form['nome']
    telefone = request.form['telefone']
    valor = request.form['valor']
    vencimento = request.form['vencimento']

    # 🔥 CONVERTE CORRETAMENTE
    valor = float(valor)
    vencimento = int(vencimento)

    hoje = datetime.now().day

    status = 'em_dia'
    if hoje > vencimento:
        status = 'atrasado'

    conn = get_db()
    c = conn.cursor()

    c.execute('''
    INSERT INTO clientes (nome, telefone, valor, vencimento, status, ultimo_pagamento, usuario)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, telefone, valor, vencimento, status, '', session['user']))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- PAGAR ----------------
@app.route('/pagar/<int:id>')
def pagar(id):
    conn = get_db()
    c = conn.cursor()

    # 🔥 DATA CORRIGIDA
    hoje = datetime.now().strftime('%d/%m/%Y')

    c.execute("UPDATE clientes SET status='pago', ultimo_pagamento=? WHERE id=?",
              (hoje, id))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- DESFAZER ----------------
@app.route('/desfazer/<int:id>')
def desfazer(id):
    conn = get_db()
    c = conn.cursor()

    hoje = datetime.now().day

    c.execute("SELECT vencimento FROM clientes WHERE id=?", (id,))
    vencimento = c.fetchone()[0]

    status = 'em_dia'
    if hoje > vencimento:
        status = 'atrasado'

    c.execute("UPDATE clientes SET status=?, ultimo_pagamento='' WHERE id=?",
              (status, id))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- DELETE ----------------
@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM clientes WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- RUN (RENDER) ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)