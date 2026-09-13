Run code in order:
    pip install -r requirements.txt
    python -m nltk.downloader punkt punkt_tab
    SSL_CERT_FILE=$(python -m certifi) python -m nltk.downloader punkt punkt_tab