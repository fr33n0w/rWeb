# rWeb v0.1 - Reticulum LXMF HTML SERVER and BROWSER CLIENT

------

**rWeb** is a complete web browsing system for the Reticulum mesh network, enabling decentralized HTML content delivery over LXMF (Lightweight Extensible Message Format). Browse websites, download files, and discover servers - all without internet infrastructure.

First version, may contain bugs, expect new updates soon!

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7+-green.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS%20%7C%20Android-lightgrey.svg)

## 🌐 Features

### rWeb Server (`rWeb_server.py`)
- **Multi-format serving**: HTML pages, images (JPG, PNG, GIF, WebP), PDFs, text files, and archives (ZIP, RAR, 7z)
- **Automatic discovery**: Announces presence on the mesh network with `[HTML]` identifier
- **File attachment support**: Binary file transfers via LXMF fields
- **Click-through navigation**: Internal links work seamlessly between pages
- **Template system**: Dynamic content with timestamp and file list variables
- **Access logging**: Track page requests and server statistics
- **Cross-platform**: Works on Linux, Windows, macOS, and Android (Termux)

### rWeb Browser (`rWeb_client.py`)
- **Auto-discovery**: Automatically detects HTML servers announcing on the network
- **Web-based UI**: Modern Flask/SocketIO interface accessible via web browser
- **Real-time updates**: Live server discovery and page notifications
- **Bookmarks system**: Save favorite servers for quick access
- **Browsing history**: Track visited pages with timestamps
- **File downloads**: Automatic downloads for images, PDFs, and archives
- **Responsive design**: Works on desktop and mobile browsers
- **Server management**: Add/remove discovered servers

## 📋 Requirements

### Core Dependencies
```bash
# Python 3.7 or higher
python3 --version

# Reticulum Network Stack
pip install rns

# LXMF (Lightweight Extensible Message Format)
pip install lxmf

# Flask and SocketIO (for browser only)
pip install flask flask-socketio
```

### System Requirements
- **Operating System**: Linux, Windows 10+, macOS, or Android (via Termux)
- **Network**: At least one configured Reticulum interface (LoRa, TCP, UDP, I2P, etc.)
- **Python**: Version 3.7 or higher
- **Disk Space**: Minimal (~10MB for software, varies with content)

## 🚀 Quick Start

### 1. Install Dependencies

**On Linux/macOS:**
```bash
# Install Python packages
pip3 install rns lxmf flask flask-socketio

# Verify installation
python3 -c "import RNS, LXMF; print('Dependencies OK')"
```

**On Windows:**
```bash
# Install Python packages
pip install rns lxmf flask flask-socketio

# Install colorama for terminal colors
pip install colorama
```

**On Android (Termux):**
```bash
# Update packages
pkg update && pkg upgrade

# Install Python and dependencies
pkg install python
pip install rns lxmf flask flask-socketio
```

### 2. Configure Reticulum

Create or edit `~/.reticulum/config`:
```ini
[reticulum]
  enable_transport = False
  share_instance = Yes

# Example: Auto-interface (discovers local Reticulum instances)
[interfaces]
  [[Default Interface]]
    type = AutoInterface
    enabled = Yes
```

