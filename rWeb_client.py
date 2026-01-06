#!/usr/bin/env python3
# lxmf_html_browser.py - Web-based LXMF HTML Browser

import os
import sys
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# Check dependencies
try:
    import RNS
    import LXMF
except ImportError:
    print("ERROR: Required packages not found!")
    print("Install with: pip install rns lxmf flask flask-socketio")
    sys.exit(1)

class HTMLServerAnnounceHandler:
    """Announce handler specifically for HTML servers (LXMF delivery destinations)"""
    def __init__(self, browser):
        self.aspect_filter = "lxmf.delivery"  # Only catch LXMF delivery announces
        self.browser = browser
    
    def received_announce(self, destination_hash, announced_identity, app_data):
        """Called when an LXMF delivery destination announces"""
        try:
            peer_hash_str = RNS.prettyhexrep(destination_hash)
            
            # Skip our own announces
            if hasattr(self.browser, 'lxmf_destination'):
                if destination_hash == self.browser.lxmf_destination.hash:
                    return
            
            print(f"[ANNOUNCE] LXMF delivery destination: {peer_hash_str[:20]}...")
            
            if app_data:
                # Use LXMF's helper to extract display name
                from LXMF import display_name_from_app_data
                display_name = display_name_from_app_data(app_data)
                
                if display_name:
                    print(f"[ANNOUNCE]   Name: '{display_name}'")
                    
                    # Check for HTML marker
                    if '[HTML]' in display_name or 'HTML' in display_name:
                        print(f"\n{'='*60}")
                        print(f"[ANNOUNCE] ✓✓✓ HTML SERVER FOUND ✓✓✓")
                        print(f"[ANNOUNCE] Name: {display_name}")
                        print(f"[ANNOUNCE] Hash: {peer_hash_str}")
                        print(f"{'='*60}\n")
                        self.browser._handle_discovery(peer_hash_str, display_name)
        
        except Exception as e:
            print(f"[!] HTML announce handler error: {e}")
            import traceback
            traceback.print_exc()

