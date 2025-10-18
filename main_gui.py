# main_gui.py

import sys
import pygame
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QFrame, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt, QThread
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPalette

from motor_controller import UnderwaterVehicleController
from camera_module import VideoThread
from config import MOTOR_PINS, RTSP_URL, VIDEO_FOLDER


def normalize_trigger(val):
    return (val + 1) / 2 if val < 0 else val


class ModernSubmarineGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌊 UV Control System")
        self.resize(1200, 800)

        # Инициализация геймпада
        pygame.init()
        pygame.joystick.init()
        self.js = None
        if pygame.joystick.get_count() > 0:
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            self.num_axes = self.js.get_numaxes()

        # Контроллер моторов
        try:
            self.controller = UnderwaterVehicleController()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Моторы: {e}")
            sys.exit(1)

        # Камера
        self.video_thread = VideoThread(RTSP_URL, VIDEO_FOLDER)
        self.video_thread.change_pixmap_signal.connect(self.update_frame)
        self.video_thread.error_signal.connect(self.handle_camera_error)
        self.video_thread.status_signal.connect(self.update_camera_status)
        self.video_thread.recording_status_signal.connect(self.update_recording_status)

        self.camera_thread = QThread()
        self.video_thread.moveToThread(self.camera_thread)
        self.camera_thread.started.connect(self.video_thread.run)
        self.camera_thread.start()

        # Состояния
        self.recording = False
        self.enter_pressed = False

        # Создание интерфейса
        self.init_ui()

        # Таймеры
        self.control_timer = QTimer()
        self.control_timer.timeout.connect(self.update_controls)
        self.control_timer.start(50)

    def init_ui(self):
        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # === ВИДЕО ===
        self.video_label = QLabel("Подключение к камере...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                color: #bbbbbb;
                font-size: 18px;
                border-radius: 8px;
            }
        """)
        self.video_label.setMinimumSize(800, 500)
        main_layout.addWidget(self.video_label)

        # === НИЖНЯЯ ПАНЕЛЬ ===
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("background-color: #252526; border-radius: 10px; padding: 10px;")
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setSpacing(20)

        # --- Левая панель: телеметрия ---
        telemetry_frame = QFrame()
        telemetry_frame.setStyleSheet("background-color: #2d2d30; border-radius: 8px; padding: 12px;")
        telemetry_layout = QVBoxLayout(telemetry_frame)
        telemetry_layout.setSpacing(10)

        title_telemetry = QLabel("📊 Телеметрия")
        title_telemetry.setStyleSheet("color: #4ec9b0; font-size: 16px; font-weight: bold;")
        telemetry_layout.addWidget(title_telemetry)

        self.motor_labels = {}
        for name in MOTOR_PINS:
            lbl = QLabel(f"{name}: --- µs")
            lbl.setStyleSheet("color: #d4d4d4; font-family: 'Courier New', monospace; font-size: 16px;")
            telemetry_layout.addWidget(lbl)
            self.motor_labels[name] = lbl

        self.depth_label = QLabel("Глубина: — м")
        self.accel_label = QLabel("Акселерометр: X:— Y:— Z:—")
        for lbl in [self.depth_label, self.accel_label]:
            lbl.setStyleSheet("color: #9cdcfe; font-size: 16px;")
            telemetry_layout.addWidget(lbl)

        telemetry_layout.addStretch()
        bottom_layout.addWidget(telemetry_frame)

        # --- Правая панель: управление ---
        control_frame = QFrame()
        control_frame.setStyleSheet("background-color: #2d2d30; border-radius: 8px; padding: 12px;")
        control_layout = QVBoxLayout(control_frame)
        control_layout.setSpacing(12)

        title_control = QLabel("🎛️ Управление")
        title_control.setStyleSheet("color: #ce9178; font-size: 16px; font-weight: bold;")
        control_layout.addWidget(title_control)

        # Статусы
        self.gamepad_status = QLabel("Геймпад: не подключён")
        self.camera_status = QLabel("Камера: ожидание...")
        self.recording_label = QLabel("⏺️ Запись: выключена")

        for lbl, color in [
            (self.gamepad_status, "#d7ba7d"),
            (self.camera_status, "#b5cea8"),
            (self.recording_label, "#f44747")
        ]:
            lbl.setStyleSheet(f"color: {color}; font-size: 14px;")
            control_layout.addWidget(lbl)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.stop_btn = QPushButton("ОСТАНОВИТЬ ВСЁ")
        self.record_btn = QPushButton("ЗАПИСЬ")

        for btn in [self.stop_btn, self.record_btn]:
            btn.setFixedHeight(40)
            btn.setFont(QFont("Segoe UI", 10, QFont.Bold))

        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #c50f1f;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #a50d19;
            }
        """)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)

        self.stop_btn.clicked.connect(self.stop_all)
        self.record_btn.clicked.connect(self.toggle_recording)

        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.record_btn)
        control_layout.addLayout(btn_layout)
        control_layout.addStretch()

        bottom_layout.addWidget(control_frame)
        main_layout.addWidget(bottom_frame)

        # Обновление телеметрии (глубина, акселерометр)
        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.update_telemetry)
        self.telemetry_timer.start(1000)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            if not self.enter_pressed and self.video_thread._connected:
                self.enter_pressed = True
                self.toggle_recording()
                QTimer.singleShot(1000, lambda: setattr(self, 'enter_pressed', False))
        elif event.key() == Qt.Key_Escape:
            self.close()

    def toggle_recording(self):
        if self.recording:
            self.video_thread.stop_recording()
        else:
            self.video_thread.start_recording()
        self.recording = not self.recording

    def update_recording_status(self, is_recording):
        self.recording = is_recording
        color = "#4ec9b0" if is_recording else "#f44747"
        text = "⏺️ Запись: включена" if is_recording else "⏺️ Запись: выключена"
        self.recording_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.recording_label.setText(text)

    def update_camera_status(self, connected):
        color = "#b5cea8" if connected else "#f44747"
        text = "Камера: подключена" if connected else "Камера: отключена"
        self.camera_status.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.camera_status.setText(text)

    def update_frame(self, frame):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap.scaled(
            self.video_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

    def update_controls(self):
        if not self.js or not self.controller:
            self.gamepad_status.setText("Геймпад: не подключён")
            self.gamepad_status.setStyleSheet("color: #f44747; font-size: 14px;")
            return

        self.gamepad_status.setText(f"Геймпад: {self.js.get_name()}")
        self.gamepad_status.setStyleSheet("color: #d7ba7d; font-size: 14px;")

        pygame.event.pump()
        left_x = self.js.get_axis(0)
        left_y = self.js.get_axis(1)
        right_x = self.js.get_axis(2) if self.num_axes > 2 else 0.0
        lt_raw = self.js.get_axis(4) if self.num_axes > 4 else -1.0
        rt_raw = self.js.get_axis(5) if self.num_axes > 5 else -1.0

        lt = normalize_trigger(lt_raw)
        rt = normalize_trigger(rt_raw)

        self.controller.update_from_gamepad(left_x, left_y, lt, rt, -right_x)

        for name, pwm in self.controller.current_pwm.items():
            self.motor_labels[name].setText(f"{name}: {int(pwm)} µs")

    def update_telemetry(self):
        import numpy as np
        self.depth_label.setText(f"Глубина: {np.random.uniform(0, 10):.2f} м")
        self.accel_label.setText(
            f"Акселерометр: X:{np.random.uniform(-1,1):.2f} "
            f"Y:{np.random.uniform(-1,1):.2f} "
            f"Z:{np.random.uniform(0.9,1.1):.2f}"
        )

    def stop_all(self):
        if self.controller:
            self.controller.stop_all()
            # Обновим метки моторов на STOP
            for name in self.motor_labels:
                self.motor_labels[name].setText(f"{name}: {self.controller.STOP} µs")

    def handle_camera_error(self, msg):
        QMessageBox.warning(self, "Камера", msg)

    def closeEvent(self, event):
        self.control_timer.stop()
        self.telemetry_timer.stop()
        if self.controller:
            self.controller.cleanup()
        if self.video_thread:
            self.video_thread.stop()
        if self.camera_thread:
            self.camera_thread.quit()
            self.camera_thread.wait()
        pygame.quit()
        event.accept()


# === Установка тёмной темы для всего приложения ===
def apply_dark_theme(app):
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")


def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = ModernSubmarineGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()