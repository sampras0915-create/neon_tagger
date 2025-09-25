
# -*- coding: utf-8 -*-
# サイバー風 MP3 タグエディタ（安定版）
# - 複数ラインのスキャン演出
# - ヘッダーに「選択中ファイル / ステータス」
# - 曲名/アーティスト/歌唱者（＆区切り、自動正規化）
# - MP3ファイル選択（未処理のみ表示トグル）
# - ID3保存、IDタグ↔ファイル名、リネーム衝突回避
# - ソフトキーボード対策（pan + auto scroll）
# - エラー時は画面表示＋ログ出力

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from kivy.clock import Clock
from kivy.properties import ListProperty
import os, traceback, re, random, json
from datetime import datetime

from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TXXX

# ---- 環境 ----
ANDROID = 'ANDROID_APP_PATH' in os.environ or 'ANDROID_ARGUMENT' in os.environ
try:
    if ANDROID:
        from android.permissions import request_permissions, Permission
        try:
            from jnius import autoclass
        except Exception:
            autoclass = None
    else:
        request_permissions = None; Permission = None; autoclass = None
except Exception:
    request_permissions = None; Permission = None; autoclass = None

# ---- ログ ----
def _ts(): return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
def _ensure_dirs(paths):
    for p in paths:
        try: os.makedirs(p, exist_ok=True)
        except Exception: pass
def write_log(msg, is_error=False):
    base_sd = "/storage/emulated/0/さんぷらす/Copilot/ログ"
    base_home = os.path.expanduser("~/さんぷらす/Copilot/ログ")
    _ensure_dirs([base_sd, base_home])
    fname = f"{'error_log' if is_error else 'app_log'}_{_ts()}.txt"
    for base in (base_sd, base_home):
        try:
            with open(os.path.join(base, fname), "w", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

# ---- 設定 ----
SETTINGS_DIR = "/storage/emulated/0/さんぷらす/GUI"
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "neon_tagger_settings.json")
def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_dir": "/storage/emulated/0", "auto_apply": False}
def save_settings(d):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ---- フォント（存在しない場合はスキップ） ----
FONT_NAME = None
JP_FONT_PATH = "/storage/emulated/0/さんぷらす/GUI/NotoSansJP-VariableFont_wght.ttf"
try:
    if os.path.exists(JP_FONT_PATH):
        LabelBase.register(name="NotoJP", fn_regular=JP_FONT_PATH)
        LabelBase.register(name="Roboto", fn_regular=JP_FONT_PATH)  # FileChooser内部対策
        FONT_NAME = "NotoJP"
except Exception as e:
    write_log("フォント登録失敗: " + traceback.format_exc(), True)
def fkw(): return {"font_name": FONT_NAME} if FONT_NAME else {}

# ---- カラー / 背景 ----
BG = (0.06, 0.08, 0.10, 1)
CYAN = (0.0, 0.95, 0.95, 1)
CYAN_SOFT = (0.0, 0.95, 0.95, 0.18)
WHITE = (1, 1, 1, 1)
GRAY_TXT = (0.86, 0.92, 0.98, 0.90)
Window.clearcolor = BG
Window.softinput_mode = "pan"

class ScanBackdrop(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*BG); self._bg = Rectangle(pos=self.pos, size=self.size)
        self.lines = []
        with self.canvas:
            for _ in range(14):
                Color(0,1,1,0.24)
                rect = Rectangle(size=(self.width, dp(random.choice([2,3,4]))))
                self.lines.append({"rect": rect, "speed": random.uniform(40, 110),
                                   "phase": random.random()})
        self.bind(pos=self._resize, size=self._resize)
        Clock.schedule_interval(self._tick, 1/60)
        self.t = 0.0
    def on_touch_down(self, t): return False
    def on_touch_move(self, t): return False
    def on_touch_up(self, t):   return False
    def _resize(self, *a):
        self._bg.pos, self._bg.size = self.pos, self.size
    def _tick(self, dt):
        self.t += dt; H = max(self.height, 1)
        for L in self.lines:
            cycle = (self.t * L["speed"] / H + L["phase"]) % 1.0
            L["rect"].pos = (self.x, self.y + cycle * H); L["rect"].size = (self.width, L["rect"].size[1])

