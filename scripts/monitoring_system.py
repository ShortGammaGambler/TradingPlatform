"""
Trading System Monitoring & Alerting - Production Version
=========================================================

Comprehensive monitoring and alerting for live trading systems.

Features:
- Multi-channel alerts (console, file, email, SMS, Slack)
- Alert throttling (prevent spam)
- Health checks with thresholds
- Metrics tracking and storage
- Dashboard data generation
- Historical analysis

Author: Built for production trading
"""

import os
import json
import time
import logging
import smtplib
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import deque, defaultdict
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Alert levels
class AlertLevel:
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

# Alert throttling (seconds between same alert)
ALERT_THROTTLE_SECONDS = {
    AlertLevel.INFO: 300,      # 5 minutes
    AlertLevel.WARNING: 180,   # 3 minutes
    AlertLevel.CRITICAL: 60    # 1 minute
}

# Health check intervals
HEALTH_CHECK_INTERVAL = 60  # seconds

# Metrics retention
MAX_METRICS_HISTORY = 10000  # Keep last 10k data points

# File paths
DEFAULT_METRICS_FILE = "metrics_history.jsonl"
DEFAULT_ALERTS_FILE = "alerts_log.jsonl"
DEFAULT_HEALTH_FILE = "health_status.json"

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Alert:
    """Represents a system alert."""
    level: str
    category: str
    message: str
    timestamp: datetime
    details: Dict = None
    
    def to_dict(self):
        return {
            'level': self.level,
            'category': self.category,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details or {}
        }

@dataclass
class HealthCheck:
    """Health check result."""
    component: str
    status: str  # 'healthy', 'degraded', 'critical'
    message: str
    timestamp: datetime
    metrics: Dict = None

@dataclass
class SystemMetrics:
    """System performance metrics snapshot."""
    timestamp: datetime
    api_success_rate: float
    api_avg_latency_ms: float
    api_p95_latency_ms: float
    api_calls_per_minute: float
    circuit_breaker_state: str
    cache_hit_rate: float
    active_positions: int
    total_pnl: float
    risk_utilization_pct: float
    
    def to_dict(self):
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d

# =============================================================================
# ALERT CHANNELS
# =============================================================================

class AlertChannel:
    """Base class for alert channels."""
    
    def send(self, alert: Alert) -> bool:
        """Send alert. Return True if successful."""
        raise NotImplementedError