For more interface options, see the [Reticulum Manual](https://markqvist.github.io/Reticulum/manual/).

### 3. Start the Server
```bash
# Basic usage
python3 rWeb_server.py

# Custom storage path
python3 rWeb_server.py --storage ~/my_html_server

# Custom server name
python3 rWeb_server.py --name "My Server"

# Custom announce interval (in seconds)
python3 rWeb_server.py --announce-interval 3600

# View statistics
python3 rWeb_server.py --stats
```

**Default content location**: `~/.lxmf_html_server/pages/`

The server will:
- Create default example pages on first run
- Announce itself on the network with `[HTML]` prefix
- Serve files to requesting clients
- Log all access requests

### 4. Start the Browser
```bash
# Basic usage
python3 rWeb_client.py

# Custom storage path
python3 rWeb_client.py --storage ~/my_browser_data
```

Then open your web browser to: **http://localhost:5080**

The browser will:
- Listen for HTML server announces
- Display discovered servers in the sidebar
- Enable bookmarking and history tracking
- Handle file downloads automatically

## 📁 File Structure

### Server
```
~/.lxmf_html_server/
├── pages/              # Your HTML files and content
│   ├── index.html      # Auto-generated index
│   ├── about.html      # Example page
│   ├── help.html       # Example page
│   └── [your files]    # Add any supported files here
├── config.json         # Server configuration
├── access.log          # Access log
└── identity            # LXMF identity
```

### Browser
```
~/.lxmf_html_browser/
├── cache/              # Downloaded files
├── html_cache/         # Rendered HTML pages
├── bookmarks.json      # Saved bookmarks
├── history.json        # Browsing history
├── discovered_servers.json  # Known servers
└── identity            # LXMF identity
```

## 📝 Creating Content

### HTML Pages
Place HTML files in `~/.lxmf_html_server/pages/`:
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>My Page</title>
</head>
<body>
    <h1>Welcome to My Page</h1>
    <p>Current time: {{timestamp}}</p>
    <p>Available files: {{page_count}}</p>
    
    <!-- Internal links work automatically -->
    <a href="about.html">About</a>
    <a href="help.html">Help</a>
</body>
</html>
```

### Template Variables
- `{{timestamp}}` - Current server time
- `{{page_count}}` - Number of available files
- `{{page_list}}` - Auto-generated HTML links to all files

### Supported File Types
- **HTML**: `.html`, `.htm`
- **Text**: `.txt`, `.md`
- **Images**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`
- **Documents**: `.pdf`
- **Archives**: `.zip`, `.rar`, `.7z`

## 🔧 Advanced Usage

### Server Commands
```bash
# Show help
python3 rWeb_server.py --help

# Set custom announce interval (1 hour)
python3 rWeb_server.py --announce-interval 3600

# Disable auto-announce
python3 rWeb_server.py --no-auto-announce

# View server statistics
python3 rWeb_server.py --stats
```

### Browser Features

**Server Discovery:**
- Servers appear automatically in the "Servers" tab
- Shows server name, LXMF address, and last seen time
- Click server name or any page to request content

**Bookmarks:**
- Click ★ Bookmark button to save current server
- Access saved servers from "Bookmarks" tab
- Remove bookmarks with 🗑️ button

**History:**
- All visited pages tracked with timestamps
- View full LXMF URLs
- Clear history with one click

**Downloads:**
- Files automatically download when served
- Saved to browser's cache directory
- Images, PDFs, and archives supported

### Manual Server Addition

If a server isn't auto-discovered, add it manually:

1. Get the server's LXMF hash from the server terminal
2. Enter in browser address bar: `lxmf://hash/index`
3. Click "Go" to connect

## 🔒 Security Notes

- **End-to-end encryption**: All LXMF messages are encrypted
- **Identity-based**: Each server/browser has unique cryptographic identity
- **No central authority**: Fully decentralized operation
- **Stamp costs**: Optional anti-spam mechanism (disabled by default)
- **Ratchets**: Forward secrecy supported (optional)

## 🐛 Troubleshooting

### Server not announcing
```bash
# Check Reticulum status
rnstatus

# Verify interfaces are up
cat ~/.reticulum/config

# Check server logs
python3 rWeb_server.py --stats
```

### Browser not discovering servers
```bash
# Verify Reticulum is running
rnstatus

# Check browser logs for [ANNOUNCE] messages
# Should see: [ANNOUNCE] LXMF delivery destination: ...

# Manually add server if needed
# Use: lxmf://server_hash/index
```

### Files not downloading
- Check file size limits in browser settings
- Verify file exists in server's pages directory
- Check server logs for access attempts

### Cannot connect to browser UI
- Verify Flask is running: `http://localhost:5080`
- Check firewall settings
- Try alternative port: modify `socketio.run(app, port=5080)` in code

## 🌍 Use Cases

- **Off-grid websites**: Host content over LoRa mesh networks
- **Emergency communications**: Serve information during infrastructure failure
- **Privacy-focused browsing**: No ISP tracking or centralized servers
- **Rural connectivity**: Share content over long-range radio
- **Disaster recovery**: Maintain local information networks
- **Private networks**: Company intranets without internet dependency

## 📚 Technical Details

### Architecture
- **Protocol**: LXMF over Reticulum Network Stack
- **Transport**: Opportunistic routing with automatic path discovery
- **Encryption**: Curve25519 + AES-256
- **Delivery**: Direct links or propagation node routing
- **File Transfer**: LXMF field 0x02 (FILE_ATTACHMENTS)
- **HTML Content**: LXMF field 0x0A (custom HTML field)

### Announce Format
Server announces include:
- Destination aspect: `lxmf.delivery`
- Display name: `[HTML] server_name`
- Stamp cost: Optional anti-spam parameter

Browser listens for announces with `[HTML]` prefix and automatically discovers servers.

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- [ ] CSS/JavaScript support in HTML pages
- [ ] Search functionality across servers
- [ ] Download progress indicators
- [ ] Multi-language support
- [ ] Custom themes for browser UI
- [ ] Page caching and offline mode
- [ ] WebDAV-style file management

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Credits

Built on:
- [Reticulum](https://github.com/markqvist/Reticulum) by Mark Qvist
- [LXMF](https://github.com/markqvist/lxmf) by Mark Qvist
- [Flask](https://flask.palletsprojects.com/) and [SocketIO](https://socket.io/)

## 📞 Support

- **Reticulum Manual**: https://markqvist.github.io/Reticulum/manual/
- **LXMF Documentation**: https://github.com/markqvist/lxmf
- **Issues**: Open an issue on GitHub

---

**rWeb v0.1** - Bringing the web to mesh networks 🌐📡
