# bdcom_olt.py
import re

class BdcomOLT:
    def __init__(self, helper, client):
        self.helper = helper
        self.client = client

    def run_flowchart(self):
        # Disable BDCOM terminal pagination
        self.helper.send_cmd('terminal length 0')

        # STEP 1: Show VLAN MAC table
        capture_mac = self.helper.send_cmd('show mac address-table vlan ' + self.client.vlan)

        # Check if a MAC is learned on a GPON interface
        if 'gpon' in capture_mac.lower():
            # msg = 'Client MAC Found on VLAN ' + self.client.vlan + ' | OLT: ' + self.client.olt_name + ' | Port: gpon' + self.client.pon_port

            lines = capture_mac.strip().splitlines()
            msg = '\n'.join(lines[:-1])
            self.helper.copy_msg_and_exit('MAC Found (BDCOM)', 'CLI Output:\n', msg)
            return

        # STEP 2: MAC Not Found -> Call mac_not_found_flow
        self.mac_not_found_flow()

    def mac_not_found_flow(self):
        # Check ONU state and basic-info for Last Down Cause
        state_data = self.helper.send_cmd('show gpon onu state gpon ' + self.client.interface + ' ' + self.client.ontID)
        info_data = self.helper.send_cmd('show gpon interface gpon ' + self.client.pon_port + ' onu basic-info')
        combined = (state_data + '\n' + info_data).lower()

        is_online = ('operation' in combined or 'working' in combined or 'online' in combined) and ('offline' not in state_data.lower())

        # BRANCH A: ONU is OFFLINE -> Check reason (LOS vs DyingGasp)
        if not is_online:
            if 'los' in combined or 'lofi' in combined or 'wire down' in combined:
                msg = 'Fiber cut on VLAN ' + self.client.vlan + ' (' + self.client.address + ') | OLT: ' + self.client.olt_name + ' gpon' + self.client.pon_port + ' SN: ' + self.client.sn + '. Forward to team.'
                self.helper.copy_msg_and_exit('Fiber Cut Alert', 'ONU is OFFLINE (LOS/LOSi). Press Ctrl+C to copy:', msg)
            else:
                reason = 'DyingGasp (Power Off)' if 'dying' in combined else 'Power Off / Other Reason'
                msg = 'End device for VLAN ' + self.client.vlan + ' (' + self.client.address + ') is down due to ' + reason + ' | OLT: ' + self.client.olt_name + ' gpon' + self.client.pon_port + ' SN: ' + self.client.sn
                self.helper.copy_msg_and_exit('Device Power Off', 'ONU is OFFLINE. Press Ctrl+C to copy:', msg)
            return

        # BRANCH B: ONU is ONLINE -> Check Optical Power (-27 dBm rule)
        opt_data = self.helper.send_cmd('show gpon optical-transceiver-diagnosis interface gpon ' + self.client.pon_port)
        rx_power = None
        m_dbm = re.search(r'([-]\d+\.\d+)', opt_data)
        if m_dbm:
            try:
                rx_power = float(m_dbm.group(1))
            except Exception:
                rx_power = None

        if rx_power is not None and rx_power < -27.0:
            msg = 'High fiber loss (' + str(rx_power) + ' dBm) on VLAN ' + self.client.vlan + ' | OLT: ' + self.client.olt_name + ' gpon' + self.client.pon_port + '. Forward team and fix dB first.'
            self.helper.copy_msg_and_exit('High dBm Loss', 'Rx Power is worse than -27 dBm! Copy message:', msg)
            return

        # STEP 3: Power is Good -> Check Running Config on GPON Port
        cfg_data = self.helper.send_cmd('show running-config interface gpon ' + self.client.pon_port)

        if self.client.vlan in cfg_data:
            # Flowchart: is vlan config added? -> YES -> reboot the onu -> verify
            if self.helper.ask_yes_no('ONU is Online (' + str(rx_power) + ' dBm) and VLAN ' + self.client.vlan + ' is in running-config.\nReboot ONU now?'):
                self.helper.send_cmd('config')
                self.helper.send_cmd('interface gpon ' + self.client.pon_port)
                self.helper.send_cmd('gpon onu reboot')
                self.helper.send_cmd('exit')
                self.helper.send_cmd('exit')
                self.helper.end_the_program('ONU Reboot command sent on gpon' + self.client.pon_port + '! Wait 2 minutes and verify.')
        else:
            # Flowchart: is vlan config added? -> NO -> check vlan-profile / add config
            self.fix_bdcom_vlan_profile(cfg_data)

    def fix_bdcom_vlan_profile(self, current_port_cfg):
        """Checks if vlan-profile exists on BDCOM, creates if missing, and binds to GPON port."""
        prof_check = self.helper.send_cmd('show running-config | include vlan-profile')
        profile_name = 'vlan' + self.client.vlan

        if not self.helper.ask_yes_no('VLAN ' + self.client.vlan + ' is MISSING on gpon' + self.client.pon_port + '!\nCurrent Config:\n' + current_port_cfg.strip() + '\n\nApply VLAN profile ' + profile_name + ' now?'):
            return

        self.helper.send_cmd('config')
        # Flowchart: is vlan-profile exist? -> NO -> create vlan-profile
        if profile_name not in prof_check:
            self.helper.send_cmd('gpon-onu-vlan-profile ' + profile_name)
            self.helper.send_cmd('gpon-onu-vlan mode tag vlan ' + self.client.vlan)
            self.helper.send_cmd('exit')

        # Flowchart: add vlan-profile and verify
        self.helper.send_cmd('interface gpon ' + self.client.pon_port)
        self.helper.send_cmd('gpon onu uni 1 vlan-profile ' + profile_name)
        self.helper.send_cmd('exit')
        self.helper.send_cmd('exit')

        # Verify MAC table after adding config
        verify_mac = self.helper.send_cmd('show mac address-table vlan ' + self.client.vlan)
        self.helper.end_the_program('VLAN Profile applied! Verification Output:\n\n' + verify_mac.strip())