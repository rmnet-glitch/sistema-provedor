from flask import Flask, render_template, request, redirect, session, url_for
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
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha TEXT,
        ativo INTEGER DEFAULT 1,
        mensagem TEXT DEFAULT ''
    )
    ''')

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
        user = request.form['usuario']
        senha = request.form['senha']

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE username=? AND senha=? AND ativo=1", (user, senha))
        u = c.fetchone()
        conn.close()

        if u:
            session['user'] = user
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

    total = sum([c[3] for c in clientes])
    recebido = sum([c[3] for c in clientes if c[5] == 'pago'])
    atrasados = len([c for c in clientes if c[5] == 'atrasado'])
    em_dia = len([c for c in clientes if c[5] == 'em_dia'])

    conn.close()

    return render_template('index.html',
                           clientes=clientes,
                           total=total,
                           recebido=recebido,
                           atrasados=atrasados,
                           em_dia=em_dia)


# ---------------- CADASTRAR CLIENTE ----------------
@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session:
        return redirect('/')

    nome = request.form['nome']
    telefone = request.form['telefone']
    valor = float(request.form['valor'])
    vencimento = int(request.form['vencimento'])

    hoje = datetime.now().day

    if hoje > vencimento:
        status = 'atrasado'
    else:
        status = 'em_dia'

    conn = get_db()
    c = conn.cursor()

    c.execute('''
    INSERT INTO clientes (nome, telefone, valor, vencimento, status, ultimo_pagamento, usuario)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (nome, telefone, valor, vencimento, status, '', session['user']))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- PAGAMENTO ----------------
@app.route('/pagar/<int:id>')
def pagar(id):
    conn = get_db()
    c = conn.cursor()

    hoje = datetime.now().strftime('%d/%m/%Y')

    c.execute("UPDATE clientes SET status='pago', ultimo_pagamento=? WHERE id=?", (hoje, id))

    conn.commit()
    conn.close()

    return redirect('/index')


@app.route('/desfazer/<int:id>')
def desfazer(id):
    conn = get_db()
    c = conn.cursor()

    hoje = datetime.now().day

    c.execute("SELECT vencimento FROM clientes WHERE id=?", (id,))
    venc = c.fetchone()[0]

    if hoje > venc:
        status = 'atrasado'
    else:
        status = 'em_dia'

    c.execute("UPDATE clientes SET status=?, ultimo_pagamento='' WHERE id=?", (status, id))

    conn.commit()
    conn.close()

    return redirect('/index')


# ---------------- DELETAR ----------------
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


# ---------------- RUN (CORRIGIDO RENDER) ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)