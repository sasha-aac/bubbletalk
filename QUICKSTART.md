# Quick Start Guide - BubbleTalk

## 🚀 First Time Setup

### 1. Install System Dependencies (Linux only)

```bash
# Install v4l2loopback for virtual camera support
sudo apt install v4l2-loopback-dkms

# Load the module
sudo modprobe v4l2loopback

# Verify it's loaded
ls /dev/video*
```

### 2. Activate Virtual Environment

```bash
cd /home/beesy/Documents/bubbletalk
source venv/bin/activate
```

### 3. Run the Application

```bash
python3 main.py
```

## 📱 Using BubbleTalk

1. **Start the stream:**
   - Make sure your webcam and virtual camera device IDs are correct
   - Click "Start Stream"

2. **Add text:**
   - Type in the message box and press Enter or click "Send"
   - Or click any of the quick phrase buttons
   - The text will appear as a speech bubble on your video for 5 seconds

3. **In Google Meet:**
   - Click on your camera icon (settings)
   - Select "BubbleTalk" as your camera
   - Your webcam with speech bubbles will appear

## ⚙️ Configuration

Edit `config.json` to customize:

```json
{
  "bubble_color": [255, 255, 255],    // RGB color (white)
  "text_color": [0, 0, 0],            // RGB color (black)
  "border_color": [0, 0, 0],          // Border RGB color
  "text_size": 24,                    // Font size
  "bubble_x": 50,                     // X position from left
  "bubble_y": 50,                     // Y position from top
  "bubble_padding": 20,               // Padding inside bubble
  "phrases": [                        // Quick access buttons
    "Hello!",
    "Thank you",
    ...
  ]
}
```

## 🎥 Finding Your Camera IDs

```bash
# List all video devices
ls -la /dev/video*

# Test camera 0
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera available:', cap.isOpened()); cap.release()"

# List virtual camera devices
python3 -c "import pyvirtualcam; print(pyvirtualcam.Camera.device_ids())"
```

## 🐛 Troubleshooting

**Webcam not detected:**
- Try different camera IDs (0, 1, 2, etc.) in the app
- Check permissions: `ls -la /dev/video*`
- Try: `sudo usermod -a -G video $USER` (then log out/in)

**Virtual camera not showing:**
- Ensure v4l2loopback is loaded: `lsmod | grep v4l2loopback`
- Load it: `sudo modprobe v4l2loopback`
- Try different device IDs (0, 1, 2, etc.)

**Text not appearing:**
- Check that "Start Stream" is enabled
- Try sending text again
- Check bubble position in config.json

**Performance issues:**
- Close other video applications
- Reduce video resolution
- Use a lower text size

## 📝 Customizing Quick Phrases

Edit `config.json` and update the `phrases` array:

```json
"phrases": [
  "Hello everyone!",
  "Could you please repeat that?",
  "I need a minute to think",
  "Thank you for your time",
  "I agree with that",
  "Can we take a break?"
]
```

The first 6 phrases will appear as quick buttons.

## 🔗 Useful Resources

- [OpenCV Documentation](https://docs.opencv.org/)
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [pyvirtualcam](https://github.com/letmaik/pyvirtualcam)

## 📞 Support

For issues or questions, check the README.md or open an issue on GitHub.
