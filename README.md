# BubbleTalk 🗨️

A desktop application that adds text speech bubbles to your webcam video stream and outputs to a virtual camera for use in Google Meet and other video conferencing tools. Designed for accessibility and communication support.

## Features

- **Real-time webcam capture** with speech bubble overlays
- **Text input** with quick-access buttons for common phrases
- **15-second auto-clear** for each sent message
- **Customizable phrases** for fast communication
- **Adjustable bubble positioning** and styling
- **Drag-and-drop bubble positioning** directly on the video preview
- **Message chain stacking** where new bubbles appear below active ones
- **Virtual camera output** for seamless Google Meet integration
- **Keyboard shortcuts** for accessibility

## Requirements

### System Requirements
- Python 3.9 or higher
- Webcam
- Linux: `v4l2loopback` driver for virtual camera support
- macOS/Windows: Virtual camera support built-in

### Linux Virtual Camera Setup

```bash
# Install v4l2loopback
sudo apt install v4l2-loopback-dkms

# Load the module
sudo modprobe v4l2loopback

# Verify (should show /dev/video*)
ls /dev/video*
```

## Installation

1. Clone or download this project
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

## Usage

1. **Start the app** - Select your webcam and virtual camera device
2. **Enable streaming** - Click "Start Stream" to begin
3. **Type or select phrases** - Use the text input or quick-access buttons
4. **Automatic timeout** - Each message bubble disappears after 15 seconds
5. **Message chaining** - Sending while another bubble is active adds a new bubble below it
6. **Drag the bubble on preview** - Click and drag any visible bubble to reposition the whole chain
7. **Watch your video** - Bubble positions on preview match the virtual camera output
8. **Open Google Meet** - Select "BubbleTalk" as your camera in Meet

## Configuration

Edit `config.json` to customize:
- Default phrases
- Bubble colors and styling
- Text size and font
- Bubble positioning

## Keyboard Shortcuts

- `Ctrl+1-5` - Quick access buttons 1-5
- `Enter` - Send current text
- `Escape` - Clear text input
- `Space` - Toggle stream on/off

## Troubleshooting

**Virtual camera not showing up:**
- Linux: Ensure v4l2loopback is loaded: `sudo modprobe v4l2loopback`
- Check available devices: `python -c "import pyvirtualcam; print(pyvirtualcam.Camera.device_ids())"`

**Webcam not detected:**
- Check permissions: `ls -la /dev/video*`
- Try a different camera ID (0, 1, 2, etc.)

**Performance issues:**
- Reduce video resolution in settings
- Lower text rendering quality

## License

MIT

## Support

For issues or feature requests, please open an issue on GitHub.
