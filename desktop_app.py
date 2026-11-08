import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer, QStandardPaths
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QDoubleSpinBox, QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget, QMenu
)

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent


def prepare_user_data_dir():
    # QStandardPaths precisa ser consultado depois de criar QApplication.
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        candidates = [base / "MinecraftAIBot", Path.home() / "MinecraftAIBot"]
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg and Path(xdg).is_absolute():
            preferred = Path(xdg) / "MinecraftAIBot"
        else:
            preferred = Path.home() / ".config" / "MinecraftAIBot"
        candidates = [preferred, Path.home() / ".local" / "share" / "MinecraftAIBot"]
        try:
            qt_path = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            )
            if qt_path:
                candidates.insert(0, Path(qt_path))
        except Exception:
            pass

    last_error = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except (OSError, PermissionError) as exc:
            last_error = exc

    # Último recurso: diretório temporário específico do usuário, nunca a raiz.
    import tempfile
    suffix = str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    fallback = Path(tempfile.gettempdir()) / f"MinecraftAIBot-{suffix}"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    except OSError as exc:
        raise RuntimeError(
            f"Não foi possível criar uma pasta gravável para as configurações. "
            f"Último erro: {last_error or exc}"
        ) from exc


USER_DATA_DIR = None
CONFIG_PATH = None
CONTROL_PATH = None
LOG_PATH = None