class ConsoleAlertChannel(AlertChannel):
    """Print alerts to console."""
    
    def send(self, alert: Alert) -> bool:
        emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨"
        }.get(alert.level, "")
        
        print(f"\n{emoji} [{alert.level}] {alert.category}")
        print(f"   {alert.message}")
        print(f"   {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if alert.details:
            print(f"   Details: {alert.details}")
        print()
        
        return True

class FileAlertChannel(AlertChannel):
    """Write alerts to file (JSONL format)."""
    
    def __init__(self, filepath: str = DEFAULT_ALERTS_FILE):
        self.filepath = filepath
        self._lock = threading.Lock()
    
    def send(self, alert: Alert) -> bool:
        try:
            with self._lock:
                with open(self.filepath, 'a') as f:
                    f.write(json.dumps(alert.to_dict()) + '\n')
            return True
        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")
            return False

class EmailAlertChannel(AlertChannel):
    """Send alerts via email (Gmail SMTP)."""
    
    def __init__(self, 
                 smtp_server: str = "smtp.gmail.com",
                 smtp_port: int = 587,
                 from_email: str = None,
                 from_password: str = None,
                 to_emails: List[str] = None):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.from_password = from_password
        self.to_emails = to_emails or []
        
        if not all([from_email, from_password, to_emails]):
            logger.warning("Email alerts not fully configured")
    
    def send(self, alert: Alert) -> bool:
        if not all([self.from_email, self.from_password, self.to_emails]):
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"[{alert.level}] Trading System Alert: {alert.category}"
            
            body = f"""
Trading System Alert

Level: {alert.level}
Category: {alert.category}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Message:
{alert.message}

Details:
{json.dumps(alert.details, indent=2) if alert.details else 'None'}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.from_email, self.from_password)
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {self.to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

class SMSAlertChannel(AlertChannel):
    """Send alerts via SMS (Twilio)."""
    
    def __init__(self,
                 account_sid: str = None,
                 auth_token: str = None,
                 from_number: str = None,
                 to_numbers: List[str] = None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.to_numbers = to_numbers or []
        
        if not all([account_sid, auth_token, from_number, to_numbers]):
            logger.warning("SMS alerts not fully configured")
    
    def send(self, alert: Alert) -> bool:
        if not all([self.account_sid, self.auth_token, self.from_number, self.to_numbers]):
            return False
        
        if not requests:
            logger.error("requests library required for SMS alerts")
            return False
        
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            
            message_body = f"[{alert.level}] {alert.category}: {alert.message}"
            
            for to_number in self.to_numbers:
                data = {
                    'From': self.from_number,
                    'To': to_number,
                    'Body': message_body[:160]  # SMS limit
                }
                
                response = requests.post(
                    url,
                    data=data,
                    auth=(self.account_sid, self.auth_token)
                )
                
                if response.status_code != 201:
                    logger.error(f"Failed to send SMS to {to_number}: {response.text}")
                    return False
            
            logger.info(f"SMS alert sent to {self.to_numbers}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
            return False

class SlackAlertChannel(AlertChannel):
    """Send alerts to Slack webhook."""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        
        if not webhook_url:
            logger.warning("Slack webhook not configured")
    
    def send(self, alert: Alert) -> bool:
        if not self.webhook_url or not requests:
            return False
        
        try:
            color = {
                AlertLevel.INFO: "#36a64f",      # Green
                AlertLevel.WARNING: "#ff9900",   # Orange
                AlertLevel.CRITICAL: "#ff0000"   # Red
            }.get(alert.level, "#808080")
            
            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"[{alert.level}] {alert.category}",
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Time",
                            "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            "short": True
                        }
                    ],
                    "footer": "Trading System Monitor",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            if alert.details:
                payload["attachments"][0]["fields"].append({
                    "title": "Details",
                    "value": f"```{json.dumps(alert.details, indent=2)}```",
                    "short": False
                })
            
            response = requests.post(self.webhook_url, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Slack webhook failed: {response.text}")
                return False
            
            logger.info("Slack alert sent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

# =============================================================================
# MONITORING SYSTEM
# =============================================================================

class MonitoringSystem:
    """
    Comprehensive monitoring and alerting system.
    
    Features:
    - Multi-channel alerts
    - Alert throttling
    - Health checks
    - Metrics tracking
    - Historical analysis
    """
    
    def __init__(self,
                 metrics_file: str = DEFAULT_METRICS_FILE,
                 alerts_file: str = DEFAULT_ALERTS_FILE,
                 health_file: str = DEFAULT_HEALTH_FILE):
        
        self.metrics_file = metrics_file
        self.alerts_file = alerts_file
        self.health_file = health_file
        
        # Alert channels
        self.channels: List[AlertChannel] = []
        self.add_channel(ConsoleAlertChannel())
        self.add_channel(FileAlertChannel(alerts_file))
        
        # Alert throttling
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_lock = threading.Lock()
        
        # Metrics history
        self.metrics_history: deque = deque(maxlen=MAX_METRICS_HISTORY)
        self._metrics_lock = threading.Lock()
        
        # Health checks
        self.health_checks: Dict[str, Callable] = {}
        self.last_health_status: Dict[str, HealthCheck] = {}
        
        # Background monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        
        logger.info("MonitoringSystem initialized")
    
    def add_channel(self, channel: AlertChannel):
        """Add an alert channel."""
        self.channels.append(channel)
        logger.info(f"Added alert channel: {channel.__class__.__name__}")
    
    def send_alert(self,
                   level: str,
                   category: str,
                   message: str,
                   details: Dict = None,
                   force: bool = False):
        """
        Send an alert through all channels.
        
        Args:
            level: AlertLevel (INFO, WARNING, CRITICAL)
            category: Alert category (e.g., 'API', 'RISK', 'POSITION')
            message: Alert message
            details: Additional details dict
            force: Skip throttling if True
        """
        alert = Alert(
            level=level,
            category=category,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
        
        # Check throttling
        if not force:
            throttle_key = f"{level}:{category}:{message}"
            
            with self._alert_lock:
                if throttle_key in self._last_alert_time:
                    last_time = self._last_alert_time[throttle_key]
                    throttle_duration = ALERT_THROTTLE_SECONDS.get(level, 300)
                    
                    if (datetime.now() - last_time).total_seconds() < throttle_duration:
                        logger.debug(f"Alert throttled: {throttle_key}")
                        return
                
                self._last_alert_time[throttle_key] = datetime.now()
        
        # Send through all channels
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception as e:
                logger.error(f"Alert channel {channel.__class__.__name__} failed: {e}")
    
    def record_metrics(self, metrics: SystemMetrics):
        """Record system metrics snapshot."""
        with self._metrics_lock:
            self.metrics_history.append(metrics)
        
        # Write to file
        try:
            with open(self.metrics_file, 'a') as f:
                f.write(json.dumps(metrics.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to write metrics: {e}")
    
    def register_health_check(self, 
                             component: str,
                             check_func: Callable[[], HealthCheck]):
        """
        Register a health check function.
        
        Args:
            component: Component name
            check_func: Function that returns HealthCheck
        """
        self.health_checks[component] = check_func
        logger.info(f"Registered health check: {component}")
    
    def run_health_checks(self) -> Dict[str, HealthCheck]:
        """
        Run all registered health checks.
        
        Returns:
            Dict of component -> HealthCheck results
        """
        results = {}
        
        for component, check_func in self.health_checks.items():
            try:
                result = check_func()
                results[component] = result
                self.last_health_status[component] = result
                
                # Auto-alert on critical status
                if result.status == 'critical':
                    self.send_alert(
                        AlertLevel.CRITICAL,
                        component,
                        result.message,
                        result.metrics
                    )
                elif result.status == 'degraded':
                    self.send_alert(
                        AlertLevel.WARNING,
                        component,
                        result.message,
                        result.metrics
                    )
                    
            except Exception as e:
                logger.error(f"Health check failed for {component}: {e}")
                results[component] = HealthCheck(
                    component=component,
                    status='critical',
                    message=f"Health check error: {str(e)}",
                    timestamp=datetime.now()
                )
        
        # Write health status
        self._write_health_status(results)
        
        return results
    
    def _write_health_status(self, results: Dict[str, HealthCheck]):
        """Write current health status to file."""
        try:
            status_data = {
                'timestamp': datetime.now().isoformat(),
                'components': {
                    component: {
                        'status': check.status,
                        'message': check.message,
                        'timestamp': check.timestamp.isoformat(),
                        'metrics': check.metrics or {}
                    }
                    for component, check in results.items()
                }
            }
            
            with open(self.health_file, 'w') as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to write health status: {e}")
    
    def get_metrics_summary(self, 
                           lookback_minutes: int = 60) -> Dict:
        """
        Get summary statistics for recent metrics.
        
        Args:
            lookback_minutes: How far back to look
            
        Returns:
            Dict with summary stats
        """
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        with self._metrics_lock:
            recent_metrics = [
                m for m in self.metrics_history
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_metrics:
            return {'error': 'No metrics in lookback period'}
        
        # Calculate statistics
        success_rates = [m.api_success_rate for m in recent_metrics]
        latencies = [m.api_avg_latency_ms for m in recent_metrics]
        p95_latencies = [m.api_p95_latency_ms for m in recent_metrics]
        pnls = [m.total_pnl for m in recent_metrics]
        
        return {
            'period_minutes': lookback_minutes,
            'data_points': len(recent_metrics),
            'api_success_rate': {
                'min': min(success_rates),
                'max': max(success_rates),
                'avg': sum(success_rates) / len(success_rates),
                'current': recent_metrics[-1].api_success_rate
            },
            'api_latency_ms': {
                'min': min(latencies),
                'max': max(latencies),
                'avg': sum(latencies) / len(latencies),
                'p95_current': recent_metrics[-1].api_p95_latency_ms
            },
            'pnl': {
                'min': min(pnls),
                'max': max(pnls),
                'current': recent_metrics[-1].total_pnl,
                'change': recent_metrics[-1].total_pnl - recent_metrics[0].total_pnl
            },
            'circuit_breaker_state': recent_metrics[-1].circuit_breaker_state,
            'risk_utilization_pct': recent_metrics[-1].risk_utilization_pct
        }
    
    def start_monitoring(self, interval: int = HEALTH_CHECK_INTERVAL):
        """
        Start background monitoring thread.
        
        Runs health checks at specified interval.
        """
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        
        def monitor_loop():
            logger.info(f"Monitoring started (interval: {interval}s)")
            
            while self.monitoring_active:
                try:
                    self.run_health_checks()
                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}")
                
                time.sleep(interval)
            
            logger.info("Monitoring stopped")
        
        self.monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)

# =============================================================================
# HEALTH CHECK BUILDERS
# =============================================================================

def create_api_health_check(connector) -> Callable[[], HealthCheck]:
    """Create health check function for API connector."""
    
    def check() -> HealthCheck:
        status_data = connector.get_system_status()
        metrics = status_data.get('metrics', {})
        
        success_rate = metrics.get('success_rate_pct', 0)
        avg_latency = metrics.get('avg_latency_ms', 0)
        circuit_state = status_data.get('circuit_breaker', {}).get('state', 'UNKNOWN')
        
        # Determine status
        if circuit_state == 'OPEN':
            status = 'critical'
            message = "Circuit breaker OPEN - API unavailable"
        elif success_rate < 90:
            status = 'critical'
            message = f"API success rate critical: {success_rate:.1f}%"
        elif success_rate < 95:
            status = 'degraded'
            message = f"API success rate degraded: {success_rate:.1f}%"
        elif avg_latency > 2000:
            status = 'degraded'
            message = f"High API latency: {avg_latency:.0f}ms"
        else:
            status = 'healthy'
            message = "API operating normally"
        
        return HealthCheck(
            component='Schwab_API',
            status=status,
            message=message,
            timestamp=datetime.now(),
            metrics={
                'success_rate_pct': success_rate,
                'avg_latency_ms': avg_latency,
                'circuit_breaker_state': circuit_state
            }
        )
    
    return check

def create_risk_health_check(risk_manager, portfolio_value: float) -> Callable[[], HealthCheck]:
    """Create health check function for risk manager."""
    
    def check() -> HealthCheck:
        # Get current risk metrics
        portfolio_greeks = risk_manager.get_portfolio_greeks()
        risk_level = risk_manager.check_risk_level()
        
        delta_util = abs(portfolio_greeks.delta / risk_manager.max_delta) if risk_manager.max_delta else 0
        gamma_util = abs(portfolio_greeks.gamma / risk_manager.max_gamma) if risk_manager.max_gamma else 0
        
        max_util = max(delta_util, gamma_util)
        
        # Determine status
        if max_util > 0.95:
            status = 'critical'
            message = f"Risk utilization critical: {max_util*100:.0f}%"
        elif max_util > 0.80:
            status = 'degraded'
            message = f"Risk utilization high: {max_util*100:.0f}%"
        else:
            status = 'healthy'
            message = "Risk within limits"
        
        return HealthCheck(
            component='Risk_Manager',
            status=status,
            message=message,
            timestamp=datetime.now(),
            metrics={
                'delta': portfolio_greeks.delta,
                'gamma': portfolio_greeks.gamma,
                'risk_utilization_pct': max_util * 100,
                'risk_level': risk_level.value
            }
        )
    
    return check

# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("MONITORING SYSTEM - PRODUCTION READY")
    print("=" * 80)
    
    print("\nExample Setup:")
    print("""
from monitoring_system import (
    MonitoringSystem, 
    AlertLevel,
    create_api_health_check,
    create_risk_health_check,
    EmailAlertChannel,
    SlackAlertChannel
)

# Initialize
monitor = MonitoringSystem()

# Add email alerts for CRITICAL only
email_channel = EmailAlertChannel(
    from_email='your@gmail.com',
    from_password='your_app_password',  # Use Gmail app password
    to_emails=['trader@example.com']
)
monitor.add_channel(email_channel)

# Add Slack webhook
slack_channel = SlackAlertChannel(
    webhook_url='https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
)
monitor.add_channel(slack_channel)

# Register health checks
monitor.register_health_check(
    'Schwab_API',
    create_api_health_check(connector)
)

monitor.register_health_check(
    'Risk_Manager',
    create_risk_health_check(risk_manager, portfolio_value=100000)
)

# Start background monitoring (checks every 60s)
monitor.start_monitoring(interval=60)

# Manual alert
monitor.send_alert(
    AlertLevel.CRITICAL,
    'POSITION',
    'Stop loss triggered on SPY position',
    details={'symbol': 'SPY', 'loss': -5000}
)

# Record metrics
from monitoring_system import SystemMetrics
metrics = SystemMetrics(
    timestamp=datetime.now(),
    api_success_rate=99.5,
    api_avg_latency_ms=250,
    api_p95_latency_ms=450,
    api_calls_per_minute=45,
    circuit_breaker_state='CLOSED',
    cache_hit_rate=65.0,
    active_positions=5,
    total_pnl=2500.0,
    risk_utilization_pct=45.0
)
monitor.record_metrics(metrics)

# Get summary
summary = monitor.get_metrics_summary(lookback_minutes=60)
print(summary)

# Stop monitoring
monitor.stop_monitoring()
    """)
    
    print("\n📊 Alert Channels Supported:")
    print("  ✅ Console - Always active")
    print("  ✅ File - JSONL log for analysis")
    print("  ✅ Email - SMTP (Gmail, etc)")
    print("  ✅ SMS - Twilio integration")
    print("  ✅ Slack - Webhook integration")
    
    print("\n🔔 Alert Levels:")
    print("  INFO - Informational (throttled 5 min)")
    print("  WARNING - Degraded performance (throttled 3 min)")
    print("  CRITICAL - Immediate action needed (throttled 1 min)")
    
    print("\n📈 Features:")
    print("  - Auto health checks on interval")
    print("  - Metrics history tracking")
    print("  - Alert throttling prevents spam")
    print("  - Thread-safe operations")
    print("  - Historical analysis tools")
    
    print("\n" + "=" * 80)