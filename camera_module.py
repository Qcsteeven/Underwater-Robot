# camera_module.py

import os
import datetime
import time
import cv2
from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np

# Папка для записи видео (можно сделать настраиваемой)
DEFAULT_VIDEO_FOLDER = r"C:\Users\ЦМИТ2024\Desktop\UUV\VIDEO_REC"

# Фиксированный размер вывода (None — использовать исходный размер)
OUTPUT_WIDTH, OUTPUT_HEIGHT = 640, 480


class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(object)  # numpy array (RGB)
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool)
    recording_status_signal = pyqtSignal(bool)

    def __init__(self, rtsp_url, video_folder=DEFAULT_VIDEO_FOLDER):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.video_folder = video_folder
        os.makedirs(self.video_folder, exist_ok=True)

        self._run_flag = True
        self._connected = False
        self._recording = False
        self.video_writer = None

        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 3  # секунды

    def connect_to_camera(self):
        """Попытка подключения к камере"""
        self.capture = cv2.VideoCapture(self.rtsp_url)
        if self.capture.isOpened():
            self._connected = True
            self.reconnect_attempts = 0
            self.status_signal.emit(True)
            print("✅ Успешное подключение к камере")
            return True
        return False

    def start_recording(self):
        if not self._recording and self._connected:
            timestamp = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
            output_file = os.path.join(self.video_folder, f"UUV_recording_{timestamp}.avi")

            # Используем исходное разрешение для записи
            frame_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.capture.get(cv2.CAP_PROP_FPS)) or 22

            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(output_file, fourcc, fps, (frame_width, frame_height))

            if self.video_writer.isOpened():
                self._recording = True
                self.recording_status_signal.emit(True)
                print(f"⏺️ Начата запись видео: {output_file}")
            else:
                print("❌ Ошибка создания файла записи")

    def stop_recording(self):
        if self._recording and self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            self._recording = False
            self.recording_status_signal.emit(False)
            print("⏹️ Запись видео остановлена")

    def run(self):
        while self._run_flag:
            if not self._connected:
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    print(f"🔄 Попытка подключения к камере ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                    if self.connect_to_camera():
                        continue
                    self.reconnect_attempts += 1
                    time.sleep(self.reconnect_delay)
                    continue
                else:
                    self.error_signal.emit("Не удалось подключиться к камере")
                    self.status_signal.emit(False)
                    time.sleep(5)
                    self.reconnect_attempts = 0
                    continue

            ret, frame = self.capture.read()
            if not ret:
                print("⚠️ Потеряно соединение с камерой")
                self._connected = False
                self.stop_recording()
                self.capture.release()
                self.status_signal.emit(False)
                continue

            try:
                # Запись кадра в оригинальном разрешении
                if self._recording and self.video_writer is not None:
                    self.video_writer.write(frame)

                # Конвертация BGR → RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Изменение размера для отображения, если задано
                if OUTPUT_WIDTH and OUTPUT_HEIGHT:
                    rgb_frame = cv2.resize(rgb_frame, (OUTPUT_WIDTH, OUTPUT_HEIGHT))

                self.change_pixmap_signal.emit(rgb_frame)

            except Exception as e:
                print(f"❌ Ошибка обработки кадра: {e}")
                self._connected = False
                self.status_signal.emit(False)
                continue

            time.sleep(0.03)  # ~30 FPS

        # Очистка при завершении
        if hasattr(self, 'capture'):
            self.capture.release()
        self.stop_recording()

    def stop(self):
        """Остановка потока"""
        self._run_flag = False
        self.wait()