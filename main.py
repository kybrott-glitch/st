import asyncio, gzip, json, copy, io, os, random, string, logging

from pathlib import Path

import lottie

from lottie.utils.font import RawFontRenderer

from lottie import objects, NVector, Color

from lottie.objects.shapes import Fill

from aiogram import Bot, Dispatcher, F

from aiogram.types import (Message, CallbackQuery,

InlineKeyboardMarkup, InlineKeyboardButton,

BufferedInputFile)

from aiogram.filters import CommandStart

from aiogram.fsm.context import FSMContext

from aiogram.fsm.state import State, StatesGroup

from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO,

format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("8872778735:AAE8C1KkGrVDzxjEcJr3FXb-GcmNY0rcTIs", "8277263200:AAFzSV6fQrwKdRkIIeSrIkC3-9-Wz4R2OQ8")

LOTTIES_DIR = Path("lotties")

LOGO_ID = "mylogo" #DON'T TOUCH!

COLOR_BA = "BA0047" #DON'T TOUCH!

COLOR_FF = "FF4A52" #DON'T TOUCH!

COLOR_NEW = "44BEF9" #DON'T TOUCH!

COLOR_WHITE = "FFFFFF" #DON'T TOUCH!

ALLOWED_USER = 1899208318

DEFAULT_FONT = str(Path(__file__).parent / "Anton-Regular.ttf")

# ── Default colors ────────────────────────────────────────────────────────────

DEFAULT_COLOR_1 = "2700a6"   # replaces BA0047 / white stroke
DEFAULT_COLOR_2 = "067DFD"   # replaces FF4A52 / 44BEF9

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())

# ── States ────────────────────────────────────────────────────────────────────

class S(StatesGroup):

    select = State()

    type = State()

    ask_ba = State()

    ask_ff = State()

    json_file = State()

    text_input = State()

    svg_file = State()

    logo_c1 = State()

    logo_c2 = State()

    scale = State()

# ── Keyboards ─────────────────────────────────────────────────────────────────

def skip_kb(callback_data: str) -> InlineKeyboardMarkup:
    """Returns a single-button keyboard with a Skip button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Skip", callback_data=callback_data)
    ]])

def scale_kb() -> InlineKeyboardMarkup:
    """Returns the size-adjustment keyboard for the scale step."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="+10", callback_data="scale_+10"),
            InlineKeyboardButton(text="+5",  callback_data="scale_+5"),
            InlineKeyboardButton(text="-5",  callback_data="scale_-5"),
            InlineKeyboardButton(text="-10", callback_data="scale_-10"),
        ],
        [
            InlineKeyboardButton(text="✅ Done", callback_data="scale_done"),
        ]
    ])

# ── Lottie utils ──────────────────────────────────────────────────────────────

def hex_to_rgba(h: str) -> list:

    h = h.lstrip("#")

    if len(h) == 3: h = "".join(c*2 for c in h)

    if len(h) != 6: raise ValueError

    return [int(h[i:i+2], 16)/255 for i in (0, 2, 4)] + [1.0]

def rgba_close(a: list, b: list, tol: float = 0.06) -> bool:

    return all(abs(a[i] - b[i]) < tol for i in range(3))

def color_exists(obj, target: list) -> bool:

    if isinstance(obj, dict):

        if obj.get("ty") in ("fl", "st"):

            k = obj.get("c", {}).get("k")

            if isinstance(k, list):

                if len(k) == 4 and isinstance(k[0], (int, float)):

                    if rgba_close(k, target): return True

                else:

                    for kf in k:

                        if isinstance(kf, dict):

                            for fld in ("s", "e"):

                                v = kf.get(fld)

                                if isinstance(v, list) and len(v) >= 3:

                                    if rgba_close(v, target): return True

        for v in obj.values():

            if color_exists(v, target): return True

    elif isinstance(obj, list):

        for item in obj:

            if color_exists(item, target): return True

    return False

