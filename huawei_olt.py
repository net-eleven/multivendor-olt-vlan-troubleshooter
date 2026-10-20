# huawei_olt.py
import time
import re

class HuaweiOLT:
    def __init__(self, helper, client):
        self.helper = helper
        self.client = client
        self.profile = '10'  # Default Huawei line/srv profile ID from your script

    def run_flowchart(self):
        # Disable Huawei pagination so outputs don't get stuck
        self.helper.send_cmd('scroll 512')

        # STEP 1: Check if client MAC is found in VLAN
        capture_mac = self.helper.send_cmd('display mac-address vlan ' + self.client.vlan)

        # If F/S/P (e.g. 0/1/12) appears in the VLAN MAC output, client MAC is found!
        if self.client.fsp in capture_mac:
            msg = 'Client MAC Found on VLAN ' + self.client.vlan + ' | OLT: ' + self.client.olt_name + ' | Port: ' + self.client.pon_port
            # msg = capture_mac
            self.helper.copy_msg_and_exit('MAC Found (Huawei)', 'CLI Output:\n' + capture_mac.strip(), msg)
            return

        # STEP 2: MAC Not Found -> Check the SN / ONT Status
        self.mac_not_found_flow()

    def mac_not_found_flow(self):
        capture_info = self.helper.send_cmd('display ont info by-sn ' + self.client.sn)

        run_state = ''
        last_down_cause = ''

        for line in capture_info.splitlines():
            clean_line = line.upper().strip()
            if 'RUN STATE' in clean_line:
                run_state = line.split(':')[-1].strip().lower()
            if 'LAST DOWN CAUSE' in clean_line:
                last_down_cause = line.split(':')[-1].strip().lower()

        # BRANCH A: ONT is OFFLINE -> Find out reason (LOS/LOSi vs DyingGasp)
        if 'online' not in run_state:
            if 'los' in last_down_cause or 'lofi' in last_down_cause:
                msg = 'Fiber cut on VLAN ' + self.client.vlan + ' (' + self.client.address + ') | OLT: ' + self.client.olt_name + ' Port: ' + self.client.pon_port + ' SN: ' + self.client.sn + ' (Cause: ' + last_down_cause + '). Forward to team.'
                self.helper.copy_msg_and_exit('Fiber Cut Alert', 'ONT is OFFLINE due to LOS/LOSi. Press Ctrl+C to copy:', msg)
            else:
                msg = 'VLAN-' + self.client.vlan + ' is down due to ' + (last_down_cause or 'power off')
                self.helper.copy_msg_and_exit('Device Power Off', 'ONT is OFFLINE. Press Ctrl+C to copy:', msg)
            return

        # BRANCH B: ONT is ONLINE -> Check Optical Power (-28 dBm rule)
        self.helper.send_cmd('config')
        self.helper.send_cmd('interface gpon ' + self.client.interface)
        opt_data = self.helper.send_cmd('display ont optical-info ' + self.client.port + ' ' + self.client.ontID)
        self.helper.send_cmd('quit')

        rx_power = None
        for line in opt_data.splitlines():
            if 'Rx optical power(dBm)' in line:
                val_str = line.split(':')[-1].strip().split(' ')[0]
                try:
                    rx_power = float(val_str)
                except Exception:
                    rx_power = None

        if rx_power is not None and rx_power < -28.0:
            self.helper.send_cmd('quit')
            msg = 'High fiber loss (' + str(rx_power) + ' dBm) on VLAN ' + self.client.vlan + ' | OLT: ' + self.client.olt_name + ' Port: ' + self.client.pon_port + '. Forward team and fix dB first.'
            self.helper.copy_msg_and_exit('High dBm Loss', 'Rx Power is worse than -28 dBm! Copy message:', msg)
            return

        # STEP 3: Power is Good -> Check Running Config (service-port & native-vlan)
        cfg_data = self.helper.send_cmd('display current-configuration ont ' + self.client.fsp + ' ' + self.client.ontID)

        if ('vlan ' + self.client.vlan) in cfg_data:
            # Flowchart: is vlan config added? -> YES -> reboot the onu -> verify
            if self.helper.ask_yes_no('ONT is Online (' + str(rx_power) + ' dBm) and VLAN ' + self.client.vlan + ' config exists.\nReboot ONT now?'):
                self.helper.send_cmd('interface gpon ' + self.client.interface)
                self.helper.send_cmd('ont reset ' + self.client.port + ' ' + self.client.ontID)
                self.helper.wait_for_me('Are you sure')
                self.helper.send_cmd('y')
                self.helper.send_cmd('quit')
                self.helper.send_cmd('quit')
                self.helper.end_the_program('ONT Reboot command sent! Wait 2 minutes and verify MAC.')
            else:
                self.helper.send_cmd('quit')
        else:
            # Flowchart: is vlan config added? -> NO -> add vlan config and verify
            if self.helper.ask_yes_no('VLAN ' + self.client.vlan + ' config is MISSING on ONT!\nAdd native-vlan and service-port now?'):
                self.helper.send_cmd('interface gpon ' + self.client.interface)
                self.helper.send_cmd('ont port native-vlan ' + self.client.port + ' ' + self.client.ontID + ' eth 1 vlan ' + self.client.vlan, need_cr=True)
                self.helper.send_cmd('quit')
                self.helper.send_cmd('service-port vlan ' + self.client.vlan + ' gpon ' + self.client.fsp + ' ont ' + self.client.ontID + ' gemport 0 multi-service user-vlan ' + self.client.vlan, need_cr=True)
                self.helper.send_cmd('quit')
                self.helper.end_the_program('VLAN ' + self.client.vlan + ' config added! Re-checking MAC table...')
            else:
                self.helper.send_cmd('quit')