class LXMFHTMLBrowser:
    def __init__(self, storage_path=None, identity_path=None):
        # Terminal UI and paths setup
        if storage_path is None:
            storage_path = os.path.expanduser("~/.lxmf_html_browser")
        
        self.storage_path = storage_path
        self.cache_path = os.path.join(storage_path, "cache")
        self.html_cache_path = os.path.join(storage_path, "html_cache")
        self.bookmarks_file = os.path.join(storage_path, "bookmarks.json")
        self.history_file = os.path.join(storage_path, "history.json")
        self.discovered_file = os.path.join(storage_path, "discovered_servers.json")
        self.identity_file = identity_path or os.path.join(storage_path, "identity")
        
        # HTML field constants
        self.FIELD_HTML_CONTENT = 10
        self.FIELD_HTML_REQUEST = 11
        
        # Runtime
        self.bookmarks = []
        self.history = []
        self.discovered_servers = {}
        self.known_peers = set()
        self.pending_requests = {}
        self.socketio = None
        self.running = True
        
        # Initialize storage and load data
        self._init_storage()
        self._load_data()
        
        # Initialize Reticulum FIRST
        self._init_reticulum()
        
        # Register announce handler BEFORE LXMF is initialized
        print("\n" + "="*60)
        print("REGISTERING ANNOUNCE HANDLER (before LXMF)")
        print("="*60 + "\n")
        self._setup_announce_handler()
        
        # NOW initialize LXMF (this will register its own handlers after ours)
        self._init_lxmf()
        
        # Don't need peer monitor
        print("="*60)
        print("Browser initialized - listening for announces")
        print("="*60 + "\n")    

    def _init_storage(self):
        for path in [self.storage_path, self.cache_path, self.html_cache_path]:
            if not os.path.exists(path):
                os.makedirs(path)
    
    def _load_data(self):
        if os.path.exists(self.bookmarks_file):
            try:
                with open(self.bookmarks_file, 'r') as f:
                    self.bookmarks = json.load(f)
            except:
                self.bookmarks = []
        
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
            except:
                self.history = []
        
        if os.path.exists(self.discovered_file):
            try:
                with open(self.discovered_file, 'r') as f:
                    self.discovered_servers = json.load(f)
                    for server_hash in self.discovered_servers.keys():
                        self.known_peers.add(server_hash)
            except:
                self.discovered_servers = {}
    
    def _save_data(self):
        with open(self.bookmarks_file, 'w') as f:
            json.dump(self.bookmarks, f, indent=2)
        
        if len(self.history) > 100:
            self.history = self.history[-100:]
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
        
        with open(self.discovered_file, 'w') as f:
            json.dump(self.discovered_servers, f, indent=2)
    
    def _init_reticulum(self):
        """Initialize Reticulum"""
        print("\n" + "="*60)
        print("LXMF HTML Browser - Initializing Reticulum")
        print("="*60 + "\n")
        
        try:
            self.reticulum = RNS.Reticulum()
            print("✓ Reticulum initialized")
            print(f"  Version: {RNS.__version__ if hasattr(RNS, '__version__') else 'Unknown'}")
            print(f"  Transport available: {hasattr(RNS, 'Transport')}")
            print(f"  Can register handlers: {hasattr(RNS.Transport, 'register_announce_handler')}")
        except Exception as e:
            print(f"ERROR: Failed to initialize Reticulum: {e}")
            sys.exit(1)
        
        # Load or create identity
        if os.path.exists(self.identity_file):
            self.identity = RNS.Identity.from_file(self.identity_file)
            print(f"✓ Loaded identity")
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(self.identity_file)
            print(f"✓ Created new identity")
    
    def _init_lxmf(self):
        self.message_router = LXMF.LXMRouter(
            identity=self.identity,
            storagepath=self.storage_path
        )
        
        self.lxmf_destination = self.message_router.register_delivery_identity(
            self.identity,
            display_name="LXMF HTML Browser"
        )
        
        self.message_router.register_delivery_callback(self._handle_message)
        
        self.lxmf_destination.announce()
        
        self.client_hash = RNS.prettyhexrep(self.lxmf_destination.hash)
        print(f"✓ LXMF initialized")
        print(f"  Client: {self.client_hash}\n")

    def _setup_announce_handler(self):
        """Set up announce handler for HTML servers"""
        print("Setting up HTML server announce handler...")
        
        # Create handler instance
        self.html_announce_handler = HTMLServerAnnounceHandler(self)
        
        # Register with RNS Transport
        RNS.Transport.register_announce_handler(self.html_announce_handler)
        
        print("✓ HTML server announce handler registered")
        print(f"  Aspect filter: {self.html_announce_handler.aspect_filter}\n")

    def _init_lxmf(self):
        self.message_router = LXMF.LXMRouter(
            identity=self.identity,
            storagepath=self.storage_path
        )
        
        self.lxmf_destination = self.message_router.register_delivery_identity(
            self.identity,
            display_name="LXMF HTML Browser"
        )
        
        self.message_router.register_delivery_callback(self._handle_message)
        
        self.lxmf_destination.announce()
        
        self.client_hash = RNS.prettyhexrep(self.lxmf_destination.hash)
        print(f"✓ LXMF initialized")
        print(f"  Client: {self.client_hash}\n")
        
        # Process any discoveries that happened before LXMF was ready
        if hasattr(self, '_pending_discoveries') and len(self._pending_discoveries) > 0:
            print(f"[*] Processing {len(self._pending_discoveries)} pending discoveries...")
            for discovery in self._pending_discoveries:
                peer_hash_str, display_name = discovery
                # Skip our own hash now that we know it
                if peer_hash_str == self.client_hash:
                    continue
                self._handle_discovery(peer_hash_str, display_name)
            self._pending_discoveries = []

    def _start_peer_monitor(self):
        """Just a simple status monitor"""
        def monitor_loop():
            print("✓ Status monitor started")
            print("="*60 + "\n")
            
            while self.running:
                time.sleep(10)
        
        threading.Thread(target=monitor_loop, daemon=True).start()

    def _handle_discovery(self, peer_hash_str, display_name):
        try:
            server_name = display_name.replace('[HTML]', '').strip()
            if not server_name:
                server_name = "Unknown Server"
            
            # Check if already discovered
            if peer_hash_str in self.known_peers:
                # Just update last seen
                if peer_hash_str in self.discovered_servers:
                    self.discovered_servers[peer_hash_str]['last_seen'] = time.time()
                    self._save_data()
                return
            
            self.discovered_servers[peer_hash_str] = {
                'name': server_name,
                'pages': [],
                'last_seen': time.time()
            }
            
            self.known_peers.add(peer_hash_str)
            self._save_data()
            
            print(f"\n{'='*60}")
            print(f"[+] NEW HTML SERVER DISCOVERED!")
            print(f"    Name: {server_name}")
            print(f"    Hash: {peer_hash_str}")
            print(f"{'='*60}\n")
            
            if self.socketio:
                with app.app_context():
                    self.socketio.emit('server_discovered', {
                        'hash': peer_hash_str,
                        'name': server_name,
                        'timestamp': time.time()
                    }, namespace='/')
                    print(f"[+] UI notification sent")
            
            # REMOVED: Automatic page list request
            # User can click on server to load pages when they want
            
        except Exception as e:
            print(f"[!] Discovery error: {e}")
            import traceback
            traceback.print_exc()
                
    def _request_page_list(self, server_hash):
        try:
            if server_hash.startswith('<') and server_hash.endswith('>'):
                server_hash = server_hash[1:-1]
            
            dest_hash = bytes.fromhex(server_hash.replace(':', ''))
            
            self.pending_requests[server_hash] = {'type': 'list', 'time': time.time()}
            
            self.lxmf_destination.announce()
            time.sleep(0.3)
            
            dest_identity = RNS.Identity.recall(dest_hash)
            if not dest_identity:
                RNS.Transport.request_path(dest_hash)
                time.sleep(2)
                dest_identity = RNS.Identity.recall(dest_hash)
            
            if dest_identity:
                dest = RNS.Destination(
                    dest_identity,
                    RNS.Destination.OUT,
                    RNS.Destination.SINGLE,
                    "lxmf", "delivery"
                )
                
                lxmf_message = LXMF.LXMessage(
                    dest,
                    self.lxmf_destination,
                    "list"
                )
                
                self.message_router.handle_outbound(lxmf_message)
                print(f"[>] Requested page list")
        except Exception as e:
            print(f"[!] Error requesting list: {e}")
    
    def _parse_page_list(self, text):
        pages = []
        try:
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('[') and ']' in line:
                    parts = line.split(']', 1)
                    if len(parts) > 1:
                        page_info = parts[1].strip()
                        if '(' in page_info:
                            page_name = page_info.split('(')[0].strip()
                            if page_name:
                                pages.append(page_name)
        except:
            pass
        return pages
    
    def _save_html_file(self, html_content, filename, server_hash):
        """Save HTML content with link interception script"""
        # Inject JavaScript to intercept internal links
        inject_script = f"""
<script>
// LXMF Browser - Link Interceptor
(function() {{
    const currentServer = '{server_hash}';
    
    document.addEventListener('DOMContentLoaded', function() {{
        // Intercept all clicks on links
        document.addEventListener('click', function(e) {{
            let target = e.target;
            
            // Find the closest <a> tag
            while (target && target.tagName !== 'A') {{
                target = target.parentElement;
            }}
            
            if (target && target.tagName === 'A') {{
                const href = target.getAttribute('href');
                
                // Check if it's a relative link or .html file
                if (href && (href.endsWith('.html') || !href.includes('://'))) {{
                    e.preventDefault();
                    
                    // Extract page name
                    let pageName = href;
                    if (pageName.startsWith('./')) {{
                        pageName = pageName.substring(2);
                    }}
                    if (pageName.startsWith('/')) {{
                        pageName = pageName.substring(1);
                    }}
                    
                    // Tell parent window to request this page from LXMF
                    window.parent.postMessage({{
                        type: 'lxmf_navigate',
                        server: currentServer,
                        page: pageName
                    }}, '*');
                }}
            }}
        }}, true);
    }});
}})();
</script>
"""
        
        # Inject before </head> or </body> or at end
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', inject_script + '</head>')
        elif '</body>' in html_content:
            html_content = html_content.replace('</body>', inject_script + '</body>')
        else:
            html_content += inject_script
        
        filepath = os.path.join(self.html_cache_path, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return filename

    def _handle_message(self, message):
        """Handle incoming LXMF messages"""
        try:
            server_hash = RNS.prettyhexrep(message.source_hash)
            content = message.content.decode('utf-8') if isinstance(message.content, bytes) else message.content
            
            print(f"[<] Message from {server_hash[:20]}...")
            
            is_pending = server_hash in self.pending_requests
            
            # Handle page list response
            if is_pending and self.pending_requests[server_hash].get('type') == 'list':
                if "Available Pages" in content:
                    pages = self._parse_page_list(content)
                    
                    print(f"[+] Received {len(pages)} pages")
                    
                    if server_hash in self.discovered_servers:
                        self.discovered_servers[server_hash]['pages'] = pages
                        self._save_data()
                        
                        if self.socketio:
                            with app.app_context():
                                self.socketio.emit('pages_updated', {
                                    'hash': server_hash,
                                    'pages': pages
                                }, namespace='/')
                    
                    del self.pending_requests[server_hash]
                    return
            
            # Check for fields
            if hasattr(message, 'fields') and message.fields:
                # Handle HTML content (for rendering in browser)
                if self.FIELD_HTML_CONTENT in message.fields:
                    html_content = message.fields[self.FIELD_HTML_CONTENT]
                    
                    page_name = "page.html"
                    if content.startswith("Serving:"):
                        page_name = content.replace("Serving:", "").strip()
                    elif "Page Index" in content or "Available Pages" in content:
                        page_name = "index.html"
                    
                    server_name = self.discovered_servers.get(server_hash, {}).get('name', 'Unknown Server')
                    
                    print(f"[+] Received HTML: {page_name} ({len(html_content)} bytes)")
                    print(f"[DEBUG] server_hash: {server_hash}")
                    print(f"[DEBUG] server_name: {server_name}")
                    
                    # Save HTML to file with link interception
                    timestamp = int(time.time())
                    filename = f"{timestamp}_{page_name}"
                    saved_filename = self._save_html_file(html_content, filename, server_hash)
                    
                    # Save to history
                    self.history.append({
                        'server': server_hash,
                        'server_name': server_name,
                        'page': page_name,
                        'timestamp': time.time()
                    })
                    self._save_data()
                    
                    # Send to web UI
                    if self.socketio:
                        with app.app_context():
                            self.socketio.emit('html_received', {
                                'server': server_hash,
                                'server_name': server_name,
                                'page': page_name,
                                'filename': saved_filename,
                                'timestamp': time.time()
                            }, namespace='/')
                            print(f"[+] WebSocket event emitted")
                    
                    if is_pending and server_hash in self.pending_requests:
                        del self.pending_requests[server_hash]
                    
                    return
                
                # Handle file attachments (for downloads)
                if 2 in message.fields:  # FIELD_FILE_ATTACHMENTS
                    file_attachments = message.fields[2]
                    
                    print(f"[+] Received {len(file_attachments)} file attachment(s)")
                    
                    server_name = self.discovered_servers.get(server_hash, {}).get('name', 'Unknown Server')
                    
                    # Process each file attachment
                    for attachment in file_attachments:
                        # Handle both list and tuple formats
                        if (isinstance(attachment, (list, tuple)) and len(attachment) >= 2):
                            filename = attachment[0]
                            file_data = attachment[1]
                            
                            # Save file to cache
                            file_path = os.path.join(self.cache_path, filename)
                            with open(file_path, 'wb') as f:
                                f.write(file_data)
                            
                            file_size = len(file_data)
                            size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
                            if file_size >= 1024*1024:
                                size_str = f"{file_size/(1024*1024):.2f} MB"
                            
                            print(f"[+] Saved file: {filename} ({size_str})")
                            
                            # Save to history
                            self.history.append({
                                'server': server_hash,
                                'server_name': server_name,
                                'page': filename,
                                'timestamp': time.time(),
                                'type': 'file'
                            })
                            self._save_data()
                            
                            # Send to web UI with download link
                            if self.socketio:
                                with app.app_context():
                                    self.socketio.emit('file_received', {
                                        'server': server_hash,
                                        'server_name': server_name,
                                        'filename': filename,
                                        'size': size_str,
                                        'timestamp': time.time()
                                    }, namespace='/')
                                    print(f"[+] file_received event emitted")
                    
                    if is_pending and server_hash in self.pending_requests:
                        del self.pending_requests[server_hash]
                    
                    return
            
            print(f"[+] Text message: {content[:50]}...")
            
        except Exception as e:
            print(f"[!] Message handler error: {e}")
            import traceback
            traceback.print_exc()
    
    def request_page(self, server_hash, page_name):
        try:
            if server_hash.startswith('<') and server_hash.endswith('>'):
                server_hash = server_hash[1:-1]
            
            if server_hash.startswith('lxmf://'):
                server_hash = server_hash[7:]
            
            if '/' in server_hash:
                parts = server_hash.split('/', 1)
                server_hash = parts[0]
                if len(parts) > 1 and not page_name:
                    page_name = parts[1]
            
            if not page_name:
                page_name = "index"
            
            print(f"[>] Requesting {page_name} from {server_hash[:20]}...")
            
            dest_hash = bytes.fromhex(server_hash.replace(':', ''))
            
            self.pending_requests[server_hash] = {'type': 'page', 'page': page_name, 'time': time.time()}
            
            self.lxmf_destination.announce()
            time.sleep(0.3)
            
            dest_identity = RNS.Identity.recall(dest_hash)
            if not dest_identity:
                print(f"[!] Requesting path...")
                RNS.Transport.request_path(dest_hash)
                time.sleep(2)
                dest_identity = RNS.Identity.recall(dest_hash)
            
            if dest_identity:
                dest = RNS.Destination(
                    dest_identity,
                    RNS.Destination.OUT,
                    RNS.Destination.SINGLE,
                    "lxmf", "delivery"
                )
                
                fields = {self.FIELD_HTML_REQUEST: page_name}
                
                lxmf_message = LXMF.LXMessage(
                    dest,
                    self.lxmf_destination,
                    f"GET:{page_name}",
                    title="",
                    fields=fields
                )
                
                self.message_router.handle_outbound(lxmf_message)
                print(f"[+] Request sent")
                return True
            else:
                print(f"[!] Could not establish path")
                return False
            
        except Exception as e:
            print(f"[!] Request error: {e}")
            import traceback
            traceback.print_exc()
            return False

# Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lxmf-html-browser-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

browser = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/html/<filename>')
def serve_html(filename):
    """Serve cached HTML files"""
    from flask import send_from_directory
    return send_from_directory(browser.html_cache_path, filename)

@app.route('/api/servers')
def get_servers():
    servers = []
    for hash, info in browser.discovered_servers.items():
        servers.append({
            'hash': hash,
            'name': info['name'],
            'pages': info.get('pages', []),
            'last_seen': info['last_seen']
        })
    return jsonify(servers)

@app.route('/api/bookmarks')
def get_bookmarks():
    return jsonify(browser.bookmarks)

@app.route('/api/bookmark/add', methods=['POST'])
def add_bookmark():
    data = request.json
    bookmark = {
        'name': data['name'],
        'hash': data['hash'],
        'added': time.time()
    }
    browser.bookmarks.append(bookmark)
    browser._save_data()
    return jsonify({'success': True})

@app.route('/api/bookmark/remove', methods=['POST'])
def remove_bookmark():
    data = request.json
    browser.bookmarks = [b for b in browser.bookmarks if b['hash'] != data['hash']]
    browser._save_data()
    return jsonify({'success': True})

@app.route('/api/history')
def get_history():
    return jsonify(browser.history[-50:])

@app.route('/api/request_page', methods=['POST'])
def request_page():
    data = request.json
    success = browser.request_page(data.get('server', ''), data.get('page', 'index'))
    return jsonify({'success': success})

@app.route('/api/refresh_server', methods=['POST'])
def refresh_server():
    data = request.json
    browser._request_page_list(data['hash'])
    return jsonify({'success': True})

@app.route('/download/<filename>')
def download_file(filename):
    """Serve downloaded files"""
    from flask import send_from_directory
    print(f"[*] Download requested: {filename}")
    print(f"[*] Cache path: {browser.cache_path}")
    
    filepath = os.path.join(browser.cache_path, filename)
    print(f"[*] Full path: {filepath}")
    print(f"[*] File exists: {os.path.exists(filepath)}")
    
    return send_from_directory(browser.cache_path, filename, as_attachment=True)

@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    browser.history = []
    browser._save_data()
    return jsonify({'success': True})

@app.route('/api/server/remove', methods=['POST'])
def remove_server():
    data = request.json
    server_hash = data['hash']
    
    if server_hash in browser.discovered_servers:
        browser.discovered_servers.pop(server_hash)
    
    if server_hash in browser.known_peers:
        browser.known_peers.remove(server_hash)
    
    browser._save_data()
    return jsonify({'success': True})

@socketio.on('connect')
def handle_connect():
    print("[+] Web UI connected")
    emit('connected', {'status': 'ready'})

@socketio.on('disconnect')
def handle_disconnect():
    print("[-] Web UI disconnected")

# Modern Blue/Black UI Template with iframe isolation AND link interception
INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LXMF Browser</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #0a0e27;
            color: #e0e6ed;
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 320px;
            background: #0d1117;
            border-right: 1px solid #1f2937;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            padding: 24px;
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
        }
        
        .header h1 {
            font-size: 1.5em;
            font-weight: 600;
        }
        
        .tabs {
            display: flex;
            background: #161b22;
            border-bottom: 1px solid #1f2937;
        }
        
        .tab {
            flex: 1;
            padding: 14px;
            background: transparent;
            border: none;
            color: #8b949e;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.9em;
            font-weight: 500;
        }
        
        .tab:hover {
            background: #1f2937;
            color: #e0e6ed;
        }
        
        .tab.active {
            background: #0d1117;
            color: #3b82f6;
            border-bottom: 2px solid #3b82f6;
        }
        
        .tab-content {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }
        
        .server-item {
            background: #161b22;
            margin: 12px 0;
            padding: 16px;
            border-radius: 8px;
            border-left: 3px solid #3b82f6;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .server-item:hover {
            background: #1f2937;
            transform: translateX(4px);
        }
        
        .server-name {
            font-size: 1.1em;
            font-weight: 600;
            color: #e0e6ed;
            margin-bottom: 8px;
        }
        
        .server-info {
            font-size: 0.85em;
            color: #8b949e;
            word-break: break-all;
        }
        
        .page-list {
            margin-top: 12px;
            padding-left: 12px;
        }
        
        .page-link {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #3b82f6;
            padding: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border-radius: 4px;
            font-size: 0.9em;
        }
        
        .page-link:hover {
            background: rgba(59, 130, 246, 0.1);
            padding-left: 12px;
        }
        
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .address-bar {
            background: #161b22;
            padding: 16px;
            display: flex;
            gap: 12px;
            align-items: center;
            border-bottom: 1px solid #1f2937;
        }
        
        .address-bar input {
            flex: 1;
            padding: 12px 16px;
            background: #0d1117;
            border: 1px solid #1f2937;
            color: #e0e6ed;
            border-radius: 6px;
            font-size: 0.95em;
            transition: all 0.2s;
        }
        
        .address-bar input:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        .btn {
            padding: 10px 20px;
            background: #3b82f6;
            border: none;
            color: white;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
            font-size: 0.9em;
            font-weight: 500;
        }
        
        .btn:hover {
            background: #2563eb;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        }
        
        .btn-secondary {
            background: #1f2937;
        }
        
        .btn-secondary:hover {
            background: #374151;
        }
        
        .content-frame {
            flex: 1;
            background: white;
            position: relative;
            overflow: hidden;
        }
        
        .content-frame iframe {
            width: 100%;
            height: 100%;
            border: none;
            display: block;
        }
        
        .welcome-content {
            padding: 32px;
            max-width: 600px;
            margin: 0 auto;
        }
        
        .welcome-content h2 {
            color: #0a0e27;
            font-size: 2em;
            margin-bottom: 16px;
        }
        
        .welcome-content p {
            color: #6b7280;
            line-height: 1.6;
            margin: 12px 0;
        }
        
        .code {
            background: #f3f4f6;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            margin: 16px 0;
            color: #1f2937;
        }
        
        .status {
            background: #161b22;
            color: #8b949e;
            padding: 12px 20px;
            border-top: 1px solid #1f2937;
            font-size: 0.85em;
        }
        
        .notification {
            position: fixed;
            top: 24px;
            right: 24px;
            background: white;
            color: #0a0e27;
            padding: 16px 24px;
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s ease-out;
            z-index: 1000;
            border-left: 4px solid #3b82f6;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .loading {
            text-align: center;
            padding: 60px 20px;
            color: #8b949e;
        }
        
        .spinner {
            display: inline-block;
            width: 48px;
            height: 48px;
            border: 4px solid #1f2937;
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #0d1117;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #1f2937;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #374151;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="header">
                <h1>🌐 LXMF Browser</h1>
            </div>
            
            <div class="tabs">
                <button class="tab active" onclick="switchTab('servers')">Servers</button>
                <button class="tab" onclick="switchTab('bookmarks')">Bookmarks</button>
                <button class="tab" onclick="switchTab('history')">History</button>
            </div>
            
            <div class="tab-content" id="servers-content">
                <div class="loading">
                    <div class="spinner"></div>
                    <div>Listening for announces...</div>
                </div>
            </div>
            
            <div class="tab-content" id="bookmarks-content" style="display:none;">
                <div class="loading">No bookmarks yet</div>
            </div>
            
            <div class="tab-content" id="history-content" style="display:none;">
                <div class="loading">No history yet</div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="address-bar">
                <input type="text" id="address" placeholder="Enter server hash or lxmf://<hash>/<page>">
                <button class="btn" onclick="navigate()">Go</button>
                <button class="btn btn-secondary" onclick="refresh()">Refresh</button>
                <button class="btn btn-secondary" onclick="addBookmark()">★ Bookmark</button>
            </div>
            
            <div class="content-frame" id="content">
                <div class="welcome-content">
                    <h2>Welcome to LXMF Browser</h2>
                    <p>Browse decentralized HTML content over the Reticulum network.</p>
                    <p><strong>To get started:</strong></p>
                    <ul style="margin-left: 20px; line-height: 2;">
                        <li>Enter a server hash in the address bar above</li>
                        <li>Or wait for HTML servers to announce on the network</li>
                        <li>Discovered servers will appear in the sidebar</li>
                    </ul>
                    <div class="code">
                        Format: lxmf://&lt;server_hash&gt;/&lt;page&gt;<br>
                        Example: lxmf://a1b2c3.../index.html
                    </div>
                </div>
            </div>
            
            <div class="status" id="status">
                Ready • Listening for announces
            </div>
        </div>
    </div>
<script>
    const socket = io();
    let currentServer = null;
    let currentPage = null;
    let servers = {};
    let bookmarks = [];
    let history = [];
    
    // Listen for messages from iframe (link clicks)
    window.addEventListener('message', function(event) {
        if (event.data.type === 'lxmf_navigate') {
            console.log('Link clicked in page:', event.data.page);
            requestPage(event.data.server, event.data.page);
        }
    });
    
    socket.on('connect', () => {
        console.log('✓ Connected to server');
        loadServers();
        loadBookmarks();
        loadHistory();
    });
    
    socket.on('connected', (data) => {
        console.log('✓ Connection confirmed:', data);
    });
    
    socket.on('server_discovered', (data) => {
        console.log('✓ Server discovered:', data);
        showNotification(`🎉 New server: ${data.name}`);
        loadServers();
    });
    
    socket.on('pages_updated', (data) => {
        console.log('✓ Pages updated:', data);
        loadServers();
    });
    
    socket.on('html_received', (data) => {
        console.log('✓ HTML received:', data.page, 'file:', data.filename);
        displayHTML(data.filename, data.server, data.server_name, data.page);
        loadHistory();
    });
    
    socket.on('file_received', (data) => {
        console.log('✓ File received event:', data);
        console.log('Download URL:', `/download/${data.filename}`);
        
        // Trigger download
        const downloadLink = document.createElement('a');
        downloadLink.href = `/download/${data.filename}`;
        downloadLink.download = data.filename;
        downloadLink.style.display = 'none';
        document.body.appendChild(downloadLink);
        
        console.log('Triggering download click...');
        downloadLink.click();
        
        setTimeout(() => {
            document.body.removeChild(downloadLink);
        }, 100);
        
        showNotification(`✓ Downloaded: ${data.filename}`);
        document.getElementById('status').textContent = `Downloaded: ${data.filename}`;
        loadHistory();
    });
    
    async function loadServers() {
        const response = await fetch('/api/servers');
        const data = await response.json();
        servers = {};
        data.forEach(s => servers[s.hash] = s);
        renderServers();
        renderBookmarks(); // Re-render bookmarks when servers update
    }
    
    async function loadBookmarks() {
        const response = await fetch('/api/bookmarks');
        bookmarks = await response.json();
        renderBookmarks();
    }
    
    async function loadHistory() {
        const response = await fetch('/api/history');
        history = await response.json();
        renderHistory();
    }

    function renderServers() {
        const container = document.getElementById('servers-content');
        const serverList = Object.values(servers);
        
        if (serverList.length === 0) {
            container.innerHTML = '<div class="loading"><div class="spinner"></div><div>No servers discovered yet</div></div>';
            return;
        }
        
        container.innerHTML = serverList.map(server => {
            // The hash is the key in the servers dict, not a property
            const serverHash = Object.keys(servers).find(key => servers[key] === server);
            
            // Escape HTML characters in the hash
            const escapedHash = serverHash
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            
            return `
            <div class="server-item" style="position: relative; cursor: pointer; padding-bottom: 10px;" onclick="requestPage('${serverHash.replace(/[<>]/g, '')}', 'index')">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 5px;">
                    <div class="server-name" style="flex: 1; padding-right: 10px;">${server.name}</div>
                    <button onclick="event.stopPropagation(); removeServer('${serverHash.replace(/[<>]/g, '')}')" 
                            style="flex-shrink: 0;
                                background: #dc2626; 
                                color: white; 
                                border: none; 
                                border-radius: 4px; 
                                padding: 6px 10px; 
                                cursor: pointer; 
                                font-size: 0.75em;
                                font-weight: 500;
                                transition: all 0.2s;"
                            onmouseover="this.style.background='#b91c1c'"
                            onmouseout="this.style.background='#dc2626'">
                        🗑️
                    </button>
                </div>
                <div class="server-info" style="font-size: 0.75em; word-break: break-all; line-height: 1.5; color: #8b949e; margin-top: 8px;">
                    <div style="margin-bottom: 4px;">
                        <strong style="color: #6b7280;">Address:</strong><br>
                        <span style="font-family: 'Courier New', monospace; font-size: 0.95em;">${escapedHash}</span>
                    </div>
                    <div style="color: #6b7280;">
                        <strong>Last seen:</strong> ${new Date(server.last_seen * 1000).toLocaleString()}
                    </div>
                </div>
                ${server.pages && server.pages.length > 0 ? `
                    <div class="page-list" style="margin-top: 12px;">
                        ${server.pages.slice(0, 8).map(page => `
                            <div class="page-link" onclick="event.stopPropagation(); requestPage('${serverHash.replace(/[<>]/g, '')}', '${page}')">
                                📄 ${page}
                            </div>
                        `).join('')}
                        ${server.pages.length > 8 ? `<div style="color: #8b949e; font-size: 0.85em; padding: 8px 5px;">...and ${server.pages.length - 8} more</div>` : ''}
                    </div>
                ` : ''}
            </div>
        `;
        }).join('');
    }

    async function removeServer(serverHash) {
        if (confirm('Remove this server from discovered list?')) {
            await fetch('/api/server/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({hash: `<${serverHash}>`})
            });
            loadServers();
            showNotification('✓ Server removed');
        }
    }    

    function renderBookmarks() {
        const container = document.getElementById('bookmarks-content');
        
        if (bookmarks.length === 0) {
            container.innerHTML = '<div class="loading">No bookmarks yet</div>';
            return;
        }
        
        container.innerHTML = bookmarks.map(bm => {
            const server = servers[bm.hash];
            const serverName = server ? server.name : bm.name;
            
            // Truncate long server names
            const displayName = serverName.length > 30 ? serverName.substring(0, 27) + '...' : serverName;
            
            return `
                <div class="server-item" style="position: relative; cursor: pointer; padding-bottom: 10px;" onclick="requestPage('${bm.hash}', 'index')">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 5px;">
                        <div class="server-name" style="flex: 1; padding-right: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${displayName}</div>
                        <button onclick="event.stopPropagation(); removeBookmark('${bm.hash}')" 
                                style="flex-shrink: 0;
                                    background: #dc2626; 
                                    color: white; 
                                    border: none; 
                                    border-radius: 4px; 
                                    padding: 6px 10px; 
                                    cursor: pointer; 
                                    font-size: 0.75em;
                                    font-weight: 500;
                                    transition: all 0.2s;"
                                onmouseover="this.style.background='#b91c1c'"
                                onmouseout="this.style.background='#dc2626'">
                            🗑️
                        </button>
                    </div>
                    ${server && server.pages && server.pages.length > 0 ? `
                        <div class="page-list" style="margin-top: 8px;">
                            ${server.pages.slice(0, 5).map(page => `
                                <div class="page-link" onclick="event.stopPropagation(); requestPage('${bm.hash}', '${page}')">
                                    📄 ${page}
                                </div>
                            `).join('')}
                            ${server.pages.length > 5 ? `<div style="color: #8b949e; font-size: 0.85em; padding: 8px 5px;">...and ${server.pages.length - 5} more</div>` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
    }        

    function renderHistory() {
        const container = document.getElementById('history-content');
        
        if (history.length === 0) {
            container.innerHTML = '<div class="loading">No history yet</div>';
            return;
        }
        
        const reversed = [...history].reverse();
        
        let html = `
            <div style="padding: 12px;">
                <button onclick="clearHistory()" 
                        style="width: 100%; 
                            padding: 12px; 
                            background: #dc2626; 
                            color: white; 
                            border: none; 
                            border-radius: 6px; 
                            cursor: pointer; 
                            font-size: 0.9em;
                            font-weight: 500;
                            transition: all 0.2s;"
                        onmouseover="this.style.background='#b91c1c'"
                        onmouseout="this.style.background='#dc2626'">
                    🗑️ Clear History
                </button>
            </div>
        `;
        
        html += reversed.map(h => {
            const serverHash = h.server || '';
            const fullUrl = serverHash ? `lxmf://${serverHash}/${h.page}` : `${h.page}`;
            
            // Escape HTML to prevent < > from being interpreted as tags
            const escapedUrl = fullUrl
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
            
            return `
                <div class="server-item" onclick="requestPage('${serverHash.replace(/[<>]/g, '')}', '${h.page}')" style="cursor: pointer;">
                    <div class="server-name" style="margin-bottom: 8px;">${h.server_name || 'Unknown Server'}</div>
                    <div class="server-info" style="font-size: 0.72em; line-height: 1.5;">
                        <div style="color: #0ff; word-break: break-all; margin-bottom: 6px; font-family: 'Courier New', monospace;">
                            ${escapedUrl}
                        </div>
                        <div style="color: #8b949e; font-size: 0.95em;">
                            ${new Date(h.timestamp * 1000).toLocaleString()}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = html;
    }        
    
    async function navigate() {
        const address = document.getElementById('address').value.trim();
        if (!address) return;
        
        let serverHash = address;
        let pageName = 'index';
        
        if (address.startsWith('lxmf://')) {
            serverHash = address.substring(7);
        }
        
        if (serverHash.includes('/')) {
            const parts = serverHash.split('/');
            serverHash = parts[0];
            pageName = parts[1] || 'index';
        }
        
        requestPage(serverHash, pageName);
    }
    
    async function requestPage(serverHash, pageName) {
        currentServer = serverHash;
        currentPage = pageName;
        
        console.log('Requesting:', serverHash, pageName);
        
        document.getElementById('address').value = `lxmf://${serverHash}/${pageName}`;
        
        // Check if this is an HTML file or other file type
        const isHTML = pageName.toLowerCase().endsWith('.html') || 
                       pageName.toLowerCase().endsWith('.htm') ||
                       pageName.toLowerCase() === 'index' ||
                       pageName.toLowerCase() === 'list';
        
        if (isHTML) {
            document.getElementById('status').textContent = `Loading ${pageName}...`;
            document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div><div>Loading page...</div></div>';
        } else {
            document.getElementById('status').textContent = `Requesting ${pageName}...`;
            showNotification(`📥 Requesting ${pageName}...`);
        }
        
        await fetch('/api/request_page', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({server: serverHash, page: pageName})
        });
    }
    
    async function refreshServer(serverHash) {
        await fetch('/api/refresh_server', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({hash: serverHash})
        });
        showNotification('Refreshing...');
    }
    
    function displayHTML(filename, serverHash, serverName, pageName) {
        console.log('Displaying HTML in iframe:', filename);
        
        // Create iframe to isolate HTML content
        const iframe = document.createElement('iframe');
        iframe.src = `/html/${filename}`;
        iframe.sandbox = 'allow-scripts allow-same-origin';
        
        document.getElementById('content').innerHTML = '';
        document.getElementById('content').appendChild(iframe);
        document.getElementById('status').textContent = `${serverName} / ${pageName}`;
    }
    
    async function addBookmark() {
        if (!currentServer) {
            alert('No page loaded');
            return;
        }
        
        const server = servers[currentServer];
        const defaultName = server ? server.name : 'Server';
        
        const name = prompt('Bookmark name:', defaultName);
        if (name) {
            await fetch('/api/bookmark/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, hash: currentServer})
            });
            loadBookmarks();
            showNotification('✓ Bookmark added!');
        }
    }
    
    async function removeBookmark(serverHash) {
        if (confirm('Remove this bookmark?')) {
            await fetch('/api/bookmark/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({hash: serverHash})
            });
            loadBookmarks();
            showNotification('✓ Bookmark removed');
        }
    }
    
    async function clearHistory() {
        if (confirm('Clear all browsing history?')) {
            await fetch('/api/history/clear', {
                method: 'POST'
            });
            loadHistory();
            showNotification('✓ History cleared');
        }
    }
    
    function refresh() {
        if (currentServer && currentPage) {
            requestPage(currentServer, currentPage);
        }
    }
    
    function switchTab(tab) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
        
        event.target.classList.add('active');
        document.getElementById(`${tab}-content`).style.display = 'block';
    }
    
    function showNotification(message) {
        const notif = document.createElement('div');
        notif.className = 'notification';
        notif.textContent = message;
        document.body.appendChild(notif);
        
        setTimeout(() => notif.remove(), 3000);
    }
    
    document.getElementById('address').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            navigate();
        }
    });
