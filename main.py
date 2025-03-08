import discum
import time
import threading
import logging
import json
import os
from tkinter import *
from tkinter import filedialog
import tkinter as tk
from tkinter import ttk
import datetime

##############################
# ЛОГИ И НАСТРОЙКИ
##############################
logging.basicConfig(filename="bot.log", level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

SETTINGS_FILE = "settings.json"

def load_config(filename=SETTINGS_FILE):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_config(config, filename=SETTINGS_FILE):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving config: {e}")

##############################
# ГЛОБАЛЫ
##############################
config = load_config()

bot_running   = False
image_path    = ""
current_sbot  = None

# Текст из config.json
accounts_text   = config.get("accounts_text", "")  # login:pass:token
message_text    = config.get("message_text", "")
auto_reply_text = config.get("auto_reply_text", "")
message_delay   = config.get("message_delay", 5)   # сек задержка
token_delay     = config.get("token_delay", 3)     # мин задержка (по умолч.)

invite_text     = ""

##############################
# ЦВЕТА / ШРИФТЫ
##############################
BG_COLOR       = "#181a1f"
FRAME_COLOR    = "#24282e"
FG_COLOR       = "#e0e0e0"

BUTTON_START   = "#4CAF50"
BUTTON_STOP    = "#f44336"
BUTTON_TEXT    = "#ffffff"

FONT_NAME    = "Segoe UI"
DEFAULT_SIZE = 10
DEFAULT_FONT = (FONT_NAME, DEFAULT_SIZE)
HEADING_FONT = (FONT_NAME, 12, "bold")

##############################
# ЛОГ В ТЕКСТОВОЕ ПОЛЕ
##############################
def log_message(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}\n"
    logging.info(msg)
    textbox_logs.config(state=NORMAL)
    textbox_logs.insert(END, formatted)
    textbox_logs.config(state=DISABLED)
    textbox_logs.see(END)

##############################
# ВЫБОР ИЗОБРАЖЕНИЯ
##############################
def choose_image():
    global image_path
    file_path = filedialog.askopenfilename(
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.gif")]
    )
    if file_path:
        image_path = file_path
        log_message(f"Выбрано изображение: {image_path}")

##############################
# ЗАГРУЗКА login:pass:token
##############################
def load_discords():
    global accounts_text
    file_path = filedialog.askopenfilename(
        filetypes=[("Text files", "*.txt")]
    )
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                accounts_text = f.read()
            config["accounts_text"] = accounts_text
            save_config(config)
            log_message("Токены (login:password:token) загружены.")
        except Exception as e:
            log_message(f"Ошибка при загрузке: {e}")

##############################
# ОБНОВЛЯЕМ ЗАДЕРЖКИ
##############################
def update_delays_in_config(*args):
    global message_delay, token_delay
    try:
        md = int(textbox_delay_channels.get("1.0", END).strip())
        message_delay = md
        config["message_delay"] = message_delay
    except:
        pass
    try:
        td = int(textbox_delay_token.get("1.0", END).strip())
        token_delay = td
        config["token_delay"] = token_delay
    except:
        pass
    save_config(config)

##############################
# Сохраняем «Текст сообщения»
##############################
def save_message_text(*args):
    global message_text
    new_text = textbox_text.get("1.0", END).strip()
    message_text = new_text
    config["message_text"] = message_text
    save_config(config)

##############################
# Сохраняем «Автоответ»
##############################
def save_auto_reply_text(*args):
    global auto_reply_text
    new_text = textbox_auto_replay.get("1.0", END).strip()
    auto_reply_text = new_text
    config["auto_reply_text"] = auto_reply_text
    save_config(config)

##############################
# Извлечь код из ссылки
##############################
def extract_invite_code(inv_url: str):
    inv_url = inv_url.strip()
    if "discord.gg/" in inv_url:
        return inv_url.rsplit("/", 1)[-1]
    return inv_url

##############################
# START/STOP
##############################
def start_stop_bot():
    global bot_running
    if bot_running:
        stop_bot()
    else:
        start_bot()

def start_bot():
    global bot_running
    if bot_running:
        return
    bot_running = True
    update_button()
    log_message("Нажата кнопка START. Запуск self-bot.")

    global invite_text
    invite_text = textbox_invite.get("1.0", END).strip()

    th = threading.Thread(target=run_single_token_cycle)
    th.start()

def stop_bot():
    global bot_running
    bot_running = False
    if current_sbot:
        try:
            current_sbot.gateway.close()
        except:
            pass
    log_message("Остановка. Текущий токен отключён.")
    update_button()

def update_button():
    if bot_running:
        button_start_stop.config(text="STOP", bg=BUTTON_STOP)
        button_send.config(state="normal")
    else:
        button_start_stop.config(text="START", bg=BUTTON_START)
        button_send.config(state="disabled")

##############################
# ГЛАВНАЯ ЛОГИКА: ОДИН ТОКЕН → ...
##############################
def run_single_token_cycle():
    global bot_running, current_sbot, invite_text

    lines = [ln.strip() for ln in accounts_text.splitlines() if ln.strip()]
    if not lines:
        log_message("Нет строк (login:password:token).")
        return

    idx = 0
    for line in lines:
        if not bot_running:
            break
        parts = line.split(":", 2)
        if len(parts) < 3:
            log_message(f"Некорректная строка: {line}")
            continue
        token = parts[2].strip()
        idx += 1

        log_message(f"Self-bot #{idx} → ONLINE (на {token_delay} мин)")

        # Минимальный вызов:
        # bot=False -> говорит Discum, что это user token (self-bot)
        # log=False -> нет спама в консоль
        sbot = discum.Client(token=token, bot=False, log=False)
        current_sbot = sbot

        code = extract_invite_code(invite_text)
        guild_id = None
        if code:
            # getInviteInfo
            try:
                resp = sbot.getInviteInfo(code, with_counts=True, with_expiration=True)
                dat = json.loads(resp.text)
                guild_id = dat["guild"]["id"]
                log_message(f"Self-bot #{idx}: getInviteInfo => guild_id={guild_id}")
            except Exception as e:
                log_message(f"Self-bot #{idx}: ошибка getInviteInfo({code}): {e}")

            # acceptInvite
            if guild_id:
                try:
                    sbot.acceptInvite(code)
                    log_message(f"Self-bot #{idx}: acceptInvite({code})")
                except Exception as e:
                    log_message(f"Self-bot #{idx}: ошибка acceptInvite({code}): {e}")

        @sbot.gateway.command
        def on_msg(resp):
            if not bot_running:
                return
            if resp.event.ready_supplemental:
                log_message(f"Self-bot #{idx} готов к работе.")
            if resp.event.message:
                m = resp.parsed.auto()
                if m["type"] == "chat" and m["channel_type"] == 1:
                    if m["author"]["id"] != sbot.user["id"]:
                        if auto_reply_text:
                            dm_channel = m["channel_id"]
                            sbot.sendMessage(dm_channel, auto_reply_text)

        # Запуск gateway
        gw_th = threading.Thread(target=sbot.gateway.run, daemon=True)
        gw_th.start()

        time.sleep(5)  # ждать, чтобы попасть на сервер

        if guild_id:
            try:
                raw_ch = sbot.getGuildChannels(guild_id)
                jdata = json.loads(raw_ch.text)
                text_channels = []
                for c in jdata:
                    if c.get("type") == 0:
                        text_channels.append(c["name"])
                def update_ch():
                    textbox_channels.delete("1.0", END)
                    if text_channels:
                        for n in text_channels:
                            textbox_channels.insert(END, n + "\n")
                    else:
                        textbox_channels.insert(END, "Нет текстовых каналов.\n")
                root.after(0, update_ch)
                log_message(f"Self-bot #{idx}: Получено {len(text_channels)} каналов.")
            except Exception as e:
                log_message(f"Self-bot #{idx}: ошибка getGuildChannels({guild_id}): {e}")

        # Держим online (token_delay) минут
        csec = token_delay * 60
        while bot_running and csec > 0:
            time.sleep(1)
            csec -= 1

        if bot_running:
            log_message(f"Время вышло. Отключаем Self-bot #{idx}.")
        try:
            sbot.gateway.close()
        except:
            pass

        current_sbot = None
        if not bot_running:
            break

    log_message("Цикл токенов завершён.")
    bot_running = False
    update_button()

##############################
# ОТПРАВИТЬ
##############################
def send_message_action():
    global bot_running, current_sbot
    if not bot_running or not current_sbot:
        log_message("Нет активного токена – не отправляем.")
        return

    global message_text
    message_text = textbox_text.get("1.0", END).strip()
    channel_id_str = textbox_channels.get("1.0", END).strip()
    if not channel_id_str:
        log_message("Введите ID канала (или доработать логику).")
        return

    t = threading.Thread(target=send_message_current, args=(channel_id_str,))
    t.start()

def send_message_current(channel_id):
    global current_sbot
    log_message(f"Ждём {message_delay} сек. перед отправкой сообщения.")
    time.sleep(message_delay)
    if not bot_running or not current_sbot:
        return

    if image_path:
        log_message(f"Отправляем файл {image_path} + текст: {message_text}")
        try:
            current_sbot.sendFile(channel_id, image_path, message_text or None)
        except Exception as e:
            log_message(f"Ошибка при отправке: {e}")
    else:
        log_message(f"Отправляем текст: {message_text}")
        try:
            current_sbot.sendMessage(channel_id, message_text or " ")
        except Exception as e:
            log_message(f"Ошибка при отправке: {e}")

##############################
# ФУНКЦИЯ LABELFRAME
##############################
def create_labeled_frame(parent, label_text, x, y, width, height):
    frame = ttk.LabelFrame(parent, style="TLabelframe")
    frame.place(x=x, y=y, width=width, height=height)
    lbl = ttk.Label(frame, text=label_text, style="CustomTitle.TLabel")
    frame["labelwidget"] = lbl
    return frame

##############################
# TKINTER
##############################
root = tk.Tk()
root.title("Discum with bot=False, no token_type. Single token logic.")
root.geometry("1400x800")
root.configure(bg=BG_COLOR)

# Тема
style = ttk.Style()
style.theme_create("DarkTheme", parent="clam", settings={
    "TFrame": {"configure": {"background": FRAME_COLOR}},
    "TLabelframe": {
        "configure": {
            "background": FRAME_COLOR,
            "foreground": FG_COLOR,
            "borderwidth": 1,
            "relief": "solid",
            "labelanchor": "n"
        }
    },
    "TLabelframe.Label": {"configure": {"background": FRAME_COLOR,"foreground": FG_COLOR}},
    "CustomTitle.TLabel": {
        "configure": {
            "background": FRAME_COLOR,
            "foreground": FG_COLOR,
            "font": HEADING_FONT,
            "anchor": "center",
            "justify": "center"
        }
    },
    "TLabel": {"configure": {"background": FRAME_COLOR,"foreground": FG_COLOR,"font": DEFAULT_FONT}},
    "TButton": {"configure": {"font": DEFAULT_FONT, "padding": 5}}
})
style.theme_use("DarkTheme")

frame_top_left = create_labeled_frame(root, "Загрузить дискорды", 20, 20, 400, 80)
button_load_discords = tk.Button(
    frame_top_left, text="Загрузить",
    bg=BUTTON_START, fg=BUTTON_TEXT, font=DEFAULT_FONT,
    command=load_discords, relief="flat"
)
button_load_discords.pack(expand=True, fill="both", padx=10, pady=10)

frame_delay_channels = create_labeled_frame(root, "Задержка сообщ. (сек)", 430, 20, 280, 80)
textbox_delay_channels = tk.Text(
    frame_delay_channels, bg=FRAME_COLOR, fg=FG_COLOR,
    font=DEFAULT_FONT, wrap="none", height=1,
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_delay_channels.pack(expand=True, fill="both", padx=10, pady=10)
textbox_delay_channels.insert("1.0", str(message_delay))
textbox_delay_channels.bind("<FocusOut>", update_delays_in_config)
textbox_delay_channels.bind("<Return>", lambda e: (update_delays_in_config(), "break"))

frame_delay_token = create_labeled_frame(root, "Задержка токенов (мин)", 730, 20, 280, 80)
textbox_delay_token = tk.Text(
    frame_delay_token, bg=FRAME_COLOR, fg=FG_COLOR,
    font=DEFAULT_FONT, wrap="none", height=1,
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_delay_token.pack(expand=True, fill="both", padx=10, pady=10)
textbox_delay_token.insert("1.0", str(token_delay))
textbox_delay_token.bind("<FocusOut>", update_delays_in_config)
textbox_delay_token.bind("<Return>", lambda e: (update_delays_in_config(), "break"))

frame_channels = create_labeled_frame(root, "Каналы (названия)", 1020, 20, 380, 200)
textbox_channels = tk.Text(
    frame_channels, bg=FRAME_COLOR, fg=FG_COLOR,
    font=DEFAULT_FONT, wrap="none",
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_channels.pack(expand=True, fill="both", padx=10, pady=10)

frame_invite = create_labeled_frame(root, "Приглашение Discord", 1020, 230, 380, 80)
textbox_invite = tk.Text(
    frame_invite, bg=FRAME_COLOR, fg=FG_COLOR,
    font=DEFAULT_FONT, wrap="none", height=1,
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_invite.pack(expand=True, fill="x", padx=10, pady=10)

frame_text = create_labeled_frame(root, "Текст сообщения", 20, 120, 400, 520)
textbox_text = tk.Text(
    frame_text, bg=FRAME_COLOR, fg=FG_COLOR,
    font=DEFAULT_FONT, wrap="word",
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_text.pack(expand=True, fill="both", padx=10, pady=10)
textbox_text.insert("1.0", message_text)
textbox_text.bind("<FocusOut>", save_message_text)
textbox_text.bind("<Return>", lambda e: (save_message_text(), "break"))

frame_image = create_labeled_frame(root, "Добавить изображение", 20, 640, 400, 80)
button_choose_image = tk.Button(
    frame_image, text="Выбрать изображение",
    bg=BUTTON_START, fg=BUTTON_TEXT,
    relief="flat", command=choose_image, font=DEFAULT_FONT
)
button_choose_image.pack(side=LEFT, padx=10, pady=10)

frame_logs = create_labeled_frame(root, "Логи", 430, 120, 280, 600)
textbox_logs = tk.Text(
    frame_logs, bg=FRAME_COLOR, fg=FG_COLOR, state=DISABLED,
    font=DEFAULT_FONT, wrap="word",
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_logs.pack(expand=True, fill="both", padx=10, pady=10)

frame_auto_reply = create_labeled_frame(root, "Автоответ", 730, 120, 280, 600)
textbox_auto_replay = tk.Text(
    frame_auto_reply, bg=FRAME_COLOR, fg=FG_COLOR,
    font=DEFAULT_FONT, wrap="word",
    borderwidth=0, highlightthickness=0, relief="flat"
)
textbox_auto_replay.pack(expand=True, fill="both", padx=10, pady=10)
textbox_auto_replay.insert("1.0", auto_reply_text)
textbox_auto_replay.bind("<FocusOut>", save_auto_reply_text)
textbox_auto_replay.bind("<Return>", lambda e: (save_auto_reply_text(), "break"))

button_start_stop = tk.Button(
    root, text="START",
    bg=BUTTON_START, fg=BUTTON_TEXT,
    font=(FONT_NAME, 14, 'bold'),
    command=start_stop_bot,
    relief="flat"
)
button_start_stop.place(x=20, y=740, width=1240, height=50)

button_send = tk.Button(
    root, text="ОТПРАВИТЬ",
    bg="#888888", fg=BUTTON_TEXT,
    font=(FONT_NAME, 14, 'bold'),
    command=send_message_action,
    relief="flat"
)
button_send.place(x=1270, y=740, width=100, height=50)
button_send.config(state="disabled")

root.mainloop()
