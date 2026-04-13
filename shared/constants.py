"""Shared constants."""

# Token lifetimes
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 5
OTP_CODE_LENGTH = 6

# WebSocket
HEARTBEAT_INTERVAL_SECONDS = 10
HEARTBEAT_TIMEOUT_SECONDS = 30  # Mark offline after this

# Subdomains
API_DOMAIN = "api.mycreativity.nl"
ADMIN_DOMAIN = "admin.mycreativity.nl"
PUBLIC_DOMAIN = "booth.mycreativity.nl"
