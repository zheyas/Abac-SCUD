import bcrypt
from models.user import get_by_username

def verify_login(username, password):
    user = get_by_username(username)
    if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None