</script>
</body>
</html>
"""

def create_templates():
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    with open(os.path.join(templates_dir, "index.html"), 'w', encoding='utf-8') as f:
        f.write(INDEX_HTML)

# Add this in main() after browser is created:
def main():
    global browser
    
    print("="*60)
    print("LXMF HTML Browser")
    print("="*60)
    
    create_templates()
    
    browser = LXMFHTMLBrowser()
    browser.socketio = socketio
    
    # Debug: Check if any servers exist
    print("\n[DEBUG] Discovered servers at startup:")
    if browser.discovered_servers:
        for server_hash, server_info in browser.discovered_servers.items():
            print(f"  - {server_info['name']}: {server_hash[:24]}...")
    else:
        print("  (none)")
    
    # TEMPORARY: Manually add your server for testing
    # Replace this hash with your actual server hash from the server terminal
    #test_server_hash = "<d4a08cf31603586d8657cd92cca71d58>"  # YOUR ACTUAL SERVER HASH
    #if test_server_hash not in browser.discovered_servers:
    #    print(f"\n[DEBUG] Adding test server manually: {test_server_hash}")
    #    browser.discovered_servers[test_server_hash] = {
    #        'name': 'Test HTML Server',
    #        'pages': [],
    #        'last_seen': time.time()
    #    }
    #    browser.known_peers.add(test_server_hash)
    #    browser._save_data()
    #    print("[DEBUG] Test server added")
    
    print("="*60)
    print("Starting web server...")
    print("="*60)
    print("\n🌐 Open browser: http://localhost:5080\n")
    
    socketio.run(app, host='0.0.0.0', port=5080, debug=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    main()