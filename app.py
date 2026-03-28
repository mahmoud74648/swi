import os
import sys

from flask import Flask, render_template, request, redirect, url_for, session
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import network_logic



app = Flask(__name__)
app.secret_key = 'An635241iS@'

USER_DB = {"foe": "An635241iS@Cisco"}


@app.after_request
def add_no_cache_headers(response):
    # Prevent browsers from showing protected pages after logout via back/forward cache.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# List of your switches
SWITCHES = [
    {'id': 3, 'name': 'Basement-first-SW', 'ip': '172.20.60.8'},
    {'id': 4, 'name': 'Basement-second-SW', 'ip': '172.20.60.9'},
    {'id': 5, 'name': 'Ground-Rack1-Sw', 'ip': '172.20.60.10'},
    {'id': 6, 'name': 'Ground-Rack1-Sw-C', 'ip': '172.20.60.11'},
    {'id': 7, 'name': 'Temp-Ground-Rack1-Sw', 'ip': '172.20.60.30'},
    {'id': 8, 'name': 'Ground-Rack2-Sw1', 'ip': '172.20.60.12'},
    {'id': 9, 'name': 'Temp-Ground-Rack2-Sw', 'ip': '172.20.60.31'},
    {'id': 10, 'name': 'First-Rack1-Sw', 'ip': '172.20.60.13'},
    {'id': 11, 'name': 'Temp-First-Rack1-Sw', 'ip': '172.20.60.32'},
    {'id': 12, 'name': 'First-Rack2-Sw', 'ip': '172.20.60.14'},
    {'id': 13, 'name': 'Temp-First-Rack2-Sw1', 'ip': '172.20.60.33'},
    {'id': 14, 'name': 'Temp-First-Rack2-Sw2', 'ip': '172.20.60.34'},
    {'id': 15, 'name': 'Second-Rack1-Sw', 'ip': '172.20.60.15'},
    {'id': 16, 'name': 'Temp-Second-Rack2-Sw1', 'ip': '172.20.60.35'},
    {'id': 17, 'name': 'Temp-Second-Rack2-Sw2', 'ip': '172.20.60.36'},
    {'id': 18, 'name': 'Second-Rack2-Sw', 'ip': '172.20.60.16'},
    {'id': 19, 'name': 'Temp-Second-Rack2-Sw1', 'ip': '172.20.60.37'},
    {'id': 20, 'name': 'Temp-Second-Rack2-Sw2', 'ip': '172.20.60.38'},
    {'id': 21, 'name': 'Third-Rack-Sw', 'ip': '172.20.60.17'},
    {'id': 22, 'name': 'Temp-Third-Rack-Sw', 'ip': '172.20.60.39'},
    {'id': 23, 'name': 'Fourth-Rack-Sw', 'ip': '172.20.60.18'},
    {'id': 24, 'name': 'Hall-Rack-SW', 'ip': '172.20.60.19'},
    {'id': 25, 'name': 'Gate1-Rack-Sw', 'ip': '172.20.60.20'},
    {'id': 26, 'name': 'Gate2-Rack-Sw', 'ip': '172.20.60.22'},
    {'id': 27, 'name': 'Gate3-Rack-Sw', 'ip': '172.20.60.23'},
    {'id': 28, 'name': 'Fence-Rack-Sw', 'ip': '172.20.60.24'},
    {'id': 29, 'name': 'Core-Secretary-Sw', 'ip': '172.20.60.90'},
    {'id': 30, 'name': 'Secretary-Rack-Sw1', 'ip': '172.20.60.91'},
    {'id': 31, 'name': 'Secretary-Rack-Sw2', 'ip': '172.20.60.92'},
    {'id': 31, 'name': 'Secretary-Rack-Sw3', 'ip': '172.20.60.93'},
]

# Cache for Port Mapping Excel Data
PORT_MAPPING_FILE = os.path.join(os.path.dirname(__file__), 'FINAL-PORT-MAP -TEMP.xlsx')
PORT_MAPPING_CACHE = {
    'mtime': 0,
    'sheets_view': [],
    'search_index': []
}

