from netmiko import ConnectHandler


def get_ports(ip):
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }

    try:
        with ConnectHandler(**device) as net_connect:
            # Detect if this is a CBS/SG switch (SMB) vs Catalyst (IOS)
            ver_out = net_connect.send_command("show version")
            print(f"DEBUG: 'show version' output snippet (first 500 chars):\n{ver_out[:500]}")
            
            is_cbs = "cbs" in ver_out.lower() or "sx300" in ver_out.lower() or "sg300" in ver_out.lower() or "sf300" in ver_out.lower() or "200 series" in ver_out.lower() or "350 series" in ver_out.lower() or "550x" in ver_out.lower()
            print(f"DEBUG: Detected CBS/SMB Switch? {is_cbs}")

            if is_cbs:
                # CBS/SG Output Handling
                raw_output = net_connect.send_command("show interface status")
                print(f"DEBUG: Raw 'show interface status' output:\n{raw_output}")
                
                parsed_ports = []
                import re
                
                # Try a more flexible regex or manual split
                lines = raw_output.splitlines()
                # Skip header lines if possible or filter by port name patterns
                for line in lines:
                    parts = line.split()
                    # Check if line starts with typical port names (g1, gi1, te1, fa1, etc.)
                    # Often CBS uses 'gi1', 'te1' etc without slashes, or 'gi1/0/1'
                    if len(parts) >= 2 and re.match(r'^(gi|te|fa|xi)[0-9]', parts[0].lower()):
                        port_name = parts[0]
                        # Status is usually the last column or near end "Up" or "Down"
                        # We need to be careful. Let's assume standard CBS output for now.
                        status_raw = parts[-1].lower()
                        status = "connected" if "up" in status_raw else "notconnect"
                        
                        duplex = 'auto'
                        speed = 'auto'
                        # Try to find speed/duplex if available in columns
                        # Example: gi1 1G-Copper Full 1000 Enabled Up
                        if len(parts) >= 4:
                             # Very naive mapping, just to get something
                             duplex = parts[2] 
                             speed = parts[3]

                        parsed_ports.append({
                            'port': port_name,
                            'name': '', 
                            'status': status,
                            'vlan_id': '1', 
                            'duplex': duplex,
                            'speed': speed
                        })
                print(f"DEBUG: Parsed {len(parsed_ports)} ports from CBS logic.")
                return parsed_ports

            else:
                # Standard IOS (Catalyst)
                print("DEBUG: Using Standard IOS TextFSM logic.")
                output = net_connect.send_command("show interface status", use_textfsm=True)
                if isinstance(output, str):
                    print("DEBUG: TextFSM returned string instead of list. Raw output:")
                    print(output)
                    # Attempt manual fallback for standard IOS if TextFSM failed
                    return []
                return output

    except Exception as e:
        print(f"Connection Error: {e}")
        return []


def configure_port_logic(ip, interface, mode, vlan=None, allowed=None):
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }

    commands = [f"interface {interface}"]

    if mode == "trunk":

        commands.append("switchport mode trunk")
        # 3. Handle allowed VLANs
        if allowed:
            if allowed.lower() == "all":
                commands.append("switchport trunk allowed vlan all")
            else:
                commands.append(f"switchport trunk allowed vlan {allowed}")

    elif mode == "access":
        commands.append("switchport mode access")
        if vlan:
            commands.append(f"switchport access vlan {vlan}")

    try:
        with ConnectHandler(**device) as net_connect:
            # Using send_config_set handles the config mode automatically
            output = net_connect.send_config_set(commands)
            # Check your terminal to see if the switch complained!
            print(f"DEBUG OUTPUT: {output}")
            return True
    except Exception as e:
        print(f"SSH Error: {e}")
        return False

    with ConnectHandler(**device) as net_connect:
        return net_connect.send_config_set(commands)


