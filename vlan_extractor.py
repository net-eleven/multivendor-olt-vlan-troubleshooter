# vlan_extractor.py
import os
import csv

class VlanData:
    def __init__(self, row_dict):
        self.vlan = row_dict.get('VLAN', '')
        self.address = row_dict.get('Address', '')
        self.olt_name = row_dict.get('OLT_Name', '')
        self.vendor = row_dict.get('Vendor', 'bdcom').lower()
        self.olt_ip = row_dict.get('OLT_IP', '')
        self.pon_port = row_dict.get('PON_Port', '')
        self.sn = row_dict.get('ONU_SN', '').replace('SN-', '')
        self.status = row_dict.get('Status', '')

        # Pre-split interface, port, and ontID for Huawei & BDCOM commands
        self.fsp = ''
        self.interface = ''
        self.port = ''
        self.ontID = ''

        if ':' in self.pon_port:
            parts = self.pon_port.split(':')
            self.fsp = parts[0].strip()      # '0/1/12' (Huawei) or '0/1' (BDCOM)
            self.ontID = parts[1].strip()    # '98' (Huawei) or '46' (BDCOM)

            if self.vendor == 'huawei' and '/' in self.fsp:
                index = self.fsp.split('/')
                self.interface = index[0] + '/' + index[1]  # '0/1'
                self.port = index[2]                        # '12'
            else:
                self.interface = self.fsp                   # '0/1'


def extract_vlan_details(vlan_id):
    """Searches clients.csv and returns a VlanData object, or None if not found."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, 'clients.csv')

    if not os.path.exists(csv_path):
        return None

    target_vlan = str(vlan_id).strip()

    with open(csv_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean_row = {}
            for k, v in row.items():
                if k is not None:
                    clean_key = k.replace('\xef\xbb\xbf', '').strip()
                    clean_row[clean_key] = v.strip() if v else ''

            if clean_row.get('VLAN', '') == target_vlan:
                return VlanData(clean_row)

    return None