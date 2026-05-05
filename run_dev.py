from app import create_app

app = create_app()

if __name__ == '__main__':
    # HTTP (no SSL) for mobile app development.
    # React Native rejects self-signed certs, so use this instead of run.py
    # when testing with Expo Go on a phone.
    app.run(host='0.0.0.0', port=5000, debug=True)
