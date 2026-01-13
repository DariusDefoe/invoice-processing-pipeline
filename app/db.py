import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_cnx():
    """Return a new MySQL connection using environment variables."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "vat_user"),
        password=os.getenv("DB_PASS", "ChangeMeUser!"),
        database=os.getenv("DB_NAME", "vat_refunder"),
        autocommit=False,  # better control; handle commits explicitly
    )
