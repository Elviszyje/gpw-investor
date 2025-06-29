
# 🚀 Przewodnik Implementacji - Mała Produkcja

## 📋 Przegląd Konfiguracji
**Profil:** small_production
**Opis:** Małe firmy, osoby prywatne
**Generowany:** 2025-06-27 00:06:14

## 🎯 Ograniczenia i Cele
- **Maksymalne tickery:** 30
- **Maksymalni użytkownicy:** 10
- **Artykuły dziennie:** 1000

## ⚙️ Konfiguracja Schedulerów
```python
# Interwały scrapowania
MULTI_TICKER_INTERVAL = 3  # minuty
NEWS_INTERVAL = 30  # minuty
ESPI_INTERVAL = 1  # godziny
ANALYSIS_INTERVAL = 60  # minuty
```

## 🔧 Zasoby Systemowe
```python
# Threading i przetwarzanie
MAX_THREADS = 12
SELENIUM_INSTANCES = 2
DB_CONNECTIONS = 10
WORKER_PROCESSES = 1
```

## 🛠️ Kroki Implementacji

### 1. Aktualizacja Konfiguracji Schedulerów
```bash
# Edytuj tickers_config.json
python -c "
import json
config = {
    'scraping_settings': {
        'interval_minutes': 3,
        'use_selenium': True,
        'headless': True
    }
}
with open('tickers_config.json', 'w') as f:
    json.dump(config, f, indent=2)
"
```

### 2. Konfiguracja Bazy Danych
```python
# Aktualizuj connection pool w workers/
DATABASE_CONFIG = {
    'max_connections': 10,
    'pool_size': 10,
    'pool_timeout': 30
}
```

### 3. Funkcje do Włączenia


## 📊 Monitoring i Alerty
```bash
# Uruchom monitor wydajności
python performance_monitor.py

# Sprawdź metryki
tail -f storage/performance_metrics.json
```

## 🚨 Krytyczne Metryki do Monitorowania
- **Thready:** Max 12, Alert >80%
- **DB Queries:** Alert >500ms
- **Schedulery:** Alert jeśli <100% uptime
- **Memory:** Alert >80% RAM

## 🔧 Troubleshooting

### Problem: Wolne scrapowanie
```bash
# Zwiększ selenium instances
SELENIUM_INSTANCES = 3

# Zmniejsz delay między requestami
SCRAPING_DELAY = 1
```

### Problem: Wysokie CPU
```bash
# Zwiększ interwały
MULTI_TICKER_INTERVAL = 4
NEWS_INTERVAL = 45
```

### Problem: Błędy bazy danych
```bash
# Zwiększ connection pool
DB_CONNECTIONS = 15
POOL_TIMEOUT = 60
```

## ✅ Checklist Implementacji
- [ ] Zaktualizowana konfiguracja schedulerów
- [ ] Dostosowane limity zasobów
- [ ] Włączone odpowiednie funkcje
- [ ] Skonfigurowany monitoring
- [ ] Przetestowane pod obciążeniem
- [ ] Wdrożone alerty
- [ ] Backup i recovery plan

## 📈 Kolejne Kroki Optymalizacji

1. Rozważenie Redis cache przy >1000 artykułów/dzień
2. Separacja procesów przy >20 użytkownikach
3. Przejście na 'medium_production' przy >30 tickerów

---
*Konfiguracja wygenerowana automatycznie przez GPW Investor Performance Configurator*
