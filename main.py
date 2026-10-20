import os
import sys


# Make sure SecureCRT can import our separate files in the same folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import crt_helper
import vlan_extractor
import huawei_olt
import bdcom_olt

reload(crt_helper)
reload(vlan_extractor)
reload(huawei_olt)
reload(bdcom_olt)


def main():
    helper = crt_helper.CRTHelper(crt)

    # 1. Ask for VLAN Prompt
    vlan_id = crt.Dialog.Prompt('Enter Corporate Client VLAN ID:', 'VLAN Troubleshooter', '')
    if not vlan_id or not vlan_id.strip():
        return

    # 2. Extract all details for this VLAN from clients.csv
    client = vlan_extractor.extract_vlan_details(vlan_id)
    if not client:
        helper.end_the_program('VLAN ' + vlan_id.strip() + ' not found in clients.csv! Program finished.')
        return

    # 3. Open OLT Session in SecureCRT and enter Enable mode
    tab = helper.connect_olt_tab(client.olt_name, client.olt_ip)
    if not tab:
        return

    # 4. Route to the right Vendor Automation File
    if client.vendor == 'huawei':
        automation = huawei_olt.HuaweiOLT(helper, client)
    else:
        automation = bdcom_olt.BdcomOLT(helper, client)

    automation.run_flowchart()


main()