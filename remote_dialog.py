#!/usr/bin/env python3
"""
Remote Dialog for Notchgent.
Floating modal providing dynamic QR code pairing, connection management,
and seamless switching between Public 5G (Cloudflare) and Home Wi-Fi (Direct LAN).
"""

from io import BytesIO
import qrcode
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QApplication
)

from icons import get_svg_icon, get_svg_pixmap


def generate_qr_pixmap(data: str, size: int = 210) -> QPixmap:
    """Generate high-contrast QR code as QPixmap."""
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
        pm = QPixmap(size, size)
        pm.fill(QColor("#1e222d"))
        return pm


class RemoteDialog(QWidget):
    """Floating modal window showing the pairing QR code and connection status."""

    closed = pyqtSignal()
    rotate_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_pos = QPoint()
        self.current_url = ""
        self.current_local_url = ""
        self.active_mode = "public"  # "public" or "lan"
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("RemoteDialog")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Outer card frame
        self.frame = QFrame(self)
        self.frame.setObjectName("DialogCard")
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(20, 16, 20, 18)
        frame_layout.setSpacing(10)
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
        sub = QLabel("Scan with your phone to review & approve commands on the go.")
        sub.setObjectName("DialogSubtitle")
        sub.setWordWrap(True)
        frame_layout.addWidget(sub)

        # Network Mode Switcher Tabs
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(0, 2, 0, 4)
        mode_layout.setSpacing(8)

        self.mode_public_btn = QPushButton(" Public (5G / Remote)")
        self.mode_public_btn.setIcon(get_svg_icon("globe", "#ffffff", 12))
        self.mode_public_btn.setFixedHeight(28)
        self.mode_public_btn.clicked.connect(lambda: self.set_mode("public"))

        self.mode_lan_btn = QPushButton(" Home Wi-Fi (LAN)")
        self.mode_lan_btn.setIcon(get_svg_icon("wifi", "#9ca3af", 12))
        self.mode_lan_btn.setFixedHeight(28)
        self.mode_lan_btn.clicked.connect(lambda: self.set_mode("lan"))

        mode_layout.addWidget(self.mode_public_btn, 1)
        mode_layout.addWidget(self.mode_lan_btn, 1)
        frame_layout.addLayout(mode_layout)

        # QR Frame Container
        qr_container = QFrame()
        qr_container.setObjectName("QRContainer")
        qr_layout = QVBoxLayout(qr_container)
        qr_layout.setContentsMargins(8, 8, 8, 8)
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.qr_label = QLabel()
        self.qr_label.setFixedSize(210, 210)
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

        self.copy_btn = QPushButton(" Copy Link")
        self.copy_btn.setObjectName("ActionBtn")
        self.copy_btn.setIcon(get_svg_icon("copy", "#fb923c", 13))
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.clicked.connect(self.copy_link)

        self.rotate_btn = QPushButton(" Rotate & Refresh")
        self.rotate_btn.setObjectName("ActionBtnSecondary")
        self.rotate_btn.setIcon(get_svg_icon("rotate", "#d1d5db", 13))
        self.rotate_btn.setFixedHeight(32)
        self.rotate_btn.clicked.connect(self._on_rotate_clicked)

        btn_layout.addWidget(self.copy_btn, 1)
        btn_layout.addWidget(self.rotate_btn, 1)
        frame_layout.addLayout(btn_layout)

        # Helper note
        self.hint_label = QLabel("Tip: Home Wi-Fi never expires. Use Public for 5G cellular.")
        self.hint_label.setObjectName("HintLabel")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.hint_label)

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
                line-height: 1.3;
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
            #HintLabel {
                color: #6b7280;
                font-size: 10px;
            }
        """)

        self._update_mode_buttons()

    def _update_mode_buttons(self):
        if self.active_mode == "public":
            self.mode_public_btn.setStyleSheet("""
                background-color: rgba(249, 115, 22, 0.25);
                border: 1px solid rgba(249, 115, 22, 0.7);
                color: #fb923c;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.mode_lan_btn.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #9ca3af;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 500;
            """)
        else:
            self.mode_lan_btn.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.22);
                border: 1px solid rgba(16, 185, 129, 0.6);
                color: #34d399;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.mode_public_btn.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #9ca3af;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 500;
            """)

    def set_mode(self, mode: str):
        """Switch between 'public' (Cloudflare 5G) and 'lan' (Local Wi-Fi)."""
        self.active_mode = mode
        self._update_mode_buttons()
        self._render_active_qr()

    def set_tunnel_url(self, public_url: str, local_url: str):
        """Update displayed URLs and re-render."""
        self.current_url = public_url
        self.current_local_url = local_url
        self._render_active_qr()

    def _render_active_qr(self):
        """Render QR code for currently selected mode."""
        if self.active_mode == "public":
            if self.current_url:
                pix = generate_qr_pixmap(self.current_url, size=210)
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
                self.qr_label.setText("Connecting to Cloudflare...")
                self.status_pill.setText("Reconnecting tunnel...")
                self.status_pill.setStyleSheet("""
                    background-color: rgba(245, 158, 11, 0.14);
                    color: #fbbf24;
                    border: 1px solid rgba(245, 158, 11, 0.3);
                    border-radius: 10px;
                """)
        else:
            if self.current_local_url:
                pix = generate_qr_pixmap(self.current_local_url, size=210)
                self.qr_label.setPixmap(pix)
                self.status_pill.setText("Home Wi-Fi • Direct LAN (Zero Lag)")
                self.status_pill.setStyleSheet("""
                    background-color: rgba(16, 185, 129, 0.14);
                    color: #34d399;
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 10px;
                """)
            else:
                self.qr_label.clear()
                self.qr_label.setText("Detecting Local Wi-Fi...")

    def update_connection_count(self, count: int):
        if count > 0:
            self.status_pill.setText(f"{count} Phone{'s' if count > 1 else ''} Connected")
        elif self.active_mode == "public" and self.current_url:
            self.status_pill.setText("Ready for Phone Pairing")

    def copy_link(self):
        url = self.current_url if self.active_mode == "public" else self.current_local_url
        if not url:
            url = self.current_local_url or self.current_url
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
        self.rotate_btn.setText(" Refreshed!")
        self.rotate_btn.setIcon(get_svg_icon("check", "#34d399", 13))
        if self.active_mode == "public":
            self.status_pill.setText("Reconnecting tunnel...")
            self.status_pill.setStyleSheet("""
                background-color: rgba(245, 158, 11, 0.14);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 10px;
            """)
            self.qr_label.clear()
            self.qr_label.setText("Refreshing tunnel...")
        QTimer.singleShot(1500, self._restore_rotate_btn)

    def _restore_rotate_btn(self):
        self.rotate_btn.setText(" Rotate & Refresh")
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
