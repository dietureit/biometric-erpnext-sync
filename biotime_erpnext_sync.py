"""
BioTime 8.5 → ERPNext Attendance Sync

Fetches devices and transactions from BioTime 8.5 API (no direct device TCP needed).
Pushes attendance logs to ERPNext Employee Checkin.

Ref: BioTime 8.5 API User Manual
"""

import biotime_config as config
import requests
import datetime
import json
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from pickledb import PickleDB
from urllib.parse import urljoin, urlencode

EMPLOYEE_NOT_FOUND_ERROR_MESSAGE = (
    "No Employee found for the given employee field value"
)
EMPLOYEE_INACTIVE_ERROR_MESSAGE = (
    "Transactions cannot be created for an Inactive Employee"
)
DUPLICATE_EMPLOYEE_CHECKIN_ERROR_MESSAGE = (
    "This employee already has a log with the same timestamp"
)
allowlisted_errors = [
    EMPLOYEE_NOT_FOUND_ERROR_MESSAGE,
    EMPLOYEE_INACTIVE_ERROR_MESSAGE,
    DUPLICATE_EMPLOYEE_CHECKIN_ERROR_MESSAGE,
]

if hasattr(config, "allowed_exceptions"):
    allowlisted_errors_temp = []
    for error_number in config.allowed_exceptions:
        allowlisted_errors_temp.append(allowlisted_errors[error_number - 1])
    allowlisted_errors = allowlisted_errors_temp

PUNCH_STATE_IN = getattr(config, "PUNCH_STATE_IN", ["0", "4"])
PUNCH_STATE_OUT = getattr(config, "PUNCH_STATE_OUT", ["1", "5"])
ERPNEXT_VERSION = getattr(config, "ERPNEXT_VERSION", 14)
BIOTIME_DEVICE_FILTER = getattr(config, "BIOTIME_DEVICE_FILTER", [])
BIOTIME_DEVICE_ID_MAP = getattr(config, "BIOTIME_DEVICE_ID_MAP", {})


