def cobrar_automatico():
    conn = conectar()
    cur = conn.cursor()

    hoje = datetime.now()
    mes = hoje.strftime("%Y-%m")
    dia_hoje = hoje.day

    cur.execute("""
        SELECT c.id, c.nome, c.telefone, c.vencimento_dia,
               u.id as usuario_id,
               u.whatsapp_msg, u.zapi_instance, u.zapi_token
        FROM clientes c
        JOIN usuarios u ON c.usuario_id = u.id
        LEFT JOIN cobrancas cb
        ON c.id = cb.cliente_id AND cb.mes_ref=%s AND cb.usuario_id=u.id
        WHERE (cb.status IS NULL OR cb.status != 'pago')
        AND u.usar_whatsapp = TRUE
    """, (mes,))

    lista = cur.fetchall()

    for cliente_id, nome, tel, venc, user_id, msg, instance, token in lista:

        venc = int(venc or 1)

        # 🚫 ainda não chegou nos 7 dias
        if dia_hoje < (venc + 7):
            continue

        # 🔎 já enviou?
        cur.execute("""
            SELECT enviado FROM cobrancas
            WHERE cliente_id=%s AND mes_ref=%s AND usuario_id=%s
        """, (cliente_id, mes, user_id))

        res = cur.fetchone()

        if res and res[0]:
            continue  # já enviou, pula

        # 📲 enviar
        mensagem = (msg or "").replace("{nome}", nome)
        enviar_whatsapp(tel, mensagem, instance, token)

        # 💾 marcar como enviado
        cur.execute("""
            INSERT INTO cobrancas (cliente_id, mes_ref, usuario_id, enviado)
            VALUES (%s,%s,%s,TRUE)
            ON CONFLICT (cliente_id, mes_ref, usuario_id)
            DO UPDATE SET enviado=TRUE
        """, (cliente_id, mes, user_id))

        conn.commit()

    cur.close()
    conn.close()