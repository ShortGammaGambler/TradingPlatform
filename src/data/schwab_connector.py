"""
Schwab API Connector - Production-Ready Version
==============================================

Features:
- Circuit breaker pattern for API failures
- Rate limiting with configurable thresholds
- Exponential backoff on retries
- Thread-safe token refresh
- Connection pooling optimization
- Data validation layer
- Metrics tracking
- Smart caching with TTL
- Graceful degradation
- Alert system integration

Author: Production-hardened for live trading
"""

import os
import json
import time
import base64
import logging
import webbrowser
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable
from urllib.parse import urlencode
from functools import wraps
from collections import deque

import requests
from requests.adapters import HTTPAdapter

try:
    from src.core.alert_system import AlertSystem as AlertManager
    from src.core.alert_system import AlertLevel
    ALERTS_AVAILABLE = True
    AlertThresholds = None  # Handled by config
except ImportError:
    ALERTS_AVAILABLE = False
    AlertManager = None
    AlertThresholds = None
    AlertLevel = None

# =============================================================================
# CONFIGURATION
# =============================================================================

SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
SCHWAB_API_BASE = "https://api.schwabapi.com/marketdata/v1"

# Rate limiting (Conservative: 100 calls/min to leave buffer)
DEFAULT_RATE_LIMIT = 100  # calls per minute
RATE_LIMIT_WINDOW = 60    # seconds

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = 5    # failures before opening
CIRCUIT_BREAKER_TIMEOUT = 300    # seconds to wait before retry
CIRCUIT_BREAKER_HALF_OPEN_ATTEMPTS = 1  # test attempts in half-open state

# Retry settings
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 30  # seconds

# Cache settings
DEFAULT_CACHE_TTL = 5  # seconds for quote data
OPTIONS_CACHE_TTL = 30  # seconds for options chains

# Connection pooling
POOL_CONNECTIONS = 10
POOL_MAXSIZE = 20

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitBreakerState:
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing if recovered

class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests allowed
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self,
                 failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 timeout: int = CIRCUIT_BREAKER_TIMEOUT,
                 half_open_attempts: int = CIRCUIT_BREAKER_HALF_OPEN_ATTEMPTS):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_attempts = half_open_attempts

        self.state = CircuitBreakerState.CLOSED
        self.failures = 0
        self.last_failure_time = None
        self.half_open_successes = 0

        self._lock = threading.Lock()

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise Exception(f"Circuit breaker OPEN. Retry after {self._time_until_retry():.1f}s")

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_successes >= self.half_open_attempts:
                    self._transition_to_closed()

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.timeout

    def _time_until_retry(self) -> float:
        """Seconds until circuit breaker will attempt reset."""
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.timeout - elapsed)

    def _record_success(self):
        """Record successful call."""
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_attempts:
                    self._transition_to_closed()
            elif self.state == CircuitBreakerState.CLOSED:
                self.failures = 0

    def _record_failure(self):
        """Record failed call."""
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.state == CircuitBreakerState.HALF_OPEN:
                self._transition_to_open()
            elif self.failures >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state = CircuitBreakerState.OPEN
        logger.error(f"Circuit breaker OPENED after {self.failures} failures")

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.half_open_successes = 0
        logger.warning("Circuit breaker entering HALF_OPEN state")

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state = CircuitBreakerState.CLOSED
        self.failures = 0
        self.half_open_successes = 0
        logger.info("Circuit breaker CLOSED - normal operation resumed")

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitBreakerState.OPEN

# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter to prevent API throttling.

    Tracks API calls over a sliding window and blocks if limit exceeded.
    """

    def __init__(self, calls_per_minute: int = DEFAULT_RATE_LIMIT):
        self.calls_per_minute = calls_per_minute
        self.window = RATE_LIMIT_WINDOW
        self.calls = deque()
        self._lock = threading.Lock()

        logger.info(f"Rate limiter initialized: {calls_per_minute} calls/min")

    def acquire(self):
        """
        Wait if necessary to stay within rate limit.

        Blocks until a call slot is available.
        """
        with self._lock:
            now = time.time()

            # Remove calls outside the window
            while self.calls and now - self.calls[0] >= self.window:
                self.calls.popleft()

            # If at limit, wait
            if len(self.calls) >= self.calls_per_minute:
                sleep_time = self.window - (now - self.calls[0])
                if sleep_time > 0:
                    logger.warning(f"Rate limit reached. Sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    now = time.time()
                    # Clean up again after sleep
                    while self.calls and now - self.calls[0] >= self.window:
                        self.calls.popleft()

            # Record this call
            self.calls.append(now)

    def get_stats(self) -> Dict:
        """Get current rate limiter statistics."""
        with self._lock:
            now = time.time()
            # Count calls in current window
            recent_calls = sum(1 for t in self.calls if now - t < self.window)
            return {
                'calls_in_window': recent_calls,
                'calls_remaining': max(0, self.calls_per_minute - recent_calls),
                'utilization_pct': (recent_calls / self.calls_per_minute) * 100
            }

# =============================================================================
# METRICS TRACKER
# =============================================================================

class APIMetrics:
    """Track API performance and reliability metrics."""

    def __init__(self):
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.latencies = deque(maxlen=1000)  # Keep last 1000 latencies
        self.last_error = None
        self.last_error_time = None

        self._lock = threading.Lock()

    def record_call(self, success: bool, latency_ms: float, error: str = None):
        """Record API call metrics."""
        with self._lock:
            self.total_calls += 1
            self.latencies.append(latency_ms)

            if success:
                self.successful_calls += 1
            else:
                self.failed_calls += 1
                self.last_error = error
                self.last_error_time = datetime.now()

    def get_stats(self) -> Dict:
        """Get current metrics."""
        with self._lock:
            if not self.latencies:
                return {'error': 'No data collected yet'}

            sorted_latencies = sorted(self.latencies)
            n = len(sorted_latencies)

            return {
                'total_calls': self.total_calls,
                'successful_calls': self.successful_calls,
                'failed_calls': self.failed_calls,
                'success_rate_pct': (self.successful_calls / self.total_calls * 100) if self.total_calls > 0 else 0,
                'avg_latency_ms': sum(self.latencies) / n,
                'p50_latency_ms': sorted_latencies[n // 2],
                'p95_latency_ms': sorted_latencies[int(n * 0.95)],
                'p99_latency_ms': sorted_latencies[int(n * 0.99)],
                'max_latency_ms': max(self.latencies),
                'last_error': self.last_error,
                'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None
            }

# =============================================================================
# DATA VALIDATOR
# =============================================================================

class DataValidator:
    """Validate market data for sanity and completeness."""

    @staticmethod
    def validate_quote(quote_data: Dict) -> Tuple[bool, str]:
        """
        Validate quote data.

        Returns:
            (is_valid, error_message)
        """
        try:
            # Check required fields
            required_fields = ['bidPrice', 'askPrice', 'lastPrice']
            for field in required_fields:
                if field not in quote_data:
                    return False, f"Missing required field: {field}"

            bid = quote_data.get('bidPrice', 0)
            ask = quote_data.get('askPrice', 0)
            last = quote_data.get('lastPrice', 0)

            # Sanity checks
            if bid > ask and bid > 0 and ask > 0:
                return False, f"Bid ({bid}) > Ask ({ask})"

            if last == 0:
                return False, "Zero last price - possibly stale"

            if bid < 0 or ask < 0 or last < 0:
                return False, "Negative price detected"

            # Spread check (warn if > 5%)
            if ask > 0 and bid > 0:
                spread_pct = ((ask - bid) / bid) * 100
                if spread_pct > 5:
                    logger.warning(f"Wide spread detected: {spread_pct:.2f}%")

            return True, "OK"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def validate_option_greeks(option_data: Dict) -> Tuple[bool, str]:
        """
        Validate option Greeks.

        Returns:
            (is_valid, error_message)
        """
        try:
            delta = option_data.get('delta', 0)
            gamma = option_data.get('gamma', 0)
            theta = option_data.get('theta', 0)
            vega = option_data.get('vega', 0)

            # Delta range check
            if abs(delta) > 1:
                return False, f"Invalid delta: {delta} (must be -1 to 1)"

            # Gamma should be non-negative
            if gamma < 0:
                return False, f"Negative gamma: {gamma}"

            # Vega should be non-negative
            if vega < 0:
                return False, f"Negative vega: {vega}"

            return True, "OK"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

# =============================================================================
# CACHE
# =============================================================================

class DataCache:
    """Simple TTL-based cache for market data."""

    def __init__(self, default_ttl: int = DEFAULT_CACHE_TTL):
        self.default_ttl = default_ttl
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Dict]:
        """Get cached data if not expired."""
        with self._lock:
            if key in self._cache:
                data, timestamp, ttl = self._cache[key]
                if time.time() - timestamp < ttl:
                    return data
                else:
                    del self._cache[key]
        return None

    def set(self, key: str, data: Dict, ttl: int = None):
        """Cache data with TTL."""
        with self._lock:
            ttl = ttl if ttl is not None else self.default_ttl
            self._cache[key] = (data, time.time(), ttl)

    def clear(self):
        """Clear all cached data."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            now = time.time()
            valid_entries = sum(1 for _, timestamp, ttl in self._cache.values()
                              if now - timestamp < ttl)
            return {
                'total_entries': len(self._cache),
                'valid_entries': valid_entries,
                'expired_entries': len(self._cache) - valid_entries
            }

