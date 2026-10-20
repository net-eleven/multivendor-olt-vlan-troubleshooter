# crt_helper.py
import time

# Folder inside SecureCRT's 'Sessions' root. Do not start with "Sessions/".
SESSION_FOLDER = '08-TCL/'

class CRTHelper:
    def __init__(self, crt_obj, tab_obj=None):
        self.crt = crt_obj
        self.tab = tab_obj if tab_obj else crt_obj

    def wait_for_me(self, wait='#'):
        self.tab.Screen.WaitForString(wait, 10)
        time.sleep(0.2)

    def send_cmd(self, cmd, need_cr=False, wait_prompt='#'):
        self.tab.Screen.Send(cmd + '\r')
        time.sleep(0.2)
        if need_cr:
            self.tab.Screen.Send('\r')
        capture_data = self.tab.Screen.ReadString(wait_prompt, 10)
        return capture_data

    def send_huawei_paged_cmd(self, cmd):
        self.tab.Screen.Send(cmd + '\r')
        time.sleep(0.3)
        self.tab.Screen.Send('q')
        capture_data = self.tab.Screen.ReadString('#', 10)
        return capture_data

    def end_the_program(self, msg='Program Finished'):
        self.crt.Dialog.MessageBox(msg)

    def copy_msg_and_exit(self, title, description, copy_text):
        self.crt.Dialog.Prompt(description, title, copy_text)

    def ask_yes_no(self, msg, title='Confirm Action'):
        choice = self.crt.Dialog.MessageBox(msg, title, 4 | 32)
        return choice == 6

    def connect_olt_tab(self, olt_name, olt_ip):
        # session_path becomes: 08-TCL/ks-bashundhara-ig-block-olt2
        session_path = SESSION_FOLDER + olt_name
        
        try:
            self.tab = self.crt.Session.ConnectInTab('/S "' + session_path + '"')
        except Exception:
            manual_path = self.crt.Dialog.Prompt(
                'Could not find SecureCRT session:\n' + session_path + ' (IP: ' + olt_ip + ')\n\n'
                'Enter exact path inside Sessions (e.g. 08-TCL/olt_name):',
                'Session Not Found',
                session_path
            )
            if not manual_path:
                return None
            clean_manual = manual_path.strip().replace('Sessions/', '', 1)
            self.tab = self.crt.Session.ConnectInTab('/S "' + clean_manual + '"')

        self.tab.Screen.Synchronous = True

        idx = self.tab.Screen.WaitForStrings(['>', '#'], 15)
        if idx == 1:
            self.tab.Screen.Send('enable\r')
            self.wait_for_me('#')

        return self.tab