## ✅ BubbleTalk Project - Setup Complete

BubbleTalk is an accessibility tool that adds text as speech bubbles to webcam video and outputs to a virtual camera for use in Google Meet and other video conferencing tools.

### Project Structure

```
bubbletalk/
├── main.py                 # Main application with PyQt5 GUI
├── config.json            # Configuration for phrases and styling
├── requirements.txt       # Python dependencies
├── setup.sh              # Automated setup script
├── README.md             # Full documentation
├── QUICKSTART.md         # Quick start guide
└── venv/                 # Virtual environment
```

### Installation Status

✅ Python 3.12 environment configured
✅ All dependencies installed:
   - PyQt5 5.15.11 (GUI framework)
   - OpenCV 4.13.0 (video processing)
   - Pillow 12.2.0 (image rendering)
   - pyvirtualcam 0.15.0 (virtual camera output)
   - NumPy 2.4.6 (array operations)

### Next Steps

1. **For Linux users only** - Set up v4l2loopback:
   ```bash
   sudo apt install v4l2-loopback-dkms
   sudo modprobe v4l2loopback
   ```

2. **Run the application:**
   ```bash
   cd /home/beesy/Documents/bubbletalk
   source venv/bin/activate
   python3 main.py
   ```

3. **Customize phrases** by editing `config.json`

### Features

- Real-time webcam capture with speech bubble overlays
- Quick-access buttons for common phrases
- Customizable bubble styling and positioning
- Virtual camera output for Google Meet integration
- Text input with 5-second display duration
- Accessible keyboard controls

### Configuration

See `config.json` for:
- Bubble colors and styling
- Text size and font
- Quick access phrases (8 phrases supported)
- Bubble positioning

### Troubleshooting

See `QUICKSTART.md` for:
- Finding camera IDs
- Virtual camera setup
- Performance optimization
- Common issues and fixes

