import requests

def enviar_whatsapp(numero, mensagem, instance, token):
    if not instance or not token:
        return False

    url = f"https://api.z-api.io/instances/{instance}/token/{token}/send-text"

    payload = {
        "phone": f"55{numero}",
        "message": mensagem
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        print("ZAPI RESPONSE:", resp.text)
        return True
    except Exception as e:
        print("ERRO WHATSAPP:", str(e))
        return False