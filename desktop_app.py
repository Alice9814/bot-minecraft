import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QStandardPaths, QObject, Signal, Slot, QUrl
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor, QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QSystemTrayIcon, QMenu
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent


def prepare_user_data_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        candidates = [base / "MinecraftAIBot", Path.home() / "MinecraftAIBot"]
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        preferred = Path(xdg) / "MinecraftAIBot" if xdg and Path(xdg).is_absolute() else Path.home() / ".config" / "MinecraftAIBot"
        candidates = [preferred, Path.home() / ".local" / "share" / "MinecraftAIBot"]
        try:
            qt_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
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
        except OSError as exc:
            last_error = exc

    import tempfile
    suffix = str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
    fallback = Path(tempfile.gettempdir()) / f"MinecraftAIBot-{suffix}"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    except OSError as exc:
        raise RuntimeError(f"Não foi possível criar uma pasta gravável. Último erro: {last_error or exc}") from exc


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
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P")
    painter.end()
    return QIcon(pixmap)


def default_config():
    return {
        "minecraft": {"host": "127.0.0.1", "port": 25565, "username": "ProtoBot", "auth": "offline", "version": "26.2"},
        "ai": {"model": "gemma-3-1b-it-Q4_K_M.gguf", "temperature": 0.7},
        "behavior": {"respond_only_when_mentioned": False, "mention_name": "ProtoBot", "max_chat_length": 180}
    }


