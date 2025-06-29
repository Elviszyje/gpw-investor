# GPW Investor - Dockerfile
FROM python:3.11-slim

# Ustaw zmienne środowiskowe
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Ustaw katalog roboczy
WORKDIR /app

# Zainstaluj zależności systemowe
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    libpq-dev \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome and dependencies for Selenium (platform-specific)
RUN ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then \
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
        && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
        && apt-get update \
        && apt-get install -y google-chrome-stable \
        && rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Skipping Chrome installation on non-amd64 architecture: $ARCH" \
        && echo "Note: Selenium scrapers may not work without Chrome"; \
    fi

# Install ChromeDriver (only for amd64) - Updated for modern Chrome versions
RUN ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then \
        CHROME_VERSION=$(google-chrome --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1) \
        && CHROME_MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d. -f1) \
        && echo "Chrome version: $CHROME_VERSION (major: $CHROME_MAJOR_VERSION)" \
        && if [ "$CHROME_MAJOR_VERSION" -ge "115" ]; then \
            echo "Using Chrome for Testing API for ChromeDriver" \
            && CHROMEDRIVER_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" \
                | grep -A 10 -B 10 "\"version\": \"$CHROME_VERSION\"" \
                | grep -A 5 "\"platform\": \"linux64\"" \
                | grep "\"chromedriver\"" \
                | grep -o "https://[^\"]*chromedriver-linux64.zip" | head -1) \
            && if [ -n "$CHROMEDRIVER_URL" ]; then \
                echo "Downloading ChromeDriver from: $CHROMEDRIVER_URL" \
                && wget -O /tmp/chromedriver.zip "$CHROMEDRIVER_URL" \
                && unzip /tmp/chromedriver.zip -d /tmp/ \
                && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
                && chmod +x /usr/local/bin/chromedriver \
                && rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64; \
            else \
                echo "ChromeDriver URL not found, trying latest stable" \
                && LATEST_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE") \
                && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${LATEST_VERSION}/chromedriver_linux64.zip" \
                && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
                && chmod +x /usr/local/bin/chromedriver \
                && rm /tmp/chromedriver.zip; \
            fi; \
        else \
            echo "Using legacy ChromeDriver API for older Chrome" \
            && CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR_VERSION}") \
            && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" \
            && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
            && chmod +x /usr/local/bin/chromedriver \
            && rm /tmp/chromedriver.zip; \
        fi \
        && echo "ChromeDriver installed successfully" \
        && chromedriver --version; \
    else \
        echo "Skipping ChromeDriver installation on non-amd64 architecture: $ARCH"; \
    fi

# Skopiuj requirements.txt i zainstaluj zależności Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dodaj dodatkowe zależności dla konteneryzacji
RUN pip install --no-cache-dir psutil gunicorn

# Skopiuj kod aplikacji
COPY . .

# Utwórz katalogi dla logów i danych
RUN mkdir -p /app/logs /app/data /app/storage/articles /app/models

# Ustaw zmienne środowiskowe
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Ustaw użytkownika non-root dla bezpieczeństwa
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Eksponuj port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/app/health || exit 1

# Skopiuj i ustaw skrypt entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
USER root
RUN chmod +x /docker-entrypoint.sh
USER app

# Ustaw entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Domyślna komenda
CMD ["python", "app.py"]