class NeonTextInput(TextInput):
    def __init__(self, **kw):
        kw.setdefault("size_hint_y", None); kw.setdefault("height", dp(44))
        kw.setdefault("multiline", False); kw.update(fkw()); super().__init__(**kw)
        self.input_type = "text"; self.bind(focus=lambda *_: setattr(self, "input_type", "text"))
        self.background_color = [1,1,1,1]; self.foreground_color = [0,0,0,1]
        self.cursor_color = CYAN; self.cursor_width = dp(2); self.hint_text_color = [0,0,0,0.5]
        self.font_size = dp(16)
        with self.canvas.after:
            Color(*CYAN_SOFT); self._outer = Line(rounded_rectangle=[self.x,self.y,self.width,self.height,12], width=dp(4))
            Color(*CYAN);      self._inner = Line(rounded_rectangle=[self.x,self.y,self.width,self.height,12], width=dp(1.6))
        self.bind(pos=self._upd, size=self._upd, focus=self._glow)
    def _upd(self, *a):
        x,y = self.pos; w,h = self.size
        self._outer.rounded_rectangle = [x,y,w,h,12]; self._inner.rounded_rectangle = [x,y,w,h,12]
    def _glow(self, *_):
        x,y = self.pos; w,h = self.size
        from kivy.graphics import Color as KColor, Line as KLine
        self.canvas.after.remove(self._inner)
        with self.canvas.after:
            KColor(*(CYAN if self.focus else (CYAN[0], CYAN[1], CYAN[2], 0.9)))
            self._inner = KLine(rounded_rectangle=[x,y,w,h,12], width=dp(1.6))

class NeonButton(Button):
    background_color = ListProperty([0,0,0,0])
    def __init__(self, **kw):
        kw.setdefault("size_hint_y", None); kw.setdefault("height", dp(48))
        kw.setdefault("font_size", dp(18)); kw.setdefault("markup", True); kw.update(fkw())
        super().__init__(**kw); self.background_normal = ''; self.background_down = ''; self.color = WHITE
        with self.canvas.before:
            Color(0.10,0.12,0.14,1); self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[16])
            Color(*CYAN_SOFT);       self._outer = Line(rounded_rectangle=[self.x,self.y,self.width,self.height,16], width=dp(6))
            Color(*CYAN);            self._inner = Line(rounded_rectangle=[self.x,self.y,self.width,self.height,16], width=dp(2))
        self.bind(pos=self._upd, size=self._upd)
    def _upd(self, *a):
        x,y = self.pos; w,h = self.size
        self._bg.pos, self._bg.size = (x,y),(w,h)
        self._outer.rounded_rectangle = [x,y,w,h,16]; self._inner.rounded_rectangle = [x,y,w,h,16]

# ---- 文字列ユーティリティ ----
DASHES = "[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D\\-]"
def normalize_dashes_spaces(s: str) -> str:
    if not s: return ""
    s = re.sub(DASHES, "-", s); s = s.replace("\u3000", " "); s = re.sub(r"\s+", " ", s).strip()
    return s
def sanitize_filename(name): return re.sub(r'[\\/:*?"<>|]', '_', name.strip())
def join_singers(lst): return '＆'.join([s for s in lst if s])
def split_singers(txt): return [p.strip() for p in re.split(r'[＆&、, ]+', txt) if p.strip()]

def make_filename_from_tags(title, artist, singers_list):
    safe_title  = sanitize_filename(title); safe_artist = sanitize_filename(artist)
    singers = join_singers(singers_list) if singers_list else "不明"; safe_singers = sanitize_filename(singers)
    return f"{safe_title} - {safe_singers} - {safe_artist}.mp3"

def unique_path(base_dir, filename, current_path=None):
    target = os.path.join(base_dir, filename)
    if current_path and os.path.abspath(target) == os.path.abspath(current_path): return target
    if not os.path.exists(target): return target
    name, ext = os.path.splitext(filename); i = 1
    while True:
        cand = os.path.join(base_dir, f"{name}_{i}{ext}")
        if current_path and os.path.abspath(cand) == os.path.abspath(current_path): return cand
        if not os.path.exists(cand): return cand
        i += 1

def parse_filename(name_no_ext):
    s = normalize_dashes_spaces(name_no_ext)
    parts = [p.strip() for p in re.split(r"\s*-\s*", s) if p.strip()]
    if len(parts) >= 3:
        title = parts[0]; artist = parts[-1]
        singers_txt = " ".join(parts[1:-1]); singers = [] if singers_txt == "不明" else split_singers(singers_txt)
        return {"title": title, "artist": artist, "singers": singers}
    elif len(parts) == 2:
        title, artist = parts; return {"title": title, "artist": artist, "singers": []}
    else:
        return {"title": s, "artist": "", "singers": []}

