#!/usr/bin/env python3
# lxmf_html_server.py - Standalone LXMF HTML Server (Enhanced with Multi-File Support)

import os
import sys
import json
import time
import argparse
import threading
import platform
import base64
import mimetypes
from datetime import datetime

# Cross-platform terminal handling
if platform.system() == 'Windows':
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass

# Check dependencies
try:
    import RNS
    import LXMF
except ImportError:
    print("ERROR: Required packages not found!")
    print("Install with: pip install rns lxmf")
    sys.exit(1)

class TerminalUI:
    """Cross-platform terminal UI handler"""
    
    def __init__(self):
        self.is_windows = platform.system() == 'Windows'
        self.is_termux = 'com.termux' in os.environ.get('PREFIX', '')
        self.supports_unicode = self._check_unicode_support()
        
    def _check_unicode_support(self):
        """Check if terminal supports Unicode"""
        try:
            if self.is_windows:
                # Windows 10+ usually supports Unicode
                return sys.version_info >= (3, 6)
            return True
        except:
            return False
    
    def icon(self, name):
        """Get appropriate icon for terminal"""
        if not self.supports_unicode:
            # ASCII fallback
            icons = {
                'server': '[S]',
                'online': '[*]',
                'offline': '[ ]',
                'page': '[-]',
                'request': '[<]',
                'response': '[>]',
                'error': '[X]',
                'info': '[i]',
                'success': '[+]',
                'warning': '[!]',
                'network': '[N]',
                'interface': '[I]',
                'path': '[P]',
                'time': '[T]',
                'stats': '[=]',
            }
        else:
            # Unicode icons
            icons = {
                'server': '🖥️ ',
                'online': '🟢',
                'offline': '⚫',
                'page': '📄',
                'request': '📨',
                'response': '📤',
                'error': '❌',
                'info': 'ℹ️ ',
                'success': '✅',
                'warning': '⚠️ ',
                'network': '🌐',
                'interface': '🔌',
                'path': '🛤️ ',
                'time': '🕐',
                'stats': '📊',
            }
        
        return icons.get(name, '')
    
    def print_header(self, text, width=60):
        """Print formatted header"""
        print("\n" + "="*width)
        print(f"{self.icon('server')} {text}")
        print("="*width + "\n")
    
    def print_status(self, status, message):
        """Print status message with icon"""
        icon = self.icon(status)
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {icon} {message}")
    
    def clear_line(self):
        """Clear current line"""
        if not self.is_windows:
            sys.stdout.write('\r\033[K')
        else:
            sys.stdout.write('\r' + ' '*80 + '\r')
        sys.stdout.flush()

class LXMFHTMLServer:
    def __init__(self, storage_path=None, identity_path=None):
        # Terminal UI
        self.ui = TerminalUI()
        
        # Setup paths
        if storage_path is None:
            storage_path = os.path.expanduser("~/.lxmf_html_server")
        
        self.storage_path = storage_path
        self.pages_path = os.path.join(storage_path, "pages")
        self.config_file = os.path.join(storage_path, "config.json")
        self.access_log = os.path.join(storage_path, "access.log")
        self.identity_file = identity_path or os.path.join(storage_path, "identity")
        
        # Server settings
        self.enabled = True
        self.transfer_mode = "embedded"
        self.server_name = "LXMF HTML Server"
        self.auto_announce_interval = 1800
        self.auto_announce_enabled = True
        
        # Supported file types
        self.supported_extensions = {
            # HTML files
            '.html': 'text/html',
            '.htm': 'text/html',
            # Text files
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            # Images
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            # Archives
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.7z': 'application/x-7z-compressed',
            # Documents
            '.pdf': 'application/pdf',
        }
        
        # HTML field constants
        self.FIELD_HTML_CONTENT = 10
        self.FIELD_HTML_REQUEST = 11

        # File transfer fields
        self.FIELD_FILE_ATTACHMENTS = 0x02  # LXMF field for file attachments
        
        # Statistics
        self.requests_served = 0
        self.start_time = time.time()
        self.last_announce = 0
        
        # Threading
        self.announce_thread = None
        self.status_thread = None
        self.running = False
        
        # Initialize
        self._init_storage()
        self._load_config()
        self._init_reticulum()
        self._init_lxmf()
        
    def _init_storage(self):
        """Create storage directories"""
        for path in [self.storage_path, self.pages_path]:
            if not os.path.exists(path):
                os.makedirs(path)
                self.ui.print_status('success', f"Created directory: {path}")
        
        if not os.listdir(self.pages_path):
            self._create_default_pages()
    
    def _create_default_pages(self):
        """Create default HTML pages with clickable navigation"""
        self.ui.print_status('info', "Creating default pages...")
        
        # About page
        about_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>About - LXMF Server</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #0f0;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        h1 { 
            color: #0f0; 
            border-bottom: 2px solid #0f0; 
            padding-bottom: 10px;
            text-shadow: 0 0 10px #0f0;
        }
        .section {
            background: rgba(0, 255, 0, 0.1);
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 3px solid #0f0;
        }
        .section h2 { color: #0ff; margin-bottom: 15px; }
        .section p { line-height: 1.6; margin: 10px 0; }
        ul { margin-left: 20px; }
        li { margin: 5px 0; }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: rgba(0, 255, 255, 0.2);
            color: #0ff;
            text-decoration: none;
            border-radius: 5px;
            border: 1px solid #0ff;
        }
        .back-link:hover {
            background: rgba(0, 255, 255, 0.3);
            box-shadow: 0 0 10px #0ff;
        }
    </style>