def replace_color_smart(obj, target: list, new: list, only_stroke: bool = False):

    """

    Smart color replacement:

    - If only_stroke=True, only changes colors of type 'st' (Stroke).

    - Used to replace white color (FFFFFF) only when it is a stroke.

    """

    if isinstance(obj, dict):

        ty = obj.get("ty")

        if ty in ("fl", "st"):

            # If only stroke is requested and this is not a stroke, skip it

            if only_stroke and ty != "st":

                pass

            else:

                k = obj.get("c", {}).get("k")

                if isinstance(k, list):

                    if len(k) == 4 and isinstance(k[0], (int, float)):

                        if rgba_close(k, target):

                            obj["c"]["k"] = new

                    else:

                        for kf in k:

                            if isinstance(kf, dict):

                                for fld in ("s", "e"):

                                    v = kf.get(fld)

                                    if isinstance(v, list) and len(v) >= 3:

                                        if rgba_close(v, target):

                                            kf[fld] = new

        for v in obj.values(): replace_color_smart(v, target, new, only_stroke)

    elif isinstance(obj, list):

        for item in obj: replace_color_smart(item, target, new, only_stroke)

def recolor_logo(obj, new: list):

    if isinstance(obj, dict):

        if obj.get("ty") in ("fl", "st"):

            k = obj.get("c", {}).get("k")

            if isinstance(k, list):

                if len(k) == 4 and isinstance(k[0], (int, float)):

                    obj["c"]["k"] = new

                else:

                    for kf in k:

                        if isinstance(kf, dict):

                            for fld in ("s", "e"):

                                if isinstance(kf.get(fld), list) and len(kf[fld]) >= 3:

                                    kf[fld] = new

        for v in obj.values(): recolor_logo(v, new)

    elif isinstance(obj, list):

        for i in obj: recolor_logo(i, new)

def make_text_layers(text: str, color: list) -> list:

    r, g, b, a = color

    n = len(text)

    fs = 200 if n<=3 else 170 if n<=4 else 140 if n<=6 else 110 if n<=8 else 85

    renderer = RawFontRenderer(DEFAULT_FONT)

    group_measure = renderer.render(text, fs, NVector(0, 0))

    bbox = group_measure.bounding_box()

    if bbox is not None:

        bx = bbox.x1 if hasattr(bbox, 'x1') else bbox[0]

        by = bbox.y1 if hasattr(bbox, 'y1') else bbox[1]

        bw = (bbox.x2 if hasattr(bbox, 'x2') else bbox[2]) - bx

        bh = (bbox.y2 if hasattr(bbox, 'y2') else bbox[3]) - by

        x_pos = 256 - bx - bw / 2

        y_pos = 256 - by - bh / 2

    else:

        x_pos = max(8, (512 - n * fs * 0.58) / 2)

        y_pos = 256 + fs * 0.35

    anim = objects.Animation()

    anim.width = 512; anim.height = 512

    anim.frame_rate = 60; anim.in_point = 0; anim.out_point = 180

    layer = objects.ShapeLayer(); anim.add_layer(layer)

    group = renderer.render(text, fs, NVector(x_pos, y_pos))

    fill = Fill(); fill.color.value = Color(r, g, b, a)

    group.add_shape(fill); layer.add_shape(group)

    src = anim.to_dict()

    layers = src.get("layers", [])

    for lyr in layers:

        ks = lyr.setdefault("ks", {})

        ks["a"] = {"a": 0, "k": [256, 256, 0]}

        ks["p"] = {"a": 0, "k": [256, 256, 0]}

        lyr["ip"] = 0

        lyr["op"] = 180

        lyr["st"] = 0

    return layers

def make_svg_layers(svg_bytes: bytes) -> list:

    from lottie.parsers.svg import parse_svg_file

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:

        tmp.write(svg_bytes)

        tmp_path = tmp.name

    try: anim = parse_svg_file(tmp_path)

    finally: os.unlink(tmp_path)

    src = anim.to_dict()

    src_layers = src.get("layers", [])

    svg_w, svg_h = src.get("w") or 512, src.get("h") or 512

    comp_w, comp_h = 512, 512

    cx, cy = comp_w / 2, comp_h / 2

    scale_pct = min(comp_w / svg_w, comp_h / svg_h) * 100

    new_layers = []

    for lyr in src_layers:

        l = copy.deepcopy(lyr)

        ks = l.setdefault("ks", {})

        ks["a"] = {"a": 0, "k": [svg_w / 2, svg_h / 2, 0]}

        ks["p"] = {"a": 0, "k": [cx, cy, 0]}

        ks["s"] = {"a": 0, "k": [scale_pct, scale_pct, 100]}

        l["ip"] = 0

        l["op"] = 180

        l["st"] = 0

        new_layers.append(l)

    return new_layers

