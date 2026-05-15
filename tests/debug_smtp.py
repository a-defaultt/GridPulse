import smtplib
from src.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

def debug_smtp():
    print(f"Testing SMTP: {SMTP_HOST}:{SMTP_PORT}")
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        print("SMTP Handshake successful!")
        server.quit()
    except Exception as e:
        print(f"SMTP Error: {e}")

if __name__ == "__main__":
    debug_smtp()
