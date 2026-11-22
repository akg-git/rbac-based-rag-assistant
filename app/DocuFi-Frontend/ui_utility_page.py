import requests
from requests.auth import HTTPBasicAuth

API_URL = "http://localhost:8000"

def verify_user_with_role(username: str, role: str, auth):
    """
    Verify if a user exists with the specified role.
    Returns: {"exists": bool, "user_data": dict or None, "message": str}
    """
    if not username:
        return {"exists": False, "user_data": None, "message": "Please enter a username."}
    
    if not auth:
        return {"exists": False, "user_data": None, "message": "Authentication required."}
    
    try:
        verify_res = requests.get(
            f"{API_URL}/user-info/{username}",
            auth=HTTPBasicAuth(*auth),
            timeout=8
        )
        
        if verify_res.ok:
            user_data = verify_res.json()
            if user_data.get("role", "").lower() == role.lower():
                return {"exists": True, "user_data": user_data, "message": f"✅ User **{username}** found with role **{role}**"}
            else:
                return {"exists": False, "user_data": user_data, "message": f"❌ User **{username}** exists but has role **{user_data.get('role')}**, not **{role}**"}
        else:
            return {"exists": False, "user_data": None, "message": f"❌ User **{username}** not found."}
    except Exception as e:
        return {"exists": False, "user_data": None, "message": f"Error verifying user: {str(e)}"}