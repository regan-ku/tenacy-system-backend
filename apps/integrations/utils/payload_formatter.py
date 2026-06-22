from typing import Dict, Any, List

def format_mpesa_stk_payload(
    phone: str, amount: float, account_ref: str, callback_url: str, transaction_desc: str = "Payment"
) -> Dict[str, Any]:
    """Formats payload for M-Pesa Daraja STK Push (fields merged with runtime auth)"""
    return {
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_ref,
        "TransactionDesc": transaction_desc
    }

def format_sms_payload(phone: str, message: str, sender_id: str = "Tennacy") -> Dict[str, Any]:
    """Formats payload for Africa's Talking SMS API"""
    return {"to": phone, "message": message, "from": sender_id}

def format_whatsapp_template_payload(
    phone: str, template_name: str, language_code: str = "en", components: List[Dict] = None
) -> Dict[str, Any]:
    """Formats payload for WhatsApp Business API template messages"""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {"name": template_name, "language": {"code": language_code}}
    }
    if components:
        payload["template"]["components"] = components
    return payload

def standardize_webhook_event(source: str, event_type: str, raw_data: Dict) -> Dict:
    """Normalizes diverse webhook payloads into consistent internal format for WebhookEvent model"""
    return {
        "source": source,
        "event_type": event_type,
        "reference": raw_data.get("transaction_id") or raw_data.get("id") or raw_data.get("message_id"),
        "status": raw_data.get("status") or raw_data.get("delivery_status"),
        "timestamp": raw_data.get("timestamp") or raw_data.get("created_at"),
        "raw_payload": raw_data
    }