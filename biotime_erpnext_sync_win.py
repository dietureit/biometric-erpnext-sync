"""Windows service wrapper for BioTime → ERPNext sync."""
import time
from SMWinservice import SMWinservice
from biotime_erpnext_sync import main


class BioTimeERPNextSyncService(SMWinservice):
    _svc_name_ = "BioTimeERPNextSyncService"
    _svc_display_name_ = "BioTime ERPNext Attendance Sync Service"
    _svc_description_ = "Syncs attendance from BioTime 8.5 to ERPNext via API"

    def start(self):
        self.isrunning = True

    def stop(self):
        self.isrunning = False

    def main(self):
        while self.isrunning:
            main()
            time.sleep(15)


if __name__ == "__main__":
    BioTimeERPNextSyncService.parse_command_line()
