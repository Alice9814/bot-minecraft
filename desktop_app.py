import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QStandardPaths, QUrl, QThread
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QColor, QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QSystemTrayIcon, QMenu, QWidget
from PySide6.QtWebView import QWebView, QtWebView

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


def default_config():
    return {
        "minecraft": {"host": "127.0.0.1", "port": 25565, "username": "ProtoBot", "auth": "offline", "version": "26.2"},
        "ai": {"model": "gemma-3-1b-it-Q4_K_M.gguf", "temperature": 0.7},
        "behavior": {"respond_only_when_mentioned": False, "mention_name": "ProtoBot", "max_chat_length": 180}
    }


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


class BotWorkerThread(QThread):
    def __init__(self, environment, parent=None):
        super().__init__(parent)
        self.environment = environment

    def run(self):
        os.environ.update(self.environment)
        try:
            run_worker()
        except BaseException as exc:
            try:
                with LOG_PATH.open("a", encoding="utf-8") as output:
                    output.write(f"[ANDROID] Falha no worker: {type(exc).__name__}: {exc}\n")
            except OSError:
                pass


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
        self.bot_thread = None
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self.process_finished)
        self.paused = False
        self.log_offset = 0
        self._polling_js = False
        self._last_state = None
        self.config = self.load_config()

        self.web_view = QWebView()
        container = QWidget.createWindowContainer(self.web_view, self)
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCentralWidget(container)

        index_file = APP_DIR / "interface" / "index.html"
        if not index_file.exists():
            QMessageBox.critical(self, "Interface não encontrada", f"Não encontrei os arquivos HTML:\n{index_file}")
        else:
            self.web_view.setUrl(QUrl.fromLocalFile(str(index_file.resolve())))

        self.setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_log_file)
        self.timer.timeout.connect(self.refresh_state)
        self.timer.timeout.connect(self.poll_ui_commands)
        self.timer.start(150)

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
            self.send_ui_event({"type":"log","text":"AVISO: este ambiente não disponibilizou uma bandeja do sistema."})

    def is_bot_running(self):
        if sys.platform == "android":
            return self.bot_thread is not None and self.bot_thread.isRunning()
        return self.process.state() != QProcess.ProcessState.NotRunning

    def send_ui_event(self, event):
        try:
            payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            script = "if(window.__protoReceive){window.__protoReceive(" + payload + ");}"
            self.web_view.runJavaScript(script, lambda _result: None)
        except Exception:
            pass

    def poll_ui_commands(self):
        if self._polling_js:
            return
        self._polling_js = True
        script = "window.__protoDrainCommands ? window.__protoDrainCommands() : []"
        self.web_view.runJavaScript(script, self.process_ui_commands)

    def process_ui_commands(self, commands):
        self._polling_js = False
        if isinstance(commands, str):
            try:
                commands = json.loads(commands)
            except json.JSONDecodeError:
                return
        if not isinstance(commands, (list, tuple)):
            return
        for command in commands[:30]:
            if not isinstance(command, dict):
                continue
            method = str(command.get("method", ""))
            args = command.get("args", [])
            if not isinstance(args, (list, tuple)):
                args = []
            try:
                self.dispatch_ui_command(method, list(args))
            except Exception as exc:
                self.send_ui_event({"type":"log","text":f"[UI] Erro em {method}: {type(exc).__name__}: {exc}"})

    def dispatch_ui_command(self, method, args):
        if method == "requestInitialData":
            self.send_ui_event({"type":"config","value":self.config})
            self.refresh_state(force=True)
            self.read_log_file()
        elif method == "saveConfig":
            self.save_config(args[0] if args else "")
        elif method == "startBot":
            self.start_bot()
        elif method == "togglePause":
            self.toggle_pause()
        elif method == "stopBot":
            self.stop_bot()
        elif method == "clearLogs":
            self.clear_logs()
        elif method == "forceQuit":
            self.force_quit_app()

    def save_config(self, raw_config):
        try:
            incoming = json.loads(raw_config)
            config = default_config()
            for section in config:
                if isinstance(incoming.get(section), dict):
                    config[section].update(incoming[section])
            config["minecraft"]["host"] = str(config["minecraft"]["host"]).strip()
            config["minecraft"]["username"] = str(config["minecraft"]["username"]).strip()
            config["minecraft"]["port"] = max(1, min(65535, int(config["minecraft"]["port"])))
            config["ai"]["temperature"] = max(0.0, min(2.0, float(config["ai"]["temperature"])))
            if not config["minecraft"]["host"]:
                raise ValueError("Informe o endereço do servidor.")
            if not config["minecraft"]["username"]:
                raise ValueError("Informe o nome do bot.")
            self.config = config
            CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.send_ui_event({"type":"log","text":"Configurações salvas."})
            self.send_ui_event({"type":"config","value":self.config})
        except Exception as exc:
            self.send_ui_event({"type":"log","text":"[ERRO] Não foi possível salvar as configurações: " + str(exc)})

    def start_bot(self):
        if self.is_bot_running():
            return
        self.save_control(False)
        try:
            LOG_PATH.write_text("", encoding="utf-8")
            self.log_offset = 0
        except OSError as exc:
            self.send_ui_event({"type":"log","text":"[ERRO] Não foi possível limpar o log: " + str(exc)})
        environment = {
            "MINEBOT_CONFIG": str(CONFIG_PATH),
            "MINEBOT_CONTROL": str(CONTROL_PATH),
            "MINEBOT_LOG": str(LOG_PATH),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "MINEBOT_MODEL_DIR": str(USER_DATA_DIR / "models")
        }
        if sys.platform == "android":
            self.bot_thread = BotWorkerThread(environment, self)
            self.bot_thread.finished.connect(self.android_worker_finished)
            self.bot_thread.start()
        else:
            env = QProcessEnvironment.systemEnvironment()
            for key, value in environment.items():
                env.insert(key, value)
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
        self.send_ui_event({"type":"log","text":"Solicitando inicialização do bot..."})
        self.refresh_state(force=True)

    def save_control(self, paused, stop=False):
        CONTROL_PATH.write_text(json.dumps({"paused": bool(paused), "stop": bool(stop)}), encoding="utf-8")

    def toggle_pause(self):
        if not self.is_bot_running():
            return
        self.paused = not self.paused
        try:
            self.save_control(self.paused)
        except OSError as exc:
            self.send_ui_event({"type":"log","text":"[ERRO] Não foi possível alterar o estado: " + str(exc)})
            return
        self.send_ui_event({"type":"log","text":"Bot pausado." if self.paused else "Bot retomado."})
        self.refresh_state(force=True)

    def stop_bot(self):
        if sys.platform == "android":
            if self.is_bot_running():
                self.save_control(False, stop=True)
                if not self.bot_thread.wait(8000):
                    self.send_ui_event({"type":"log","text":"O bot ainda está encerrando; aguarde alguns segundos."})
                else:
                    self.send_ui_event({"type":"log","text":"Bot encerrado."})
        elif self.is_bot_running():
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
            self.send_ui_event({"type":"log","text":"Bot encerrado."})
        self.paused = False
        self.refresh_state(force=True)

    def android_worker_finished(self):
        self.paused = False
        self.send_ui_event({"type":"log","text":"Processo do bot finalizado."})
        self.refresh_state(force=True)

    def clear_logs(self):
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text("", encoding="utf-8")
            self.log_offset = 0
            self.send_ui_event({"type":"clearLogs"})
        except OSError as exc:
            self.send_ui_event({"type":"log","text":"[ERRO] Não foi possível limpar os logs: " + str(exc)})

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
                    self.send_ui_event({"type":"log","text":line})
        except OSError:
            pass

    def process_finished(self, code, status):
        self.paused = False
        self.send_ui_event({"type":"log","text":f"Processo do bot finalizado (código {code})."})
        self.refresh_state(force=True)

    def refresh_state(self, force=False):
        running = self.is_bot_running()
        self.tray_pause.setText("Retomar bot" if self.paused else "Pausar bot")
        self.tray.setToolTip("ProtoBot — " + ("pausado" if self.paused else "em execução" if running else "parado"))
        state = (running, self.paused)
        if force or state != self._last_state:
            self._last_state = state
            self.send_ui_event({"type":"state","running":running,"paused":self.paused})

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
        if sys.platform == "android":
            if self.is_bot_running():
                self.save_control(False, stop=True)
                if not self.bot_thread.wait(15000):
                    self.send_ui_event({"type":"log","text":"O bot ainda está encerrando. Aguarde antes de fechar o aplicativo."})
                    return
        elif self.is_bot_running():
            self.process.kill()
            self.process.waitForFinished(2000)
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if sys.platform == "android":
            if self.is_bot_running():
                self.save_control(False, stop=True)
                if not self.bot_thread.wait(15000):
                    event.ignore()
                    self.send_ui_event({"type":"log","text":"O bot ainda está encerrando. Aguarde e tente voltar."})
                    return
            event.accept()
            return
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


def run_gui():
    QtWebView.initialize()
    app = QApplication(sys.argv)
    app.setOrganizationName("ProtoBot")
    app.setApplicationName("ProtoBot")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    if "--worker" in sys.argv:
        run_worker()
    else:
        run_gui()
