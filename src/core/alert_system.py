"""
MULTI-CHANNEL ALERT SYSTEM
Desktop, Email, SMS, Discord Notifications
Built for: Travis @ Trav's Trader Lounge

Alert channels by priority:
- LOW: Log only
- MEDIUM: Desktop notification
- HIGH: Desktop + Email + Discord
- CRITICAL: All channels including SMS
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable
from enum import Enum
import threading
import queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = 1         # Log only
    MEDIUM = 2      # Desktop
    HIGH = 3        # Desktop + Email + Discord
    CRITICAL = 4    # All channels including SMS


class AlertType(Enum):
    """Types of alerts"""
    PRICE = "price"
    REGIME_CHANGE = "regime_change"
    POSITION_PNL = "position_pnl"
    RISK_WARNING = "risk_warning"
    TRADE_SIGNAL = "trade_signal"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class Alert:
    """Alert data structure"""
    alert_id: str
    timestamp: datetime
    priority: AlertPriority
    alert_type: AlertType
    title: str
    message: str
    symbol: Optional[str] = None
    data: Dict = field(default_factory=dict)
    channels_sent: List[str] = field(default_factory=list)
    acknowledged: bool = False


class DesktopNotifier:
    """Desktop notification handler"""

    def __init__(self):
        self.enabled = True
        self._check_availability()

    def _check_availability(self):
        """Check if desktop notifications are available"""
        try:
            # Try Windows toast notifications
            from win10toast import ToastNotifier
            self.notifier = ToastNotifier()
            self.backend = "win10toast"
        except ImportError:
            try:
                # Try plyer as fallback
                from plyer import notification
                self.notifier = notification
                self.backend = "plyer"
            except ImportError:
                logger.warning("No desktop notification library available")
                self.enabled = False
                self.backend = None

    def send(self, title: str, message: str, timeout: int = 10) -> bool:
        """Send desktop notification"""
        if not self.enabled:
            logger.info(f"Desktop (disabled): {title}")
            return False

        try:
            if self.backend == "win10toast":
                self.notifier.show_toast(
                    title,
                    message,
                    duration=timeout,
                    threaded=True
                )
            elif self.backend == "plyer":
                self.notifier.notify(
                    title=title,
                    message=message,
                    timeout=timeout
                )

            logger.info(f"Desktop notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Desktop notification failed: {e}")
            return False


class EmailNotifier:
    """Email notification handler"""

    def __init__(
        self,
        smtp_server: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_email: str = "",
        to_email: str = ""
    ):
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "")
        self.smtp_port = smtp_port
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.from_email = from_email or os.getenv("EMAIL_FROM", "")
        self.to_email = to_email or os.getenv("EMAIL_TO", "")

        self.enabled = bool(self.smtp_server and self.username and self.password)

    def send(self, subject: str, body: str, html: bool = False) -> bool:
        """Send email notification"""
        if not self.enabled:
            logger.info(f"Email (disabled): {subject}")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[Trading Alert] {subject}"
            msg["From"] = self.from_email
            msg["To"] = self.to_email

            if html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info(f"Email sent: {subject}")
            return True

        except Exception as e:
            logger.error(f"Email failed: {e}")
            return False


class DiscordNotifier:
    """Discord webhook notification handler"""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK", "")
        self.enabled = bool(self.webhook_url)

    def send(
        self,
        title: str,
        message: str,
        color: int = 0x00FF00,
        fields: Optional[List[Dict]] = None
    ) -> bool:
        """Send Discord notification via webhook"""
        if not self.enabled:
            logger.info(f"Discord (disabled): {title}")
            return False

        try:
            import requests

            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }

            if fields:
                embed["fields"] = fields

            payload = {"embeds": [embed]}

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            logger.info(f"Discord notification sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return False


class SMSNotifier:
    """SMS notification handler using Twilio"""

    def __init__(
        self,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
        to_number: str = ""
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_SID", "")
        self.auth_token = auth_token or os.getenv("TWILIO_TOKEN", "")
        self.from_number = from_number or os.getenv("TWILIO_FROM", "")
        self.to_number = to_number or os.getenv("SMS_TO", "")

        self.enabled = bool(
            self.account_sid and self.auth_token and
            self.from_number and self.to_number
        )

    def send(self, message: str) -> bool:
        """Send SMS via Twilio"""
        if not self.enabled:
            logger.info(f"SMS (disabled): {message[:50]}...")
            return False

        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)

            sms = client.messages.create(
                body=message[:160],  # SMS limit
                from_=self.from_number,
                to=self.to_number
            )

            logger.info(f"SMS sent: {sms.sid}")
            return True

        except Exception as e:
            logger.error(f"SMS failed: {e}")
            return False


class AlertSystem:
    """
    Central alert management system.

    Routes alerts to appropriate channels based on priority.
    Handles rate limiting and deduplication.
    """

    PRIORITY_COLORS = {
        AlertPriority.LOW: 0x808080,      # Gray
        AlertPriority.MEDIUM: 0x0000FF,   # Blue
        AlertPriority.HIGH: 0xFFA500,     # Orange
        AlertPriority.CRITICAL: 0xFF0000  # Red
    }

    def __init__(
        self,
        enable_desktop: bool = True,
        enable_email: bool = True,
        enable_discord: bool = True,
        enable_sms: bool = False
    ):
        # Initialize notifiers
        self.desktop = DesktopNotifier() if enable_desktop else None
        self.email = EmailNotifier() if enable_email else None
        self.discord = DiscordNotifier() if enable_discord else None
        self.sms = SMSNotifier() if enable_sms else None

        # Alert history
        self._alerts: List[Alert] = []
        self._alert_counter = 0

        # Rate limiting
        self._last_alert_time: Dict[str, datetime] = {}
        self._rate_limit_seconds = 60  # Min seconds between similar alerts

        # Callbacks
        self._callbacks: List[Callable[[Alert], None]] = []

        logger.info("Alert System initialized")

    @classmethod
    def from_config(cls, config) -> "AlertSystem":
        """Create AlertSystem from unified Config object."""
        return cls(
            enable_desktop=config.alerts.enable_desktop,
            enable_email=config.alerts.enable_email,
            enable_discord=config.alerts.enable_discord,
            enable_sms=config.alerts.enable_sms,
        )

    def add_callback(self, callback: Callable[[Alert], None]):
        """Add callback function to be called on each alert"""
        self._callbacks.append(callback)

    def send_alert(
        self,
        priority: AlertPriority,
        alert_type: AlertType,
        title: str,
        message: str,
        symbol: Optional[str] = None,
        data: Optional[Dict] = None,
        force: bool = False
    ) -> Alert:
        """
        Send alert through appropriate channels.

        Args:
            priority: Alert priority level
            alert_type: Type of alert
            title: Alert title
            message: Alert message
            symbol: Related symbol (optional)
            data: Additional data (optional)
            force: Bypass rate limiting

        Returns:
            Alert object
        """
        # Generate alert ID
        self._alert_counter += 1
        alert_id = f"ALT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._alert_counter:04d}"

        # Create alert object
        alert = Alert(
            alert_id=alert_id,
            timestamp=datetime.now(),
            priority=priority,
            alert_type=alert_type,
            title=title,
            message=message,
            symbol=symbol,
            data=data or {}
        )

        # Rate limiting check
        rate_key = f"{alert_type.value}:{symbol or 'global'}:{title}"

        if not force and rate_key in self._last_alert_time:
            elapsed = (datetime.now() - self._last_alert_time[rate_key]).seconds
            if elapsed < self._rate_limit_seconds:
                logger.debug(f"Rate limited: {title}")
                return alert

        self._last_alert_time[rate_key] = datetime.now()

        # Log all alerts
        log_message = f"[{priority.name}] {alert_type.value}: {title} - {message}"
        if priority == AlertPriority.CRITICAL:
            logger.critical(log_message)
        elif priority == AlertPriority.HIGH:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Route to channels based on priority
        channels_sent = []

        if priority.value >= AlertPriority.MEDIUM.value:
            if self.desktop and self.desktop.send(title, message):
                channels_sent.append("desktop")

        if priority.value >= AlertPriority.HIGH.value:
            if self.email and self.email.send(title, message):
                channels_sent.append("email")

            if self.discord:
                color = self.PRIORITY_COLORS.get(priority, 0x000000)
                fields = []

                if symbol:
                    fields.append({"name": "Symbol", "value": symbol, "inline": True})

                fields.append({"name": "Priority", "value": priority.name, "inline": True})
                fields.append({"name": "Type", "value": alert_type.value, "inline": True})

                if self.discord.send(title, message, color, fields):
                    channels_sent.append("discord")

        if priority == AlertPriority.CRITICAL:
            if self.sms and self.sms.send(f"{title}: {message}"):
                channels_sent.append("sms")

        alert.channels_sent = channels_sent

        # Store alert
        self._alerts.append(alert)

        # Execute callbacks
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        return alert

    # Convenience methods for common alert types
    def price_alert(
        self,
        symbol: str,
        price: float,
        condition: str,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> Alert:
        """Send price alert"""
        return self.send_alert(
            priority=priority,
            alert_type=AlertType.PRICE,
            title=f"{symbol} Price Alert",
            message=f"{symbol} {condition} at ${price:.2f}",
            symbol=symbol,
            data={"price": price, "condition": condition}
        )

    def regime_change_alert(
        self,
        old_regime: str,
        new_regime: str,
        priority: AlertPriority = AlertPriority.HIGH
    ) -> Alert:
        """Send regime change alert"""
        return self.send_alert(
            priority=priority,
            alert_type=AlertType.REGIME_CHANGE,
            title="Market Regime Change",
            message=f"Regime changed from {old_regime} to {new_regime}",
            data={"old_regime": old_regime, "new_regime": new_regime}
        )

    def pnl_alert(
        self,
        symbol: str,
        pnl: float,
        pnl_pct: float,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> Alert:
        """Send P&L alert"""
        direction = "up" if pnl > 0 else "down"
        return self.send_alert(
            priority=priority,
            alert_type=AlertType.POSITION_PNL,
            title=f"{symbol} P&L Alert",
            message=f"{symbol} {direction} ${abs(pnl):.2f} ({pnl_pct:+.1f}%)",
            symbol=symbol,
            data={"pnl": pnl, "pnl_pct": pnl_pct}
        )

    def risk_warning(
        self,
        warning_type: str,
        message: str,
        priority: AlertPriority = AlertPriority.HIGH
    ) -> Alert:
        """Send risk warning"""
        return self.send_alert(
            priority=priority,
            alert_type=AlertType.RISK_WARNING,
            title=f"Risk Warning: {warning_type}",
            message=message,
            data={"warning_type": warning_type}
        )

    def trade_signal(
        self,
        symbol: str,
        signal_type: str,
        details: str,
        priority: AlertPriority = AlertPriority.MEDIUM
    ) -> Alert:
        """Send trade signal alert"""
        return self.send_alert(
            priority=priority,
            alert_type=AlertType.TRADE_SIGNAL,
            title=f"Trade Signal: {symbol}",
            message=f"{signal_type} - {details}",
            symbol=symbol,
            data={"signal_type": signal_type}
        )

    def get_recent_alerts(
        self,
        count: int = 10,
        priority: Optional[AlertPriority] = None,
        alert_type: Optional[AlertType] = None
    ) -> List[Alert]:
        """Get recent alerts with optional filters"""
        alerts = self._alerts

        if priority:
            alerts = [a for a in alerts if a.priority == priority]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        return alerts[-count:]


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ALERT SYSTEM TEST")
    print("=" * 60)

    # Initialize alert system
    alerts = AlertSystem(
        enable_desktop=True,
        enable_email=False,   # Disabled for testing
        enable_discord=False,  # Disabled for testing
        enable_sms=False
    )

    # Test alerts at different priorities
    print("\nSending test alerts...")

    alerts.send_alert(
        priority=AlertPriority.LOW,
        alert_type=AlertType.SYSTEM,
        title="System Started",
        message="Trading system initialized successfully"
    )

    alerts.price_alert(
        symbol="SPY",
        price=510.50,
        condition="broke above resistance"
    )

    alerts.regime_change_alert(
        old_regime="POSITIVE_GAMMA",
        new_regime="NEGATIVE_GAMMA"
    )

    alerts.risk_warning(
        warning_type="Portfolio Heat",
        message="Portfolio heat at 18% - approaching 20% limit",
        priority=AlertPriority.HIGH
    )

    alerts.trade_signal(
        symbol="NVDA",
        signal_type="MTF Confluence",
        details="5 timeframes aligned bullish, score 85/100"
    )

    # Show recent alerts
    print("\nRecent Alerts:")
    for alert in alerts.get_recent_alerts(5):
        print(f"  [{alert.priority.name}] {alert.title}")
        print(f"    {alert.message}")
        print(f"    Channels: {', '.join(alert.channels_sent) or 'log only'}")
        print()


# Aliases for cross-codebase compatibility
AlertLevel = AlertPriority  # Gamma_Backtest used AlertLevel
