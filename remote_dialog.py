#!/usr/bin/env python3
"""
Remote Dialog / Modal for Notchgent.
Displays the live QR code, connection status, token rotation, and copy buttons.
"""

from io import BytesIO
import qrcode
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QImage, QPixmap, QClipboard
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication
)


def generate_qr_pixmap(data: str, size: int = 220) -> QPixmap:
    """Generate a crisp dark-mode styled QPixmap QR code."""
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#ffffff", back_color="#0e1017")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        qimg = QImage.fromData(buf.getvalue())
        pixmap = QPixmap.fromImage(qimg)
        return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    except Exception:
        # Fallback empty pixmap
        pm = QPixmap(size, size)
        pm.fill(QColor("#1e222d"))
        return pm


from icons import get_svg_icon, get_svg_pixmap


class RemoteDialog(QWidget):
    """Floating modal window showing the pairing QR code and connection status."""

    closed = pyqtSignal()
    rotate_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_pos = QPoint()
        self.current_url = ""
        self.current_local_url = ""
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("RemoteDialog")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Outer card frame
        self.frame = QFrame(self)
        self.frame.setObjectName("DialogCard")
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(20, 16, 20, 18)
        frame_layout.setSpacing(12)
        frame_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header row
        hdr_layout = QHBoxLayout()
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(8)

        title_icon = QLabel()
        title_icon.setPixmap(get_svg_pixmap("phone", "#f97316", 16))

        title = QLabel("Mobile Remote")
        title.setObjectName("DialogTitle")
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        title.setFont(font)

        close_btn = QPushButton()
        close_btn.setObjectName("DialogCloseBtn")
        close_btn.setIcon(get_svg_icon("x", "#9ca3af", 12))
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(self.close)

        hdr_layout.addWidget(title_icon)
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        hdr_layout.addWidget(close_btn)
        frame_layout.addLayout(hdr_layout)

        # Subtitle
        sub = QLabel("Scan with your phone camera to review and approve actions from anywhere.")
        sub.setObjectName("DialogSubtitle")
        sub.setWordWrap(True)
        frame_layout.addWidget(sub)

        # QR Frame Container
        qr_container = QFrame()
        qr_container.setObjectName("QRContainer")
        qr_layout = QVBoxLayout(qr_container)
        qr_layout.setContentsMargins(8, 8, 8, 8)
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.qr_label = QLabel()
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setText("Starting secure tunnel...")
        self.qr_label.setObjectName("QRLabel")
        qr_layout.addWidget(self.qr_label)
        frame_layout.addWidget(qr_container)

        # Status badge
        self.status_pill = QLabel("Generating tunnel...")
        self.status_pill.setObjectName("StatusPill")
        self.status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.status_pill)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.copy_btn = QPushButton("Copy Link")
        self.copy_btn.setObjectName("ActionBtn")
        self.copy_btn.setIcon(get_svg_icon("copy", "#fb923c", 13))
        self.copy_btn.setFixedHeight(30)
        self.copy_btn.clicked.connect(self.copy_link)

        self.rotate_btn = QPushButton("Rotate Key")
        self.rotate_btn.setObjectName("ActionBtnSecondary")
        self.rotate_btn.setIcon(get_svg_icon("rotate", "#d1d5db", 13))
        self.rotate_btn.setFixedHeight(30)
        self.rotate_btn.clicked.connect(self._on_rotate_clicked)

        btn_layout.addWidget(self.copy_btn, 1)
        btn_layout.addWidget(self.rotate_btn, 1)
        frame_layout.addLayout(btn_layout)

        # Local LAN row
        lan_layout = QHBoxLayout()
        lan_layout.setContentsMargins(0, 0, 0, 0)
        lan_layout.setSpacing(5)
        lan_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lan_icon = QLabel()
        self.lan_icon.setPixmap(get_svg_pixmap("wifi", "#6b7280", 12))

        self.lan_label = QLabel("Home Wi-Fi: Ready")
        self.lan_label.setObjectName("LanLabel")

        lan_layout.addWidget(self.lan_icon)
        lan_layout.addWidget(self.lan_label)
        frame_layout.addLayout(lan_layout)

        layout.addWidget(self.frame)

        # Stylesheet
        self.setStyleSheet("""
            QWidget#RemoteDialog {
                background: transparent;
            }
            #DialogCard {
                background-color: rgba(14, 16, 22, 0.96);
                border: 1.5px solid rgba(249, 115, 22, 0.90);
                border-radius: 20px;
            }
            #DialogTitle {
                color: #ffffff;
            }
            #DialogSubtitle {
                color: #9ca3af;
                font-size: 11px;
                line-height: 1.4;
            }
            #DialogCloseBtn {
                background: transparent;
                color: #9ca3af;
                border: none;
                font-size: 12px;
                font-weight: bold;
                border-radius: 11px;
            }
            #DialogCloseBtn:hover {
                background-color: rgba(239, 68, 68, 0.3);
                color: #ef4444;
            }
            #QRContainer {
                background-color: #0e1017;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 14px;
            }
            #QRLabel {
                color: #9ca3af;
                font-size: 12px;
            }
            #StatusPill {
                background-color: rgba(16, 185, 129, 0.14);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 10px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            #ActionBtn {
                background: rgba(249, 115, 22, 0.2);
                border: 1px solid rgba(249, 115, 22, 0.5);
                color: #fb923c;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            }
            #ActionBtn:hover {
                background: rgba(249, 115, 22, 0.35);
                color: #ffffff;
            }
            #ActionBtnSecondary {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #d1d5db;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            }
            #ActionBtnSecondary:hover {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }
            #LanLabel {
                color: #6b7280;
                font-size: 10px;
            }
        """)

    def set_tunnel_url(self, public_url: str, local_url: str):
        """Update displayed QR code and links."""
        self.current_url = public_url
        self.current_local_url = local_url

        if public_url:
            pix = generate_qr_pixmap(public_url, size=210)
            self.qr_label.setPixmap(pix)
            self.status_pill.setText("Secure Tunnel Active")
            self.status_pill.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.14);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 10px;
            """)
        else:
            self.qr_label.clear()
            self.qr_label.setText("Generating tunnel...")
            self.status_pill.setText("Connecting...")

        if local_url:
            self.lan_label.setText(f"Home Wi-Fi: {local_url.split('/#')[0]}")

    def update_connection_count(self, count: int):
        if count > 0:
            self.status_pill.setText(f"{count} Phone{'s' if count > 1 else ''} Connected")
        elif self.current_url:
            self.status_pill.setText("Ready for Phone Pairing")

    def copy_link(self):
        url = self.current_url or self.current_local_url
        if url:
            cb = QApplication.clipboard()
            cb.setText(url)
            self.copy_btn.setText(" Copied!")
            self.copy_btn.setIcon(get_svg_icon("check", "#34d399", 13))
            QTimer.singleShot(1500, self._restore_copy_btn)

    def _restore_copy_btn(self):
        self.copy_btn.setText(" Copy Link")
        self.copy_btn.setIcon(get_svg_icon("copy", "#fb923c", 13))

    def _on_rotate_clicked(self):
        self.rotate_requested.emit()
        self.rotate_btn.setText(" Rotated")
        self.rotate_btn.setIcon(get_svg_icon("check", "#34d399", 13))
        QTimer.singleShot(1500, self._restore_rotate_btn)

    def _restore_rotate_btn(self):
        self.rotate_btn.setText(" Rotate Key")
        self.rotate_btn.setIcon(get_svg_icon("rotate", "#d1d5db", 13))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_pos = QPoint()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
