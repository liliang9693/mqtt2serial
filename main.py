import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel, QComboBox, QPushButton, QMessageBox, QGroupBox, QHBoxLayout, QPlainTextEdit, QStylePainter, QStyleOptionComboBox, QStyle
from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QIcon
import os
from pathlib import Path
import siot
import serial
from serial.tools import list_ports

class PortCombo(QComboBox):
    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        opt.initFrom(self)
        opt.currentText = self.fontMetrics().elidedText(self.currentText(), Qt.ElideMiddle, self.width() - 24)
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)


class MainWindow(QMainWindow):
    message_received = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.serial = None
        self.forwarding_active = False
        self.setWindowTitle("MQTT2Serial v1.0.1")
        self.setFixedSize(340, 560)
        try:
            self.setWindowIcon(QIcon(self._resource_path("assets/icon.ico")))
        except Exception:
            pass
        self._build_ui()

    def _build_ui(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout()
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)
        cw.setLayout(root)

        mqtt_group = QGroupBox("MQTT服务器信息")
        mqtt_form = QFormLayout()
        mqtt_form.setLabelAlignment(Qt.AlignLeft)
        mqtt_form.setFormAlignment(Qt.AlignTop)
        mqtt_form.setVerticalSpacing(10)
        mqtt_group.setLayout(mqtt_form)

        self.server_input = QLineEdit("10.1.2.3")
        self.port_input = QLineEdit("1883")
        self.user_input = QLineEdit("siot")
        self.password_input = QLineEdit("dfrobot")
        self.password_input.setEchoMode(QLineEdit.Normal)
        self.topic_input = QLineEdit("siot/serial")

        mqtt_form.addRow("地址", self.server_input)
        mqtt_form.addRow("端口", self.port_input)
        mqtt_form.addRow("用户名", self.user_input)
        mqtt_form.addRow("密码", self.password_input)
        mqtt_form.addRow("Topic", self.topic_input)

        serial_group = QGroupBox("目标回环串口")
        serial_form = QFormLayout()
        serial_form.setLabelAlignment(Qt.AlignLeft)
        serial_form.setFormAlignment(Qt.AlignTop)
        serial_form.setVerticalSpacing(10)
        serial_group.setLayout(serial_form)

        self.port_combo = PortCombo()
        self.baud_input = QLineEdit("115200")
        serial_form.addRow("串口列表", self.port_combo)
        serial_form.addRow("波特率", self.baud_input)

        self.toggle_button = QPushButton("开始转发")
        self.toggle_button.setObjectName("toggle_button")
        self.toggle_button.clicked.connect(self._on_toggle)

        root.addWidget(mqtt_group)
        root.addWidget(serial_group)

        recv_group = QGroupBox("当前接收到的数据")
        recv_layout = QVBoxLayout()
        recv_group.setLayout(recv_layout)
        self.recv_text = QPlainTextEdit()
        self.recv_text.setReadOnly(True)
        self.recv_text.setPlaceholderText("暂无数据")
        self.recv_text.setFixedHeight(72)
        self.recv_text.setMaximumBlockCount(1000)
        recv_layout.addWidget(self.recv_text)

        root.addWidget(recv_group)

        doc_link = QLabel('<a href="https://gitee.com/liliang9693/mqtt2serial">使用说明</a>')
        doc_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        doc_link.setOpenExternalLinks(True)
        doc_link.setAlignment(Qt.AlignRight)
        root.addWidget(doc_link)
        root.addSpacing(10)
        root.addWidget(self.toggle_button)

        self.setStyleSheet(
            """
            QMainWindow { background: #ffffff; }
            QGroupBox { border: 1px solid #e5e5e5; border-radius: 8px; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLabel { font-size: 13px; }
            QLineEdit, QComboBox { height: 28px; font-size: 13px; }
            #toggle_button { height: 34px; font-size: 14px; background: #2a83f7; color: #ffffff; border: none; border-radius: 6px; }
            #toggle_button:disabled { background: #9ec3fb; }
            """
        )

        self._refresh_ports()
        try:
            self.port_combo.view().setTextElideMode(Qt.ElideMiddle)
        except Exception:
            pass
        self.message_received.connect(self._append_received_line)

    def _refresh_ports(self):
        self.port_combo.clear()
        ports = list_ports.comports()
        for p in ports:
            desc = getattr(p, "description", "") or ""
            label = f"{desc} ({p.device})" if desc else p.device
            self.port_combo.addItem(label, p.device)
        if self.port_combo.count() == 0:
            self.port_combo.addItem("未检测到串口", None)

    def _on_toggle(self):
        if self.forwarding_active:
            self._stop_forwarding()
        else:
            self._start_forwarding()

    def _start_forwarding(self):
        server = self.server_input.text().strip()
        port_text = self.port_input.text().strip()
        user = self.user_input.text().strip()
        password = self.password_input.text().strip()
        topic = self.topic_input.text().strip()
        com_text = self.port_combo.currentText().strip()
        com = self.port_combo.currentData()
        baud_text = self.baud_input.text().strip()

        if not server or not port_text or not topic or not baud_text or not com:
            QMessageBox.critical(self, "错误", "请完整填写信息并选择有效串口")
            return

        try:
            port = int(port_text)
        except Exception:
            QMessageBox.critical(self, "错误", "端口必须为数字")
            return

        try:
            baudrate = int(baud_text)
            if baudrate <= 0:
                raise ValueError
        except Exception:
            QMessageBox.critical(self, "错误", "波特率必须为正整数")
            return

        self.toggle_button.setText("连接中...")
        self.toggle_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            self.recv_text.clear()
        except Exception:
            pass

        try:
            self.serial = serial.Serial(com, baudrate=baudrate, timeout=1)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.toggle_button.setText("开始转发")
            self.toggle_button.setEnabled(True)
            QMessageBox.critical(self, "错误", f"打开串口失败: {e}")
            return

        try:
            siot.init(client_id="", server=server, port=port, user=user, password=password)
            siot.connect()
            siot.loop()
            siot.set_callback(self._on_message_callback)
            siot.getsubscribe(topic=topic)
        except Exception as e:
            try:
                if self.serial:
                    self.serial.close()
                    self.serial = None
            finally:
                QApplication.restoreOverrideCursor()
                self.toggle_button.setText("开始转发")
                self.toggle_button.setEnabled(True)
                QMessageBox.critical(self, "错误", f"连接MQTT失败: {e}")
                return

        self.forwarding_active = True
        self.toggle_button.setText("停止转发")
        self.toggle_button.setEnabled(True)
        QApplication.restoreOverrideCursor()
        self._set_inputs_enabled(False)

    def _stop_forwarding(self):
        try:
            try:
                siot.stop()
            except Exception:
                pass
            try:
                siot.set_callback(None)
            except Exception:
                pass
            if self.serial:
                try:
                    self.serial.close()
                finally:
                    self.serial = None
        finally:
            self.forwarding_active = False
            self.toggle_button.setText("开始转发")
            self._set_inputs_enabled(True)

    def _set_inputs_enabled(self, enabled: bool):
        for w in [self.server_input, self.port_input, self.user_input, self.password_input, self.topic_input, self.port_combo, self.baud_input]:
            w.setEnabled(enabled)

    def _on_message_callback(self, client, userdata, msg):
        if not self.forwarding_active:
            return
        data = msg.payload
        if not isinstance(data, (bytes, bytearray)):
            try:
                data = str(data).encode("utf-8")
            except Exception:
                return
        if self.serial and self.serial.is_open:
            try:
                self.serial.write(data)
            except Exception:
                pass
        try:
            from datetime import datetime
            ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = str(data)
            line = f"{ts} {text}"
            self.message_received.emit(line)
        except Exception:
            pass

    def _append_received_line(self, line: str):
        try:
            self.recv_text.appendPlainText(line)
        except Exception:
            pass

    def closeEvent(self, event):
        if self.forwarding_active:
            self._stop_forwarding()
        event.accept()

    def _resource_path(self, relative: str) -> str:
        base = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parent))
        return os.path.join(base, relative)

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    try:
        app.setWindowIcon(QIcon(w._resource_path("assets/icon.ico")))
    except Exception:
        pass
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