# ── Logo inject ───────────────────────────────────────────────────────────────

def build_anim(anim_data: dict, logo_layers: list, extra_assets: list,

               scale: float,

               ba_color: list | None, ff_color: list | None,

               logo_c1: list | None, logo_c2: list | None,

               file_num: int = 1) -> dict:

    out = copy.deepcopy(anim_data)

    orig_ip = out.get('ip', 0)

    orig_op = out.get('op', 180)

    COMP_W, COMP_H = out.get("w", 512), out.get("h", 512)

    cx, cy = COMP_W / 2, COMP_H / 2

    # 1. Check colors

    t_ba, t_ff, t_new = hex_to_rgba(COLOR_BA), hex_to_rgba(COLOR_FF), hex_to_rgba(COLOR_NEW)

    t_white = hex_to_rgba(COLOR_WHITE)

    has_special = color_exists(out, t_ba) or color_exists(out, t_ff) or (file_num >= 67 and color_exists(out, t_new))

    logo_color = logo_c1 if has_special else logo_c2

    # 2. Prepare logo layers

    prepared_logo_layers = []

    for i, lyr in enumerate(copy.deepcopy(logo_layers)):

        ks = lyr.setdefault("ks", {})

        ks["a"] = {"a": 0, "k": [cx, cy, 0]}

        ks["p"] = {"a": 0, "k": [cx, cy, 0]}

        ks["s"] = {"a": 0, "k": [scale, scale, 100]}

        lyr["ip"] = 0

        lyr["op"] = 500

        lyr["st"] = 0

        lyr["ind"] = i + 1

        lyr["nm"] = f"Injected Logo {i+1}"

        prepared_logo_layers.append(lyr)

    if logo_color: recolor_logo(prepared_logo_layers, logo_color)

    # 3. Identify logo assets

    logo_asset_ids = set()

    for asset in out.get("assets", []):

        nm = (asset.get("nm") or "").upper()

        aid = (asset.get("id") or "").upper()

        if "LOGO" in nm or "LOGO" in aid or aid == LOGO_ID.upper():

            asset["layers"] = copy.deepcopy(prepared_logo_layers)

            logo_asset_ids.add(asset.get("id"))

    # 4. Fix timing (Recursive)

    def fix_layers_recursive(layers):

        for lyr in layers:

            is_logo_ref = lyr.get("ty") == 0 and lyr.get("refId") in logo_asset_ids

            is_logo_name = "LOGO" in (lyr.get("nm") or "").upper()

            if is_logo_ref or is_logo_name:

                lyr["ip"] = 0

                lyr["op"] = 500

                if lyr.get("st", 0) != orig_ip:

                    lyr["st"] = orig_ip

            if "layers" in lyr: fix_layers_recursive(lyr["layers"])

    fix_layers_recursive(out.get("layers", []))

    for asset in out.get("assets", []):

        if "layers" in asset: fix_layers_recursive(asset["layers"])

    # 5. Extra assets

    if extra_assets:

        ex_ids = {a.get("id") for a in out["assets"]}

        for a in extra_assets:

            if a.get("id") not in ex_ids: out["assets"].append(copy.deepcopy(a))

    # 6. Replace colors

    if ba_color:

        # Replace the main BA0047 color

        replace_color_smart(out, t_ba, ba_color)

        # REPLACE WHITE COLOR WITH BA0047 ONLY IF IT IS A STROKE

        replace_color_smart(out, t_white, ba_color, only_stroke=True)

    if ff_color:

        replace_color_smart(out, t_ff, ff_color)

        if file_num >= 67:

            replace_color_smart(out, t_new, ff_color)

    return out

