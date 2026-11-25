"""Ícone na bandeja do Windows + painel de status (tkinter) para o servidor.

O servidor roda sem janela (pythonw). O painel só aparece quando o usuário
pede: duplo clique no ícone, menu "Abrir painel" ou abrindo o programa de
novo (a segunda instância só avisa a primeira e sai).
"""
import ctypes
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger("companion")

kernel32 = ctypes.windll.kernel32
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.OpenEventW.restype = wintypes.HANDLE
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.SetEvent.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

MUTEX_NAME = "Local\\CompanionPCServer"
SHOW_EVENT = "Local\\CompanionPCShowPanel"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002

COLORS = {"ok": (46, 204, 113), "wait": (241, 196, 15), "off": (127, 140, 141)}


# --------------------------------------------------------------------------
# Instância única
# --------------------------------------------------------------------------
_mutex = None


def acquire_single_instance(wait_s=0.0):
    """True se esta é a única instância. Com wait_s, espera a anterior sair (reinício)."""
    global _mutex
    deadline = time.monotonic() + wait_s
    while True:
        h = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if ctypes.GetLastError() != ERROR_ALREADY_EXISTS:
            _mutex = h
            return True
        kernel32.CloseHandle(h)
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.3)


def signal_running_instance():
    """Pede para a instância que já está rodando mostrar o painel."""
    h = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT)
    if h:
        kernel32.SetEvent(h)
        kernel32.CloseHandle(h)


# --------------------------------------------------------------------------
# Ícone
# --------------------------------------------------------------------------
def make_icon(color):
    from PIL import Image, ImageDraw
    s = 64
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, s - 3, s - 3), 14, fill=(30, 34, 42, 255))
    # controle estilizado
    d.rounded_rectangle((9, 20, 55, 46), 12, fill=color + (255,))
    d.rectangle((17, 31, 27, 35), fill=(30, 34, 42, 255))
    d.rectangle((20, 28, 24, 38), fill=(30, 34, 42, 255))
    d.ellipse((38, 26, 44, 32), fill=(30, 34, 42, 255))
    d.ellipse((44, 33, 50, 39), fill=(30, 34, 42, 255))
    return im