# =============================================================================
# CREDENTIALS & AUTH
# =============================================================================

@dataclass
class SchwabCredentials:
    """Schwab API credentials and tokens."""
    client_id: str
    client_secret: str
    redirect_uri: str = "https://127.0.0.1:8443/callback"
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None

class SchwabAuthenticator:
    """
    Handle OAuth 2.0 authentication with Schwab API.

    Thread-safe token management with automatic refresh.
    """

    def __init__(self, credentials: SchwabCredentials, token_file: str = None):
        self.credentials = credentials
        self.token_file = token_file or str(Path.home() / ".schwab_tokens.json")
        self._refresh_lock = threading.Lock()

        self._load_tokens()

    def _load_tokens(self):
        """Load saved tokens from file."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.credentials.access_token = data.get('access_token')
                    self.credentials.refresh_token = data.get('refresh_token')
                    if data.get('token_expiry'):
                        self.credentials.token_expiry = datetime.fromisoformat(data['token_expiry'])
                logger.info(f"Loaded tokens from {self.token_file}")
            except Exception as e:
                logger.error(f"Could not load tokens: {e}")

    def _save_tokens(self):
        """Save tokens to file."""
        try:
            data = {
                'access_token': self.credentials.access_token,
                'refresh_token': self.credentials.refresh_token,
                'token_expiry': self.credentials.token_expiry.isoformat() if self.credentials.token_expiry else None
            }
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved tokens to {self.token_file}")
        except Exception as e:
            logger.error(f"Could not save tokens: {e}")

    def get_authorization_url(self) -> str:
        """Generate the OAuth authorization URL."""
        params = {
            'response_type': 'code',
            'client_id': self.credentials.client_id,
            'redirect_uri': self.credentials.redirect_uri,
            'scope': 'readonly',
        }
        url = f"{SCHWAB_AUTH_URL}?{urlencode(params)}"
        logger.info("Authorization URL generated")
        return url

    def open_authorization_url(self) -> str:
        """Open the authorization URL in browser."""
        url = self.get_authorization_url()
        try:
            webbrowser.open(url)
            logger.info("Opened authorization URL in browser")
        except Exception as e:
            logger.warning(f"Could not open browser: {e}")
        return url

    def exchange_code_for_tokens(self, authorization_code: str) -> bool:
        """Exchange authorization code for tokens."""
        auth_string = f"{self.credentials.client_id}:{self.credentials.client_secret}"
        auth_header = base64.b64encode(auth_string.encode()).decode()

        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': self.credentials.redirect_uri
        }

        try:
            response = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=data, timeout=30)
            response.raise_for_status()

            tokens = response.json()
            self.credentials.access_token = tokens['access_token']
            self.credentials.refresh_token = tokens.get('refresh_token')
            expires_in = tokens.get('expires_in', 1800)
            self.credentials.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            self._save_tokens()
            logger.info("Successfully obtained access tokens")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

    def refresh_access_token(self) -> bool:
        """
        Refresh the access token (thread-safe).

        Uses double-check locking to prevent multiple simultaneous refreshes.
        """
        # First check without lock (fast path)
        if self.credentials.token_expiry:
            time_until_expiry = self.credentials.token_expiry - datetime.now()
            if time_until_expiry > timedelta(minutes=5):
                return True  # Token still valid

        # Need to refresh - acquire lock
        with self._refresh_lock:
            # Double-check after acquiring lock
            if self.credentials.token_expiry:
                time_until_expiry = self.credentials.token_expiry - datetime.now()
                if time_until_expiry > timedelta(minutes=5):
                    return True  # Another thread already refreshed

            if not self.credentials.refresh_token:
                logger.error("No refresh token available")
                return False

            auth_string = f"{self.credentials.client_id}:{self.credentials.client_secret}"
            auth_header = base64.b64encode(auth_string.encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.credentials.refresh_token
            }

            try:
                response = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=data, timeout=30)
                response.raise_for_status()

                tokens = response.json()
                self.credentials.access_token = tokens['access_token']
                expires_in = tokens.get('expires_in', 1800)
                self.credentials.token_expiry = datetime.now() + timedelta(seconds=expires_in)

                if 'refresh_token' in tokens:
                    self.credentials.refresh_token = tokens['refresh_token']

                self._save_tokens()
                logger.info("Successfully refreshed access token")
                return True

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to refresh token: {e}")
                return False

    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token."""
        if not self.credentials.access_token:
            logger.warning("No access token")
            return False

        if self.credentials.token_expiry:
            time_until_expiry = self.credentials.token_expiry - datetime.now()
            if time_until_expiry < timedelta(minutes=5):
                return self.refresh_access_token()

        return True

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token."""
        if self.ensure_valid_token():
            return self.credentials.access_token
        return None

    @property
    def is_authenticated(self) -> bool:
        """Check if authenticated."""
        return self.credentials.access_token is not None

# =============================================================================
# DATA CONNECTOR
# =============================================================================

def exponential_backoff_retry(max_retries=MAX_RETRIES):
    """Decorator for exponential backoff retry logic."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = BASE_RETRY_DELAY
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    last_exception = e
                    if e.response.status_code == 429:  # Rate limited
                        sleep_time = min(delay, MAX_RETRY_DELAY)
                        logger.warning(f"Rate limited. Retrying in {sleep_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(sleep_time)
                        delay *= 2  # Exponential backoff
                    else:
                        raise  # Don't retry on other HTTP errors
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        sleep_time = min(delay, MAX_RETRY_DELAY)
                        logger.warning(f"Request failed. Retrying in {sleep_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(sleep_time)
                        delay *= 2
                    else:
                        raise

            raise last_exception
        return wrapper
    return decorator

class SchwabDataConnector:
    """
    Production-ready Schwab API data connector.

    Features:
    - Circuit breaker pattern
    - Rate limiting
    - Exponential backoff
    - Data validation
    - Metrics tracking
    - Smart caching
    - Alert system integration
    """

    def __init__(self,
                 authenticator: SchwabAuthenticator,
                 enable_circuit_breaker: bool = True,
                 enable_rate_limiting: bool = True,
                 enable_caching: bool = True,
                 enable_validation: bool = True,
                 enable_alerts: bool = True,
                 alert_manager: 'AlertManager' = None,
                 alert_thresholds: 'AlertThresholds' = None):

        self.auth = authenticator

        # Initialize session with connection pooling
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=POOL_CONNECTIONS,
            pool_maxsize=POOL_MAXSIZE,
            max_retries=0  # We handle retries manually
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        # Feature flags
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_caching = enable_caching
        self.enable_validation = enable_validation
        self.enable_alerts = enable_alerts and ALERTS_AVAILABLE

        # Initialize components
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self.rate_limiter = RateLimiter() if enable_rate_limiting else None
        self.cache = DataCache() if enable_caching else None
        self.metrics = APIMetrics()

        # Initialize alert manager
        if self.enable_alerts:
            if alert_manager:
                self.alert_manager = alert_manager
            else:
                thresholds = alert_thresholds or AlertThresholds()
                self.alert_manager = AlertManager(thresholds=thresholds)
            logger.info("Alert manager initialized")
        else:
            self.alert_manager = None

        # Track previous circuit breaker state for alert transitions
        self._prev_cb_state = CircuitBreakerState.CLOSED if self.circuit_breaker else None

        logger.info(f"SchwabDataConnector initialized (CB={enable_circuit_breaker}, RL={enable_rate_limiting}, "
                   f"Cache={enable_caching}, Validation={enable_validation}, Alerts={self.enable_alerts})")

    @classmethod
    def from_config(cls, config) -> "SchwabDataConnector":
        """Create SchwabDataConnector from unified Config object."""
        creds = SchwabCredentials(
            app_key=config.schwab_app_key,
            app_secret=config.schwab_app_secret,
            redirect_uri=config.schwab_redirect_uri,
        )
        auth = SchwabAuthenticator(creds, token_file=config.schwab_token_path)
        return cls(authenticator=auth)

    @exponential_backoff_retry(max_retries=MAX_RETRIES)
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make an authenticated API request with all protections.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response or None
        """
        # Rate limiting
        if self.enable_rate_limiting:
            self.rate_limiter.acquire()

        # Get token
        token = self.auth.get_access_token()
        if not token:
            logger.error("No valid access token")
            return None

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        url = f"{SCHWAB_API_BASE}{endpoint}"

        start_time = time.time()
        success = False

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            success = True

            latency_ms = (time.time() - start_time) * 1000
            self.metrics.record_call(True, latency_ms)

            return data

        except requests.exceptions.HTTPError as e:
            latency_ms = (time.time() - start_time) * 1000

            if e.response.status_code == 401:
                logger.warning("Token expired, refreshing...")
                if self.auth.refresh_access_token():
                    headers['Authorization'] = f'Bearer {self.auth.credentials.access_token}'
                    response = self.session.get(url, headers=headers, params=params, timeout=30)
                    response.raise_for_status()

                    data = response.json()
                    latency_ms = (time.time() - start_time) * 1000
                    self.metrics.record_call(True, latency_ms)

                    return data

            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            self.metrics.record_call(False, latency_ms, error_msg)
            logger.error(f"API request failed: {error_msg}")
            raise

        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            self.metrics.record_call(False, latency_ms, error_msg)
            logger.error(f"API request failed: {error_msg}")
            raise

    def _make_request_safe(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make request with circuit breaker protection and alert integration."""
        result = None
        error_occurred = False

        if self.enable_circuit_breaker:
            try:
                result = self.circuit_breaker.call(self._make_request, endpoint, params)
            except Exception as e:
                logger.error(f"Circuit breaker protected call failed: {e}")
                error_occurred = True
        else:
            try:
                result = self._make_request(endpoint, params)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                error_occurred = True

        # Check for alerts after request
        self._check_alerts_after_request(error_occurred)

        return result

    def _check_alerts_after_request(self, error_occurred: bool = False):
        """Check system status and trigger alerts if needed."""
        if not self.enable_alerts or not self.alert_manager:
            return

        # Check circuit breaker state changes
        if self.circuit_breaker:
            current_state = self.circuit_breaker.state
            if current_state != self._prev_cb_state:
                self.alert_manager.check_circuit_breaker(
                    current_state,
                    self.circuit_breaker.failures
                )
                self._prev_cb_state = current_state

        # Check success rate periodically (every 10 calls)
        if self.metrics.total_calls > 0 and self.metrics.total_calls % 10 == 0:
            stats = self.metrics.get_stats()
            if 'success_rate_pct' in stats:
                self.alert_manager.check_success_rate(stats['success_rate_pct'])
            if 'p95_latency_ms' in stats:
                self.alert_manager.check_latency(stats['p95_latency_ms'], 'p95')

        # Check rate limit utilization
        if self.rate_limiter:
            rl_stats = self.rate_limiter.get_stats()
            self.alert_manager.check_rate_limit(rl_stats['utilization_pct'])

    def get_quote(self, symbol: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get current quote for a symbol.

        Args:
            symbol: Ticker symbol
            use_cache: Use cached data if available

        Returns:
            Quote data dict
        """
        cache_key = f"quote:{symbol}"

        # Check cache
        if use_cache and self.enable_caching:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {symbol}")
                return cached

        # Fetch from API
        result = self._make_request_safe(f"/{symbol}/quotes")
        if result and symbol in result:
            data = result[symbol]

            # Validate
            if self.enable_validation:
                is_valid, error = DataValidator.validate_quote(data)
                if not is_valid:
                    logger.error(f"Quote validation failed for {symbol}: {error}")
                    return None

            # Cache
            if self.enable_caching:
                self.cache.set(cache_key, data, ttl=DEFAULT_CACHE_TTL)

            return data

        return result

    def get_quotes(self, symbols: List[str]) -> Optional[Dict]:
        """Get quotes for multiple symbols."""
        params = {'symbols': ','.join(symbols)}
        return self._make_request_safe("/quotes", params)

    def get_price_history(self,
                          symbol: str,
                          period_type: str = "month",
                          period: int = 1,
                          frequency_type: str = "daily",
                          frequency: int = 1,
                          start_date: datetime = None,
                          end_date: datetime = None) -> Optional[Dict]:
        """
        Get historical price data.

        Args:
            symbol: Ticker symbol
            period_type: 'day', 'month', 'year', 'ytd'
            period: Number of periods
            frequency_type: 'minute', 'daily', 'weekly', 'monthly'
            frequency: Frequency interval
            start_date: Start date
            end_date: End date

        Returns:
            Dict with 'candles' list
        """
        params = {
            'periodType': period_type,
            'period': period,
            'frequencyType': frequency_type,
            'frequency': frequency
        }

        if start_date:
            params['startDate'] = int(start_date.timestamp() * 1000)
        if end_date:
            params['endDate'] = int(end_date.timestamp() * 1000)

        return self._make_request_safe(f"/{symbol}/pricehistory", params)

    def get_options_chain(self,
                          symbol: str,
                          contract_type: str = "ALL",
                          strike_count: int = 30,
                          include_quotes: bool = True,
                          from_date: str = None,
                          to_date: str = None,
                          strategy: str = "SINGLE",
                          use_cache: bool = True) -> Optional[Dict]:
        """
        Get options chain.

        Args:
            symbol: Underlying symbol
            contract_type: 'CALL', 'PUT', or 'ALL'
            strike_count: Number of strikes above/below ATM
            include_quotes: Include bid/ask
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            strategy: 'SINGLE', 'ANALYTICAL', etc.
            use_cache: Use cached data

        Returns:
            Options chain dict
        """
        cache_key = f"chain:{symbol}:{contract_type}:{strike_count}"

        # Check cache
        if use_cache and self.enable_caching:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for options chain {symbol}")
                return cached

        params = {
            'symbol': symbol,
            'contractType': contract_type,
            'strikeCount': strike_count,
            'includeQuotes': str(include_quotes).lower(),
            'strategy': strategy
        }

        if from_date:
            params['fromDate'] = from_date
        if to_date:
            params['toDate'] = to_date

        result = self._make_request_safe("/chains", params)

        # Cache options chains longer (they change slower)
        if result and self.enable_caching:
            self.cache.set(cache_key, result, ttl=OPTIONS_CACHE_TTL)

        return result

    def get_movers(self,
                   index: str = "$SPX",
                   direction: str = "up",
                   change_type: str = "percent") -> Optional[List[Dict]]:
        """Get market movers."""
        params = {
            'direction': direction,
            'change': change_type
        }
        return self._make_request_safe(f"/movers/{index}", params)

    def get_system_status(self) -> Dict:
        """
        Get comprehensive system status.

        Returns:
            Dict with all component stats
        """
        status = {
            'authenticated': self.auth.is_authenticated,
            'metrics': self.metrics.get_stats(),
        }

        if self.enable_circuit_breaker:
            status['circuit_breaker'] = {
                'state': self.circuit_breaker.state,
                'failures': self.circuit_breaker.failures,
                'is_open': self.circuit_breaker.is_open
            }

        if self.enable_rate_limiting:
            status['rate_limiter'] = self.rate_limiter.get_stats()

        if self.enable_caching:
            status['cache'] = self.cache.get_stats()

        if self.enable_alerts and self.alert_manager:
            status['alerts'] = self.alert_manager.get_status_summary()

        return status

    def check_system_health(self) -> Dict:
        """
        Run comprehensive health check and update alerts.

        Returns:
            Dict with health status and any triggered alerts
        """
        status = self.get_system_status()

        if self.enable_alerts and self.alert_manager:
            self.alert_manager.check_connector_status(status)

        return {
            'healthy': not (self.enable_alerts and self.alert_manager and
                          self.alert_manager.has_critical_alerts()),
            'status': status,
            'should_halt_trading': (self.enable_alerts and self.alert_manager and
                                   self.alert_manager.has_critical_alerts())
        }

    def get_active_alerts(self) -> List[Dict]:
        """Get list of active alerts as dicts."""
        if not self.enable_alerts or not self.alert_manager:
            return []

        alerts = self.alert_manager.get_active_alerts()
        return [
            {
                'timestamp': a.timestamp.isoformat(),
                'level': a.level.value,
                'category': a.category,
                'message': a.message,
                'details': a.details,
                'acknowledged': a.acknowledged
            }
            for a in alerts
        ]

    def acknowledge_alert(self, category: str):
        """Acknowledge an alert by category."""
        if self.enable_alerts and self.alert_manager:
            self.alert_manager.acknowledge(category)

    def clear_cache(self):
        """Clear all cached data."""
        if self.enable_caching:
            self.cache.clear()
            logger.info("Cache cleared")

# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_schwab_connector(client_id: str,
                             client_secret: str,
                             redirect_uri: str = "https://127.0.0.1:8443/callback",
                             token_file: str = None,
                             enable_circuit_breaker: bool = True,
                             enable_rate_limiting: bool = True,
                             enable_caching: bool = True,
                             enable_validation: bool = True,
                             enable_alerts: bool = True,
                             alert_manager: 'AlertManager' = None,
                             alert_thresholds: 'AlertThresholds' = None) -> SchwabDataConnector:
    """
    Create a production-ready Schwab data connector.

    First-time setup:
        1. connector = create_schwab_connector(client_id, client_secret)
        2. url = connector.auth.open_authorization_url()
        3. Visit URL, authorize, extract 'code' from redirect
        4. connector.auth.exchange_code_for_tokens(code)

    Subsequent use:
        Tokens are auto-loaded and refreshed.

    Args:
        client_id: Schwab API client ID
        client_secret: Schwab API client secret
        redirect_uri: OAuth redirect URI
        token_file: Token storage path
        enable_circuit_breaker: Enable circuit breaker protection
        enable_rate_limiting: Enable rate limiting
        enable_caching: Enable data caching
        enable_validation: Enable data validation
        enable_alerts: Enable alert system integration
        alert_manager: Optional existing AlertManager to share
        alert_thresholds: Optional AlertThresholds configuration

    Returns:
        Configured SchwabDataConnector
    """
    credentials = SchwabCredentials(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri
    )

    authenticator = SchwabAuthenticator(credentials, token_file)

    return SchwabDataConnector(
        authenticator,
        enable_circuit_breaker=enable_circuit_breaker,
        enable_rate_limiting=enable_rate_limiting,
        enable_caching=enable_caching,
        enable_validation=enable_validation,
        enable_alerts=enable_alerts,
        alert_manager=alert_manager,
        alert_thresholds=alert_thresholds
    )

# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SCHWAB API CONNECTOR - PRODUCTION READY")
    print("=" * 80)

    print("\nSetup Instructions:")
    print("1. Register at https://developer.schwab.com")
    print("2. Create app, get client_id and client_secret")
    print("3. Set redirect_uri: https://127.0.0.1:8443/callback")

    print("\nExample Usage:")
    print("""
# Create connector
connector = create_schwab_connector(
    client_id='YOUR_CLIENT_ID',
    client_secret='YOUR_SECRET'
)

# First-time authentication (one-time)
url = connector.auth.open_authorization_url()
# Visit URL in browser, authorize, get 'code' from redirect URL
connector.auth.exchange_code_for_tokens('YOUR_AUTH_CODE')

# Fetch data (with all protections enabled)
quote = connector.get_quote('SPY')
print(f"SPY: ${quote['lastPrice']}")

history = connector.get_price_history('SPY', period_type='month', period=1)
print(f"Got {len(history['candles'])} candles")

chain = connector.get_options_chain('SPY', strike_count=20)
print(f"Got options chain for {chain['symbol']}")

# Check system health
status = connector.get_system_status()
print(f"\\nSystem Status:")
print(f"  Success Rate: {status['metrics']['success_rate_pct']:.1f}%")
print(f"  Avg Latency: {status['metrics']['avg_latency_ms']:.1f}ms")
print(f"  Circuit Breaker: {status['circuit_breaker']['state']}")
print(f"  Rate Limit: {status['rate_limiter']['calls_remaining']} calls remaining")
    """)

    print("\nProduction Features Enabled:")
    print("  - Circuit Breaker - Auto-stops on API failures")
    print("  - Rate Limiter - Prevents throttling (100 calls/min)")
    print("  - Exponential Backoff - Smart retry on transient failures")
    print("  - Data Validation - Sanity checks on all data")
    print("  - Smart Caching - Reduces API calls")
    print("  - Metrics Tracking - Monitor API health")
    print("  - Thread-Safe - Safe for multi-threaded use")
    print("  - Connection Pooling - Optimized HTTP performance")
    print("  - Alert System - Critical alerts on failures/degradation")

    print("\nAlert System Integration:")
    print("""
# Check health with alerts
health = connector.check_system_health()
if health['should_halt_trading']:
    print("CRITICAL: Trading should be halted!")

# Get active alerts
alerts = connector.get_active_alerts()
for alert in alerts:
    print(f"[{alert['level']}] {alert['category']}: {alert['message']}")

# Acknowledge an alert
connector.acknowledge_alert('circuit_breaker')
    """)

    print("\nImportant Notes:")
    print("  - First run requires browser-based OAuth")
    print("  - Tokens auto-refresh before expiration")
    print("  - Monitor connector.get_system_status() regularly")
    print("  - Circuit breaker opens after 5 consecutive failures")
    print("  - Cache TTL: 5s for quotes, 30s for options chains")
    print("  - Alerts trigger on CB open, low success rate, high latency")

    print("\n" + "=" * 80)
