import os
import psycopg2
from datetime import datetime
from whatsapp_service import enviar_whatsapp

DATABASE_URL = os.getenv("DATABASE_URL")


def conectar():
    return psycopg2.connect(DATABASE_URL)


def rodar_cobranca():
    conn = conectar()
    cur = conn.cursor()

    hoje = datetime.now()
    mes = hoje.strftime("%Y-%m")
    dia_hoje = hoje.day

    # 🔥 pega clientes atrasados + config do usuário
    cur.execute("""
        SELECT 
            c.id, c.nome, c.telefone, c.vencimento_dia,
            u.id, u.whatsapp_msg, u.zapi_instance, u.zapi_token, u.usar_whatsapp
        FROM clientes c
        JOIN usuarios u ON c.usuario_id = u.id
    """)

    clientes = cur.fetchall()

    for c in clientes:
        cliente_id, nome, telefone, vencimento, user_id, msg, instance, token, usar = c

        if not usar:
            continue

        # 📅 verifica atraso de 7 dias
        if dia_hoje < (vencimento + 7):
            continue

        # 🔍 verifica se já foi cobrado esse mês
        cur.execute("""
            SELECT 1 FROM cobrancas
            WHERE cliente_id=%s AND mes_ref=%s AND status='cobrado_auto'
        """, (cliente_id, mes))

        ja_cobrado = cur.fetchone()

        if ja_cobrado:
            continue

        # 📲 monta mensagem
        mensagem = (msg or "").replace("{nome}", nome)

        try:
            enviar_whatsapp(telefone, mensagem, instance, token)

            # 💾 registra envio automático
            cur.execute("""
                INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, status)
                VALUES (%s,%s,%s,'cobrado_auto')
            """, (cliente_id, mes, user_id))

            conn.commit()

            print(f"✔ Cobrança enviada para {nome}")

        except Exception as e:
            print(f"Erro ao enviar para {nome}: {e}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    rodar_cobranca()