import bcrypt
from models import User

def verify_login(username, password):
    user = User.get_by_username(username)
    if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None