def save_config(ip):
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }
    with ConnectHandler(**device) as net_connect:
        # Executes 'write memory' or 'copy running-config startup-config'
        return net_connect.save_config()


def reset_port_to_default(ip, interface):
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }
    with ConnectHandler(**device) as net_connect:
        # Move to config mode
        net_connect.config_mode()

        # We send the command specifically.
        # Note: 'default interface' is executed at the (config)# prompt,
        # NOT inside the (config-if)# prompt.
        command = f"default interface {interface}"
        output = net_connect.send_command(command, expect_string=r"#")

        # Force a save to ensure it sticks
        net_connect.save_config()
        return output


def configure_rstp(ip, interface, enable):
    """
    Enable or disable RSTP (Rapid Spanning Tree) on a specific interface.
    enable=True  -> sets portfast + bpduguard on the interface
    enable=False -> removes portfast + bpduguard from the interface
    Also ensures the global STP mode is rapid-pvst.
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }

    global_commands = ['spanning-tree mode rapid-pvst']

    if enable:
        interface_commands = [
            f'interface {interface}',
            'spanning-tree portfast',
            'spanning-tree bpduguard enable',
        ]
    else:
        interface_commands = [
            f'interface {interface}',
            'no spanning-tree portfast',
            'no spanning-tree bpduguard enable',
        ]

    try:
        with ConnectHandler(**device) as net_connect:
            output = net_connect.send_config_set(global_commands + interface_commands)
            print(f"DEBUG RSTP OUTPUT: {output}")
            return True
    except Exception as e:
        print(f"SSH RSTP Error: {e}")
        return False


def get_rstp_status(ip, interface):
    """
    Returns a dict with keys 'portfast' and 'bpduguard' (bool each)
    by parsing 'show running-config interface <intf>'.
    This works even when the port is down (unlike 'show spanning-tree detail').
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }
    try:
        with ConnectHandler(**device) as net_connect:
            output = net_connect.send_command(
                f'show running-config interface {interface}'
            )
            output_lower = output.lower()
            # Check for positive presence and absence of 'no' prefix
            portfast = ('spanning-tree portfast' in output_lower and
                        'no spanning-tree portfast' not in output_lower)
            bpduguard = ('spanning-tree bpduguard enable' in output_lower and
                         'no spanning-tree bpduguard enable' not in output_lower)
            print(f"DEBUG RSTP STATUS [{interface}]: portfast={portfast}, bpduguard={bpduguard}")
            print(f"DEBUG RAW OUTPUT:\n{output}")
            return {'portfast': portfast, 'bpduguard': bpduguard}
    except Exception as e:
        print(f"SSH RSTP Status Error: {e}")
        return {'portfast': False, 'bpduguard': False}


def configure_port_isolation(ip, interface, enable):
    """
    Enable or disable port isolation (switchport protected) on a specific interface.
    enable=True  -> adds 'switchport protected'
    enable=False -> removes 'switchport protected'
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }

    if enable:
        commands = [
            f'interface {interface}',
            'switchport protected',
        ]
    else:
        commands = [
            f'interface {interface}',
            'no switchport protected',
        ]

    try:
        with ConnectHandler(**device) as net_connect:
            output = net_connect.send_config_set(commands)
            print(f"DEBUG PORT ISOLATION OUTPUT: {output}")
            return True
    except Exception as e:
        print(f"SSH Port Isolation Error: {e}")
        return False


def get_port_isolation_status(ip, interface):
    """
    Returns a dict with key 'isolated' (bool) by parsing
    'show running-config interface <intf>'.
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }
    try:
        with ConnectHandler(**device) as net_connect:
            output = net_connect.send_command(
                f'show running-config interface {interface}'
            )
            output_lower = output.lower()
            isolated = ('switchport protected' in output_lower and
                        'no switchport protected' not in output_lower)
            print(f"DEBUG ISOLATION STATUS [{interface}]: isolated={isolated}")
            print(f"DEBUG RAW OUTPUT:\n{output}")
            return {'isolated': isolated}
    except Exception as e:
        print(f"SSH Port Isolation Status Error: {e}")
        return {'isolated': False}


