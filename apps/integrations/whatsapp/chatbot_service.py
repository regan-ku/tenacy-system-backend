from typing import Dict

class ChatbotService:
    """
    Handles basic inbound keyword routing. 
    Complex logic is delegated to apps/services via EventDispatcher.
    """
    KEYWORD_MAP = {
        "rent": {"type": "transactional", "action": "query_balance", "response": "Checking your rent balance..."},
        "pay": {"type": "transactional", "action": "request_stk", "response": "Initiating payment request..."},
        "maintenance": {"type": "reminder", "action": "log_issue", "response": "Please describe your issue."},
        "help": {"type": "system", "action": "show_menu", "response": "1: Pay Rent\n2: Report Issue\n3: Contact Support"}
    }

    @staticmethod
    def route_inbound(text: str, sender_phone: str) -> Dict:
        clean_text = text.strip().lower()
        match = ChatbotService.KEYWORD_MAP.get(clean_text)
        
        if not match:
            return {
                "response": "Unknown command. Reply HELP for options.",
                "action": "fallback"
            }
            
        return {
            "response": match["response"],
            "action": match["action"],
            "type": match["type"],
            "sender": sender_phone
        }