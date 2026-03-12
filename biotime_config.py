# BioTime 8.5 API configs
# Ref: BioTime 8.5 API User Manual
BIOTIME_BASE_URL = "http://dieture.dyndns.org:8081"  # http://serverIP:serverPort
BIOTIME_USERNAME = "admin"
BIOTIME_PASSWORD = "admin123"

# ERPNext configs
ERPNEXT_API_KEY = "48ef06a169ff5db"
ERPNEXT_API_SECRET = "1188c2182181dc7"
ERPNEXT_URL = "https://erp.dieture.com"
ERPNEXT_VERSION = 15

# Operational configs
PULL_FREQUENCY = 0  # minutes between sync runs (0 = every run)
LOGS_DIRECTORY = "logs"
IMPORT_START_DATE = "20260101"  # format: YYYYMMDD, punches before this are skipped

# BioTime punch_state to log_type mapping
# punch_state values from BioTime: "0"=Check-in, "1"=Check-out (typical ZKTeco convention)
# Adjust if your BioTime uses different values
PUNCH_STATE_IN = ["0", "4"]   # Check-in, Break-in
PUNCH_STATE_OUT = ["1", "5"]  # Check-out, Break-out
# If punch_state not in either list, log_type=None (AUTO equivalent)

# Optional: filter devices by serial numbers. Empty list = sync all devices.
# Example: ["CQZ7231060408", "A3T5183160008"]
BIOTIME_DEVICE_FILTER = []  # [] = all devices

# Optional: device_id override - map BioTime terminal_sn to ERPNext device_id
# Use when BioTime serial differs from ERPNext device_id. Empty = use terminal_sn as device_id
# BIOTIME_DEVICE_ID_MAP = {"CQZ7231060408": "AdminOffice"}

# Ignore ERPNext exceptions and continue (same as original sync tool)
# 1=Employee not found, 2=Inactive employee, 3=Duplicate checkin
allowed_exceptions = [1, 2, 3]
