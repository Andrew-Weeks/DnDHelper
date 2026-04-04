import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    cert_file = 'cert.pem'
    key_file = 'key.pem'
    ssl_context = (cert_file, key_file) if os.path.exists(cert_file) and os.path.exists(key_file) else None

    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=ssl_context)