# --------------------------------------------------------------------------
# App da bandeja
# --------------------------------------------------------------------------
class TrayApp:
    def __init__(self, status_fn, log_path: Path, base: Path, version: str, stop_server, open_on_phone=None,
                 voice_set=None, updater=None):
        """status_fn() -> dict(state='ok'|'wait'|'off', text=str, game=str|None, phone=dict)."""
        self.status_fn = status_fn
        self.open_on_phone_fn = open_on_phone
        self.voice_set = voice_set
        self.updater = updater
        self.log_path = log_path
        self.base = base
        self.version = version
        self.stop_server = stop_server
        self.icon = None
        self.panel_q = queue.Queue()
        self.panel_open = False
        self._last_state = None
        self._last_update = None

    # -- ações --
    def open_panel(self, *_):
        if self.panel_open:
            self.panel_q.put("raise")
            return
        self.panel_open = True
        threading.Thread(target=self._panel_thread, daemon=True, name="panel").start()

    def open_folder(self, *_):
        os.startfile(self.base)

    def open_editor(self, *_):
        """Página de personalizar (tema, menu, cartões, botões) no navegador do PC."""
        links = (self.status_fn().get("phone") or {}).get("links") or {}
        url = links.get("cabo")  # http://localhost:<porta>/#t=TOKEN
        if url:
            os.startfile(url.replace("/#t=", "/editor#t=", 1))

    def update(self, *_):
        """Baixa e instala a versão nova (o instalador reinicia o servidor)."""
        def run():
            try:
                self.updater.install()
                if self.icon:
                    self.icon.notify("Instalando a atualização. O Companion PC reinicia sozinho em instantes.",
                                     "Companion PC")
            except Exception as e:  # noqa: BLE001
                if self.icon:
                    self.icon.notify(str(e)[:200], "Companion PC")
        threading.Thread(target=run, daemon=True, name="update").start()

    def check_update(self, *_):
        def run():
            st = self.updater.check()
            if self.icon:
                msg = (f"Versão {st['latest']} disponível — use \"Atualizar\" no menu." if st["latest"]
                       else st["err"] or f"Você já está na versão mais nova ({st['current']}).")
                self.icon.notify(msg[:200], "Companion PC")
        threading.Thread(target=run, daemon=True, name="update-check").start()

    def open_log(self, *_):
        os.startfile(self.log_path)

    def open_on_phone(self, *_):
        """Abre o app no celular ligado no cabo (adb). Retorna mensagem de erro ou None."""
        try:
            self.open_on_phone_fn()
            return None
        except Exception as e:  # noqa: BLE001
            log.warning("abrir no celular: %s", e)
            return str(e)

    def restart(self, *_):
        log.info("reiniciando pelo ícone da bandeja")
        script = str(self.base / "companion_server.py")
        subprocess.Popen([sys.executable, script, "--restart"], cwd=str(self.base),
                         creationflags=subprocess.CREATE_NO_WINDOW)
        self.quit(restarting=True)

    def quit(self, *_, restarting=False):
        if not restarting:
            log.info("encerrado pelo ícone da bandeja")
        try:
            self.stop_server()
        finally:
            if self.icon:
                self.icon.stop()
            logging.shutdown()
            os._exit(0)

    # -- threads --
    def _watch_show_event(self):
        h = kernel32.CreateEventW(None, False, False, SHOW_EVENT)
        while True:
            if kernel32.WaitForSingleObject(h, 0xFFFFFFFF) == 0:
                self.open_panel()

    def _watch_status(self):
        while True:
            try:
                st = self.status_fn()
                if self.icon:
                    key = (st["state"], st["text"])
                    if key != self._last_state:
                        self._last_state = key
                        self.icon.icon = make_icon(COLORS[st["state"]])
                        self.icon.title = f"Companion PC – {st['text']}"[:127]
                    upd = self.updater and self.updater.latest
                    if upd != self._last_update:  # o menu do Windows só reavalia "visible" assim
                        self._last_update = upd
                        self.icon.update_menu()
            except Exception:  # noqa: BLE001
                log.exception("tray status")
            time.sleep(1.5)

    def _panel_thread(self):
        try:
            Panel(self).run()
        except Exception:  # noqa: BLE001
            log.exception("painel")
        finally:
            self.panel_open = False

    def run(self):
        import pystray
        from pystray import Menu, MenuItem as Item

        st = self.status_fn()
        self.icon = pystray.Icon(
            "companion-pc", make_icon(COLORS[st["state"]]), "Companion PC",
            menu=Menu(
                Item(lambda _: f"Companion PC {self.version}", None, enabled=False),
                Item(lambda _: self.status_fn()["text"], None, enabled=False),
                Item(lambda _: f"Atualizar para a versão {(self.updater.latest or {}).get('version', '')}",
                     self.update, visible=lambda _: bool(self.updater and self.updater.latest)),
                Menu.SEPARATOR,
                Item("Abrir painel", self.open_panel, default=True),
                Item("Personalizar (tema e layout)", self.open_editor),
                Item("Abrir app no celular (cabo)", self.open_on_phone,
                     visible=lambda _: bool(self.open_on_phone_fn and self.status_fn().get("phone", {}).get("adb"))),
                Item("Ver log", self.open_log),
                Item("Abrir pasta (config.json)", self.open_folder),
                Menu.SEPARATOR,
                Item("Procurar atualização", self.check_update, visible=lambda _: bool(self.updater)),
                Item("Reiniciar servidor", self.restart),
                Item("Sair", self.quit),
            ),
        )
        threading.Thread(target=self._watch_show_event, daemon=True, name="show-event").start()
        threading.Thread(target=self._watch_status, daemon=True, name="tray-status").start()
        self.icon.run()