def protect_json(d: dict) -> dict:

    fake_layer = {

        "ddd": 0, "ind": 999, "ty": 4, "nm": ".", "sr": 1,

        "ks": {

            "o": {"a": 0, "k": 0}, "r": {"a": 0, "k": 0},

            "p": {"a": 0, "k": [0, 0, 0]}, "a": {"a": 0, "k": [0, 0, 0]},

            "s": {"a": 0, "k": [0, 0, 0]}

        },

        "ao": 0, "sh\u0430\u0440es": [{"ty": "gr", "it": [], "nm": "."}],

        "ip": d.get("ip", 0), "op": d.get("op", 180), "st": 0, "bm": 0

    }

    if d.get("assets"):

        for a in d["assets"]:

            if isinstance(a.get("layers"), list): a["layers"].insert(0, copy.deepcopy(fake_layer))

    if isinstance(d.get("layers"), list): d["layers"].insert(0, copy.deepcopy(fake_layer))

    return d

def to_tgs(d: dict) -> bytes:

    buf = io.BytesIO()

    data = copy.deepcopy(d); data["tgs"] = 1

    protect_json(data)

    with gzip.open(buf, "wb") as gz:

        gz.write(json.dumps(data, separators=(",", ":")).encode())

    return buf.getvalue()

def get_001() -> dict | None:

    files = sorted(LOTTIES_DIR.glob("*.json"))

    if not files: return None

    with open(files[0], encoding="utf-8") as f: return json.load(f)

def main_kb():

    return InlineKeyboardMarkup(inline_keyboard=[[

        InlineKeyboardButton(text="🖼 JSON (Logo)", callback_data="json"),

        InlineKeyboardButton(text="✏️ Text", callback_data="text"),

        InlineKeyboardButton(text="🎨 SVG", callback_data="svg"),

    ]])

def select_kb():

    return InlineKeyboardMarkup(inline_keyboard=[[

        InlineKeyboardButton(text="🎯 FULL (102 ta)", callback_data="full"),

    ]])

def parse_indices(text: str) -> list[int] | None:

    parts = text.replace(",", ".").replace(" ", ".").split(".")

    result = []

    for p in parts:

        p = p.strip();

        if not p: continue

        try:

            n = int(p)

            if n < 1 or n > 102: return None

            result.append(n)

        except ValueError: return None

    return result

@dp.message(CommandStart())

async def cmd_start(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    await state.clear()

    await msg.answer("Welcome! Choose an animation type:", reply_markup=main_kb())

@dp.callback_query(F.data.in_(["json", "text", "svg"]))

async def cb_type(call: CallbackQuery, state: FSMContext):

    if call.from_user.id != ALLOWED_USER: return

    await call.answer(); await state.update_data(mode=call.data)

    await call.message.edit_text("Which animations do you want to modify?", reply_markup=select_kb())

    await state.set_state(S.select)

@dp.callback_query(S.select, F.data == "full")

async def cb_select_full(call: CallbackQuery, state: FSMContext):

    if call.from_user.id != ALLOWED_USER: return

    await call.answer(); await state.update_data(selected=list(range(1, 140)))

    await call.message.edit_text(
        f"🎨 Enter color for <b>BA0047</b> (and white Stroke):\n"
        f"<i>Default: #{DEFAULT_COLOR_1} — tap Skip to use default</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_ba")
    )

    await state.set_state(S.ask_ba)

@dp.message(S.select)

async def select_indices(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    indices = parse_indices(msg.text)

    if indices is None:

        await msg.answer("⚠️ Invalid number format.")

        return

    await state.update_data(selected=indices)

    await msg.answer(
        f"🎨 Enter color for <b>BA0047</b> (and white Stroke):\n"
        f"<i>Default: #{DEFAULT_COLOR_1} — tap Skip to use default</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_ba")
    )

    await state.set_state(S.ask_ba)

# ── Skip callbacks ────────────────────────────────────────────────────────────