class UiBridge(QObject):
    logLine = Signal(str)
    stateChanged = Signal(bool, bool)
    configLoaded = Signal(str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @Slot()
    def requestInitialData(self):
        self.configLoaded.emit(json.dumps(self.window.config, ensure_ascii=False))
        self.stateChanged.emit(self.window.is_bot_running(), self.window.paused)
        self.window.read_log_file()

    @Slot(str)
    def saveConfig(self, raw_config):
        try:
            incoming = json.loads(raw_config)
            config = default_config()
            for section in config:
                if isinstance(incoming.get(section), dict):
                    config[section].update(incoming[section])
            config["minecraft"]["port"] = max(1, min(65535, int(config["minecraft"]["port"])))
            config["ai"]["temperature"] = max(0.0, min(2.0, float(config["ai"]["temperature"])))
            if not config["minecraft"]["host"].strip():
                raise ValueError("Informe o endereço do servidor.")
            if not config["minecraft"]["username"].strip():
                raise ValueError("Informe o nome do bot.")
            self.window.config = config
            CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.logLine.emit("Configurações salvas.")
            self.configLoaded.emit(json.dumps(config, ensure_ascii=False))
        except Exception as exc:
            self.logLine.emit("[ERRO] Não foi possível salvar as configurações: " + str(exc))

    @Slot()
    def startBot(self):
        self.window.start_bot()

    @Slot()
    def togglePause(self):
        self.window.toggle_pause()

    @Slot()
    def stopBot(self):
        self.window.stop_bot()

    @Slot()
    def clearLogs(self):
        self.window.clear_logs()

    @Slot()
    def forceQuit(self):
        self.window.force_quit_app()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        global USER_DATA_DIR, CONFIG_PATH, CONTROL_PATH, LOG_PATH
        USER_DATA_DIR = prepare_user_data_dir()
        CONFIG_PATH = USER_DATA_DIR / "config.json"
        CONTROL_PATH = USER_DATA_DIR / "bot-control.json"
        LOG_PATH = USER_DATA_DIR / "bot.log"

        self.setWindowTitle("ProtoBot — Minecraft AI")
        self.setWindowIcon(make_icon())
        self.resize(1120, 780)
        self.setMinimumSize(650, 520)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self.process_finished)
        self.paused = False
        self.log_offset = 0
        self.config = self.load_config()

        self.web_view = QWebEngineView(self)
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = UiBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.setCentralWidget(self.web_view)

        index_file = APP_DIR / "interface" / "index.html"
        if not index_file.exists():
            QMessageBox.critical(self, "Interface não encontrada", f"Não encontrei os arquivos HTML:\n{index_file}")
        else:
            self.web_view.load(QUrl.fromLocalFile(str(index_file.resolve())))

        self.setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_log_file)
        self.timer.timeout.connect(self.refresh_state)
        self.timer.start(500)

    def load_config(self):
        config = default_config()
        try:
            if CONFIG_PATH.exists():
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                for section in config:
                    if isinstance(loaded.get(section), dict):
                        config[section].update(loaded[section])
                if "ai" not in loaded and "ollama" in loaded:
                    config["ai"]["temperature"] = loaded["ollama"].get("temperature", 0.7)
        except Exception as exc:
            QMessageBox.warning(self, "Configuração", f"Não foi possível ler config.json:\n{exc}")
        return config

    def setup_tray(self):
        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip("ProtoBot — parado")
        menu = QMenu()
        show_action = QAction("Abrir janela", self)
        show_action.triggered.connect(self.show_window)
        self.tray_pause = QAction("Pausar bot", self)
        self.tray_pause.triggered.connect(self.toggle_pause)
        stop_action = QAction("Encerrar bot", self)
        stop_action.triggered.connect(self.stop_bot)
        quit_action = QAction("Sair do aplicativo", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(self.tray_pause)
        menu.addAction(stop_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            self.bridge.logLine.emit("AVISO: este ambiente não disponibilizou uma bandeja do sistema.")

    def is_bot_running(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    def start_bot(self):
        if self.is_bot_running():
            return
        self.save_control(False)
        try:
            LOG_PATH.write_text("", encoding="utf-8")
            self.log_offset = 0
        except OSError as exc:
            self.bridge.logLine.emit("[ERRO] Não foi possível limpar o log: " + str(exc))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("MINEBOT_CONFIG", str(CONFIG_PATH))
        env.insert("MINEBOT_CONTROL", str(CONTROL_PATH))
        env.insert("MINEBOT_LOG", str(LOG_PATH))
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("MINEBOT_MODEL_DIR", str(USER_DATA_DIR / "models"))
        self.process.setProcessEnvironment(env)
        if FROZEN:
            self.process.start(sys.executable, ["--worker"])
        else:
            worker_python = sys.executable
            if sys.platform == "win32":
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                if pythonw.exists():
                    worker_python = str(pythonw)
            self.process.start(worker_python, [str(APP_DIR / "bot.py")])
        self.bridge.logLine.emit("Solicitando inicialização do bot...")
        self.refresh_state()

    def save_control(self, paused):
        CONTROL_PATH.write_text(json.dumps({"paused": bool(paused)}), encoding="utf-8")

    def toggle_pause(self):
        if not self.is_bot_running():
            return
        self.paused = not self.paused
        try:
            self.save_control(self.paused)
        except OSError as exc:
            self.bridge.logLine.emit("[ERRO] Não foi possível alterar o estado: " + str(exc))
            return
        self.bridge.logLine.emit("Bot pausado." if self.paused else "Bot retomado.")
        self.refresh_state()

    def stop_bot(self):
        if self.is_bot_running():
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
            self.bridge.logLine.emit("Bot encerrado.")
        self.paused = False
        self.refresh_state()

    def clear_logs(self):
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text("", encoding="utf-8")
            self.log_offset = 0
            self.bridge.logLine.emit("Logs limpos.")
        except OSError as exc:
            self.bridge.logLine.emit("[ERRO] Não foi possível limpar os logs: " + str(exc))

    def read_log_file(self):
        if not LOG_PATH.exists():
            return
        try:
            with LOG_PATH.open("r", encoding="utf-8", errors="replace") as source:
                source.seek(self.log_offset)
                new_text = source.read()
                self.log_offset = source.tell()
            if new_text:
                for line in new_text.splitlines():
                    self.bridge.logLine.emit(line)
        except OSError:
            pass

    def process_finished(self, code, status):
        self.paused = False
        self.bridge.logLine.emit(f"Processo do bot finalizado (código {code}).")
        self.refresh_state()

    def refresh_state(self):
        running = self.is_bot_running()
        self.tray_pause.setText("Retomar bot" if self.paused else "Pausar bot")
        self.tray.setToolTip("ProtoBot — " + ("pausado" if self.paused else "em execução" if running else "parado"))
        self.bridge.stateChanged.emit(running, self.paused)

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.stop_bot()
        self.tray.hide()
        QApplication.quit()

    def force_quit_app(self):
        if self.is_bot_running():
            self.process.kill()
            self.process.waitForFinished(2000)
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "ProtoBot",
                "O aplicativo continua ativo na bandeja do sistema.",
                QSystemTrayIcon.MessageIcon.Information,
                2500
            )
        else:
            event.ignore()
            QMessageBox.information(
                self,
                "Bandeja indisponível",
                "Este ambiente não disponibilizou uma bandeja do sistema. Use o botão 'Forçar fechar' no aplicativo."
            )


def run_worker():
    import bot
    bot.main()


if __name__ == "__main__":
    if "--worker" in sys.argv:
        run_worker()
    else:
        app = QApplication(sys.argv)
        app.setOrganizationName("ProtoBot")
        app.setApplicationName("ProtoBot")
        app.setQuitOnLastWindowClosed(False)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