def configure_port_shutdown(ip, interface, enable):
    """
    Enable or disable port shutdown on a specific interface.
    enable=True  -> adds 'shutdown' (administratively down)
    enable=False -> adds 'no shutdown' (administratively up)
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }

    if enable:
        commands = [
            f'interface {interface}',
            'shutdown',
        ]
    else:
        commands = [
            f'interface {interface}',
            'no shutdown',
        ]

    try:
        with ConnectHandler(**device) as net_connect:
            output = net_connect.send_config_set(commands)
            print(f"DEBUG PORT SHUTDOWN OUTPUT: {output}")
            return True
    except Exception as e:
        print(f"SSH Port Shutdown Error: {e}")
        return False


def get_port_shutdown_status(ip, interface):
    """
    Returns a dict with key 'shutdown' (bool) by parsing
    'show running-config interface <intf>'.
    If 'shutdown' is present, the port is administratively down.
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }
    try:
        with ConnectHandler(**device) as net_connect:
            output = net_connect.send_command(
                f'show running-config interface {interface}'
            )
            output_lower = output.lower()
            # In running-config, 'shutdown' appears when admin down.
            # 'no shutdown' is default and usually doesn't appear, or appears explicitly depending on version.
            # We look for explicit 'shutdown' command.
            is_shutdown = ('shutdown' in output_lower and
                           'no shutdown' not in output_lower)
            
            print(f"DEBUG SHUTDOWN STATUS [{interface}]: shutdown={is_shutdown}")
            print(f"DEBUG RAW OUTPUT:\n{output}")
            return {'shutdown': is_shutdown}
    except Exception as e:
        print(f"SSH Port Shutdown Status Error: {e}")
        return {'shutdown': False}


def search_mac(ip, mac_address):
    """
    Searches for a MAC address on the switch at the given IP.
    Returns a list of matching entries (port and VLAN),
    filtered to only include physical access ports (e.g. Gi2/0/8).
    Excludes uplinks like TenGigabitEthernet (Te).
    """
    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': 'foe',
        'password': 'An635241iS@SWHQ',
        'conn_timeout': 5,
        'timeout': 10,
    }
    try:
        with ConnectHandler(**device) as net_connect:
            cmd = f'show mac address-table | include {mac_address}'
            output = net_connect.send_command(cmd)
            
            results = []
            # Physical access port prefixes to include (Gigabit, FastEthernet, etc.)
            physical_prefixes = ('gi', 'fa', 'eth', 'ge', 'xi', 'ti')
            # Port patterns to exclude (Uplinks like Te, Port-channels, etc.)
            exclude_prefixes = ('te', 'ten', 'po', 'vl', 'lo', 'tu', 'di', 'vi', 'cpu', 'sup', 'null', 'tw', 'hu', 'fo')
            
            for line in output.splitlines():
                line = line.strip()
                if line:
                    parts = line.split()
                    # Typical Cisco output: VLAN  MAC Address  Type  Port
                    # 100    0011.2233.4455    DYNAMIC     Gi1/0/1
                    if len(parts) >= 4:
                        port = parts[3]
                        port_lower = port.lower()
                        
                        # Check if it starts with a physical prefix AND doesn't start with an exclude prefix
                        is_physical = any(port_lower.startswith(pre) for pre in physical_prefixes)
                        is_excluded = any(port_lower.startswith(pre) for pre in exclude_prefixes)
                        
                        if is_physical and not is_excluded:
                            results.append({
                                'vlan': parts[0],
                                'mac': parts[1],
                                'type': parts[2],
                                'port': port
                            })
            return results
    except Exception as e:
        print(f"SSH MAC Search Error on {ip}: {e}")
        return []