def make_icon(color="#7cdb8a"):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#20252b"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(3, 3, 58, 58)
    painter.setBrush(QColor(color))
    painter.drawEllipse(17, 17, 30, 30)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        global USER_DATA_DIR, CONFIG_PATH, CONTROL_PATH, LOG_PATH
        USER_DATA_DIR = prepare_user_data_dir()
        CONFIG_PATH = USER_DATA_DIR / "config.json"
        CONTROL_PATH = USER_DATA_DIR / "bot-control.json"
        LOG_PATH = USER_DATA_DIR / "bot.log"
        self.setWindowTitle("Minecraft AI Bot")
        self.setWindowIcon(make_icon())
        self.resize(680, 650)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        # No Windows console window for the background worker (including
        # development runs where sys.executable is python.exe).
        if sys.platform == "win32":
            def hide_worker_console(arguments):
                arguments.flags |= 0x08000000  # CREATE_NO_WINDOW
            self.process.setCreateProcessArgumentsModifier(hide_worker_console)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)
        self.paused = False
        self.log_offset = 0
        self.config = self.load_config()
        self.build_ui()
        self.setup_tray()
        self.refresh_state()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_state)
        self.timer.timeout.connect(self.read_log_file)
        self.timer.start(1000)

    def load_config(self):
        defaults = {
            "minecraft": {"host": "127.0.0.1", "port": 25565, "username": "OllamaBot", "auth": "offline", "version": False},
            "ollama": {"url": "http://127.0.0.1:11434/api/chat", "model": "gemma3:270m", "timeout_seconds": 90, "temperature": 0.3},
            "behavior": {"respond_only_when_mentioned": False, "mention_name": "OllamaBot", "max_chat_length": 180}
        }
        try:
            if CONFIG_PATH.exists():
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                for section in defaults:
                    defaults[section].update(loaded.get(section, {}))
        except Exception as exc:
            QMessageBox.warning(self, "Configuração", f"Não foi possível ler config.json:\n{exc}")
        return defaults

    def build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("Minecraft AI Bot")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        subtitle = QLabel("Configure o servidor e a IA. Fechar esta janela mantém o bot na bandeja.")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        mc_box = QGroupBox("Servidor Minecraft")
        mc = QFormLayout(mc_box)
        self.host = QLineEdit(str(self.config["minecraft"].get("host", "127.0.0.1")))
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(int(self.config["minecraft"].get("port", 25565)))
        self.username = QLineEdit(str(self.config["minecraft"].get("username", "OllamaBot")))
        self.auth = QComboBox(); self.auth.addItems(["offline", "microsoft"])
        self.auth.setCurrentText(str(self.config["minecraft"].get("auth", "offline")))
        mc.addRow("Endereço:", self.host); mc.addRow("Porta:", self.port)
        mc.addRow("Nome do bot:", self.username); mc.addRow("Autenticação:", self.auth)
        layout.addWidget(mc_box)

        ai_box = QGroupBox("Inteligência artificial — Ollama")
        ai = QFormLayout(ai_box)
        self.model = QLineEdit(str(self.config["ollama"].get("model", "gemma3:270m")))
        self.ollama_url = QLineEdit(str(self.config["ollama"].get("url", "http://127.0.0.1:11434/api/chat")))
        self.temperature = QDoubleSpinBox(); self.temperature.setRange(0, 2); self.temperature.setSingleStep(0.1)
        self.temperature.setValue(float(self.config["ollama"].get("temperature", 0.3)))
        ai.addRow("Modelo:", self.model); ai.addRow("API:", self.ollama_url); ai.addRow("Temperatura:", self.temperature)
        layout.addWidget(ai_box)

        self.mention = QCheckBox("Responder somente quando mencionarem o nome do bot")
        self.mention.setChecked(bool(self.config["behavior"].get("respond_only_when_mentioned", False)))
        layout.addWidget(self.mention)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Iniciar bot")
        self.pause_button = QPushButton("Pausar")
        self.stop_button = QPushButton("Encerrar")
        self.save_button = QPushButton("Salvar configurações")
        self.pause_button.setEnabled(False); self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_bot)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.stop_button.clicked.connect(self.stop_bot)
        self.save_button.clicked.connect(self.save_config)
        for button in (self.start_button, self.pause_button, self.stop_button, self.save_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.status = QLabel("Status: parado")
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Console"))
        self.console = QTextEdit(); self.console.setReadOnly(True)
        layout.addWidget(self.console, 1)
        self.setCentralWidget(root)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip("Minecraft AI Bot — parado")
        menu = QMenu()
        show_action = QAction("Abrir janela", self); show_action.triggered.connect(self.show_window)
        self.tray_pause = QAction("Pausar bot", self); self.tray_pause.triggered.connect(self.toggle_pause)
        stop_action = QAction("Encerrar bot", self); stop_action.triggered.connect(self.stop_bot)
        quit_action = QAction("Sair do aplicativo", self); quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action); menu.addAction(self.tray_pause)
        menu.addAction(stop_action); menu.addSeparator(); menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            self.console.append("AVISO: este ambiente não disponibilizou uma bandeja do sistema.")

    def save_config(self):
        self.config["minecraft"].update({"host": self.host.text().strip(), "port": self.port.value(),
            "username": self.username.text().strip(), "auth": self.auth.currentText()})
        self.config["ollama"].update({"model": self.model.text().strip(), "url": self.ollama_url.text().strip(),
            "temperature": self.temperature.value()})
        self.config["behavior"]["respond_only_when_mentioned"] = self.mention.isChecked()
        try:
            CONFIG_PATH.write_text(json.dumps(self.config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.console.append("Configurações salvas.")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar config.json:\n{exc}")

    def start_bot(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self.save_config()
        CONTROL_PATH.write_text(json.dumps({"paused": False}), encoding="utf-8")
        LOG_PATH.write_text("", encoding="utf-8")
        self.log_offset = 0
        env = self.process.processEnvironment()
        env.insert("MINEBOT_CONFIG", str(CONFIG_PATH))
        env.insert("MINEBOT_CONTROL", str(CONTROL_PATH))
        env.insert("MINEBOT_LOG", str(LOG_PATH))
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("NODE_PATH", str(APP_DIR / "node_modules"))
        env.insert("PATH", str(APP_DIR) + os.pathsep + env.value("PATH"))
        self.process.setProcessEnvironment(env)
        if FROZEN:
            self.process.start(sys.executable, ["--worker"])
        else:
            self.process.start(sys.executable, [str(APP_DIR / "bot.py")])
        self.console.append("Solicitando inicialização do bot...")
        self.refresh_state()

    def toggle_pause(self):
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self.paused = not self.paused
        CONTROL_PATH.write_text(json.dumps({"paused": self.paused}), encoding="utf-8")
        self.pause_button.setText("Retomar" if self.paused else "Pausar")
        self.tray_pause.setText("Retomar bot" if self.paused else "Pausar bot")
        self.status.setText("Status: pausado" if self.paused else "Status: em execução")
        self.console.append("Bot pausado." if self.paused else "Bot retomado.")

    def stop_bot(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
            self.console.append("Bot encerrado.")

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.console.append(data.rstrip())

    def read_log_file(self):
        if not FROZEN or not LOG_PATH.exists():
            return
        try:
            with LOG_PATH.open("r", encoding="utf-8", errors="replace") as source:
                source.seek(self.log_offset)
                new_text = source.read()
                self.log_offset = source.tell()
            if new_text:
                self.console.append(new_text.rstrip())
        except OSError:
            pass

    def process_finished(self, code, status):
        self.paused = False
        self.refresh_state()
        self.console.append(f"Processo do bot finalizado (código {code}).")

    def refresh_state(self):
        running = self.process.state() != QProcess.ProcessState.NotRunning
        self.start_button.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.stop_button.setEnabled(running)
        if not running:
            self.status.setText("Status: parado")
            self.tray.setToolTip("Minecraft AI Bot — parado")
        else:
            state = "pausado" if self.paused else "em execução"
            self.status.setText(f"Status: {state}")
            self.tray.setToolTip(f"Minecraft AI Bot — {state}")

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self):
        self.show(); self.raise_(); self.activateWindow()

    def quit_app(self):
        self.stop_bot()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage("Minecraft AI Bot", "O aplicativo continua ativo na bandeja do sistema.",
                QSystemTrayIcon.MessageIcon.Information, 2500)
        else:
            event.ignore()
            QMessageBox.information(self, "Bandeja indisponível",
                "Este ambiente não disponibilizou uma bandeja do sistema. Deixe a janela aberta para continuar usando o aplicativo.")


def run_worker():
    import bot
    bot.main()


if __name__ == "__main__":
    if "--worker" in sys.argv:
        run_worker()
    else:
        app = QApplication(sys.argv)
        app.setOrganizationName("MinecraftAIBot")
        app.setApplicationName("MinecraftAIBot")
        app.setQuitOnLastWindowClosed(False)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