# --------------------------------------------------------------------------
# Painel
# --------------------------------------------------------------------------
class Panel:
    BG, CARD, TEXT, DIM = "#14171c", "#1f242c", "#e8ecf1", "#8a94a3"
    STATE_HEX = {"ok": "#2ecc71", "wait": "#f1c40f", "off": "#7f8c8d"}

    def __init__(self, app: TrayApp):
        self.app = app

    def run(self):
        import tkinter as tk
        from tkinter import font as tkfont

        root = self.root = tk.Tk()
        root.title("Companion PC")
        root.configure(bg=self.BG)
        root.geometry("600x720")
        root.minsize(460, 340)
        try:
            from PIL import ImageTk
            self._ico = ImageTk.PhotoImage(make_icon(COLORS["ok"]), master=root)
            root.iconphoto(True, self._ico)
        except Exception:  # noqa: BLE001
            pass

        base = tkfont.nametofont("TkDefaultFont").actual("family")
        f_title = (base, 15, "bold")
        f = (base, 10)
        f_b = (base, 10, "bold")

        head = tk.Frame(root, bg=self.BG)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text="Companion PC", font=f_title, fg=self.TEXT, bg=self.BG).pack(side="left")
        tk.Label(head, text=f"v{self.app.version}", font=f, fg=self.DIM, bg=self.BG).pack(side="left", padx=8, pady=(4, 0))

        card = tk.Frame(root, bg=self.CARD)
        card.pack(fill="x", padx=16)
        row = tk.Frame(card, bg=self.CARD)
        row.pack(fill="x", padx=12, pady=(10, 2))
        self.dot = tk.Canvas(row, width=12, height=12, bg=self.CARD, highlightthickness=0)
        self.dot.pack(side="left", pady=2)
        self.dot_id = self.dot.create_oval(1, 1, 11, 11, fill=self.STATE_HEX["off"], outline="")
        self.status = tk.Label(row, font=f_b, fg=self.TEXT, bg=self.CARD, anchor="w")
        self.status.pack(side="left", padx=8)
        self.game = tk.Label(card, font=f, fg=self.DIM, bg=self.CARD, anchor="w")
        self.game.pack(fill="x", padx=32, pady=(0, 10))

        # Comandos de voz ("PC, próxima música")
        self.voice_title = tk.Label(root, text="Comandos de voz", font=f_b, fg=self.DIM, bg=self.BG, anchor="w")
        self.voice_card = vc = tk.Frame(root, bg=self.CARD)
        vrow = tk.Frame(vc, bg=self.CARD)
        vrow.pack(fill="x", padx=12, pady=(10, 2))
        self.vdot = tk.Canvas(vrow, width=12, height=12, bg=self.CARD, highlightthickness=0)
        self.vdot.pack(side="left", pady=2)
        self.vdot_id = self.vdot.create_oval(1, 1, 11, 11, fill=self.STATE_HEX["off"], outline="")
        self.voice_status = tk.Label(vrow, font=f_b, fg=self.TEXT, bg=self.CARD, anchor="w")
        self.voice_status.pack(side="left", padx=8)
        self.voice_last = tk.Label(vc, font=f, fg=self.DIM, bg=self.CARD, anchor="w", justify="left", wraplength=520)
        self.voice_last.pack(fill="x", padx=32)
        vb = tk.Frame(vc, bg=self.CARD)
        vb.pack(fill="x", padx=32, pady=(6, 10))

        def vbutton(cmd):
            b = tk.Button(vb, font=f, fg=self.TEXT, bg="#2b323c", activebackground="#36404c", activeforeground=self.TEXT,
                          relief="flat", borderwidth=0, padx=12, pady=4, cursor="hand2", command=cmd)
            b.pack(side="left", padx=(0, 8))
            return b
        self.voice_on_btn = vbutton(lambda: self._voice({"on": "toggle"}))
        self.voice_ov_btn = vbutton(lambda: self._voice({"overlay": not self._vstate.get("overlay")}))
        self._vstate = {}

        # Celular: QR com o link (HTTPS do Tailscale, ou Wi-Fi) + estado do cabo
        tk.Label(root, text="Celular (Android)", font=f_b, fg=self.DIM, bg=self.BG, anchor="w").pack(fill="x", padx=16, pady=(12, 4))
        pc = tk.Frame(root, bg=self.CARD)
        pc.pack(fill="x", padx=16)
        self.qr = tk.Label(pc, bg=self.CARD)
        self.qr.pack(side="left", padx=10, pady=10)
        info = tk.Frame(pc, bg=self.CARD)
        info.pack(side="left", fill="both", expand=True, padx=(4, 12), pady=10)
        self.phone_wifi = tk.Label(info, font=f, fg=self.TEXT, bg=self.CARD, anchor="w", justify="left", wraplength=380)
        self.phone_wifi.pack(fill="x")
        self.phone_https = tk.Label(info, font=f, fg=self.DIM, bg=self.CARD, anchor="w", justify="left", wraplength=380)
        self.phone_https.pack(fill="x", pady=(8, 0))
        self.phone_cable = tk.Label(info, font=f, fg=self.DIM, bg=self.CARD, anchor="w", justify="left", wraplength=380)
        self.phone_cable.pack(fill="x", pady=(8, 0))
        self.phone_btn = tk.Button(info, text="Abrir app no celular (cabo)", font=f, fg=self.TEXT, bg="#2b323c",
                                   activebackground="#36404c", activeforeground=self.TEXT, relief="flat",
                                   borderwidth=0, padx=12, pady=5, cursor="hand2", command=self._open_phone)
        self.phone_msg = tk.Label(info, font=f, fg=self.DIM, bg=self.CARD, anchor="w")
        self._qr_url = None

        tk.Label(root, text="Log", font=f_b, fg=self.DIM, bg=self.BG, anchor="w").pack(fill="x", padx=16, pady=(12, 4))
        self.log = tk.Text(root, height=10, bg=self.CARD, fg=self.TEXT, font=("Consolas", 9), relief="flat",
                           borderwidth=0, highlightthickness=0, wrap="word", padx=8, pady=6)
        self.log.pack(fill="both", expand=True, padx=16)
        self.log.configure(state="disabled")

        btns = tk.Frame(root, bg=self.BG)
        btns.pack(fill="x", padx=16, pady=12)

        def button(text, cmd, side="left"):
            b = tk.Button(btns, text=text, command=cmd, font=f, fg=self.TEXT, bg=self.CARD,
                          activebackground="#2b323c", activeforeground=self.TEXT, relief="flat",
                          borderwidth=0, padx=12, pady=5, cursor="hand2")
            b.pack(side=side, padx=(0, 8) if side == "left" else (8, 0))

        button("Personalizar", self.app.open_editor)
        button("Abrir pasta", self.app.open_folder)
        button("Ver log completo", self.app.open_log)
        button("Fechar", root.destroy, "right")
        button("Sair do servidor", self.app.quit, "right")
        button("Reiniciar", self.app.restart, "right")

        root.protocol("WM_DELETE_WINDOW", root.destroy)
        self._log_mtime = None
        self.refresh()
        self.bring_to_front()
        root.mainloop()

    def _voice(self, p):
        if self.app.voice_set:
            threading.Thread(target=self.app.voice_set, args=(p,), daemon=True).start()
            self.root.after(300, self.refresh_voice_soon)

    def refresh_voice_soon(self):
        self._refresh_voice(self.app.status_fn().get("voice"))

    def _refresh_voice(self, v):
        if not v or not v.get("available"):
            if self.voice_card.winfo_ismapped():
                self.voice_title.pack_forget()
                self.voice_card.pack_forget()
            return
        if not self.voice_card.winfo_ismapped():
            self.voice_title.pack(fill="x", padx=16, pady=(12, 4), after=self.status.master.master)
            self.voice_card.pack(fill="x", padx=16, after=self.voice_title)
        self._vstate = v
        st = v.get("status")
        if not v.get("on"):
            text, color = "Desligado", "off"
        elif st == "listening":
            text = f"Ouvindo: {v.get('device')}" + ("  (principal no mudo)" if v.get("fallback") else "")
            color = "ok"
        elif st == "loading":
            text, color = "Carregando o reconhecimento de fala...", "wait"
        else:
            text, color = f"Erro: {v.get('error')}", "err"
        self.vdot.itemconfigure(self.vdot_id, fill={**self.STATE_HEX, "err": "#e74c3c"}[color])
        self.voice_status.configure(text=text)
        last = v.get("last")
        self.voice_last.configure(
            text=(f"Último: \u201c{last['text']}\u201d  >  {last['msg']}" if last else 'Diga "PC" e o comando. Ex.: PC, próxima música'),
            fg=("#e74c3c" if last and not last.get("ok") else self.DIM))
        self.voice_on_btn.configure(text="Desligar voz" if v.get("on") else "Ligar voz")
        self.voice_ov_btn.configure(text="Aviso na tela: " + ("sim" if v.get("overlay") else "não"))

    def _open_phone(self):
        err = self.app.open_on_phone()
        self.phone_msg.configure(text=err or "Abrindo no celular…", fg="#e74c3c" if err else self.DIM)

    def _refresh_phone(self, phone):
        links = phone.get("links") or {}
        hs = phone.get("https")
        if "https" in links:
            self.phone_https.configure(text="Seguro (Tailscale): o QR abre " + links["https"].split("#")[0]
                                            + "\nFunciona em casa e fora, com o Tailscale ligado no celular.", fg="#2ecc71")
        elif hs:
            self.phone_https.configure(text=f"HTTPS: {hs.get('error') or 'preparando o certificado…'}", fg=self.DIM)
        else:
            self.phone_https.configure(text="")
        if not phone.get("web"):
            self.phone_wifi.configure(text=f"App do celular desligado (porta {phone.get('port')} em uso?)")
        elif "wifi" in links and "https" in links:
            self.phone_wifi.configure(text=f"Wi-Fi sem Tailscale: abra {links['wifi'].split('#')[0]} e digite o token.")
        elif "wifi" in links:
            self.phone_wifi.configure(text="Wi-Fi: aponte a câmera do celular para o QR code\n"
                                           f"ou abra {links['wifi'].split('#')[0]} e digite o token.")
        else:
            self.phone_wifi.configure(text="Wi-Fi desativado (web.host = 127.0.0.1). Use o cabo.")
        if phone.get("adb"):
            self.phone_cable.configure(text="Cabo: celular conectado. Abra o app ou use o botão.", fg="#2ecc71")
            if not self.phone_btn.winfo_ismapped():
                self.phone_btn.pack(anchor="w", pady=(8, 0))
                self.phone_msg.pack(fill="x", pady=(4, 0))
        else:
            self.phone_cable.configure(text="Cabo: ligue o celular com 'Depuração USB' ativa "
                                            f"e abra http://localhost:{phone.get('port')}", fg=self.DIM)
            if self.phone_btn.winfo_ismapped():
                self.phone_btn.pack_forget()
                self.phone_msg.pack_forget()
        url = links.get("https") or links.get("wifi")
        if url != self._qr_url:
            self._qr_url = url
            self._qr_img = None
            if url:
                try:
                    import qrcode
                    from PIL import ImageTk
                    q = qrcode.QRCode(border=2, box_size=4)
                    q.add_data(url)
                    self._qr_img = ImageTk.PhotoImage(q.make_image(fill_color="black", back_color="white").get_image(), master=self.qr)
                except Exception:  # noqa: BLE001  (qrcode não instalado)
                    log.info("qrcode indisponível - painel sem QR")
            self.qr.configure(image=self._qr_img or "")
            if not self._qr_img:
                self.qr.pack_forget()
            elif not self.qr.winfo_ismapped():
                self.qr.pack(side="left", padx=10, pady=10, before=self.qr.master.winfo_children()[1])

    def bring_to_front(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def refresh(self):
        try:
            while True:
                if self.app.panel_q.get_nowait() == "raise":
                    self.bring_to_front()
        except queue.Empty:
            pass

        st = self.app.status_fn()
        self.dot.itemconfigure(self.dot_id, fill=self.STATE_HEX[st["state"]])
        self.status.configure(text=st["text"])
        self.game.configure(text=f"Jogando: {st['game']}" if st.get("game") else "Nenhum jogo detectado")
        if "phone" in st:
            self._refresh_phone(st["phone"])
        self._refresh_voice(st.get("voice"))

        try:
            mtime = self.app.log_path.stat().st_mtime
            if mtime != self._log_mtime:
                self._log_mtime = mtime
                with open(self.app.log_path, "rb") as fh:
                    fh.seek(0, 2)
                    fh.seek(max(0, fh.tell() - 8000))
                    lines = fh.read().decode("utf-8", "replace").splitlines()[-60:]
                lines = [ln.split(" ", 1)[1] if ln[:4].isdigit() else ln for ln in lines]  # tira a data
                self.log.configure(state="normal")
                self.log.delete("1.0", "end")
                self.log.insert("end", "\n".join(lines))
                self.log.see("end")
                self.log.configure(state="disabled")
        except OSError:
            pass
        self.root.after(1000, self.refresh)