# ---- ID3 ----
def _frame_text_to_str(frame, default=""):
    if frame is None: return default
    val = getattr(frame, "text", "")
    if isinstance(val, (list, tuple)): return val[0] if val else default
    return str(val)

def read_id3(path):
    try:
        audio = ID3(path)
        title  = _frame_text_to_str(audio.get("TIT2"))
        artist = _frame_text_to_str(audio.get("TPE1"))
        performers = ""
        for txxx in audio.getall("TXXX"):
            if getattr(txxx, "desc", "").lower() == "performer":
                performers = _frame_text_to_str(txxx); break
        singers = split_singers(performers)
        return title, artist, singers
    except Exception:
        return "", "", []

def write_id3(path, title, artist, singers_list):
    try:
        try: audio = ID3(path)
        except ID3NoHeaderError: audio = ID3()
        audio["TIT2"] = TIT2(encoding=3, text=title)
        audio["TPE1"] = TPE1(encoding=3, text=artist)
        audio["TXXX:Performer"] = TXXX(encoding=3, desc="Performer", text=join_singers(singers_list))
        audio.save(path, v2_version=3)
        return True, ""
    except Exception as e:
        write_log("write_id3 error: " + traceback.format_exc(), True)
        return False, str(e)

# ---- 画面 ----
class CyberTagger(BoxLayout):
    def __init__(self, scrollview, **kw):
        super().__init__(orientation="vertical", spacing=dp(12), padding=dp(16), **kw)
        self.scrollview = scrollview
        # 背景
        self.add_widget(ScanBackdrop())
        content = BoxLayout(orientation="vertical", spacing=dp(12)); self.add_widget(content)

        # ヘッダー
        self.header_file = Label(text="[b]Selected:[/b] (none)", markup=True, color=CYAN,
                                 font_size=dp(18), size_hint_y=None, height=dp(28), **fkw())
        self.header_status = Label(text="Ready", markup=True, color=GRAY_TXT,
                                   font_size=dp(14), size_hint_y=None, height=dp(22), **fkw())
        content.add_widget(self.header_file); content.add_widget(self.header_status)

        # 入力欄
        content.add_widget(Label(text="[b]Song Title[/b]", markup=True, color=GRAY_TXT,
                                 size_hint_y=None, height=dp(18), **fkw()))
        self.title = NeonTextInput(hint_text="曲名", **fkw()); content.add_widget(self.title)

        content.add_widget(Label(text="[b]Artist[/b]", markup=True, color=GRAY_TXT,
                                 size_hint_y=None, height=dp(18), **fkw()))
        self.artist = NeonTextInput(hint_text="アーティスト", **fkw()); content.add_widget(self.artist)

        content.add_widget(Label(text="[b]Singers (Max 3 / ＆区切り可)[/b]", markup=True, color=GRAY_TXT,
                                 size_hint_y=None, height=dp(18), **fkw()))
        self.singers = NeonTextInput(hint_text="例）A＆B", **fkw()); content.add_widget(self.singers)
        self._singers_updating = False
        self.singers.bind(text=self._auto_separate_singers)

        # フォーカス時オートスクロール
        for w in (self.title, self.artist, self.singers):
            w.bind(focus=lambda inst, val: self._scroll_into_view(inst) if val else None)

        # 自動適用トグル
        self.toggle_auto = ToggleButton(text="選択時にファイル名→IDタグ", state="normal",
                                        size_hint_y=None, height=dp(36), **fkw())
        self.toggle_auto.background_normal = ""; self.toggle_auto.background_down = ""; self.toggle_auto.color = WHITE
        with self.toggle_auto.canvas.before:
            Color(0.10,0.12,0.14,1); self._tbg = RoundedRectangle(pos=self.toggle_auto.pos, size=self.toggle_auto.size, radius=[10])
            Color(*CYAN_SOFT); self._touter = Line(rounded_rectangle=[0,0,0,0,10], width=dp(4))
            Color(*CYAN);      self._tinner = Line(rounded_rectangle=[0,0,0,0,10], width=dp(1.6))
        def _upd_toggle(*_):
            x,y = self.toggle_auto.pos; w,h = self.toggle_auto.size
            self._tbg.pos, self._tbg.size = (x,y),(w,h)
            self._touter.rounded_rectangle = [x,y,w,h,10]; self._tinner.rounded_rectangle = [x,y,w,h,10]
        self.toggle_auto.bind(pos=_upd_toggle, size=_upd_toggle)
        content.add_widget(self.toggle_auto)

        # ボタン
        row1 = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        self.btn_select = NeonButton(text="[b]MP3を選択[/b]", **fkw())
        self.btn_save   = NeonButton(text="[b]タグを保存[/b]", **fkw())
        self.btn_reset  = NeonButton(text="[b]入力リセット[/b]", **fkw())
        row1.add_widget(self.btn_select); row1.add_widget(self.btn_save); row1.add_widget(self.btn_reset)
        content.add_widget(row1)

        row2 = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        self.btn_rename = NeonButton(text="[b]IDタグ→ファイル名[/b]", **fkw())
        self.btn_parse  = NeonButton(text="[b]ファイル名→IDタグ[/b]", **fkw())
        row2.add_widget(self.btn_rename); row2.add_widget(self.btn_parse)
        content.add_widget(row2)

        # イベント
        self.btn_select.bind(on_release=self.open_filechooser)
        self.btn_save.bind(on_release=self.save_tags)
        self.btn_reset.bind(on_release=self.reset_inputs)
        self.btn_rename.bind(on_release=self.rename_from_tags)
        self.btn_parse.bind(on_release=self.tags_from_filename)
        self.toggle_auto.bind(on_press=self._on_toggle_auto)

        # 状態
        st = load_settings()
        self.file_path = ""
        self.last_dir  = st.get("last_dir") if os.path.isdir(st.get("last_dir","")) else ("/storage/emulated/0" if os.path.isdir("/storage/emulated/0") else os.path.expanduser("~"))
        self.toggle_auto.state = "down" if st.get("auto_apply", False) else "normal"

    # ---- ユーティリティ ----
    def _set_status(self, text, ok=True):
        self.header_status.text = f"[color=80ff80]{text}[/color]" if ok else f"[color=ff8080]{text}[/color]"
        self.header_status.markup = True

    def _scroll_into_view(self, widget):
        if not self.scrollview: return
        Clock.schedule_once(lambda dt: self.scrollview.scroll_to(widget, padding=dp(160)), 0)

    def _auto_separate_singers(self, instance, value):
        if getattr(self, "_singers_updating", False): return
        parts = split_singers(value)[:3]; normalized = '＆'.join(parts)
        if normalized != value:
            self._singers_updating = True; instance.text = normalized; self._singers_updating = False

    def _on_toggle_auto(self, *_):
        save_settings({"last_dir": self.last_dir, "auto_apply": (self.toggle_auto.state=="down")})

    # ---- ファイル選択 ----
    def open_filechooser(self, _):
        chooser = FileChooserListView(filters=["*.mp3"], path=self.last_dir)
        toggle_unproc = ToggleButton(text="未処理のみ表示", size_hint_y=None, height=dp(36), state="normal", **fkw())
        def _apply_filter(*_):
            try:
                if toggle_unproc.state == "down":
                    def filter_func(folder, name):
                        if not name.lower().endswith(".mp3"): return False
                        path = os.path.join(folder, name)
                        t,a,_ = read_id3(path); return not (t and a)
                    chooser.filters = [filter_func]
                else:
                    chooser.filters = ["*.mp3"]
                # refresh（Kivyのバージョン差異に対応）
                try:
                    chooser._update_files()  # ある場合
                except Exception:
                    chooser.path = chooser.path  # 無理やり更新
            except Exception:
                self._set_status("フィルタ更新中にエラー", ok=False)
        toggle_unproc.bind(on_press=_apply_filter)

        btn_row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        btn_ok = NeonButton(text="[b]決定[/b]", **fkw())
        btn_cancel = NeonButton(text="[b]キャンセル[/b]", **fkw())
        btn_row.add_widget(btn_ok); btn_row.add_widget(btn_cancel)

        layout = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        layout.add_widget(toggle_unproc); layout.add_widget(chooser); layout.add_widget(btn_row)
        popup = Popup(title="MP3を選択", content=layout, size_hint=(0.95, 0.95))

        def do_select(*_):
            if chooser.selection:
                self._apply(chooser.selection[0]); popup.dismiss()
            else:
                self._set_status("ファイル未選択", ok=False)
        btn_ok.bind(on_release=do_select)
        btn_cancel.bind(on_release=lambda *_: popup.dismiss())
        chooser.bind(on_submit=lambda inst, sel, touch: do_select() if sel else None)
        popup.open()

    def _apply(self, path):
        self.file_path = path; self.last_dir  = os.path.dirname(path)
        save_settings({"last_dir": self.last_dir, "auto_apply": (self.toggle_auto.state=="down")})
        self.header_file.text = f"[b]Selected:[/b] {os.path.basename(path)}"

        try:
            t, a, s_list = read_id3(path)
        except Exception:
            t,a,s_list = "","",""
        # 自動適用ONならファイル名→IDタグ優先
        if self.toggle_auto.state=="down":
            base = os.path.splitext(os.path.basename(path))[0]; parsed = parse_filename(base)
            t = parsed["title"] or t; a = parsed["artist"] or a; s_list = parsed["singers"] if parsed["singers"] else s_list
            ok, err = write_id3(self.file_path, t.strip(), a.strip(), s_list or [])
            if ok: self._set_status("ファイル名→IDタグ 自動適用 ✓", ok=True)
            else:  self._set_status("IDタグ更新失敗: " + err, ok=False)

        self.title.text  = t
        self.artist.text = a
        self.singers.text = join_singers(s_list) if s_list else ""

    # ---- 操作 ----
    def save_tags(self, _):
        if not self.file_path:
            self._set_status("ファイルが選択されていません", False); return
        t = self.title.text.strip(); a = self.artist.text.strip(); s = split_singers(self.singers.text.strip())
        if not (t and a): self._set_status("曲名/アーティストが未入力です", False); return
        ok, err = write_id3(self.file_path, t, a, s)
        if ok:
            self._set_status(f"保存成功  Title:{t} / Artist:{a} / Singer:{join_singers(s) or '不明'}", True)
            write_log(f"保存成功: {os.path.basename(self.file_path)} / {t} / {a} / {join_singers(s)}")
        else:
            self._set_status("保存エラー: " + err, False); write_log(err, True)

    def rename_from_tags(self, _):
        if not self.file_path:
            self._set_status("ファイルが選択されていません", False); return
        t = self.title.text.strip(); a = self.artist.text.strip(); s = split_singers(self.singers.text.strip())
        if not (t and a): self._set_status("曲名/アーティストが未入力です", False); return
        base_dir = os.path.dirname(self.file_path); new_name = make_filename_from_tags(t, a, s)
        target_path = os.path.join(base_dir, new_name)
        if os.path.abspath(target_path) == os.path.abspath(self.file_path):
            self._set_status("変更なし  " + os.path.basename(self.file_path), True); return
        new_path = unique_path(base_dir, new_name, current_path=self.file_path)
        try:
            os.rename(self.file_path, new_path); self.file_path = new_path
            self.header_file.text = f"[b]Selected:[/b] {os.path.basename(new_path)}"
            self._set_status("リネーム完了 → " + os.path.basename(new_path), True)
        except Exception as e:
            self._set_status("リネーム失敗: " + str(e), False)

    def tags_from_filename(self, _):
        if not self.file_path:
            self._set_status("ファイルが選択されていません", False); return
        base = os.path.splitext(os.path.basename(self.file_path))[0]; p = parse_filename(base)
        self.title.text  = p["title"]; self.artist.text = p["artist"]; self.singers.text = join_singers(p["singers"]) if p["singers"] else ""
        ok, err = write_id3(self.file_path, self.title.text.strip(), self.artist.text.strip(), p["singers"])
        if ok: self._set_status("IDタグ更新（ファイル名→タグ）", True)
        else:  self._set_status("IDタグ更新失敗: " + err, False)

    def reset_inputs(self, _):
        self.file_path = ""; self.header_file.text = "[b]Selected:[/b] (none)"
        self.title.text = self.artist.text = self.singers.text = ""; self._set_status("Ready", True)

# ---- アプリ ----
class CyberApp(App):
    def build(self):
        # 権限（あれば）
        if ANDROID and request_permissions and Permission:
            try:
                api_level = 0
                if autoclass:
                    Build = autoclass("android.os.Build"); api_level = Build.VERSION.SDK_INT
                perms = [Permission.READ_MEDIA_AUDIO] if api_level >= 33 else \
                        [Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE]
                if perms: request_permissions(perms)
            except Exception:
                write_log("権限リクエスト失敗:\n" + traceback.format_exc(), True)
        self.sv = ScrollView()
        cont = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10), padding=dp(10))
        cont.bind(minimum_height=cont.setter("height"))
        cont.add_widget(CyberTagger(scrollview=self.sv, size_hint_y=None, height=Window.height))
        self.sv.add_widget(cont)
        return self.sv

if __name__ == "__main__":
    CyberApp().run()