@dp.callback_query(S.ask_ba, F.data == "skip_ba")
async def skip_ba(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ALLOWED_USER: return
    await call.answer()
    await state.update_data(ba_color=hex_to_rgba(DEFAULT_COLOR_1))
    await call.message.edit_text(
        f"🎨 New color for <b>FF4A52 & 44BEF9</b> (HEX):\n"
        f"<i>Default: #{DEFAULT_COLOR_2} — tap Skip to use default</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_ff")
    )
    await state.set_state(S.ask_ff)

@dp.callback_query(S.ask_ff, F.data == "skip_ff")
async def skip_ff(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ALLOWED_USER: return
    await call.answer()
    await state.update_data(ff_color=hex_to_rgba(DEFAULT_COLOR_2))
    d = await state.get_data()
    if d["mode"] == "json":
        await call.message.edit_text("📁 Send the Logo <b>.json</b> file:", parse_mode="HTML")
        await state.set_state(S.json_file)
    elif d["mode"] == "svg":
        await call.message.edit_text("🎨 Send the Logo <b>.svg</b> file:", parse_mode="HTML")
        await state.set_state(S.svg_file)
    else:
        await call.message.edit_text("✏️ Enter emoji text:", parse_mode="HTML")
        await state.set_state(S.text_input)

@dp.callback_query(S.logo_c1, F.data == "skip_logo_c1")
async def skip_logo_c1(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ALLOWED_USER: return
    await call.answer()
    await state.update_data(logo_c1=None)
    await call.message.edit_text(
        "🎨 <b>Logo color 2</b> (when BA/FF colors are absent):\n<i>Tap Skip to leave unchanged</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_logo_c2")
    )
    await state.set_state(S.logo_c2)

@dp.callback_query(S.logo_c2, F.data == "skip_logo_c2")
async def skip_logo_c2(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ALLOWED_USER: return
    await call.answer()
    await state.update_data(logo_c2=None)
    d = await state.get_data()
    if d.get("layers") is None:
        c = d.get("logo_c1") or hex_to_rgba("FFFFFF")
        d["layers"] = await asyncio.get_running_loop().run_in_executor(None, lambda: make_text_layers(d["user_text"], c))
        await state.update_data(layers=d["layers"])
    await state.update_data(scale=100.0)
    await send_preview(call.message, state)
    await state.set_state(S.scale)

# ── Scale callbacks ───────────────────────────────────────────────────────────

@dp.callback_query(S.scale, F.data.startswith("scale_"))
async def scale_button(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ALLOWED_USER: return
    await call.answer()
    action = call.data[len("scale_"):]
    if action == "done":
        await call.message.edit_reply_markup(reply_markup=None)
        d = await state.get_data()
        await state.clear()
        # Pass real user id explicitly — call.message.from_user would be the bot
        await run_pack(call.message, d, uid=call.from_user.id)
        return
    d = await state.get_data()
    cur = d.get("scale", 100.0)
    try:
        if action.startswith("+"):
            new_s = cur + float(action[1:])
        elif action.startswith("-"):
            new_s = cur - float(action[1:])
        else:
            new_s = float(action)
    except:
        return
    await state.update_data(scale=new_s)
    await send_preview(call.message, state)

# ── Message handlers ──────────────────────────────────────────────────────────

@dp.message(S.ask_ba)

async def ask_ba(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    t = msg.text.strip(); color = None

    if t.lower() != "skip":

        try: color = hex_to_rgba(t)

        except:

            await msg.answer("⚠️ Invalid HEX color."); return

    else:

        color = hex_to_rgba(DEFAULT_COLOR_1)

    await state.update_data(ba_color=color)

    await msg.answer(
        f"🎨 New color for <b>FF4A52 & 44BEF9</b> (HEX):\n"
        f"<i>Default: #{DEFAULT_COLOR_2} — tap Skip to use default</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_ff")
    )

    await state.set_state(S.ask_ff)

@dp.message(S.ask_ff)

async def ask_ff(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    t = msg.text.strip(); color = None

    if t.lower() != "skip":

        try: color = hex_to_rgba(t)

        except:

            await msg.answer("⚠️ Invalid HEX color."); return

    else:

        color = hex_to_rgba(DEFAULT_COLOR_2)

    await state.update_data(ff_color=color)

    d = await state.get_data()

    if d["mode"] == "json":

        await msg.answer("📁 Send the Logo <b>.json</b> file:", parse_mode="HTML")

        await state.set_state(S.json_file)

    elif d["mode"] == "svg":

        await msg.answer("🎨 Send the Logo <b>.svg</b> file:", parse_mode="HTML")

        await state.set_state(S.svg_file)

    else:

        await msg.answer("✏️ Enter emoji text:", parse_mode="HTML")

        await state.set_state(S.text_input)

@dp.message(S.json_file, F.document)

async def got_json(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    if not (msg.document.file_name or "").endswith(".json"):

        await msg.answer("⚠️ Only .json files allowed!"); return

    f = await bot.get_file(msg.document.file_id); buf = io.BytesIO(); await bot.download_file(f.file_path, buf); buf.seek(0)

    data = json.load(buf)

    await state.update_data(layers=data.get("layers", []), extra=[a for a in data.get("assets", []) if a.get("id") != LOGO_ID])

    await msg.answer(
        "🎨 <b>Logo color 1</b> (when BA/FF colors exist):\n<i>Tap Skip to leave unchanged</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_logo_c1")
    )

    await state.set_state(S.logo_c1)

@dp.message(S.svg_file, F.document)

async def got_svg(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    if not (msg.document.file_name or "").lower().endswith(".svg"):

        await msg.answer("⚠️ Only .svg files allowed!"); return

    f = await bot.get_file(msg.document.file_id); buf = io.BytesIO(); await bot.download_file(f.file_path, buf); buf.seek(0)

    layers = await asyncio.get_running_loop().run_in_executor(None, lambda: make_svg_layers(buf.read()))

    await state.update_data(layers=layers, extra=[])

    await msg.answer(
        "🎨 <b>Logo color 1</b> (when BA/FF colors exist):\n<i>Tap Skip to leave unchanged</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_logo_c1")
    )

    await state.set_state(S.logo_c1)

@dp.message(S.text_input)

async def got_text(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    await state.update_data(user_text=msg.text.strip(), layers=None, extra=[])

    await msg.answer(
        "🎨 <b>Logo color 1</b> (when BA/FF colors exist):\n<i>Tap Skip to leave unchanged</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_logo_c1")
    )

    await state.set_state(S.logo_c1)

@dp.message(S.logo_c1)

async def got_logo_c1(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    t = msg.text.strip(); color = None

    if t.lower() != "skip":

        try: color = hex_to_rgba(t)

        except:

            await msg.answer("⚠️ Invalid HEX."); return

    await state.update_data(logo_c1=color)

    await msg.answer(
        "🎨 <b>Logo color 2</b> (when BA/FF colors are absent):\n<i>Tap Skip to leave unchanged</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("skip_logo_c2")
    )

    await state.set_state(S.logo_c2)

@dp.message(S.logo_c2)

async def got_logo_c2(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    t = msg.text.strip(); color = None

    if t.lower() != "skip":

        try: color = hex_to_rgba(t)

        except:

            await msg.answer("⚠️ Invalid HEX."); return

    await state.update_data(logo_c2=color)

    d = await state.get_data()

    if d.get("layers") is None:

        c = d.get("logo_c1") or color or hex_to_rgba("FFFFFF")

        d["layers"] = await asyncio.get_running_loop().run_in_executor(None, lambda: make_text_layers(d["user_text"], c))

        await state.update_data(layers=d["layers"])

    await state.update_data(scale=100.0); await send_preview(msg, state); await state.set_state(S.scale)

async def send_preview(msg: Message, state: FSMContext):

    d = await state.get_data(); anim = get_001()

    if not anim: await msg.answer("❌ lotties/ is empty!"); return

    mod = build_anim(anim, d["layers"], d.get("extra", []), d.get("scale", 100.0), d.get("ba_color"), d.get("ff_color"), d.get("logo_c1"), d.get("logo_c2"), 1)

    await msg.answer_document(
        BufferedInputFile(to_tgs(mod), filename="preview.tgs"),
        caption=f"👀 Preview — Scale: {d['scale']}%\nUse the buttons to adjust size, or type a value (+5, -10, 75…)\nPress ✅ Done when ready.",
        reply_markup=scale_kb()
    )

@dp.message(S.scale)

async def scale_input(msg: Message, state: FSMContext):

    if msg.from_user.id != ALLOWED_USER: return

    t = msg.text.strip()

    if t.upper() == "DONE":
        d = await state.get_data()
        await state.clear()
        await run_pack(msg, d)
        return

    d = await state.get_data(); cur = d.get("scale", 100.0)

    try:

        if t.startswith("+"): new_s = cur + float(t[1:])

        elif t.startswith("-"): new_s = cur - float(t[1:])

        else: new_s = float(t)

    except: return

    await state.update_data(scale=new_s); await send_preview(msg, state)

async def run_pack(msg: Message, d: dict, uid: int | None = None):
    import traceback

    # uid may be passed explicitly when msg is a bot-sent message (callback context)
    if uid is None:
        uid = msg.from_user.id
    me = await bot.get_me()

    name = f"pk{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}_by_{me.username}"

    stat = await msg.answer(f"⚙️ Processing... <code>{name}</code>", parse_mode="HTML")

    # ── Check lotties dir ──
    if not LOTTIES_DIR.exists() or not any(LOTTIES_DIR.glob("*.json")):
        await stat.edit_text(f"❌ Error: <code>lotties/</code> folder is empty or missing.", parse_mode="HTML")
        return

    # ── Check layers ──
    if not d.get("layers"):
        await stat.edit_text("❌ Error: No logo/text layers found in state. Please restart with /start.", parse_mode="HTML")
        return

    files = []

    for fp in sorted(LOTTIES_DIR.glob("*.json")):

        try:

            n = int(fp.stem)

            if n in set(d.get("selected", [])): files.append((fp, n))

        except: pass

    if not files:
        await stat.edit_text("❌ Error: No matching lottie files found for selected indices.", parse_mode="HTML")
        return

    created = False; ok = 0; last_error = ""

    for i, (fp, n) in enumerate(files):

        try:

            with open(fp, encoding="utf-8") as f: anim = json.load(f)

            mod = build_anim(anim, d["layers"], d.get("extra", []), d.get("scale", 100.0), d.get("ba_color"), d.get("ff_color"), d.get("logo_c1"), d.get("logo_c2"), n)

            sd = {"sticker": BufferedInputFile(to_tgs(mod), filename="s.tgs"), "emoji_list": ["⭐️"], "format": "animated"}

            if not created:
                await bot.create_new_sticker_set(user_id=uid, name=name, title=f"Pack {name[:5]}", stickers=[sd], sticker_type="custom_emoji")
                created = True
            else:
                await bot.add_sticker_to_set(user_id=uid, name=name, sticker=sd)

            ok += 1

            if ok % 10 == 0: await stat.edit_text(f"⚙️ {ok}/{len(files)} ✅")

        except Exception as e:
            tb = traceback.format_exc()
            last_error = f"File {fp.name}: {type(e).__name__}: {e}"
            logger.error(f"[run_pack] {last_error}\n{tb}")
            # Send first error to chat so you can see it immediately
            if not created and i == 0:
                short = (last_error[:300] + "…") if len(last_error) > 300 else last_error
                await stat.edit_text(
                    f"❌ Failed on first sticker:\n<code>{short}</code>",
                    parse_mode="HTML"
                )
                return

    if created:
        await stat.edit_text(
            f"✅ Done! ({ok}/{len(files)} stickers)\n"
            f"🔗 <a href='https://t.me/addemoji/{name}'>t.me/addemoji/{name}</a>"
            + (f"\n⚠️ {len(files)-ok} failed — check logs" if ok < len(files) else ""),
            parse_mode="HTML"
        )
    else:
        short = (last_error[:400] + "…") if len(last_error) > 400 else last_error
        await stat.edit_text(
            f"❌ Error — nothing was created.\n<code>{short}</code>",
            parse_mode="HTML"
        )

async def main(): await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
