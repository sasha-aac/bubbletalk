#!/usr/bin/env python3
"""
BubbleTalk - Speech Bubble Overlay for Video Calls
Main application entry point with PyQt5 GUI
"""

import sys
import os
import json
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
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QGridLayout,
    QSlider,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QImage, QPixmap


class PreviewLabel(QLabel):
    """Preview widget that emits mouse events for bubble dragging."""

    mouse_pressed = pyqtSignal(int, int)
    mouse_moved = pyqtSignal(int, int)
    mouse_released = pyqtSignal(int, int)

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.mouse_pressed.emit(pos.x(), pos.y())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            pos = event.pos()
            self.mouse_moved.emit(pos.x(), pos.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.mouse_released.emit(pos.x(), pos.y())
        super().mouseReleaseEvent(event)


class VideoProcessor(QObject):
    """Handles video capture, processing, and virtual camera output."""

    frame_ready = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_running = False
        self.active_messages = []
        self.message_duration_seconds = 15
        self.cap = None
        self.vcam = None
        self.output_width = 1920
        self.output_height = 1080
        self.output_fps = 30
        self.last_bubble_box = None
        self.last_bubble_boxes = []
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from config.json."""
        config = self.default_config()
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    config.update(loaded)
            except Exception:
                # Keep defaults if config is malformed/unreadable.
                pass
        return config

    def save_config(self):
        """Persist current configuration to config.json."""
        config_path = Path(__file__).parent / "config.json"
        try:
            with open(config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.status_changed.emit(f"ERROR: Could not save config ({e})")

    @staticmethod
    def default_config():
        """Default configuration."""
        return {
            "bubble_color": [255, 255, 255],
            "text_color": [0, 0, 0],
            "border_color": [0, 0, 0],
            "text_size": 20,
            "bubble_scale": 1.0,
            "wrap_width_scale": 0.75,
            "bubble_x": 50,
            "bubble_y": 50,
            "bubble_padding": 20,
            "font_path": None,
            "phrases": [
                "Hello!",
                "Thank you",
                "Can you repeat that?",
                "One moment please",
                "I agree",
            ],
        }

    def start_stream(self, camera_id=0, vcam_id=0):
        """Start video capture and virtual camera output."""
        try:
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

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.output_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.output_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.output_fps)

            capture_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            capture_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            capture_fps = self.cap.get(cv2.CAP_PROP_FPS) or self.output_fps

            camera_kwargs = {
                "width": self.output_width,
                "height": self.output_height,
                "fps": self.output_fps,
            }

            params = inspect.signature(pyvirtualcam.Camera).parameters
            if "device_idx" in params:
                camera_kwargs["device_idx"] = vcam_id
            elif "device" in params and sys.platform.startswith("linux"):
                camera_kwargs["device"] = f"/dev/video{10 + vcam_id}"

            self.vcam = pyvirtualcam.Camera(**camera_kwargs)
            self.vcam.__enter__()

            self.is_running = True
            self.status_changed.emit(
                f"Streaming: 1920x1080 @ {self.output_fps}fps (capture {capture_width}x{capture_height} @ {capture_fps:.0f}fps)"
            )
            return True

        except Exception as e:
            self.status_changed.emit(f"ERROR: {str(e)}")
            return False

    def stop_stream(self):
        """Stop video capture and virtual camera."""
        self.is_running = False

        if self.cap:
            self.cap.release()
            self.cap = None

        if self.vcam:
            self.vcam.__exit__(None, None, None)
            self.vcam = None

        self.status_changed.emit("Stopped")

    def process_frame(self):
        """Capture, process, and output frame."""
        if not self.cap or not self.vcam or not self.is_running:
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        if frame.shape[1] != self.output_width or frame.shape[0] != self.output_height:
            frame = cv2.resize(frame, (self.output_width, self.output_height), interpolation=cv2.INTER_LINEAR)

        now = datetime.now()
        self.active_messages = [m for m in self.active_messages if m["expires_at"] > now]

        if self.active_messages:
            frame = self.draw_message_chain(frame)
        else:
            self.last_bubble_box = None
            self.last_bubble_boxes = []

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.vcam.send(rgb_frame)
        self.frame_ready.emit(frame)

    def wrap_text_lines(self, draw, font, text, max_text_width):
        """Wrap text into lines that fit the requested width."""
        wrapped_lines = []
        source_lines = text.splitlines() or [text]

        for source_line in source_lines:
            words = source_line.split(" ") if source_line else [""]
            current_line = ""

            for word in words:
                candidate = word if not current_line else f"{current_line} {word}"
                bbox = draw.textbbox((0, 0), candidate, font=font)
                candidate_width = bbox[2] - bbox[0]

                if candidate_width <= max_text_width:
                    current_line = candidate
                    continue

                if current_line:
                    wrapped_lines.append(current_line)

                long_word = word
                while long_word:
                    best_fit = ""
                    for idx in range(1, len(long_word) + 1):
                        part = long_word[:idx]
                        part_bbox = draw.textbbox((0, 0), part, font=font)
                        part_width = part_bbox[2] - part_bbox[0]
                        if part_width <= max_text_width:
                            best_fit = part
                        else:
                            break

                    if not best_fit:
                        best_fit = long_word[0]

                    if len(best_fit) < len(long_word):
                        wrapped_lines.append(best_fit)
                        long_word = long_word[len(best_fit):]
                    else:
                        current_line = best_fit
                        long_word = ""

            if current_line:
                wrapped_lines.append(current_line)
            elif not words:
                wrapped_lines.append("")

        if not wrapped_lines:
            wrapped_lines = [""]

        return wrapped_lines

    def draw_message_chain(self, frame):
        """Draw active messages as a vertical chain of speech bubbles."""
        config = self.config
        bubble_scale = float(config.get("bubble_scale", 1.0))
        bubble_scale = max(0.5, min(2.0, bubble_scale))
        text_size = max(12, int(config.get("text_size", 20) * bubble_scale))
        padding = max(8, int(config.get("bubble_padding", 20) * bubble_scale))
        tail_size = max(8, int(15 * bubble_scale))
        border_width = max(1, int(3 * bubble_scale))
        chain_spacing = max(6, int(12 * bubble_scale))
        margin = 10

        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", text_size)
        except Exception:
            font = ImageFont.load_default()

        frame_height, frame_width = frame.shape[:2]
        bubble_x = int(config.get("bubble_x", 50))
        bubble_y = int(config.get("bubble_y", 50))

        max_bubble_width = max(120, frame_width - bubble_x - margin)
        bubble_layouts = []

        for message in self.active_messages:
            text = message["text"]
            wrap_width_scale = float(config.get("wrap_width_scale", 0.75))
            wrap_width_scale = max(0.5, min(1.0, wrap_width_scale))
            max_text_width = max(40, int((max_bubble_width - (padding * 2)) * wrap_width_scale))
            wrapped_lines = self.wrap_text_lines(draw, font, text, max_text_width)

            line_heights = []
            line_widths = []
            line_spacing = max(4, text_size // 4)
            for line in wrapped_lines:
                line_bbox = draw.textbbox((0, 0), line or " ", font=font)
                line_widths.append(line_bbox[2] - line_bbox[0])
                line_heights.append(line_bbox[3] - line_bbox[1])

            text_width = max(line_widths) if line_widths else 0
            text_height = sum(line_heights) + (line_spacing * (len(wrapped_lines) - 1))
            bubble_width = min(text_width + padding * 2, max_bubble_width)
            bubble_height = text_height + padding * 2
            total_height = bubble_height + tail_size

            bubble_layouts.append(
                {
                    "wrapped_lines": wrapped_lines,
                    "line_heights": line_heights,
                    "line_spacing": line_spacing,
                    "bubble_width": bubble_width,
                    "bubble_height": bubble_height,
                    "total_height": total_height,
                }
            )

        if not bubble_layouts:
            self.last_bubble_box = None
            self.last_bubble_boxes = []
            return frame

        widest_bubble = max(layout["bubble_width"] for layout in bubble_layouts)
        bubble_x = max(margin, min(bubble_x, frame_width - widest_bubble - margin))
        total_chain_height = sum(layout["total_height"] for layout in bubble_layouts)
        total_chain_height += chain_spacing * (len(bubble_layouts) - 1)
        max_chain_top = frame_height - total_chain_height - margin
        bubble_y = max(margin, min(bubble_y, max_chain_top))

        bubble_color = tuple(config.get("bubble_color", [255, 255, 255]))
        border_color = tuple(config.get("border_color", [0, 0, 0]))
        text_color = tuple(config.get("text_color", [0, 0, 0]))

        self.last_bubble_boxes = []
        current_y = bubble_y
        for idx, layout in enumerate(bubble_layouts):
            bubble_width = layout["bubble_width"]
            bubble_height = layout["bubble_height"]

            bubble_box = [
                bubble_x,
                current_y,
                bubble_x + bubble_width,
                current_y + bubble_height,
            ]
            draw.rectangle(bubble_box, fill=bubble_color, outline=border_color, width=border_width)

            tail_x = bubble_x + bubble_width // 2
            tail_y = current_y + bubble_height
            tail_points = [
                (tail_x - tail_size, tail_y),
                (tail_x + tail_size, tail_y),
                (tail_x, tail_y + tail_size),
            ]
            draw.polygon(tail_points, fill=bubble_color, outline=border_color)

            text_x = bubble_x + padding
            text_y = current_y + padding
            text_cursor_y = text_y
            for line, line_height in zip(layout["wrapped_lines"], layout["line_heights"]):
                draw.text((text_x, text_cursor_y), line, fill=text_color, font=font)
                text_cursor_y += line_height + layout["line_spacing"]

            box = (bubble_x, current_y, bubble_width, bubble_height + tail_size)
            self.last_bubble_boxes.append(box)
            if idx == 0:
                self.last_bubble_box = box

            current_y += layout["total_height"] + chain_spacing

        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def set_text(self, text):
        """Add a message bubble that expires after a fixed timeout."""
        message_text = (text or "").strip()
        if not message_text:
            return
        expires_at = datetime.now() + timedelta(seconds=self.message_duration_seconds)
        self.active_messages.append({"text": message_text, "expires_at": expires_at})

    def clear_text(self):
        """Clear all active messages."""
        self.active_messages = []
        self.last_bubble_box = None
        self.last_bubble_boxes = []

    def set_bubble_scale_percent(self, percent):
        """Set speech bubble size scale from a UI percentage value."""
        clamped = max(50, min(200, int(percent)))
        self.config["bubble_scale"] = clamped / 100.0
        self.save_config()

    def set_bubble_position(self, x, y, persist=False):
        """Set speech bubble top-left position in output-frame coordinates."""
        max_x = max(0, self.output_width - 1)
        max_y = max(0, self.output_height - 1)
        self.config["bubble_x"] = max(0, min(int(x), max_x))
        self.config["bubble_y"] = max(0, min(int(y), max_y))
        if persist:
            self.save_config()

    def set_wrap_width_percent(self, percent):
        """Set wrapping width as a percent of available bubble text width."""
        clamped = max(50, min(100, int(percent)))
        self.config["wrap_width_scale"] = clamped / 100.0
        self.save_config()


class BubbleTalkApp(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.processor = VideoProcessor()
        self.processor.frame_ready.connect(self.update_preview)
        self.processor.status_changed.connect(self.update_status)

        self.dragging_bubble = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.preview_draw_x = 0
        self.preview_draw_y = 0
        self.preview_draw_width = 500
        self.preview_draw_height = 375

        self.init_ui()
        self.setup_timer()
        self.load_config()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("BubbleTalk - Speech Bubble Overlay")
        self.setGeometry(100, 100, 1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        self.video_label = PreviewLabel("Video Preview")
        self.video_label.setStyleSheet("border: 2px solid black; min-height: 400px; min-width: 500px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.mouse_pressed.connect(self.on_preview_mouse_pressed)
        self.video_label.mouse_moved.connect(self.on_preview_mouse_moved)
        self.video_label.mouse_released.connect(self.on_preview_mouse_released)
        left_layout.addWidget(self.video_label)

        right_layout = QVBoxLayout()

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

        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        right_layout.addWidget(self.status_label)

        right_layout.addWidget(QLabel("Message:"))
        self.text_input = QLineEdit()
        self.text_input.returnPressed.connect(self.send_text)
        self.text_input.setPlaceholderText("Type your message here...")
        self.text_input.setStyleSheet("font-size: 14px; padding: 10px;")
        right_layout.addWidget(self.text_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_text)
        self.send_btn.setStyleSheet("background-color: #87CEEB; font-size: 12px; padding: 10px;")
        right_layout.addWidget(self.send_btn)

        right_layout.addWidget(QLabel("Quick Phrases:"))
        phrases_grid = QGridLayout()
        phrases = self.processor.config.get("phrases", [])
        for i, phrase in enumerate(phrases[:6]):
            btn = QPushButton(phrase)
            btn.clicked.connect(lambda checked, p=phrase: self.quick_phrase(p))
            btn.setStyleSheet("font-size: 11px; padding: 8px;")
            phrases_grid.addWidget(btn, i // 2, i % 2)
        right_layout.addLayout(phrases_grid)

        bubble_size_row = QHBoxLayout()
        bubble_size_row.addWidget(QLabel("Bubble Size:"))
        self.bubble_size_slider = QSlider(Qt.Horizontal)
        self.bubble_size_slider.setMinimum(50)
        self.bubble_size_slider.setMaximum(200)
        self.bubble_size_slider.setSingleStep(5)
        self.bubble_size_slider.setPageStep(10)
        self.bubble_size_slider.setValue(100)
        self.bubble_size_slider.valueChanged.connect(self.on_bubble_size_changed)
        bubble_size_row.addWidget(self.bubble_size_slider)

        self.bubble_size_value = QLabel("100%")
        self.bubble_size_value.setMinimumWidth(48)
        bubble_size_row.addWidget(self.bubble_size_value)
        right_layout.addLayout(bubble_size_row)

        wrap_width_row = QHBoxLayout()
        wrap_width_row.addWidget(QLabel("Wrap Width:"))
        self.wrap_width_slider = QSlider(Qt.Horizontal)
        self.wrap_width_slider.setMinimum(50)
        self.wrap_width_slider.setMaximum(100)
        self.wrap_width_slider.setSingleStep(1)
        self.wrap_width_slider.setPageStep(5)
        self.wrap_width_slider.setValue(75)
        self.wrap_width_slider.valueChanged.connect(self.on_wrap_width_changed)
        wrap_width_row.addWidget(self.wrap_width_slider)

        self.wrap_width_value = QLabel("75%")
        self.wrap_width_value.setMinimumWidth(48)
        wrap_width_row.addWidget(self.wrap_width_value)
        right_layout.addLayout(wrap_width_row)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_text)
        self.clear_btn.setStyleSheet("font-size: 12px; padding: 8px;")
        right_layout.addWidget(self.clear_btn)

        right_layout.addStretch()

        layout.addLayout(left_layout, 2)
        layout.addLayout(right_layout, 1)
        central_widget.setLayout(layout)

    def load_config(self):
        """Load config values into the UI."""
        config = self.processor.config
        percent = int(float(config.get("bubble_scale", 1.0)) * 100)
        percent = max(50, min(200, percent))
        self.bubble_size_slider.setValue(percent)
        self.bubble_size_value.setText(f"{percent}%")

        wrap_percent = int(float(config.get("wrap_width_scale", 0.75)) * 100)
        wrap_percent = max(50, min(100, wrap_percent))
        self.wrap_width_slider.setValue(wrap_percent)
        self.wrap_width_value.setText(f"{wrap_percent}%")

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
            self.camera_combo.addItems(["0", "1", "2", "3"])

    def start_stream(self):
        """Start video streaming."""
        camera_id = int(self.camera_combo.currentText())
        vcam_id = int(self.vcam_combo.currentText())

        if self.processor.start_stream(camera_id, vcam_id):
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.camera_combo.setEnabled(False)
            self.vcam_combo.setEnabled(False)

    def stop_stream(self):
        """Stop video streaming."""
        self.processor.stop_stream()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.camera_combo.setEnabled(True)
        self.vcam_combo.setEnabled(True)
        self.video_label.setText("Video Preview (Stopped)")

    def send_text(self):
        """Send text as speech bubble."""
        text = self.text_input.text().strip()
        if text:
            self.processor.set_text(text)
            self.text_input.clear()

    def quick_phrase(self, phrase):
        """Use a quick access phrase."""
        self.text_input.setText(phrase)
        self.send_text()

    def clear_text(self):
        """Clear all active bubbles."""
        self.dragging_bubble = False
        self.text_input.clear()
        self.processor.clear_text()

    def on_bubble_size_changed(self, value):
        """Update speech bubble size scale from slider input."""
        self.processor.set_bubble_scale_percent(value)
        self.bubble_size_value.setText(f"{value}%")

    def on_wrap_width_changed(self, value):
        """Update wrap width percentage from slider input."""
        self.processor.set_wrap_width_percent(value)
        self.wrap_width_value.setText(f"{value}%")

    def update_status(self, status):
        """Update status label."""
        self.status_label.setText(f"Status: {status}")

    def update_preview(self, frame):
        """Update video preview while preserving aspect ratio."""
        label_width = max(1, self.video_label.width())
        label_height = max(1, self.video_label.height())
        frame_height, frame_width = frame.shape[:2]

        scale = min(label_width / frame_width, label_height / frame_height)
        draw_width = max(1, int(frame_width * scale))
        draw_height = max(1, int(frame_height * scale))

        self.preview_draw_width = draw_width
        self.preview_draw_height = draw_height
        self.preview_draw_x = (label_width - draw_width) // 2
        self.preview_draw_y = (label_height - draw_height) // 2

        display_frame = cv2.resize(frame, (draw_width, draw_height))
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb_frame.shape
        bytes_per_line = 3 * w

        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap)

    def map_preview_to_output(self, preview_x, preview_y, clamp=False):
        """Map preview-label coordinates to output-frame coordinates."""
        x = preview_x
        y = preview_y

        if clamp:
            x = max(self.preview_draw_x, min(x, self.preview_draw_x + self.preview_draw_width - 1))
            y = max(self.preview_draw_y, min(y, self.preview_draw_y + self.preview_draw_height - 1))
        else:
            in_x = self.preview_draw_x <= x < (self.preview_draw_x + self.preview_draw_width)
            in_y = self.preview_draw_y <= y < (self.preview_draw_y + self.preview_draw_height)
            if not (in_x and in_y):
                return None

        rel_x = (x - self.preview_draw_x) / max(1, self.preview_draw_width)
        rel_y = (y - self.preview_draw_y) / max(1, self.preview_draw_height)

        output_x = int(rel_x * self.processor.output_width)
        output_y = int(rel_y * self.processor.output_height)
        output_x = max(0, min(output_x, self.processor.output_width - 1))
        output_y = max(0, min(output_y, self.processor.output_height - 1))
        return output_x, output_y

    def on_preview_mouse_pressed(self, preview_x, preview_y):
        """Start drag only when user clicks inside a visible bubble."""
        if not self.processor.active_messages:
            return

        mapped = self.map_preview_to_output(preview_x, preview_y, clamp=False)
        if not mapped or not self.processor.last_bubble_boxes:
            return

        output_x, output_y = mapped
        for bubble_x, bubble_y, bubble_width, bubble_height in self.processor.last_bubble_boxes:
            in_bubble_x = bubble_x <= output_x <= (bubble_x + bubble_width)
            in_bubble_y = bubble_y <= output_y <= (bubble_y + bubble_height)
            if in_bubble_x and in_bubble_y:
                self.dragging_bubble = True
                self.drag_offset_x = output_x - bubble_x
                self.drag_offset_y = output_y - bubble_y
                break

    def on_preview_mouse_moved(self, preview_x, preview_y):
        """Move bubble chain while dragging and sync to output coordinates."""
        if not self.dragging_bubble:
            return

        mapped = self.map_preview_to_output(preview_x, preview_y, clamp=True)
        if not mapped:
            return

        output_x, output_y = mapped
        new_bubble_x = output_x - self.drag_offset_x
        new_bubble_y = output_y - self.drag_offset_y
        self.processor.set_bubble_position(new_bubble_x, new_bubble_y)

    def on_preview_mouse_released(self, _preview_x, _preview_y):
        """Stop drag operation."""
        if self.dragging_bubble:
            # Persist the final dragged position once the drag operation completes.
            self.processor.set_bubble_position(
                self.processor.config.get("bubble_x", 50),
                self.processor.config.get("bubble_y", 50),
                persist=True,
            )
        self.dragging_bubble = False

    def setup_timer(self):
        """Setup timer for frame processing."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.processor.process_frame)
        self.timer.start(33)  # ~30 FPS

    def closeEvent(self, event):
        """Clean up on close."""
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