def get_cached_port_mapping():
    global PORT_MAPPING_CACHE
    try:
        if not os.path.exists(PORT_MAPPING_FILE):
            return None

        current_mtime = os.path.getmtime(PORT_MAPPING_FILE)
        if PORT_MAPPING_CACHE['mtime'] == current_mtime and PORT_MAPPING_CACHE['sheets_view']:
            return PORT_MAPPING_CACHE

        print("DEBUG: Loading and caching Excel file...")
        # Read all sheets at once with header=None to capture all rows for search
        xl = pd.read_excel(PORT_MAPPING_FILE, sheet_name=None, header=None)
        
        new_sheets_view = []
        new_search_index = []

        for sheet_name, df in xl.items():
            df = df.fillna('')
            rows = df.values.tolist()

            # 1. Prepare View Data (Treat first row as header)
            if rows:
                headers = [str(c) for c in rows[0]]
                # Convert all cells to string for consistency
                view_rows = [[str(cell) if cell != '' else '' for cell in row] for row in rows[1:]]
            else:
                headers = []
                view_rows = []

            new_sheets_view.append({
                'name': sheet_name,
                'headers': headers,
                'rows': view_rows
            })

            # 2. Build Search Index
            # Iterate rows to find 'LABEL' and extract context
            for i, row in enumerate(rows):
                if not row: continue
                col0 = str(row[0]).strip()
                if col0 != 'LABEL':
                    continue

                # Context rows
                # i-2: PP, i-1: DISC, i: LABEL, i+1: SW
                pp_row   = rows[i - 2] if i >= 2 else [''] * len(row)
                disc_row = rows[i - 1] if i >= 1 else [''] * len(row)
                sw_row   = rows[i + 1] if i + 1 < len(rows) else [''] * len(row)
                
                pp_label = str(pp_row[0]).strip()

                for col_idx in range(1, len(row)):
                    label_val = str(row[col_idx]).strip()
                    if not label_val or label_val.lower() == 'nan':
                        continue

                    # Port number
                    raw_port = str(pp_row[col_idx]).strip() if col_idx < len(pp_row) else ''
                    try:
                        # Handle float '1.0' -> '1'
                        port_num = str(int(float(raw_port))) if raw_port and raw_port != '' else ''
                    except (ValueError, TypeError):
                        port_num = raw_port

                    disc     = str(disc_row[col_idx]).strip() if col_idx < len(disc_row) else ''
                    sw_port  = str(sw_row[col_idx]).strip()   if col_idx < len(sw_row)   else ''

                    new_search_index.append({
                        'location':    sheet_name,
                        'pp':          pp_label,
                        'port':        port_num,
                        'label':       label_val,
                        'discipline':  disc if disc.lower() != 'nan' else '',
                        'switch_port': sw_port if sw_port.lower() != 'nan' else '',
                        'label_lower': label_val.lower() # Pre-compute lower for search
                    })

        PORT_MAPPING_CACHE = {
            'mtime': current_mtime,
            'sheets_view': new_sheets_view,
            'search_index': new_search_index
        }
        print("DEBUG: Excel file cached successfully.")
        return PORT_MAPPING_CACHE

    except Exception as e:
        print(f"ERROR: Caching failed: {e}")
        return None


@app.route('/')
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/auth', methods=['POST'])
def auth():
    if request.is_json:
        data = request.json
        username = data.get('username')
        password = data.get('password')
    else:
        username = request.form.get('username')
        password = request.form.get('password')

    if USER_DB.get(username) == password:
        session['logged_in'] = True
        print("DEBUG: Password matched. Session set to True.")
        
        if request.is_json:
            return {"status": "success", "token": "valid_session_token"}, 200
        return redirect(url_for('dashboard'))
    
    print("DEBUG: Password did not match.")
    if request.is_json:
        return {"status": "error", "message": "Invalid username or password"}, 401
    return render_template('login.html', error="Invalid username or password")

@app.route('/session', methods=['GET'])
def session_status():
    return {"logged_in": bool(session.get('logged_in'))}, 200