def get_biotime_token():
    """Get JWT auth token from BioTime 8.5."""
    url = urljoin(config.BIOTIME_BASE_URL.rstrip("/") + "/", "jwt-api-token-auth/")
    resp = requests.post(
        url,
        json={"username": config.BIOTIME_USERNAME, "password": config.BIOTIME_PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token") or data.get("access")
    if not token:
        raise ValueError("No token in BioTime auth response: " + str(data))
    return token


def get_biotime_devices(token):
    """Fetch all devices (terminals) from BioTime API."""
    url = urljoin(config.BIOTIME_BASE_URL.rstrip("/") + "/", "iclock/api/terminals/")
    headers = {
        "Authorization": f"JWT {token}",
        "Content-Type": "application/json",
    }
    devices = []
    next_url = url
    while next_url:
        resp = requests.get(next_url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data") or data.get("results") or []
        for d in results:
            sn = d.get("sn") or str(d.get("id", ""))
            if BIOTIME_DEVICE_FILTER and sn not in BIOTIME_DEVICE_FILTER:
                continue
            if d.get("is_attendance") is False:
                continue
            devices.append(d)
        next_url = data.get("next")
    return devices


def get_biotime_transactions(token, start_time, end_time, terminal_sn=None):
    """Fetch transactions from BioTime API. Paginates through all results."""
    base = urljoin(config.BIOTIME_BASE_URL.rstrip("/") + "/", "iclock/api/transactions/")
    params = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if terminal_sn:
        params["terminal_sn"] = terminal_sn
    url = f"{base}?{urlencode(params)}"
    headers = {
        "Authorization": f"JWT {token}",
        "Content-Type": "application/json",
    }
    transactions = []
    next_url = url
    while next_url:
        resp = requests.get(next_url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data") or data.get("results") or []
        transactions.extend(results)
        next_url = data.get("next")
    return transactions


def punch_state_to_log_type(punch_state):
    """Map BioTime punch_state to ERPNext log_type (IN/OUT/None)."""
    ps = str(punch_state) if punch_state is not None else ""
    if ps in PUNCH_STATE_IN:
        return "IN"
    if ps in PUNCH_STATE_OUT:
        return "OUT"
    return None


def send_to_erpnext(
    employee_field_value,
    timestamp,
    device_id=None,
    log_type=None,
    latitude=None,
    longitude=None,
):
    """Push single checkin to ERPNext."""
    endpoint_app = "hrms" if ERPNEXT_VERSION > 13 else "erpnext"
    url = f"{config.ERPNEXT_URL}/api/method/{endpoint_app}.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
    headers = {
        "Authorization": f"token {config.ERPNEXT_API_KEY}:{config.ERPNEXT_API_SECRET}",
        "Accept": "application/json",
    }
    data = {
        "employee_field_value": employee_field_value,
        "timestamp": str(timestamp),
        "device_id": device_id,
        "log_type": log_type,
        "latitude": latitude,
        "longitude": longitude,
    }
    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        return 200, json.loads(response.content)["message"]["name"]
    error_str = _safe_get_error_str(response)
    if EMPLOYEE_NOT_FOUND_ERROR_MESSAGE in error_str:
        error_logger.error(
            "\t".join(
                [
                    "Error during ERPNext API Call.",
                    str(employee_field_value),
                    str(timestamp),
                    str(device_id),
                    str(log_type),
                    error_str,
                ]
            )
        )
    else:
        error_logger.error(
            "\t".join(
                [
                    "Error during ERPNext API Call.",
                    str(employee_field_value),
                    str(timestamp),
                    str(device_id),
                    str(log_type),
                    error_str,
                ]
            )
        )
    return response.status_code, error_str


def _safe_get_error_str(res):
    try:
        error_json = json.loads(res.content)
        if "exc" in error_json:
            error_str = json.loads(error_json["exc"])[0]
        else:
            error_str = json.dumps(error_json)
    except Exception:
        error_str = str(res.__dict__)
    return error_str


def _safe_convert_date(datestring, pattern):
    try:
        return datetime.datetime.strptime(datestring, pattern)
    except Exception:
        return None


def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")
    handler = RotatingFileHandler(log_file, maxBytes=10000000, backupCount=50)
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.hasHandlers():
        logger.addHandler(handler)
    return logger


def get_last_line_from_file(filepath):
    line = None
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        return None
    if os.stat(filepath).st_size < 5000:
        with open(filepath, "r") as f:
            for line in f:
                pass
    else:
        with open(filepath, "rb") as f:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
            line = f.readline().decode()
    return line


def process_and_push_transactions(transactions, device_sn, success_logger, failed_logger):
    """Process transactions and push to ERPNext. Uses success log for resume."""
    import_start = _safe_convert_date(config.IMPORT_START_DATE, "%Y%m%d")
    device_id = BIOTIME_DEVICE_ID_MAP.get(device_sn, device_sn)

    success_log_path = os.path.join(
        config.LOGS_DIRECTORY, f"attendance_success_log_{device_id}.log"
    )
    last_line = get_last_line_from_file(success_log_path)
    index_of_last = -1
    last_emp_code = None
    last_punch_time = None

    if last_line:
        parts = last_line.split("\t")
        if len(parts) >= 6:
            last_emp_code = parts[4]
            try:
                last_punch_time = datetime.datetime.fromtimestamp(float(parts[5]))
            except Exception:
                pass

    if import_start or last_emp_code:
        for i, tx in enumerate(transactions):
            emp_code = str(tx.get("emp_code", ""))
            punch_str = tx.get("punch_time") or tx.get("upload_time")
            if not punch_str:
                continue
            punch_dt = _safe_convert_date(punch_str.strip(), "%Y-%m-%d %H:%M:%S")
            if not punch_dt:
                punch_dt = _safe_convert_date(punch_str.strip(), "%Y-%m-%d %H:%M:%S.%f")
            if not punch_dt:
                continue
            if import_start and punch_dt < import_start:
                continue
            if last_emp_code and last_punch_time:
                if emp_code == last_emp_code and punch_dt == last_punch_time:
                    index_of_last = i
                    break

    to_process = transactions[index_of_last + 1 :]
    for tx in to_process:
        emp_code = str(tx.get("emp_code", ""))
        punch_str = tx.get("punch_time") or tx.get("upload_time")
        if not punch_str:
            continue
        punch_dt = _safe_convert_date(punch_str.strip(), "%Y-%m-%d %H:%M:%S")
        if not punch_dt:
            punch_dt = _safe_convert_date(punch_str.strip(), "%Y-%m-%d %H:%M:%S.%f")
        if not punch_dt:
            continue
        if import_start and punch_dt < import_start:
            continue

        log_type = punch_state_to_log_type(tx.get("punch_state"))
        lat = tx.get("latitude")
        lon = tx.get("longitude")
        if lat is not None and lon is not None:
            try:
                lat, lon = float(lat), float(lon)
            except (TypeError, ValueError):
                lat, lon = None, None

        code, msg = send_to_erpnext(
            emp_code,
            punch_dt,
            device_id=device_id,
            log_type=log_type,
            latitude=lat,
            longitude=lon,
        )
        if code == 200:
            success_logger.info(
                "\t".join(
                    [
                        msg,
                        str(tx.get("id", "")),
                        emp_code,
                        str(punch_dt.timestamp()),
                        str(tx.get("punch_state", "")),
                        str(tx.get("verify_type", "")),
                        json.dumps(tx, default=str),
                    ]
                )
            )
        else:
            failed_logger.error(
                "\t".join(
                    [
                        str(code),
                        str(tx.get("id", "")),
                        emp_code,
                        str(punch_dt.timestamp()),
                        str(tx.get("punch_state", "")),
                        str(tx.get("verify_type", "")),
                        json.dumps(tx, default=str),
                    ]
                )
            )
            if not any(err in msg for err in allowlisted_errors):
                raise RuntimeError(f"API call failed: {msg}")


def main():
    """Fetch devices from BioTime, get transactions, push to ERPNext."""
    try:
        last_lift_off = _safe_convert_date(
            status.get("lift_off_timestamp"), "%Y-%m-%d %H:%M:%S.%f"
        )
        now = datetime.datetime.now()
        if (
            last_lift_off
            and last_lift_off > now - datetime.timedelta(minutes=config.PULL_FREQUENCY)
        ) and config.PULL_FREQUENCY > 0:
            return

        status.set("lift_off_timestamp", str(now))
        status.save()
        info_logger.info("Cleared for lift off!")

        token = get_biotime_token()
        devices = get_biotime_devices(token)
        info_logger.info(f"Fetched {len(devices)} devices from BioTime")

        # Use last sync or 24h ago as start
        last_sync = _safe_convert_date(
            status.get("biotime_last_sync"), "%Y-%m-%d %H:%M:%S.%f"
        )
        start_time = last_sync or (now - datetime.timedelta(hours=24))
        end_time = now

        # Fetch all transactions in one call, then group by device
        all_transactions = get_biotime_transactions(token, start_time, end_time)
        info_logger.info(f"Fetched {len(all_transactions)} total transactions")

        by_device = {}
        unknown_count = 0
        for tx in all_transactions:
            sn = tx.get("terminal_sn") or tx.get("terminal", "") or ""
            if isinstance(sn, dict):
                sn = sn.get("sn", "") or str(sn.get("id", ""))
            sn = str(sn).strip()
            if sn:
                by_device.setdefault(sn, []).append(tx)
            else:
                unknown_count += 1
        if unknown_count:
            info_logger.info(f"Skipped {unknown_count} transactions with no terminal_sn")

        device_sns = {d.get("sn") or str(d.get("id", "")) for d in devices}
        for sn in device_sns:
            if sn not in by_device:
                by_device[sn] = []

        for device in devices:
            sn = device.get("sn") or str(device.get("id", ""))
            device_id = BIOTIME_DEVICE_ID_MAP.get(sn, sn)
            transactions = by_device.get(sn, [])
            info_logger.info(f"Processing device: {sn} ({device.get('alias', '')}) - {len(transactions)} transactions")

            success_logger = setup_logger(
                f"attendance_success_{device_id}",
                os.path.join(config.LOGS_DIRECTORY, f"attendance_success_log_{device_id}.log"),
            )
            failed_logger = setup_logger(
                f"attendance_failed_{device_id}",
                os.path.join(config.LOGS_DIRECTORY, f"attendance_failed_log_{device_id}.log"),
                level=logging.ERROR,
            )

            try:
                if transactions:
                    transactions.sort(
                        key=lambda t: (
                            t.get("punch_time") or t.get("upload_time") or ""
                        )
                    )
                    process_and_push_transactions(
                        transactions, sn, success_logger, failed_logger
                    )
                status.set(f"{device_id}_push_timestamp", str(now))
                status.set(f"{device_id}_pull_timestamp", str(now))
                status.save()
            except Exception:
                error_logger.exception(
                    f"Exception processing device {sn}: " + json.dumps(device, default=str)
                )

        status.set("biotime_last_sync", str(end_time))
        status.set("mission_accomplished_timestamp", str(now))
        status.save()
        info_logger.info("Mission Accomplished!")
    except Exception:
        error_logger.exception("Exception in main")


# Setup
os.makedirs(config.LOGS_DIRECTORY, exist_ok=True)
error_logger = setup_logger(
    "error_logger",
    os.path.join(config.LOGS_DIRECTORY, "biotime_error.log"),
    level=logging.ERROR,
)
info_logger = setup_logger(
    "info_logger",
    os.path.join(config.LOGS_DIRECTORY, "biotime_logs.log"),
)
status = PickleDB(os.path.join(config.LOGS_DIRECTORY, "biotime_status.json"))


def infinite_loop(sleep_time=15):
    print("BioTime → ERPNext sync running...")
    while True:
        try:
            main()
            time.sleep(sleep_time)
        except BaseException as e:
            print(e)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        main()
    else:
        infinite_loop()