</head>
<body>
    <h1>📖 About This Server</h1>
    
    <div class="section">
        <h2>🔧 What is LXMF?</h2>
        <p>LXMF (Lightweight Extensible Message Format) is a messaging protocol built on top of the Reticulum Network Stack.</p>
        <p>It enables secure, decentralized communication over various transport mediums including:</p>
        <ul>
            <li>📡 LoRa radio networks</li>
            <li>📻 Packet radio</li>
            <li>📶 WiFi mesh networks</li>
            <li>🌐 Internet (TCP/UDP)</li>
            <li>🔌 Serial connections</li>
        </ul>
    </div>
    
    <div class="section">
        <h2>✨ Features</h2>
        <ul>
            <li>🔒 End-to-end encryption</li>
            <li>📴 Works offline and in mesh networks</li>
            <li>🏢 No central servers required</li>
            <li>📄 HTML content delivery</li>
            <li>📉 Extremely low bandwidth</li>
            <li>🔗 Clickable page navigation</li>
            <li>📦 Multi-file type support (images, PDFs, archives)</li>
        </ul>
    </div>
    
    <div class="section">
        <h2>📊 Server Stats</h2>
        <p><strong>Started:</strong> {{timestamp}}</p>
        <p><strong>Available Files:</strong> {{page_count}}</p>
    </div>
    
    <a href="index" class="back-link">← Back to Index</a>
