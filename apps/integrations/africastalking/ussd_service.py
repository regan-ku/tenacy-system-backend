from typing import Dict

class UssdService:
    """
    Stateless USSD session router. 
    Integrations/tenancy/payments apps will handle business logic; 
    this layer only formats AT-compliant XML responses.
    """
    @staticmethod
    def format_response(message: str, level: int = 1) -> str:
        """Returns AT-compatible USSD XML response"""
        prefix = "CON" if level < 2 else "END"
        return f"{prefix} {message}"

    @staticmethod
    def route_session(session_id: str, phone: str, text: str, service_code: str) -> Dict:
        """Parses incoming USSD text and returns routing decision"""
        steps = text.split("*") if text else []
        
        if not text or text == "":
            return {"response": UssdService.format_response("Welcome to Tennacy. Dial 1 for Rent, 2 for Maintenance, 3 for Support"), "next_level": 1}
        
        if steps[0] == "1":
            return {"response": UssdService.format_response("Enter your tenancy code:"), "next_level": 2}
        elif steps[0] == "2":
            return {"response": UssdService.format_response("Enter issue description:"), "next_level": 2}
        else:
            return {"response": UssdService.format_response("Invalid option. Goodbye."), "next_level": 2}