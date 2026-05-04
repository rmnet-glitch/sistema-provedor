from datetime import datetime
import psycopg2
import os
from whatsapp_service import enviar_whatsapp

DATABASE_URL = os.getenv("DATABASE_URL")

def conectar():
    return psycopg2.connect(DATABASE_URL)

def cobrar_automatico():
    conn = conectar()
    cur = conn.cursor()

    hoje = datetime.now()
    mes = hoje.strftime("%Y-%m")
    dia = hoje.day

    cur.execute("""
        SELECT c.nome, c.telefone,
               u.whatsapp_msg, u.zapi_instance, u.zapi_token
        FROM clientes c
        JOIN usuarios u ON c.usuario_id = u.id
        LEFT JOIN cobrancas cb
        ON c.id = cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=u.id
        WHERE c.vencimento_dia < %s
        AND (cb.status IS NULL OR cb.status != 'pago')
        AND u.usar_whatsapp = TRUE
    """, (mes, dia))

    lista = cur.fetchall()

    for nome, tel, msg, instance, token in lista:
        mensagem = (msg or "").replace("{nome}", nome)
        enviar_whatsapp(tel, mensagem, instance, token)

    cur.close()
    conn.close()

if __name__ == "__main__":
    cobrar_automatico()