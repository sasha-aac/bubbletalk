#!/usr/bin/env python3
"""
BubbleTalk - Speech Bubble Overlay for Video Calls
Main application entry point with PyQt5 GUI
"""

import sys
import os
import json
import threading
import queue
import importlib.util
import inspect
from pathlib import Path
from datetime import datetime, timedelta


def preconfigure_qt_environment():
    """Prevent OpenCV Qt plugin conflicts with PyQt on Linux."""
    if not sys.platform.startswith("linux"):
        return

    pyqt_spec = importlib.util.find_spec("PyQt5")
    if pyqt_spec and pyqt_spec.origin:
        pyqt_plugins = Path(pyqt_spec.origin).resolve().parent / "Qt5" / "plugins"
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(pyqt_plugins)

    os.environ.pop("QT_PLUGIN_PATH", None)
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


preconfigure_qt_environment()
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pyvirtualcam

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QTextEdit,
    QTabWidget, QGridLayout, QCheckBox, QSlider
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor
from PyQt5.QtWidgets import QMessageBox


class VideoProcessor(QObject):
    """Handles video capture, processing, and virtual camera output"""
    
    frame_ready = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.current_text = ""
        self.cap = None
        self.vcam = None
        self.config = self.load_config()
        
    def load_config(self):
        """Load configuration from config.json"""
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        return self.default_config()
    
    @staticmethod
    def default_config():
        """Default configuration"""
        return {
            "bubble_color": [255, 255, 255],
            "text_color": [0, 0, 0],
            "border_color": [0, 0, 0],
            "text_size": 20,
            "bubble_x": 50,
            "bubble_y": 50,
            "bubble_padding": 20,
            "font_path": None,
            "phrases": [
                "Hello!",
                "Thank you",
                "Can you repeat that?",
                "One moment please",
                "I agree"
            ]
        }
    
    def start_stream(self, camera_id=0, vcam_id=0):
        """Start video capture and virtual camera output"""
        try:
            # Prefer V4L2 backend on Linux for more reliable webcam access.
            if sys.platform.startswith("linux"):
                self.cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
            else:
                self.cap = cv2.VideoCapture(camera_id)

            if not self.cap.isOpened():
                msg = f"ERROR: Could not open camera index {camera_id}"
                if sys.platform.startswith("linux"):
                    video_nodes = list(Path("/dev").glob("video*"))
                    if video_nodes:
                        has_access = any(os.access(node, os.R_OK | os.W_OK) for node in video_nodes)
                        if not has_access:
                            msg += " (camera permission denied - add user to video group)"

                self.status_changed.emit(msg)
                return False
            
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

            camera_kwargs = {
                "width": width,
                "height": height,
                "fps": fps,
            }

            # Support both pyvirtualcam APIs:
            # - Older: device_idx=<int>
            # - Newer Linux v4l2loopback: device=<str>
            params = inspect.signature(pyvirtualcam.Camera).parameters
            if "device_idx" in params:
                camera_kwargs["device_idx"] = vcam_id
            elif "device" in params and sys.platform.startswith("linux"):
                # Use the explicit loopback device path (video_nr=10 from modprobe).
                camera_kwargs["device"] = f"/dev/video{10 + vcam_id}"

            self.vcam = pyvirtualcam.Camera(**camera_kwargs)
            self.vcam.__enter__()
            
            self.is_running = True
            self.status_changed.emit(f"Streaming: {width}x{height} @ {fps:.0f}fps")
            return True
            
        except Exception as e:
            self.status_changed.emit(f"ERROR: {str(e)}")
            return False
    
    def stop_stream(self):
        """Stop video capture and virtual camera"""
        self.is_running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        if self.vcam:
            self.vcam.__exit__(None, None, None)
            self.vcam = None
        
        self.status_changed.emit("Stopped")
    
    def process_frame(self):
        """Capture, process, and output frame"""
        if not self.cap or not self.vcam or not self.is_running:
            return
        
        ret, frame = self.cap.read()
        if not ret:
            return
        
        # Add speech bubble if there's text
        if self.current_text:
            frame = self.draw_speech_bubble(frame, self.current_text)
        
        # Send to virtual camera
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.vcam.send(rgb_frame)
        
        # Emit for preview
        self.frame_ready.emit(frame)
    
    def draw_speech_bubble(self, frame, text):
        """Draw text as a speech bubble on the frame"""
        config = self.config
        
        # Convert to PIL for text rendering
        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)
        
        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", config["text_size"])
        except:
            font = ImageFont.load_default()
        
        # Calculate text size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Bubble dimensions
        padding = config["bubble_padding"]
        bubble_x = config["bubble_x"]
        bubble_y = config["bubble_y"]
        bubble_width = text_width + padding * 2
        bubble_height = text_height + padding * 2
        
        # Draw bubble background
        bubble_box = [
            bubble_x,
            bubble_y,
            bubble_x + bubble_width,
            bubble_y + bubble_height
        ]
        
        bubble_color = tuple(config["bubble_color"])
        border_color = tuple(config["border_color"])
        
        # Draw rounded rectangle effect with simple rectangle
        draw.rectangle(bubble_box, fill=bubble_color, outline=border_color, width=3)
        
        # Draw tail (small triangle pointing down)
        tail_x = bubble_x + bubble_width // 2
        tail_y = bubble_y + bubble_height
        tail_points = [
            (tail_x - 15, tail_y),
            (tail_x + 15, tail_y),
            (tail_x, tail_y + 15)
        ]
        draw.polygon(tail_points, fill=bubble_color, outline=border_color)
        
        # Draw text
        text_x = bubble_x + padding
        text_y = bubble_y + padding
        text_color = tuple(config["text_color"])
        draw.text((text_x, text_y), text, fill=text_color, font=font)
        
        # Convert back to OpenCV
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    def set_text(self, text):
        """Update the text to display"""
        self.current_text = text
    
    def clear_text(self):
        """Clear the current text"""
        self.current_text = ""


class BubbleTalkApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.processor = VideoProcessor()
        self.processor.frame_ready.connect(self.update_preview)
        self.processor.status_changed.connect(self.update_status)
        
        self.init_ui()
        self.setup_timer()
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("BubbleTalk - Speech Bubble Overlay")
        self.setGeometry(100, 100, 1000, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout()
        
        # Left side: Video preview
        left_layout = QVBoxLayout()
        
        self.video_label = QLabel("Video Preview")
        self.video_label.setStyleSheet("border: 2px solid black; min-height: 400px; min-width: 500px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.video_label)
        
        # Right side: Controls
        right_layout = QVBoxLayout()
        
        # Camera selection
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel("Camera:"))
        self.camera_combo = QComboBox()
        self.populate_camera_choices()
        camera_layout.addWidget(self.camera_combo)
        
        camera_layout.addWidget(QLabel("Virtual Camera:"))
        self.vcam_combo = QComboBox()
        self.vcam_combo.addItems(["0", "1", "2", "3"])
        camera_layout.addWidget(self.vcam_combo)
        right_layout.addLayout(camera_layout)
        
        # Start/Stop buttons
        stream_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Stream")
        self.start_btn.clicked.connect(self.start_stream)
        self.start_btn.setStyleSheet("background-color: #90EE90; font-size: 14px; padding: 10px;")
        
        self.stop_btn = QPushButton("Stop Stream")
        self.stop_btn.clicked.connect(self.stop_stream)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #FFB6C6; font-size: 14px; padding: 10px;")
        
        stream_layout.addWidget(self.start_btn)
        stream_layout.addWidget(self.stop_btn)
        right_layout.addLayout(stream_layout)
        
        # Status
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        right_layout.addWidget(self.status_label)
        
        # Text input
        right_layout.addWidget(QLabel("Message:"))
        self.text_input = QLineEdit()
        self.text_input.returnPressed.connect(self.send_text)
        self.text_input.setPlaceholderText("Type your message here...")
        self.text_input.setStyleSheet("font-size: 14px; padding: 10px;")
        right_layout.addWidget(self.text_input)
        
        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_text)
        self.send_btn.setStyleSheet("background-color: #87CEEB; font-size: 12px; padding: 10px;")
        right_layout.addWidget(self.send_btn)
        
        # Quick access phrases
        right_layout.addWidget(QLabel("Quick Phrases:"))
        phrases_grid = QGridLayout()
        self.phrase_buttons = []
        phrases = self.processor.config.get("phrases", [])
        
        for i, phrase in enumerate(phrases[:6]):
            btn = QPushButton(phrase)
            btn.clicked.connect(lambda checked, p=phrase: self.quick_phrase(p))
            btn.setStyleSheet("font-size: 11px; padding: 8px;")
            phrases_grid.addWidget(btn, i // 2, i % 2)
            self.phrase_buttons.append(btn)
        
        right_layout.addLayout(phrases_grid)
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_text)
        self.clear_btn.setStyleSheet("font-size: 12px; padding: 8px;")
        right_layout.addWidget(self.clear_btn)
        
        right_layout.addStretch()
        
        layout.addLayout(left_layout, 2)
        layout.addLayout(right_layout, 1)
        
        central_widget.setLayout(layout)
    
    def load_config(self):
        """Load phrases from config"""
        config = self.processor.config
        self.processor.config = config

    def populate_camera_choices(self):
        """Populate camera dropdown with indices that are likely available."""
        self.camera_combo.clear()
        found = []

        for index in range(6):
            if sys.platform.startswith("linux"):
                cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
            else:
                cap = cv2.VideoCapture(index)

            if cap.isOpened():
                found.append(str(index))
            cap.release()

        if found:
            self.camera_combo.addItems(found)
            if "0" in found:
                self.camera_combo.setCurrentText("0")
        else:
            # Keep manual options in case probe fails but camera can still open later.
            self.camera_combo.addItems(["0", "1", "2", "3"])
    
    def start_stream(self):
        """Start video streaming"""
        camera_id = int(self.camera_combo.currentText())
        vcam_id = int(self.vcam_combo.currentText())
        
        if self.processor.start_stream(camera_id, vcam_id):
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.camera_combo.setEnabled(False)
            self.vcam_combo.setEnabled(False)
    
    def stop_stream(self):
        """Stop video streaming"""
        self.processor.stop_stream()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.camera_combo.setEnabled(True)
        self.vcam_combo.setEnabled(True)
        self.video_label.setText("Video Preview (Stopped)")
    
    def send_text(self):
        """Send text as speech bubble"""
        text = self.text_input.text().strip()
        if text:
            self.processor.set_text(text)
            # Keep text for 5 seconds then clear
            QTimer.singleShot(5000, self.clear_text)
    
    def quick_phrase(self, phrase):
        """Use a quick access phrase"""
        self.text_input.setText(phrase)
        self.send_text()
    
    def clear_text(self):
        """Clear the text input and bubble"""
        self.text_input.clear()
        self.processor.clear_text()
    
    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(f"Status: {status}")
    
    def update_preview(self, frame):
        """Update video preview"""
        # Resize for display
        display_frame = cv2.resize(frame, (500, 375))
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = 3 * w
        
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap)
    
    def setup_timer(self):
        """Setup timer for frame processing"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.processor.process_frame)
        self.timer.start(33)  # ~30 FPS
    
    def closeEvent(self, event):
        """Clean up on close"""
        self.processor.stop_stream()
        self.timer.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = BubbleTalkApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