@app.route('/logout', methods=['GET'])
def logout_get():
    session.clear()
    return redirect(url_for('login'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return {"status": "logged_out"}, 200


@app.route('/dashboard')
def dashboard():
    print(f"DEBUG: Session 'logged_in' value is: {session.get('logged_in')}")
    if not session.get('logged_in'):
        print("DEBUG: Redirecting to login because session is empty.")
        return redirect(url_for('login'))
    return render_template('dashboard_view.html', switches=SWITCHES)


@app.route('/switch/<ip>')
def switch_manage(ip):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    import network_logic
    port_list = network_logic.get_ports(ip)
    return render_template('switch_detail.html', switch_ip=ip, ports=port_list)


@app.route('/update_vlan', methods=['POST'])
def update_vlan():
    data = request.json
    ip = data.get('ip')
    interface = data.get('interface')
    vlan = data.get('vlan')

    import network_logic
    try:
        network_logic.update_port_vlan(ip, interface, vlan)
        return {"status": "success"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/save_config', methods=['POST'])
def save_cfg():
    data = request.json
    import network_logic
    network_logic.save_config(data['ip'])
    return {"status": "saved"}, 200


@app.route('/update_port_mode', methods=['POST'])
def update_port_mode():
    data = request.json
    import network_logic
    try:
        network_logic.configure_port_logic(
            data['ip'],
            data['interface'],
            data['mode'],
            data.get('vlan'),
            data.get('allowed')
        )
        return {"status": "success"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/default_port', methods=['POST'])
def default_port():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    data = request.json
    ip = data.get('ip')
    interface = data.get('interface')

    import network_logic
    try:
        network_logic.reset_port_to_default(ip, interface)
        return {"status": "success"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/configure_rstp', methods=['POST'])
def configure_rstp():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    data = request.json
    ip = data.get('ip')
    interface = data.get('interface')
    enable = data.get('enable', True)  # True = enable RSTP, False = disable

    import network_logic
    try:
        success = network_logic.configure_rstp(ip, interface, enable)
        if success:
            return {"status": "success"}, 200
        else:
            return {"status": "error", "message": "Failed to apply RSTP configuration"}, 500
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/rstp_status', methods=['GET'])
def rstp_status():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    ip = request.args.get('ip')
    interface = request.args.get('interface')

    import network_logic
    try:
        status = network_logic.get_rstp_status(ip, interface)
        return status, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/configure_port_isolation', methods=['POST'])
def configure_port_isolation():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    data = request.json
    ip = data.get('ip')
    interface = data.get('interface')
    enable = data.get('enable', True)  # True = isolate, False = remove isolation

    import network_logic
    try:
        success = network_logic.configure_port_isolation(ip, interface, enable)
        if success:
            return {"status": "success"}, 200
        else:
            return {"status": "error", "message": "Failed to apply port isolation"}, 500
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/port_isolation_status', methods=['GET'])
def port_isolation_status():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    ip = request.args.get('ip')
    interface = request.args.get('interface')

    import network_logic
    try:
        status = network_logic.get_port_isolation_status(ip, interface)
        return status, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/configure_port_shutdown', methods=['POST'])
def configure_port_shutdown():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    data = request.json
    ip = data.get('ip')
    interface = data.get('interface')
    enable = data.get('enable', True)  # True = shutdown, False = no shutdown

    import network_logic
    try:
        success = network_logic.configure_port_shutdown(ip, interface, enable)
        if success:
            return {"status": "success"}, 200
        else:
            return {"status": "error", "message": "Failed to apply port shutdown configuration"}, 500
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/port_shutdown_status', methods=['GET'])
def port_shutdown_status():
    if not session.get('logged_in'):
        return "Unauthorized", 401

    ip = request.args.get('ip')
    interface = request.args.get('interface')

    import network_logic
    try:
        status = network_logic.get_port_shutdown_status(ip, interface)
        return status, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.route('/portmapping/search')
def portmapping_search():
    if not session.get('logged_in'):
        return {"error": "Unauthorized"}, 401

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return {"results": []}, 200

    cache = get_cached_port_mapping()
    if not cache:
         return {"error": "Port mapping data unavailable."}, 500

    q_lower = query.lower()
    
    # Filter from pre-built search index
    # (Checking 'label_lower' which we added to the index)
    results = [
        item for item in cache['search_index'] 
        if q_lower in item['label_lower']
    ]
    
    return {"results": results, "count": len(results)}, 200


@app.route('/search_mac', methods=['POST'])
def search_mac_route():
    if not session.get('logged_in'):
        return {"error": "Unauthorized"}, 401

    mac_address = request.json.get('mac_address', '').strip()
    if not mac_address:
        return {"error": "MAC address is required"}, 400

    import network_logic
    results = []

    def check_switch(sw):
        mac_entries = network_logic.search_mac(sw['ip'], mac_address)
        if mac_entries:
            return {
                'switch_name': sw['name'],
                'switch_ip': sw['ip'],
                'entries': mac_entries
            }
        return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(check_switch, sw) for sw in SWITCHES]
        for future in futures:
            res = future.result()
            if res:
                results.append(res)

    return {"results": results}, 200


@app.route('/portmapping')
def portmapping():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    cache = get_cached_port_mapping()
    if cache:
        sheets_data = cache['sheets_view']
        error = None
    else:
        sheets_data = []
        error = 'Port mapping file not found or invalid.'

    return render_template('portmapping.html', sheets=sheets_data, error=error)


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
