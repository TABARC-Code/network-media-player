from app import create_app

app = create_app()

if __name__ == "__main__":
    # Threaded: Flask needs to serve the UI while playback and artwork requests happen.
    app.run(host="0.0.0.0", port=5000, threaded=True)
