"""
Data Operations Blueprint - podstawowe operacje na danych giełdowych
Obsługuje: quotes daily, quotes intraday, rules, basic data views
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from workers.quotes_daily import save_daily_quotes, get_daily_quotes
from workers.quotes_intraday import save_intraday_quotes
from workers.rule_alert import detect_price_drop_alert
from workers.bankier_scraper import BankierScraper
from utils.error_handlers import (
    handle_db_errors, get_companies_safe, get_daily_quotes_safe, 
    get_intraday_quotes_safe, format_error_message
)

data_ops_bp = Blueprint('data_ops', __name__)

@data_ops_bp.route("/run/daily", methods=["GET", "POST"])
@handle_db_errors(fallback_template="run_daily.html", fallback_data={"companies": []})
def run_daily():
    companies = get_companies_safe()
    if request.method == "POST":
        ticker = request.form.get("ticker")
        new_ticker = request.form.get("new_ticker")
        ticker = new_ticker.strip().upper() if new_ticker else ticker
        if not ticker:
            flash("❌ Nie wybrano ani nie wpisano spółki.", "danger")
            return render_template("run_daily.html", companies=companies)
        try:
            rows = save_daily_quotes(ticker)
            if rows > 0:
                flash(f"✅ Dane dzienne dla {ticker} zostały poprawnie załadowane ({rows} wierszy).", "success")
            else:
                flash(f"⚠️ Brak nowych danych do załadowania lub wystąpił błąd dla {ticker}.", "warning")
        except Exception as e:
            error_msg = format_error_message('import_error', str(e))
            flash(f"❌ {error_msg}", "danger")
        return redirect(url_for('index'))
    return render_template("run_daily.html", companies=companies)

@data_ops_bp.route("/run/intraday", methods=["GET", "POST"])
@handle_db_errors(fallback_template="run_intraday.html", fallback_data={"companies": []})
def run_intraday():
    companies = get_companies_safe()
    if request.method == "POST":
        ticker = request.form.get("ticker")
        new_ticker = request.form.get("new_ticker")
        ticker = new_ticker.strip().upper() if new_ticker else ticker
        if not ticker:
            flash("❌ Nie wybrano ani nie wpisano spółki.", "danger")
            return render_template("run_intraday.html", companies=companies)
        try:
            # Użyj scrapera Bankier.pl do pobrania danych
            scraper = BankierScraper(use_selenium=True, headless=True)
            result = scraper.scrape_single_ticker(ticker)
            scraper.close()
            
            if result and result.get('price'):
                # Zapisz do bazy przez scraper (już zrobione w scrape_single_ticker)
                flash(f"✅ Dane intraday dla {ticker} zostały pobrane z Bankier.pl: {result['price']} PLN", "success")
            else:
                flash(f"⚠️ Nie udało się pobrać danych intraday dla {ticker} z Bankier.pl.", "warning")
        except Exception as e:
            flash(f"❌ Błąd podczas scrapowania danych intraday: {e}", "danger")
        return redirect(url_for('index'))
    return render_template("run_intraday.html", companies=companies)

@data_ops_bp.route("/run/rules")
def run_rules():
    try:
        detect_price_drop_alert("CDR")
        flash("✅ Reguły inwestycyjne zostały uruchomione.", "success")
    except Exception as e:
        flash(f"❌ Błąd podczas uruchamiania reguł: {e}", "danger")
    return redirect(url_for('index'))

@data_ops_bp.route("/dane", methods=["GET", "POST"])
@handle_db_errors(fallback_template="data.html", fallback_data={"companies": [], "selected": None, "data": []})
def show_data():
    companies = get_companies_safe()
    selected = request.form.get("ticker") if request.method == "POST" else None
    data = get_daily_quotes_safe(selected) if selected else []
    return render_template("data.html", companies=companies, selected=selected, data=data)

@data_ops_bp.route("/intraday", methods=["GET", "POST"])
@handle_db_errors(fallback_template="intraday.html", fallback_data={"companies": [], "selected": None, "data": []})
def show_intraday():
    companies = get_companies_safe()
    selected = request.form.get("ticker") if request.method == "POST" else None
    data = get_intraday_quotes_safe(selected) if selected else []
    return render_template("intraday.html", companies=companies, selected=selected, data=data)

@data_ops_bp.route("/dane_intraday", methods=["GET", "POST"])
@handle_db_errors(fallback_template="data_intraday.html", fallback_data={"companies": [], "selected": None, "data": []})
def show_intraday_data():
    companies = get_companies_safe()
    selected = request.form.get("ticker") if request.method == "POST" else None
    data = get_intraday_quotes_safe(selected) if selected else []
    return render_template("data_intraday.html", companies=companies, selected=selected, data=data)