</body>
</html>"""
        
        with open(os.path.join(self.pages_path, "about.html"), 'w', encoding='utf-8') as f:
            f.write(about_html)
        
        # Help page
        help_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Help - LXMF Server</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #0f0;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
        }
        h1 { 
            color: #0f0; 
            border-bottom: 2px solid #0f0; 
            padding-bottom: 10px;
            text-shadow: 0 0 10px #0f0;
        }
        .section {
            background: rgba(0, 255, 0, 0.1);
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            border-left: 3px solid #0f0;
        }
        .section h2 { color: #0ff; margin-bottom: 15px; }
        .section p { line-height: 1.6; margin: 10px 0; }
        .code {
            background: rgba(0, 0, 0, 0.5);
            padding: 10px;
            margin: 10px 0;
            border-radius: 3px;
            font-family: monospace;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: rgba(0, 255, 255, 0.2);
            color: #0ff;
            text-decoration: none;
            border-radius: 5px;
            border: 1px solid #0ff;
        }
        .back-link:hover {
            background: rgba(0, 255, 255, 0.3);
            box-shadow: 0 0 10px #0ff;
        }
    </style>
</head>
<body>
    <h1>❓ Server Help</h1>
    
    <div class="section">
        <h2>📝 Commands</h2>
        <p>You can interact with this server using text commands:</p>
        <div class="code">
            <strong>GET:&lt;file&gt;</strong> - Request a specific file<br>
            Example: GET:about.html
        </div>
        <div class="code">
            <strong>list</strong> or <strong>pages</strong> - Get file listing
        </div>
        <div class="code">
            <strong>announce</strong> or <strong>ping</strong> - Test connection
        </div>
    </div>
    
    <div class="section">
        <h2>📁 Supported File Types</h2>
        <p>This server can serve:</p>
        <ul>
            <li>🌐 HTML pages (.html, .htm)</li>
            <li>📝 Text files (.txt, .md)</li>
            <li>🖼️ Images (.jpg, .png, .gif, .webp)</li>
            <li>📄 PDF documents (.pdf)</li>
            <li>📦 Archives (.zip, .rar, .7z)</li>
        </ul>
    </div>
    
    <div class="section">
        <h2>🖱️ Web Navigation</h2>
        <p>If you're using an HTML-capable client, you can simply click links to navigate between pages!</p>
    </div>
    
    <div class="section">
        <h2>🔧 Server Information</h2>
        <p><strong>Time:</strong> {{timestamp}}</p>
        <p><strong>Files:</strong> {{page_count}}</p>
    </div>
    
    <a href="index" class="back-link">← Back to Index</a>
</body>
</html>"""
        
        with open(os.path.join(self.pages_path, "help.html"), 'w', encoding='utf-8') as f:
            f.write(help_html)
        
        self.ui.print_status('success', f"Created default pages in {self.pages_path}")
    
    def _load_config(self):
        """Load server configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.enabled = config.get('enabled', True)
                    self.transfer_mode = config.get('transfer_mode', 'embedded')
                    self.server_name = config.get('server_name', 'LXMF HTML Server')
                    self.auto_announce_interval = config.get('auto_announce_interval', 1800)
                    self.auto_announce_enabled = config.get('auto_announce_enabled', True)
            except Exception as e:
                self.ui.print_status('warning', f"Could not load config: {e}")
    
    def _save_config(self):
        """Save server configuration"""
        config = {
            'enabled': self.enabled,
            'transfer_mode': self.transfer_mode,
            'server_name': self.server_name,
            'auto_announce_interval': self.auto_announce_interval,
            'auto_announce_enabled': self.auto_announce_enabled
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def _init_reticulum(self):
        """Initialize Reticulum"""
        self.ui.print_header("LXMF HTML Server - Initializing")
        
        try:
            self.reticulum = RNS.Reticulum()
            self.ui.print_status('success', "Reticulum initialized")
            self._show_reticulum_status()
        except Exception as e:
            self.ui.print_status('error', f"Failed to initialize Reticulum: {e}")
            sys.exit(1)
        
        # Load or create identity
        if os.path.exists(self.identity_file):
            self.identity = RNS.Identity.from_file(self.identity_file)
            self.ui.print_status('success', f"Loaded identity")
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(self.identity_file)
            self.ui.print_status('success', f"Created new identity")
    
    def _show_reticulum_status(self):
        """Display Reticulum network status"""
        try:
            # Show interfaces
            interfaces = RNS.Transport.interfaces
            
            # Handle both dict and list formats
            if isinstance(interfaces, dict):
                interface_list = list(interfaces.keys())
                self.ui.print_status('interface', f"Active interfaces: {len(interface_list)}")
                
                for iface_name in interface_list[:3]:  # Show first 3
                    iface = interfaces[iface_name]
                    iface_type = iface.__class__.__name__
                    self.ui.print_status('info', f"  └─ {iface_name} ({iface_type})")
                
                if len(interface_list) > 3:
                    self.ui.print_status('info', f"  └─ ... and {len(interface_list)-3} more")
            
            elif isinstance(interfaces, list):
                self.ui.print_status('interface', f"Active interfaces: {len(interfaces)}")
                
                for iface in interfaces[:3]:  # Show first 3
                    iface_name = getattr(iface, 'name', 'Unknown')
                    iface_type = iface.__class__.__name__
                    self.ui.print_status('info', f"  └─ {iface_name} ({iface_type})")
                
                if len(interfaces) > 3:
                    self.ui.print_status('info', f"  └─ ... and {len(interfaces)-3} more")
            
            else:
                # Fallback if it's neither dict nor list
                self.ui.print_status('interface', f"Interfaces initialized")
            
            # Show paths - try different attribute names for different RNS versions
            try:
                if hasattr(RNS.Transport, 'destination_table'):
                    path_count = len(RNS.Transport.destination_table)
                elif hasattr(RNS.Transport, 'destinations'):
                    path_count = len(RNS.Transport.destinations)
                elif hasattr(RNS.Transport, 'path_table'):
                    path_count = len(RNS.Transport.path_table)
                else:
                    path_count = 0
                
                if path_count > 0:
                    self.ui.print_status('path', f"Known paths: {path_count}")
            except:
                pass
                
        except Exception as e:
            self.ui.print_status('warning', f"Could not read network status: {e}")
    
    def _init_lxmf(self):
        """Initialize LXMF"""
        self.message_router = LXMF.LXMRouter(
            identity=self.identity,
            storagepath=self.storage_path
        )
        
        display_name = f"[HTML] {self.server_name}"
        
        self.lxmf_destination = self.message_router.register_delivery_identity(
            self.identity,
            display_name=display_name
        )
        
        self.message_router.register_delivery_callback(self._handle_message)
        
        self.server_hash = RNS.prettyhexrep(self.lxmf_destination.hash)
        
        self._announce_server()
        
        self.ui.print_status('success', f"LXMF router initialized")
        print(f"\n{self.ui.icon('network')} SERVER HASH: {self.server_hash}")
        print(f"{self.ui.icon('info')} DISPLAY NAME: {display_name}\n")
    
    def _announce_server(self):
        """Announce server"""
        try:
            self.lxmf_destination.announce()
            self.last_announce = time.time()
            
            files = len(self._get_page_list())
            self.ui.print_status('network', f"Server announced with {files} files")
            
        except Exception as e:
            self.ui.print_status('error', f"Error announcing server: {e}")
    
    def _auto_announce_loop(self):
        """Background thread for auto-announcing"""
        while self.running:
            try:
                if self.auto_announce_enabled:
                    time_since_announce = time.time() - self.last_announce
                    
                    if time_since_announce >= self.auto_announce_interval:
                        self._announce_server()
                
                time.sleep(10)
                
            except Exception as e:
                self.ui.print_status('error', f"Error in announce loop: {e}")
    
    def _log_access(self, sender_hash, page, success):
        """Log page access"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sender_short = RNS.prettyhexrep(sender_hash)
        status = "SUCCESS" if success else "FAILED"
        
        log_entry = f"[{timestamp}] {sender_short} requested '{page}' - {status}\n"
        
        try:
            with open(self.access_log, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except:
            pass
    
    def _get_page_list(self):
        """Get list of available files"""
        files = []
        try:
            for filename in os.listdir(self.pages_path):
                # Check if file has supported extension
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.supported_extensions:
                    files.append(filename)
        except:
            pass
        return sorted(files)
    
    def _get_file_icon(self, filename):
        """Get appropriate icon for file type"""
        ext = os.path.splitext(filename)[1].lower()
        
        icons = {
            '.html': '🌐',
            '.htm': '🌐',
            '.txt': '📝',
            '.md': '📝',
            '.jpg': '🖼️',
            '.jpeg': '🖼️',
            '.png': '🖼️',
            '.gif': '🖼️',
            '.bmp': '🖼️',
            '.webp': '🖼️',
            '.pdf': '📄',
            '.zip': '📦',
            '.rar': '📦',
            '.7z': '📦',
        }
        
        return icons.get(ext, '📄')
    
    def _get_mime_type(self, filename):
        """Get MIME type for file"""
        ext = os.path.splitext(filename)[1].lower()
        return self.supported_extensions.get(ext, 'application/octet-stream')
    
    def _is_binary_file(self, filename):
        """Check if file is binary"""
        ext = os.path.splitext(filename)[1].lower()
        text_extensions = ['.html', '.htm', '.txt', '.md']
        return ext not in text_extensions
    
    def _process_template(self, html_content):
        """Process template variables"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        files = self._get_page_list()
        
        # Generate clickable HTML links for {{page_list}}
        file_links = []
        for filename in files:
            icon = self._get_file_icon(filename)
            file_links.append(f'<a href="{filename}">{icon} {filename}</a>')
        
        page_list_html = '<br>\n'.join(file_links)
        
        html_content = html_content.replace('{{timestamp}}', timestamp)
        html_content = html_content.replace('{{page_list}}', page_list_html)
        html_content = html_content.replace('{{page_count}}', str(len(files)))
        
        return html_content

    def _wrap_text_in_html(self, text_content, filename):
        """Wrap text content as downloadable file"""
        file_path = os.path.join(self.pages_path, filename)
        file_size = os.path.getsize(file_path)
        size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
        
        # Encode as base64 for download
        base64_data = base64.b64encode(text_content.encode('utf-8')).decode('utf-8')
        
        html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{filename} - Download</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                color: #0f0;
                padding: 20px;
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{
                color: #0ff;
                border-bottom: 2px solid #0f0;
                padding-bottom: 10px;
                text-shadow: 0 0 10px #0ff;
            }}
            .file-info {{
                background: rgba(0, 255, 0, 0.1);
                padding: 20px;
                border-radius: 5px;
                border-left: 3px solid #0f0;
                margin: 20px 0;
            }}
            .file-info p {{
                margin: 10px 0;
            }}
            .download-section {{
                background: rgba(0, 255, 255, 0.1);
                padding: 30px;
                border-radius: 5px;
                margin: 20px 0;
                text-align: center;
            }}
            .download-btn {{
                display: inline-block;
                padding: 20px 40px;
                background: rgba(0, 255, 0, 0.3);
                color: #0f0;
                text-decoration: none;
                border-radius: 5px;
                border: 2px solid #0f0;
                margin: 10px;
                font-size: 1.3em;
                cursor: pointer;
            }}
            .download-btn:hover {{
                background: rgba(0, 255, 0, 0.5);
                box-shadow: 0 0 15px #0f0;
            }}
            .preview {{
                background: rgba(0, 0, 0, 0.5);
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                max-height: 300px;
                overflow-y: auto;
                border: 1px solid #0f0;
            }}
            .preview pre {{
                margin: 0;
                white-space: pre-wrap;
                word-wrap: break-word;
                color: #0ff;
            }}
            .back-link {{
                display: inline-block;
                margin-top: 20px;
                padding: 10px 20px;
                background: rgba(0, 255, 255, 0.2);
                color: #0ff;
                text-decoration: none;
                border-radius: 5px;
                border: 1px solid #0ff;
            }}
            .back-link:hover {{
                background: rgba(0, 255, 255, 0.3);
            }}
        </style>
    </head>
    <body>
        <h1>📝 {filename}</h1>
        
        <div class="file-info">
            <p><strong>Filename:</strong> {filename}</p>
            <p><strong>Size:</strong> {size_str}</p>
            <p><strong>Type:</strong> Text File</p>
            <p><strong>Status:</strong> <span style="color: #0f0;">✓ Ready for Download</span></p>
        </div>
        
        <div class="download-section">
            <p style="color: #0ff; margin-bottom: 20px; font-size: 1.1em;">File is ready to download</p>
            <a href="data:text/plain;base64,{base64_data}" download="{filename}" class="download-btn">
                ⬇️ Download {filename}
            </a>
            <p style="color: #888; margin-top: 15px; font-size: 0.9em;">
                Click to save the file to your device
            </p>
        </div>
        
        <div class="file-info">
            <p><strong>Preview:</strong></p>
            <div class="preview">
                <pre>{text_content[:500]}{'...' if len(text_content) > 500 else ''}</pre>
            </div>
        </div>
        
        <a href="index" class="back-link">← Back to Index</a>
    </body>
    </html>"""
        return html

    def _wrap_image_in_html(self, base64_data, filename, mime_type):
        """Wrap image as downloadable file with preview"""
        file_path = os.path.join(self.pages_path, filename)
        file_size = os.path.getsize(file_path)
        size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
        if file_size >= 1024*1024:
            size_str = f"{file_size/(1024*1024):.2f} MB"
        
        html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{filename} - Download</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                color: #0f0;
                padding: 20px;
                max-width: 1000px;
                margin: 0 auto;
            }}
            h1 {{
                color: #0ff;
                text-align: center;
                margin-bottom: 10px;
                text-shadow: 0 0 10px #0ff;
            }}
            .file-info {{
                background: rgba(0, 255, 0, 0.1);
                padding: 15px;
                border-radius: 5px;
                border-left: 3px solid #0f0;
                margin: 20px 0;
                text-align: center;
            }}
            .file-info p {{
                margin: 5px 0;
            }}
            .image-preview {{
                background: rgba(0, 255, 0, 0.05);
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
                text-align: center;
            }}
            img {{
                max-width: 100%;
                height: auto;
                border: 2px solid #0f0;
                border-radius: 5px;
                box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
            }}
            .download-section {{
                text-align: center;
                margin: 30px 0;
            }}
            .download-btn {{
                display: inline-block;
                padding: 20px 40px;
                background: rgba(0, 255, 0, 0.3);
                color: #0f0;
                text-decoration: none;
                border-radius: 5px;
                border: 2px solid #0f0;
                font-size: 1.3em;
                cursor: pointer;
            }}
            .download-btn:hover {{
                background: rgba(0, 255, 0, 0.5);
                box-shadow: 0 0 15px #0f0;
            }}
            .back-link {{
                display: inline-block;
                margin-top: 20px;
                padding: 10px 20px;
                background: rgba(0, 255, 255, 0.2);
                color: #0ff;
                text-decoration: none;
                border-radius: 5px;
                border: 1px solid #0ff;
            }}
            .back-link:hover {{
                background: rgba(0, 255, 255, 0.3);
            }}
        </style>
    </head>
    <body>
        <h1>🖼️ {filename}</h1>
        
        <div class="file-info">
            <p><strong>Size:</strong> {size_str} | <strong>Type:</strong> {mime_type}</p>
            <p style="color: #0f0;">✓ Ready for Download</p>
        </div>
        
        <div class="image-preview">
            <img src="data:{mime_type};base64,{base64_data}" alt="{filename}">
        </div>
        
        <div class="download-section">
            <a href="data:{mime_type};base64,{base64_data}" download="{filename}" class="download-btn">
                ⬇️ Download Image
            </a>
            <p style="color: #888; margin-top: 15px;">Click to save to your device</p>
        </div>
        
        <div style="text-align: center;">
            <a href="index" class="back-link">← Back to Index</a>
        </div>
    </body>
    </html>"""
        return html

    def _wrap_binary_in_html(self, base64_data, filename, mime_type):
        """Wrap binary file as downloadable with info"""
        file_path = os.path.join(self.pages_path, filename)
        file_size = os.path.getsize(file_path)
        size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size/1024:.2f} KB"
        if file_size >= 1024*1024:
            size_str = f"{file_size/(1024*1024):.2f} MB"
        
        # Determine file type icon and description
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.pdf':
            icon = '📄'
            type_desc = 'PDF Document'
        elif ext in ['.zip', '.rar', '.7z']:
            icon = '📦'
            type_desc = 'Archive File'
        else:
            icon = '📁'
            type_desc = 'Binary File'
        
        html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{filename} - Download</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                color: #0f0;
                padding: 20px;
                max-width: 800px;
                margin: 0 auto;
            }}
            h1 {{
                color: #0ff;
                text-align: center;
                margin-bottom: 20px;
                text-shadow: 0 0 10px #0ff;
            }}
            .file-icon {{
                text-align: center;
                font-size: 5em;
                margin: 20px 0;
            }}
            .file-info {{
                background: rgba(0, 255, 0, 0.1);
                padding: 20px;
                border-radius: 5px;
                border-left: 3px solid #0f0;
                margin: 20px 0;
            }}
            .file-info p {{
                margin: 10px 0;
                font-size: 1.1em;
            }}
            .download-section {{
                background: rgba(0, 255, 255, 0.1);
                padding: 40px;
                border-radius: 5px;
                margin: 30px 0;
                text-align: center;
            }}
            .download-btn {{
                display: inline-block;
                padding: 25px 50px;
                background: rgba(0, 255, 0, 0.3);
                color: #0f0;
                text-decoration: none;
                border-radius: 5px;
                border: 3px solid #0f0;
                font-size: 1.5em;
                font-weight: bold;
                cursor: pointer;
            }}
            .download-btn:hover {{
                background: rgba(0, 255, 0, 0.5);
                box-shadow: 0 0 20px #0f0;
                transform: scale(1.05);
                transition: all 0.3s;
            }}
            .info-note {{
                background: rgba(0, 255, 255, 0.1);
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                border: 1px solid #0ff;
                color: #0ff;
            }}
            .back-link {{
                display: inline-block;
                margin-top: 20px;
                padding: 10px 20px;
                background: rgba(0, 255, 255, 0.2);
                color: #0ff;
                text-decoration: none;
                border-radius: 5px;
                border: 1px solid #0ff;
            }}
            .back-link:hover {{
                background: rgba(0, 255, 255, 0.3);
            }}
        </style>
    </head>
    <body>
        <div class="file-icon">{icon}</div>
        <h1>{filename}</h1>
        
        <div class="file-info">
            <p><strong>Filename:</strong> {filename}</p>
            <p><strong>Type:</strong> {type_desc}</p>
            <p><strong>Size:</strong> {size_str}</p>
            <p><strong>MIME:</strong> {mime_type}</p>
            <p><strong>Status:</strong> <span style="color: #0f0;">✓ Ready for Download</span></p>
        </div>
        
        <div class="download-section">
            <p style="color: #0ff; margin-bottom: 25px; font-size: 1.2em;">File is ready to download</p>
            <a href="data:{mime_type};base64,{base64_data}" download="{filename}" class="download-btn">
                ⬇️ DOWNLOAD
            </a>
            <p style="color: #888; margin-top: 20px; font-size: 0.95em;">
                Click the button above to save this file
            </p>
        </div>
        
        <div class="info-note">
            <strong>ℹ️ Note:</strong> This file will be downloaded to your device's default download location.
            The download behavior may vary depending on your browser or client.
        </div>
        
        <div style="text-align: center;">
            <a href="index" class="back-link">← Back to Index</a>
        </div>
    </body>
    </html>"""
        
        return html    
    
    def _generate_dynamic_index(self):
        """Generate dynamic HTML index with clickable links"""
        files = self._get_page_list()
        
        # Group files by type
        file_groups = {
            'HTML Pages': [],
            'Text Files': [],
            'Images': [],
            'Documents': [],
            'Archives': []
        }
        
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            file_path = os.path.join(self.pages_path, filename)
            size = os.path.getsize(file_path)
            size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
            icon = self._get_file_icon(filename)
            
            item_html = f"""                <li class="file-item">
                    <a href="{filename}" class="file-link">{icon} {filename}</a>
                    <div class="file-info">Size: {size_str}</div>
                </li>"""
            
            if ext in ['.html', '.htm']:
                file_groups['HTML Pages'].append(item_html)
            elif ext in ['.txt', '.md']:
                file_groups['Text Files'].append(item_html)
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                file_groups['Images'].append(item_html)
            elif ext == '.pdf':
                file_groups['Documents'].append(item_html)
            elif ext in ['.zip', '.rar', '.7z']:
                file_groups['Archives'].append(item_html)
        
        # Build sections
        sections_html = ""
        for group_name, items in file_groups.items():
            if items:
                sections_html += f"""
        <div class="file-group">
            <h3>{group_name} ({len(items)})</h3>
            <ul class="file-list">
{''.join(items)}
            </ul>
        </div>"""
        
        # Full index HTML
        index_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LXMF HTML Server - Index</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #0f0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.8);
            border: 2px solid #0f0;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.3);
        }}
        h1 {{
            color: #0f0;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2em;
            text-shadow: 0 0 10px #0f0;
        }}
        .subtitle {{
            text-align: center;
            color: #0ff;
            margin-bottom: 30px;
            opacity: 0.8;
        }}
        .info {{
            background: rgba(0, 255, 0, 0.1);
            border-left: 3px solid #0f0;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .info h2 {{
            color: #0ff;
            margin-bottom: 10px;
            font-size: 1.2em;
        }}
        .file-group {{
            margin: 25px 0;
        }}
        .file-group h3 {{
            color: #0ff;
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 1px solid #0f0;
        }}
        .file-list {{
            list-style: none;
            padding: 0;
        }}
        .file-item {{
            background: rgba(0, 255, 255, 0.1);
            margin: 8px 0;
            padding: 12px;
            border-radius: 5px;
            transition: all 0.3s;
        }}
        .file-item:hover {{
            background: rgba(0, 255, 255, 0.2);
            transform: translateX(5px);
        }}
        .file-link {{
            color: #0ff;
            text-decoration: none;
            font-size: 1.1em;
            display: block;
        }}
        .file-link:hover {{
            color: #0f0;
            text-shadow: 0 0 5px #0ff;
        }}
        .file-info {{
            color: #888;
            font-size: 0.85em;
            margin-top: 5px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #0f0;
            color: #888;
            font-size: 0.9em;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .pulse {{ animation: pulse 2s infinite; }}
        .status-indicator {{
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #0f0;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📡 LXMF HTML Server</h1>
        <div class="subtitle">Decentralized Web Over Mesh Networks</div>
        
        <div class="info">
            <h2>🌐 Server Information</h2>
            <p><span class="status-indicator pulse"></span><strong>Status:</strong> ONLINE</p>
            <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Total Files:</strong> {len(files)}</p>
            <p><strong>Protocol:</strong> LXMF over Reticulum</p>
        </div>
        
        <div class="info">
            <h2>📚 Available Files</h2>
{sections_html}
        </div>
        
        <div class="info">
            <h2>💡 Usage</h2>
            <p>Click any file link above to view/download, or send manual requests:</p>
            <p style="margin-top: 10px; font-family: monospace; background: rgba(0,0,0,0.5); padding: 10px; border-radius: 3px;">
                GET:&lt;filename&gt;<br>
                Example: GET:about.html
            </p>
        </div>
        
        <div class="footer">
            Powered by Standalone LXMF HTML Server<br>
            Reticulum Network Stack
        </div>
    </div>
</body>
</html>"""
        
        return index_html
    
    def _generate_text_index(self):
        """Generate text-based file index"""
        files = self._get_page_list()
        
        if not files:
            return "No files available"
        
        text = f"{self.ui.icon('page')} Available Files ({len(files)}):\n\n"
        
        for i, filename in enumerate(files, 1):
            file_path = os.path.join(self.pages_path, filename)
            size = os.path.getsize(file_path)
            size_str = f"{size:,}B" if size < 1024 else f"{size/1024:.1f}KB"
            icon = self._get_file_icon(filename)
            text += f"  [{i}] {icon} {filename} ({size_str})\n"
        
        text += f"\n{self.ui.icon('info')} To view a file, send: GET:<filename>\n"
        text += f"Example: GET:{files[0]}\n"
        text += f"Send 'list' or 'pages' to see this index again"
        
        return text

    def _create_auto_download_html(self, base64_data, filename, mime_type):
        """Create minimal HTML that auto-downloads the file"""
        html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Downloading {filename}</title>
        <style>
            body {{
                font-family: 'Courier New', monospace;
                background: #1a1a1a;
                color: #0f0;
                padding: 50px;
                text-align: center;
            }}
            .message {{
                font-size: 1.5em;
                margin: 20px 0;
            }}
            .filename {{
                color: #0ff;
                font-size: 1.2em;
                margin: 20px 0;
            }}
            a {{
                display: inline-block;
                margin-top: 20px;
                padding: 15px 30px;
                background: rgba(0, 255, 0, 0.3);
                color: #0f0;
                text-decoration: none;
                border-radius: 5px;
                border: 2px solid #0f0;
                font-size: 1.2em;
            }}
            a:hover {{
                background: rgba(0, 255, 0, 0.5);
            }}
            .back {{
                margin-top: 30px;
                padding: 10px 20px;
                background: rgba(0, 255, 255, 0.2);
                color: #0ff;
                border: 1px solid #0ff;
                font-size: 1em;
            }}
        </style>
        <script>
            window.onload = function() {{
                // Auto-download on page load
                var link = document.getElementById('download-link');
                link.click();
            }};
        </script>
    </head>
    <body>
        <div class="message">⬇️ Downloading...</div>
        <div class="filename">{filename}</div>
        <p>If download doesn't start automatically:</p>
        <a id="download-link" href="data:{mime_type};base64,{base64_data}" download="{filename}">
            Click Here to Download
        </a>
        <br>
        <a href="index" class="back">← Back to Index</a>
    </body>
    </html>"""
        return html
    
    def _send_file(self, dest_hash, file_path, filename):
        """Send file as LXMF attachment for download"""
        try:
            dest_identity = RNS.Identity.recall(dest_hash)
            
            if not dest_identity:
                self.ui.print_status('warning', "Client identity not in cache, requesting path...")
                RNS.Transport.request_path(dest_hash)
                
                max_wait = 15
                wait_interval = 0.5
                waited = 0
                
                while waited < max_wait:
                    time.sleep(wait_interval)
                    waited += wait_interval
                    dest_identity = RNS.Identity.recall(dest_hash)
                    if dest_identity:
                        self.ui.print_status('success', "Identity received")
                        break
                    
                    if int(waited) % 3 == 0:
                        self.ui.print_status('info', f"Still waiting... ({int(waited)}s)")
                
                if not dest_identity:
                    self.ui.print_status('error', f"Could not establish path")
                    return False
            
            dest = RNS.Destination(
                dest_identity,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "lxmf", "delivery"
            )
            
            # Read file data
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Get file size
            file_size = len(file_data)
            size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
            if file_size >= 1024*1024:
                size_str = f"{file_size/(1024*1024):.2f} MB"
            
            # Create file attachment tuple: (filename, file_data)
            file_attachment = (filename, file_data)
            
            # Create LXMF message with file attachment
            lxmf_message = LXMF.LXMessage(
                dest,
                self.lxmf_destination,
                f"File: {filename} ({size_str})",
                title=filename,
                fields={
                    self.FIELD_FILE_ATTACHMENTS: [file_attachment]
                }
            )
            
            self.message_router.handle_outbound(lxmf_message)
            self.ui.print_status('success', f"File queued for delivery: {filename} ({size_str})")
            return True
            
        except Exception as e:
            self.ui.print_status('error', f"Error sending file: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _serve_page(self, sender_hash, page_name):
        """Serve file to requester"""
        try:
            page_name = os.path.basename(page_name)
            
            # Handle index/list requests - ALWAYS generate dynamic index for these
            if not page_name or page_name.lower() in ['index', '_index', '_list', 'list', '']:
                html_content = self._generate_dynamic_index()
                text_index = self._generate_text_index()
                
                self._send_html(sender_hash, html_content, "File Index")
                self._send_simple_message(sender_hash, text_index)
                
                self._log_access(sender_hash, "INDEX", True)
                self.ui.print_status('response', f"Served INDEX to {RNS.prettyhexrep(sender_hash)}")
                return True
            
            # For any other file, try to serve it
            file_path = os.path.join(self.pages_path, page_name)
            
            if not os.path.exists(file_path):
                error_html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>404 Not Found</title>
        <style>
            body {{
                font-family: monospace;
                background: #1a1a1a;
                color: #f00;
                padding: 50px;
                text-align: center;
            }}
            h1 {{ font-size: 3em; text-shadow: 0 0 10px #f00; }}
            a {{
                color: #0ff;
                text-decoration: none;
                margin-top: 20px;
                display: inline-block;
                padding: 10px 20px;
                border: 1px solid #0ff;
                border-radius: 5px;
            }}
            a:hover {{
                background: rgba(0, 255, 255, 0.2);
            }}
        </style>
    </head>
    <body>
        <h1>404 - File Not Found</h1>
        <p>The requested file '{page_name}' does not exist.</p>
        <a href="index">← Back to Index</a>
    </body>
    </html>"""
                self._send_html(sender_hash, error_html, f"404: {page_name}")
                self._log_access(sender_hash, page_name, False)
                self.ui.print_status('error', f"404: {page_name}")
                return False
            
            # Determine file type
            ext = os.path.splitext(page_name)[1].lower()
            
            # HTML files - send as HTML content for rendering
            if ext in ['.html', '.htm']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                # Process templates
                html_content = self._process_template(html_content)
                
                self._send_html(sender_hash, html_content, f"Serving: {page_name}")
                self._log_access(sender_hash, page_name, True)
                self.requests_served += 1
                
                self.ui.print_status('response', f"Served '{page_name}' (HTML) to {RNS.prettyhexrep(sender_hash)}")
                return True
            
            # All other files - send as file attachment for download
            else:
                self._send_file(sender_hash, file_path, page_name)
                self._log_access(sender_hash, page_name, True)
                self.requests_served += 1
                
                mime_type = self._get_mime_type(page_name)
                self.ui.print_status('response', f"Sent file '{page_name}' ({mime_type}) to {RNS.prettyhexrep(sender_hash)}")
                return True
            
        except Exception as e:
            self.ui.print_status('error', f"Error serving file: {e}")
            import traceback
            traceback.print_exc()
            self._log_access(sender_hash, page_name, False)
            return False
    
    def _send_html(self, dest_hash, html_content, message_text):
        """Send HTML content via LXMF"""
        try:
            dest_identity = RNS.Identity.recall(dest_hash)
            
            if not dest_identity:
                self.ui.print_status('warning', "Client identity not in cache, requesting path...")
                RNS.Transport.request_path(dest_hash)
                
                max_wait = 15
                wait_interval = 0.5
                waited = 0
                
                while waited < max_wait:
                    time.sleep(wait_interval)
                    waited += wait_interval
                    dest_identity = RNS.Identity.recall(dest_hash)
                    if dest_identity:
                        self.ui.print_status('success', "Identity received")
                        break
                    
                    if int(waited) % 3 == 0:
                        self.ui.print_status('info', f"Still waiting... ({int(waited)}s)")
                
                if not dest_identity:
                    self.ui.print_status('error', f"Could not establish path")
                    return False
            
            dest = RNS.Destination(
                dest_identity,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "lxmf", "delivery"
            )
            
            lxmf_message = LXMF.LXMessage(
                dest,
                self.lxmf_destination,
                message_text,
                title="",
                fields={self.FIELD_HTML_CONTENT: html_content}
            )
            
            self.message_router.handle_outbound(lxmf_message)
            self.ui.print_status('success', "HTML message queued for delivery")
            return True
            
        except Exception as e:
            self.ui.print_status('error', f"Error sending HTML: {e}")
            return False
    
    def _send_simple_message(self, dest_hash, text):
        """Send a simple text message"""
        try:
            dest_identity = RNS.Identity.recall(dest_hash)
            
            if not dest_identity:
                RNS.Transport.request_path(dest_hash)
                time.sleep(2)
                dest_identity = RNS.Identity.recall(dest_hash)
                
                if not dest_identity:
                    return False
            
            dest = RNS.Destination(
                dest_identity,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "lxmf", "delivery"
            )
            
            simple_message = LXMF.LXMessage(dest, self.lxmf_destination, text)
            self.message_router.handle_outbound(simple_message)
            return True
            
        except Exception as e:
            self.ui.print_status('error', f"Error sending message: {e}")
            return False
    
    def _handle_message(self, message):
        """Handle incoming LXMF messages"""
        try:
            sender_hash = message.source_hash
            content = message.content.decode('utf-8') if isinstance(message.content, bytes) else message.content
            
            sender_full = RNS.prettyhexrep(sender_hash)
            self.ui.print_status('request', f"Request from {sender_full}: {content[:50]}")
            
            # Check for HTML request in fields
            if hasattr(message, 'fields') and message.fields:
                if self.FIELD_HTML_REQUEST in message.fields:
                    page_name = message.fields[self.FIELD_HTML_REQUEST]
                    self._serve_page(sender_hash, page_name)
                    return
            
            content_lower = content.lower().strip()
            
            # Index/list requests
            if content_lower in ['list', 'pages', 'dir', 'ls', '_index', '_list']:
                self._serve_page(sender_hash, '_index')
                return
            
            # "index" command
            if content_lower == 'index':
                self._serve_page(sender_hash, 'index')
                return
            
            # GET requests
            if content.startswith("GET:") or content.startswith("get:"):
                page_name = content[4:].strip()
                self._serve_page(sender_hash, page_name)
                return
            
            # Announce request
            if content_lower in ['announce', 'hello', 'ping']:
                self.ui.print_status('info', "Client announced itself")
                self._send_simple_message(sender_hash, "Server received your announcement")
                return
            
            # Default: show help
            help_text = f"""{self.ui.icon('server')} LXMF HTML Server

Available commands:
- GET:<file> - Request a specific file
- list or pages - Get file listing
- index - Get file index
- announce - Announce your presence

Supported file types:
🌐 HTML (.html, .htm)
📝 Text (.txt, .md)
🖼️ Images (.jpg, .png, .gif, .webp)
📄 PDF (.pdf)
📦 Archives (.zip, .rar, .7z)

Example: GET:about.html

Server: {self.server_hash}
Files: {len(self._get_page_list())}
"""
            self._send_simple_message(sender_hash, help_text)
            
        except Exception as e:
            self.ui.print_status('error', f"Error handling message: {e}")
            import traceback
            traceback.print_exc()
    
    def show_stats(self):
        """Display server statistics"""
        uptime = time.time() - self.start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        
        time_since_announce = time.time() - self.last_announce
        next_announce = max(0, self.auto_announce_interval - time_since_announce)
        
        self.ui.print_header("SERVER STATISTICS")
        print(f"{self.ui.icon('online')} Status: {'ENABLED' if self.enabled else 'DISABLED'}")
        print(f"{self.ui.icon('time')} Uptime: {hours}h {minutes}m")
        print(f"{self.ui.icon('stats')} Requests served: {self.requests_served}")
        print(f"{self.ui.icon('page')} Files available: {len(self._get_page_list())}")
        print(f"{self.ui.icon('info')} Files directory: {self.pages_path}")
        print(f"\n{self.ui.icon('network')} Auto-announce: {'ENABLED' if self.auto_announce_enabled else 'DISABLED'}")
        print(f"{self.ui.icon('time')} Announce interval: {self.auto_announce_interval}s ({self.auto_announce_interval//60}min)")
        if self.auto_announce_enabled and next_announce > 0:
            print(f"{self.ui.icon('info')} Next announce in: {int(next_announce)}s ({int(next_announce//60)}min)")
        
        # File types breakdown
        files = self._get_page_list()
        file_types = {}
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            file_types[ext] = file_types.get(ext, 0) + 1
        
        print(f"\n{self.ui.icon('page')} File types:")
        for ext, count in sorted(file_types.items()):
            print(f"  {ext}: {count}")
        
        # Network status
        try:
            interfaces = RNS.Transport.interfaces
            
            if isinstance(interfaces, dict):
                interface_count = len(interfaces)
            elif isinstance(interfaces, list):
                interface_count = len(interfaces)
            else:
                interface_count = 0
            
            try:
                if hasattr(RNS.Transport, 'destination_table'):
                    path_count = len(RNS.Transport.destination_table)
                elif hasattr(RNS.Transport, 'destinations'):
                    path_count = len(RNS.Transport.destinations)
                elif hasattr(RNS.Transport, 'path_table'):
                    path_count = len(RNS.Transport.path_table)
                else:
                    path_count = 0
            except:
                path_count = 0
            
            print(f"\n{self.ui.icon('interface')} Active interfaces: {interface_count}")
            print(f"{self.ui.icon('path')} Known paths: {path_count}")
        except Exception as e:
            self.ui.print_status('warning', f"Could not read network status: {e}")
        
        print("="*60 + "\n")
    
    def set_announce_interval(self, seconds):
        """Set auto-announce interval"""
        if seconds < 60:
            self.ui.print_status('warning', "Minimum interval is 60 seconds")
            return False
        
        self.auto_announce_interval = seconds
        self._save_config()
        self.ui.print_status('success', f"Auto-announce interval set to {seconds}s ({seconds//60}min)")
        return True
    
    def run(self):
        """Run the server"""
        self.running = True
        
        # Start auto-announce thread
        self.announce_thread = threading.Thread(target=self._auto_announce_loop, daemon=True)
        self.announce_thread.start()
        
        self.ui.print_status('online', f"Server started: {self.server_name}")
        self.ui.print_status('info', "Listening for requests...")
        self.ui.print_status('network', f"Auto-announce: {'ENABLED' if self.auto_announce_enabled else 'DISABLED'} ({self.auto_announce_interval}s)")
        
        print(f"\n{self.ui.icon('info')} Supported file types:")
        print(f"   🌐 HTML, 📝 Text, 🖼️ Images, 📄 PDF, 📦 Archives")
        print(f"\n{self.ui.icon('info')} Clients can request files using:")
        print(f"   • GET:<filename>")
        print(f"   • 'index' or 'list' for file listing")
        print(f"   • Click links in HTML pages\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n")
            self.ui.print_status('warning', "Server stopping...")
            self.running = False
            self.show_stats()
            self.ui.print_status('info', "Goodbye!\n")

def main():
    parser = argparse.ArgumentParser(
        description='Standalone LXMF HTML Server with Multi-File Support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Start server with default settings
  %(prog)s --storage ~/myserver         # Use custom storage path
  %(prog)s --name "My Server"           # Set custom server name
  %(prog)s --announce-interval 3600     # Announce every hour
  %(prog)s --no-auto-announce           # Disable auto-announce
  %(prog)s --stats                      # Show statistics
  
Supported file types:
  - HTML pages (.html, .htm)
  - Text files (.txt, .md)
  - Images (.jpg, .png, .gif, .webp, .bmp)
  - PDF documents (.pdf)
  - Archives (.zip, .rar, .7z)
        """
    )
    
    parser.add_argument('--storage', type=str, default=None,
                       help='Storage path (default: ~/.lxmf_html_server)')
    parser.add_argument('--identity', type=str, default=None,
                       help='Path to identity file')
    parser.add_argument('--name', type=str, default=None,
                       help='Server display name')
    parser.add_argument('--announce-interval', type=int, default=None,
                       help='Auto-announce interval in seconds (default: 1800)')
    parser.add_argument('--no-auto-announce', action='store_true',
                       help='Disable automatic announcements')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics and exit')
    
    args = parser.parse_args()
    
    server = LXMFHTMLServer(storage_path=args.storage, identity_path=args.identity)
    
    # Apply --name argument BEFORE saving config
    if args.name is not None:
        server.server_name = args.name
    
    if args.announce_interval is not None:
        server.set_announce_interval(args.announce_interval)
    
    if args.no_auto_announce:
        server.auto_announce_enabled = False
    
    # Save config after applying all settings
    server._save_config()
    
    if args.stats:
        server.show_stats()
    else:
        server.run()

if __name__ == "__main__":
    main()