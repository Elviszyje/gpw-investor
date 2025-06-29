"""
Notifications Blueprint - zarządzanie powiadomieniami i alertami
Obsługuje: telegram notifications, price alerts, notification management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import logging

notifications_bp = Blueprint('notifications', __name__)
logger = logging.getLogger(__name__)

# =============================================================================
# TELEGRAM NOTIFICATIONS MANAGEMENT ENDPOINTS
# =============================================================================

@notifications_bp.route("/notifications/telegram")
def telegram_notifications():
    """Panel zarządzania powiadomieniami Telegram"""
    try:
        from telegram_notifications import TelegramNotificationManager
        telegram_manager = TelegramNotificationManager()
        
        # Pobierz dane
        subscriptions = telegram_manager.get_subscriptions()
        notification_types = telegram_manager.get_notification_types()
        notification_history = telegram_manager.get_notification_history(limit=50)
        bot_status = telegram_manager.test_connection()
        
        # Oblicz aktywne subskrypcje
        active_subscriptions = len([s for s in subscriptions if s['is_active']])
        
        return render_template(
            "telegram_notifications.html",
            subscriptions=subscriptions,
            notification_types=notification_types,
            notification_history=notification_history,
            bot_status=bot_status,
            active_subscriptions=active_subscriptions
        )
        
    except Exception as e:
        flash(f"❌ Błąd ładowania powiadomień: {e}", "danger")
        return redirect(url_for('index'))

@notifications_bp.route("/notifications/telegram/test")
def test_telegram():
    """Test połączenia z Telegram Bot API"""
    try:
        from telegram_notifications import TelegramNotificationManager
        telegram_manager = TelegramNotificationManager()
        test_result = telegram_manager.test_connection()
        
        if test_result['success']:
            flash(f"✅ {test_result['message']}", "success")
        else:
            flash(f"❌ {test_result['error']}", "danger")
            
    except Exception as e:
        flash(f"❌ Błąd testu połączenia: {e}", "danger")
    
    return redirect(url_for('notifications.telegram_notifications'))

@notifications_bp.route("/notifications/telegram/send-test", methods=["POST"])
def send_test_notification():
    """Wysyła testową wiadomość Telegram"""
    try:
        from telegram_notifications import TelegramNotificationManager
        telegram_manager = TelegramNotificationManager()
        
        chat_id = request.form.get('chat_id')
        title = request.form.get('title')
        message = request.form.get('message')
        notification_type = request.form.get('notification_type', 'system_alert')
        
        if not chat_id or not message:
            flash("❌ Wymagane: Chat ID i wiadomość", "danger")
            return redirect(url_for('notifications.telegram_notifications'))
        
        success = telegram_manager.send_message(
            chat_id=chat_id,
            message=message,
            title=title or "",
            notification_type=notification_type,
            ticker="TEST"
        )
        
        if success:
            flash(f"✅ Testowa wiadomość wysłana do {chat_id}", "success")
        else:
            flash(f"❌ Błąd wysyłania wiadomości do {chat_id}", "danger")
            
    except Exception as e:
        flash(f"❌ Błąd wysyłania testowej wiadomości: {e}", "danger")
    
    return redirect(url_for('notifications.telegram_notifications'))

@notifications_bp.route("/notifications/telegram/add-subscription", methods=["POST"])
def add_subscription():
    """Dodaje nową subskrypcję"""
    try:
        from telegram_notifications import TelegramNotificationManager
        telegram_manager = TelegramNotificationManager()
        
        chat_id = request.form.get('chat_id')
        username = request.form.get('username')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        if not chat_id:
            flash("❌ Wymagany Chat ID", "danger")
            return redirect(url_for('notifications.telegram_notifications'))
        
        success = telegram_manager.subscribe_chat(
            chat_id=chat_id,
            username=username or "",
            first_name=first_name or "",
            last_name=last_name or ""
        )
        
        if success:
            flash(f"✅ Subskrypcja dodana: {chat_id}", "success")
        else:
            flash(f"❌ Błąd dodawania subskrypcji", "danger")
            
    except Exception as e:
        flash(f"❌ Błąd dodawania subskrypcji: {e}", "danger")
    
    return redirect(url_for('notifications.telegram_notifications'))

@notifications_bp.route("/notifications/telegram/toggle-subscription", methods=["POST"])
def toggle_subscription():
    """Aktywuje/dezaktywuje subskrypcję"""
    try:
        from telegram_notifications import TelegramNotificationManager
        telegram_manager = TelegramNotificationManager()
        
        chat_id = request.form.get('chat_id')
        action = request.form.get('action')
        
        if not chat_id or not action:
            flash("❌ Brak wymaganych parametrów", "danger")
            return redirect(url_for('notifications.telegram_notifications'))
        
        if action == 'deactivate':
            success = telegram_manager.unsubscribe_chat(chat_id)
            message = "dezaktywowana" if success else "błąd dezaktywacji"
        else:
            success = telegram_manager.subscribe_chat(chat_id)
            message = "aktywowana" if success else "błąd aktywacji"
        
        if success:
            flash(f"✅ Subskrypcja {chat_id} {message}", "success")
        else:
            flash(f"❌ Błąd zmiany statusu subskrypcji", "danger")
            
    except Exception as e:
        flash(f"❌ Błąd zmiany statusu subskrypcji: {e}", "danger")
    
    return redirect(url_for('notifications.telegram_notifications'))

# =============================================================================
# PRICE ALERTS MANAGEMENT ENDPOINTS
# =============================================================================

@notifications_bp.route("/alerts/price")
def price_alerts():
    """Panel zarządzania alertami cenowymi"""
    try:
        from price_alerts import PriceAlertSystem
        from ticker_manager import TickerManager
        
        alert_system = PriceAlertSystem()
        ticker_manager = TickerManager()
        
        # Pobierz dane
        active_alerts = alert_system.get_active_alerts()
        alert_history = alert_system.get_alert_history(20)
        available_tickers = ticker_manager.get_all_tickers(active_only=True)
        
        # Statystyki
        triggered_alerts = len([a for a in active_alerts if a['is_triggered']])
        
        return render_template(
            "price_alerts.html",
            active_alerts=active_alerts,
            alert_history=alert_history,
            available_tickers=available_tickers,
            triggered_alerts=triggered_alerts,
            last_check=datetime.now()
        )
        
    except Exception as e:
        flash(f"❌ Błąd ładowania alertów: {e}", "danger")
        return redirect(url_for('index'))

@notifications_bp.route("/alerts/price/create", methods=["POST"])
def create_price_alert():
    """Tworzy nowy alert cenowy"""
    try:
        from price_alerts import PriceAlertSystem
        
        alert_system = PriceAlertSystem()
        
        ticker = request.form.get('ticker')
        alert_type = request.form.get('alert_type')
        threshold_value = request.form.get('threshold_value')
        description = request.form.get('description')
        
        if not ticker or not alert_type or not threshold_value:
            flash("❌ Wymagane: Ticker, typ alertu i wartość progu", "danger")
            return redirect(url_for('notifications.price_alerts'))
        
        try:
            threshold_value = float(threshold_value)
        except ValueError:
            flash("❌ Nieprawidłowa wartość progu", "danger")
            return redirect(url_for('notifications.price_alerts'))
        
        alert_id = alert_system.create_price_alert(
            ticker=ticker,
            alert_type=alert_type,
            threshold_value=threshold_value,
            description=description or ""
        )
        
        if alert_id > 0:
            flash(f"✅ Alert cenowy utworzony dla {ticker}", "success")
        else:
            flash(f"❌ Błąd tworzenia alertu dla {ticker}", "danger")
            
    except Exception as e:
        flash(f"❌ Błąd tworzenia alertu: {e}", "danger")
    
    return redirect(url_for('notifications.price_alerts'))

@notifications_bp.route("/alerts/price/delete", methods=["POST"])
def delete_price_alert():
    """Usuwa alert cenowy"""
    try:
        from price_alerts import PriceAlertSystem
        
        alert_system = PriceAlertSystem()
        
        alert_id = request.form.get('alert_id')
        
        if not alert_id:
            flash("❌ Brak ID alertu", "danger")
            return redirect(url_for('notifications.price_alerts'))
        
        try:
            alert_id = int(alert_id)
        except ValueError:
            flash("❌ Nieprawidłowe ID alertu", "danger")
            return redirect(url_for('notifications.price_alerts'))
        
        success = alert_system.delete_alert(alert_id)
        
        if success:
            flash(f"✅ Alert usunięty", "success")
        else:
            flash(f"❌ Błąd usuwania alertu", "danger")
            
    except Exception as e:
        flash(f"❌ Błąd usuwania alertu: {e}", "danger")
    
    return redirect(url_for('notifications.price_alerts'))

@notifications_bp.route("/alerts/price/check")
def check_price_alerts():
    """Sprawdza wszystkie alerty cenowe"""
    try:
        from price_alerts import PriceAlertSystem
        
        alert_system = PriceAlertSystem()
        result = alert_system.check_alerts()
        
        if 'error' in result:
            flash(f"❌ Błąd sprawdzania alertów: {result['error']}", "danger")
        else:
            flash(f"✅ Sprawdzono {result['checked']} alertów, triggered: {result['triggered']}", "success")
            
    except Exception as e:
        flash(f"❌ Błąd sprawdzania alertów: {e}", "danger")
    
    return redirect(url_for('notifications.price_alerts'))

@notifications_bp.route("/alerts/price/test")
def test_price_alert():
    """Testuje alert cenowy (demo)"""
    try:
        from price_alerts import PriceAlertSystem
        
        alert_system = PriceAlertSystem()
        
        # Wyślij testowe powiadomienie
        alert_system.telegram_manager.broadcast_message(
            message="To jest testowy alert cenowy z systemu GPW Investor.\n\nSymulacja: Cena PKN przekroczyła próg 100 PLN\nAktualna cena: 105.50 PLN",
            title="🚨 TEST - Alert Cenowy PKN",
            notification_type='price_alert',
            ticker="PKN",
            metadata={'test': True, 'alert_type': 'above', 'trigger_price': 105.50}
        )
        
        flash("✅ Testowy alert wysłany", "success")
        
    except Exception as e:
        flash(f"❌ Błąd testowego alertu: {e}", "danger")
    
    return redirect(url_for('notifications.price_alerts'))

# =============================================================================
# API ENDPOINTS
# =============================================================================

@notifications_bp.route("/api/notifications/telegram/broadcast", methods=["POST"])
def api_broadcast_notification():
    """API - Wysyła broadcast powiadomienia"""
    try:
        from telegram_notifications import TelegramNotificationManager
        telegram_manager = TelegramNotificationManager()
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych JSON'}), 400
        
        message = data.get('message')
        title = data.get('title')
        notification_type = data.get('notification_type', 'system_alert')
        ticker = data.get('ticker')
        metadata = data.get('metadata')
        
        if not message:
            return jsonify({'success': False, 'error': 'Brak wiadomości'}), 400
        
        result = telegram_manager.broadcast_message(
            message=message,
            title=title,
            notification_type=notification_type,
            ticker=ticker,
            metadata=metadata
        )
        
        return jsonify({
            'success': True,
            'sent': result['sent'],
            'failed': result['failed'],
            'message': f"Wysłano do {result['sent']} subskrybentów, błędów: {result['failed']}"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@notifications_bp.route("/api/alerts/price/check", methods=["POST"])
def api_check_price_alerts():
    """API - Sprawdza alerty cenowe"""
    try:
        from price_alerts import PriceAlertSystem
        
        alert_system = PriceAlertSystem()
        result = alert_system.check_alerts()
        
        return jsonify({
            'success': True,
            'checked': result.get('checked', 0),
            'triggered': result.get('triggered', 0),
            'timestamp': result.get('timestamp', datetime.now().isoformat()),
            'message': f"Sprawdzono {result.get('checked', 0)} alertów, triggered: {result.get('triggered', 0)}"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
