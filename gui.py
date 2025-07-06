import sys
import os
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QLineEdit, QFormLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QDialog
)
from PySide6 import QtGui, QtCore
from PySide6.QtGui import QImage, QPixmap

from qrcode_utils import generate_qr
from database import init_db, get_db_path

import cv2
from pyzbar.pyzbar import decode

class QRScanDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📷 QR-Code scannen")
        self.resize(400, 300)

        self.label = QLabel("Starte Kamera…")
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.cap = cv2.VideoCapture(0)

        self.qr_data = None

        self.timer.start(30)

    def next_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        decoded_objs = decode(frame)
        for obj in decoded_objs:
            self.qr_data = obj.data.decode("utf-8")
            self.accept()
            return

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(qimg).scaled(
            self.label.width(), self.label.height(),
            QtCore.Qt.KeepAspectRatio
        ))

    def closeEvent(self, event):
        self.timer.stop()
        self.cap.release()
        super().closeEvent(event)

class HardwareApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hardware-Geräteverwaltung")
        self.resize(750, 600)

        self.qr_ids = []
        self.edit_mode = False

        self.init_ui()
        init_db()
        self.load_devices()

        self.device_table.itemSelectionChanged.connect(self.show_qr_preview)

    def init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.serial_input = QLineEdit()
        self.date_input = QLineEdit()
        self.location_input = QLineEdit()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Name oder Seriennummer suchen…")
        self.search_input.textChanged.connect(self.search_devices)

        form.addRow("Gerätename:", self.name_input)
        form.addRow("Seriennummer:", self.serial_input)
        form.addRow("Kaufdatum (YYYY-MM-DD):", self.date_input)
        form.addRow("Standort:", self.location_input)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Speichern")
        self.edit_btn = QPushButton("✏️ Bearbeiten")
        self.delete_btn = QPushButton("🗑️ Löschen")
        self.scan_btn = QPushButton("📷 QR-Scannen")

        self.save_btn.clicked.connect(self.save_device)
        self.edit_btn.clicked.connect(self.edit_device)
        self.delete_btn.clicked.connect(self.delete_device)
        self.scan_btn.clicked.connect(self.scan_qr)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.scan_btn)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["Name", "Seriennummer", "Datum", "Standort"])
        self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = self.device_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(QtCore.Qt.AlignCenter)

        layout.addLayout(form)
        layout.addLayout(btn_layout)
        layout.addWidget(self.search_input)
        layout.addWidget(QLabel("📋 Geräteübersicht:"))
        layout.addWidget(self.device_table)
        layout.addSpacing(5)
        layout.addWidget(QLabel("📷 QR-Code Vorschau:"))
        layout.addWidget(self.qr_label)

        self.setLayout(layout)

    def save_device(self):
        name = self.name_input.text().strip()
        serial = self.serial_input.text().strip()
        date = self.date_input.text().strip()
        location = self.location_input.text().strip()
        qr_id = f"{serial}-{name}"

        if not all([name, serial, date, location]):
            QMessageBox.warning(self, "Fehler", "Bitte alle Felder ausfüllen.")
            return

        db_file = get_db_path()
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        try:
            if self.edit_mode:
                selected_row = self.device_table.currentRow()
                old_serial = self.device_table.item(selected_row, 1).text()
                c.execute(
                    "UPDATE devices SET name=?, serial=?, purchase_date=?, location=?, qr_id=? WHERE serial=?",
                    (name, serial, date, location, qr_id, old_serial)
                )
                QMessageBox.information(self, "Erfolg", "Gerät erfolgreich bearbeitet.")
                self.edit_mode = False
            else:
                c.execute(
                    "INSERT INTO devices (name, serial, purchase_date, location, qr_id) VALUES (?, ?, ?, ?, ?)",
                    (name, serial, date, location, qr_id)
                )

                qr_dir = os.path.join(os.path.dirname(get_db_path()), "qrcodes")
                os.makedirs(qr_dir, exist_ok=True)

                generate_qr(qr_id)
                QMessageBox.information(self, "Erfolg", "Gerät gespeichert und QR-Code erstellt.")

            conn.commit()
            self.load_devices()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Fehler", "Seriennummer oder QR-ID bereits vorhanden.")
        finally:
            conn.close()

    def edit_device(self):
        row = self.device_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte eine Zeile auswählen.")
            return

        self.edit_mode = True
        self.name_input.setText(self.device_table.item(row, 0).text())
        self.serial_input.setText(self.device_table.item(row, 1).text())
        self.date_input.setText(self.device_table.item(row, 2).text())
        self.location_input.setText(self.device_table.item(row, 3).text())

    def delete_device(self):
        row = self.device_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte eine Zeile auswählen.")
            return

        serial = self.device_table.item(row, 1).text()
        db_file = get_db_path()
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("DELETE FROM devices WHERE serial = ?", (serial,))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Gelöscht", f"Gerät {serial} wurde gelöscht.")
        self.load_devices()

    def load_devices(self, filter_text=""):
        db_file = get_db_path()
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        if filter_text:
            query = """
            SELECT name, serial, purchase_date, location, qr_id
            FROM devices
            WHERE name LIKE ? OR serial LIKE ?
            """
            c.execute(query, (f"%{filter_text}%", f"%{filter_text}%"))
        else:
            c.execute("SELECT name, serial, purchase_date, location, qr_id FROM devices")

        rows = c.fetchall()
        conn.close()

        self.device_table.setRowCount(len(rows))
        self.qr_ids.clear()
        for ri, (name, serial, date, loc, qr_id) in enumerate(rows):
            self.device_table.setItem(ri, 0, QTableWidgetItem(name))
            self.device_table.setItem(ri, 1, QTableWidgetItem(serial))
            self.device_table.setItem(ri, 2, QTableWidgetItem(date))
            self.device_table.setItem(ri, 3, QTableWidgetItem(loc))
            self.qr_ids.append(qr_id)

        if rows:
            self.device_table.selectRow(0)
            self.show_qr_preview()
        else:
            self.qr_label.clear()

    def search_devices(self):
        text = self.search_input.text().strip()
        self.load_devices(filter_text=text)

    def show_qr_preview(self):
        idx = self.device_table.currentRow()
        if idx < 0 or idx >= len(self.qr_ids):
            self.qr_label.clear()
            return

        qr_id = self.qr_ids[idx]
        qr_path = os.path.join(os.path.dirname(get_db_path()), "qrcodes", f"{qr_id}.png")

        if os.path.exists(qr_path):
            pix = QtGui.QPixmap(qr_path)
            self.qr_label.setPixmap(
                pix.scaled(120, 120,
                           QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                           QtCore.Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.qr_label.clear()

    def scan_qr(self):
        dlg = QRScanDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.qr_data:
            self.handle_qr_result(dlg.qr_data)

    def handle_qr_result(self, qr_data):
        db_file = get_db_path()
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT name, serial, purchase_date, location FROM devices WHERE qr_id = ?", (qr_data,))
        row = c.fetchone()
        conn.close()

        if row:
            name, serial, date, location = row
            self.name_input.setText(name)
            self.serial_input.setText(serial)
            self.date_input.setText(date)
            self.location_input.setText(location)
            QMessageBox.information(self, "QR-Code erkannt", f"✅ Gerät gefunden:\n{name}, {serial}")
        else:
            QMessageBox.warning(self, "QR-Code", "Kein Gerät gefunden.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = HardwareApp()
    win.show()
    sys.exit(app.exec())
