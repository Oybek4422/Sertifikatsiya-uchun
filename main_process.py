# C:\tris_autofill\restored\playwright_bot\main_process.py
import os
import re
import time
import importlib.util
import importlib.machinery

from .logger import logger

_PYC_PATH = os.path.join(os.path.dirname(__file__), "main_process.pyc")

_loader = importlib.machinery.SourcelessFileLoader("playwright_bot._orig_main_process", _PYC_PATH)
_spec = importlib.util.spec_from_file_location("playwright_bot._orig_main_process", _PYC_PATH, loader=_loader)
_orig = importlib.util.module_from_spec(_spec)
_loader.exec_module(_orig)

for _k, _v in vars(_orig).items():
    if _k.startswith("__"):
        continue
    if _k in {"main_process_tris_pw", "_v"}:
        continue
    globals()[_k] = _v

_ORIG_SAVE_ALL_ADDED_BLOCKS = getattr(_orig, "save_all_added_blocks", None)

SPEED_K = 1.3
UNIT_FIND_MAX_SEC = 15


def _wait(page, ms: int):
    page.wait_for_timeout(int(ms * SPEED_K))


def _set_value_react_textarea(locator, page, value: str, field_name: str, timeout_ms: int = 25000):
    locator.wait_for(state="visible", timeout=int(timeout_ms * SPEED_K))
    try:
        locator.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        locator.click()
    except Exception:
        pass
    _wait(page, 60)

    locator.evaluate(
        """
        (el, val) => {
          const value = String(val ?? "");
          let target = el;
          const tag = (target.tagName || "").toLowerCase();
          if (tag !== "input" && tag !== "textarea") {
            const inner = target.querySelector && target.querySelector("input,textarea");
            if (inner) target = inner;
          }
          if (target.disabled || target.readOnly) return;
          try { target.focus(); } catch(e){}
          const proto = Object.getPrototypeOf(target);
          const desc = Object.getOwnPropertyDescriptor(proto, "value");
          const setter = desc && desc.set;
          if (setter) setter.call(target, value);
          else target.value = value;
          target.dispatchEvent(new Event("input", { bubbles: true }));
          target.dispatchEvent(new Event("change", { bubbles: true }));
        }
        """,
        value,
    )
    _wait(page, 120)
    try:
        page.keyboard.press("Tab")
    except Exception:
        pass
    _wait(page, 150)
    logger.info("✅ '%s' kiritildi.", field_name)


def _get_first_nonempty(d: dict, keys: list[str]) -> str:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _get_nd_from_subtest(subtest: dict) -> str:
    candidates = [
        "requirements_nd", "nd_requirements", "requirements", "nd",
        "standard_req", "normative_value",
        "Требования НД", "Me'yoriy qiymat",
        "nd_text", "req_text", "requirements_text",
        "test_requirements", "method_requirements",
        "Q",
    ]
    v = _get_first_nonempty(subtest, candidates)
    if v:
        return v
    for vv in subtest.values():
        if isinstance(vv, str):
            s = vv.strip()
            if s and ("ГОСТ" in s or "O'zDSt" in s or "п." in s):
                return s
    return ""


def _detect_k_code(subtest: dict) -> str:
    direct_keys = [
        "k", "K", "col_k", "K_column", "type_k",
        "type_code", "kind_code", "method_code",
        "test_kind_code", "test_type_code",
        "quant_qual_code",
    ]
    for k in direct_keys:
        if k in subtest:
            s = str(subtest.get(k)).strip()
            if s in ("1", "2"):
                return s
    for k, v in subtest.items():
        kn = str(k).lower()
        if any(tok in kn for tok in ("type", "kind", "method", "тип", "вид", "category", "klass")):
            s = str(v).strip()
            if s in ("1", "2"):
                return s
    return ""


def _is_quantitative(subtest: dict) -> bool:
    k = _detect_k_code(subtest)
    if k == "2":
        return True
    if k == "1":
        return False
    return True


def _click_radio_type_by_value(page, scope, want_val: str, label_name: str) -> bool:
    inp = scope.locator(f"input[type='radio'][value='{want_val}']").first
    if not inp.count():
        logger.warning("⚠️ Radio topilmadi: value=%s", want_val)
        return False
    try:
        if inp.is_checked():
            logger.info("ℹ️ Radio already checked: %s", label_name)
            return True
    except Exception:
        pass
    try:
        inp.scroll_into_view_if_needed()
    except Exception:
        pass
    _wait(page, 60)
    try:
        inp.click(force=True, timeout=int(4000 * SPEED_K))
        _wait(page, 120)
        logger.info("✅ Radio bosildi: %s", label_name)
        return True
    except Exception:
        pass
    try:
        lbl = inp.locator("xpath=ancestor::label[1]")
        if lbl.count():
            lbl.click(force=True, timeout=int(4000 * SPEED_K))
            _wait(page, 120)
            logger.info("✅ Radio bosildi (label): %s", label_name)
            return True
    except Exception:
        pass
    try:
        inp.evaluate("(el) => el.click()")
        _wait(page, 120)
        logger.info("✅ Radio bosildi (js): %s", label_name)
        return True
    except Exception as e:
        logger.warning("⚠️ Radio bosilmadi: %s | %s", label_name, e)
        return False


def _ensure_correct_type_after_add(page, row_scope, is_quant: bool):
    if is_quant:
        logger.info("ℹ️ K=2 => Количественный default. Radio bosilmaydi.")
        return True
    return _click_radio_type_by_value(page, row_scope, want_val="2", label_name="Качественный (K=1)")


def _open_units_editor_if_needed(page, scope):
    pencil = scope.locator("i.tabler-pencil.text-primary:visible").first
    if not pencil.count():
        logger.warning("⚠️ Pencil topilmadi (unit editor chiqmasligi mumkin).")
        return False
    try:
        pencil.scroll_into_view_if_needed()
    except Exception:
        pass
    _wait(page, 80)
    try:
        pencil.click(force=True)
        _wait(page, 350)
        logger.info("✅ ✏️ Pencil bosildi.")
        return True
    except Exception as e:
        logger.warning("⚠️ Pencil bosilmadi: %s", e)
        return False


def _find_unit_input_by_label(scope, label_text: str):
    anchor = scope.locator(
        f"xpath=.//*[normalize-space()='{label_text}' or contains(normalize-space(), '{label_text}')]"
    ).first
    if not anchor.count():
        return None

    container = anchor.locator(
        "xpath=ancestor::*[self::div or self::td][.//input[@placeholder='🔍 Search...']][1]"
    ).first
    if container.count():
        inp = container.locator("input[placeholder='🔍 Search...']:visible").first
        if inp.count():
            return inp

    near = anchor.locator("xpath=following::input[@placeholder='🔍 Search...'][1]").first
    if near.count():
        return near

    return None


# =========================
# ✅ AUTOCOMPLETE UNIT FIX
# =========================

def _autocomplete_type_only(page, inp, text: str):
    inp.wait_for(state="visible", timeout=int(15000 * SPEED_K))
    try:
        inp.scroll_into_view_if_needed()
    except Exception:
        pass

    _wait(page, 80)
    inp.click(force=True)
    _wait(page, 60)

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    _wait(page, 80)

    page.keyboard.type(str(text), delay=int(35 * SPEED_K))
    _wait(page, 180)

    # dropdownni majburan ochish
    try:
        page.keyboard.press("ArrowDown")
    except Exception:
        pass
    _wait(page, 150)


def _normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _find_option_and_click(page, full_value: str) -> bool:
    want = _normalize_space(full_value)
    if not want:
        return False

    listbox = page.locator("ul[role='listbox']:visible").first
    if not listbox.count():
        listbox = page.locator("[role='listbox']:visible").first

    start = time.time()
    while time.time() - start < UNIT_FIND_MAX_SEC:
        opts = page.locator("[role='option']:visible")
        cnt = opts.count()

        for i in range(min(cnt, 120)):
            try:
                t = opts.nth(i).inner_text(timeout=int(800 * SPEED_K))
            except Exception:
                continue
            if _normalize_space(t) == want:
                try:
                    opts.nth(i).click(force=True, timeout=int(3000 * SPEED_K))
                    _wait(page, 180)
                    return True
                except Exception:
                    pass

        # scroll listbox
        if listbox.count():
            try:
                listbox.evaluate("el => { el.scrollTop = el.scrollTop + el.clientHeight; }")
            except Exception:
                try:
                    page.mouse.wheel(0, 800)
                except Exception:
                    pass
        else:
            try:
                page.mouse.wheel(0, 800)
            except Exception:
                pass

        _wait(page, 220)

    return False


def _pick_unit_autocomplete(page, inp, full_value: str, field_name: str) -> bool:
    full_value = (full_value or "").strip()
    if not full_value:
        return False

    search_term = full_value.split("(")[0].strip() or full_value

    try:
        _autocomplete_type_only(page, inp, search_term)

        ok = _find_option_and_click(page, full_value)
        if ok:
            logger.info("✅ %s tanlandi: %s", field_name, full_value)
            return True

        logger.warning("⚠️ %s topilmadi (10s): %s", field_name, full_value)
        return False

    except Exception as e:
        logger.warning("⚠️ %s autocomplete xato: %s", field_name, e)
        return False


# =========================
# ✅ UNIT VALUE FLEXIBLE EXTRACT
# =========================

def _guess_units_flexible(subtest: dict):
    """
    1) Key nomidan unitlarni topish (unit/izm/ед/osn/vspom/main/aux/R/S)
    2) Topilmasa, value ichidan taxmin:
       - "(...)" bor uzunroq => base
       - juda qisqa (<=6) => aux
    """
    base = ""
    aux = ""

    # 1) key pattern
    for k, v in subtest.items():
        if v is None:
            continue
        vs = str(v).strip()
        if not vs:
            continue
        kn = str(k).lower()

        if not base and (kn in ("r", "основная", "основн", "osn", "main", "base")
                         or ("ос" in kn and "ед" in kn) or ("osn" in kn and "ed" in kn)
                         or ("main" in kn and "unit" in kn) or ("base" in kn and "unit" in kn)
                         or ("unit" in kn and "main" in kn)):
            base = vs
            continue

        if not aux and (kn in ("s", "вспомогательная", "вспом", "vspom", "aux", "secondary")
                        or ("всп" in kn and "ед" in kn) or ("vspom" in kn and "ed" in kn)
                        or ("aux" in kn and "unit" in kn) or ("secondary" in kn and "unit" in kn)
                        or ("unit" in kn and "aux" in kn)):
            aux = vs
            continue

    # 2) value heuristic
    if not base:
        for v in subtest.values():
            if v is None:
                continue
            s = str(v).strip()
            if not s:
                continue
            if "(" in s and ")" in s and 3 <= len(s) <= 60:
                base = s
                break

    if not aux:
        for v in subtest.values():
            if v is None:
                continue
            s = str(v).strip()
            if not s:
                continue
            # "g", "A", "V", "W", "kg" ... kabi
            if len(s) <= 6 and re.fullmatch(r"[A-Za-zА-Яа-яµ°ΩΩ%/.\-]+", s):
                aux = s
                break

    return base, aux


def _fill_units_quantitative(page, row_scope, subtest: dict):
    # avval eski aniq keys
    base_unit = _get_first_nonempty(subtest, ["R", "r", "osn_ed_izm", "Осн. ед. изм.", "base_unit", "unit_main"])
    aux_unit = _get_first_nonempty(subtest, ["S", "s", "vspom_ed_izm", "Вспом. ед. изм.", "aux_unit", "unit_aux"])

    # ✅ flexible fallback
    if not base_unit and not aux_unit:
        base_unit, aux_unit = _guess_units_flexible(subtest)

    # ✅ agar hammasi bo'sh bo'lsa: debug keys chiqaramiz
    if not base_unit and not aux_unit:
        keys_preview = ", ".join(list(map(str, list(subtest.keys())[:40])))
        logger.warning("⚠️ R/S unit topilmadi. subtest keys preview: %s", keys_preview)
        logger.info("ℹ️ R/S birliklar yo'q (skip).")
        return

    logger.info("ℹ️ Unit detected -> base='%s' aux='%s'", base_unit, aux_unit)

    _open_units_editor_if_needed(page, row_scope)

    base_inp = _find_unit_input_by_label(row_scope, "Осн. ед. изм.")
    aux_inp = _find_unit_input_by_label(row_scope, "Вспом. ед. изм.")

    all_inputs = row_scope.locator("input[placeholder='🔍 Search...']:visible")
    if base_inp is None and all_inputs.count() >= 1:
        base_inp = all_inputs.nth(0)
    if aux_inp is None and all_inputs.count() >= 2:
        aux_inp = all_inputs.nth(1)

    if base_unit and base_inp is not None:
        _pick_unit_autocomplete(page, base_inp, base_unit, "Осн. ед. изм.")
    elif base_unit:
        logger.warning("⚠️ Осн. ед. изм. input topilmadi (hatto fallback ham).")

    if aux_unit and aux_inp is not None:
        _pick_unit_autocomplete(page, aux_inp, aux_unit, "Вспом. ед. изм.")
    elif aux_unit:
        logger.warning("⚠️ Вспом. ед. изм. input topilmadi (hatto fallback ham).")


def add_test_block_and_fill(page, subtest, *args, **kwargs):
    if not isinstance(subtest, dict):
        logger.error("❌ subtest dict emas.")
        return False

    name_val = str(subtest.get("subtest_name", "")).strip()
    nd_val = _get_nd_from_subtest(subtest)

    rows = page.locator("tbody tr")
    before = rows.count()

    btn = page.get_by_role("button", name=re.compile(r"Add\s*params", re.I)).first
    try:
        btn.scroll_into_view_if_needed()
    except Exception:
        pass
    _wait(page, 120)
    btn.click()

    page.wait_for_function(
        "(n) => document.querySelectorAll('tbody tr').length > n",
        arg=before,
        timeout=int(35000 * SPEED_K),
    )
    _wait(page, 300)

    rows = page.locator("tbody tr")
    new_row = rows.nth(rows.count() - 1)

    is_quant = _is_quantitative(subtest)
    k_code = _detect_k_code(subtest)
    logger.info("ℹ️ K code: %s | type: %s", k_code or "?", "Колич" if is_quant else "Кач")

    _ensure_correct_type_after_add(page, new_row, is_quant)

    name_field = new_row.locator("textarea[placeholder*='Parametr nomini']").first
    nd_field = new_row.locator(
        "textarea[placeholder*=\"Me'yoriy qiymat\"], textarea[placeholder*=\"Me’yoriy qiymat\"]"
    ).first

    if not name_field.count():
        ta = new_row.locator("textarea:visible")
        if ta.count() >= 1:
            name_field = ta.nth(0)

    if not nd_field.count():
        ta = new_row.locator("textarea:visible")
        if ta.count() >= 2:
            nd_field = ta.nth(1)

    if name_field.count():
        _set_value_react_textarea(name_field, page, name_val, "Наименование испытаний (E)")
    else:
        logger.warning("⚠️ Наименование испытаний input topilmadi.")

    if nd_field.count():
        _set_value_react_textarea(nd_field, page, nd_val, "Требования НД (Q)")
    else:
        logger.warning("⚠️ Требования НД input topilmadi.")

    if is_quant:
        _fill_units_quantitative(page, new_row, subtest)

    return True


def save_all_added_blocks(page, *args, **kwargs):
    if _ORIG_SAVE_ALL_ADDED_BLOCKS is None:
        logger.warning("⚠️ Original save_all_added_blocks topilmadi.")
        return None

    res = _ORIG_SAVE_ALL_ADDED_BLOCKS(page, *args, **kwargs)

    try:
        anim = page.locator("img[alt='animation']:visible").first
        if anim.count():
            try:
                anim.scroll_into_view_if_needed()
            except Exception:
                pass
            _wait(page, 120)
            anim.click(force=True)
            _wait(page, 500)
            logger.info("✅ Animation bosildi (Entering result uchun).")
    except Exception as e:
        logger.warning("⚠️ Animation bosilmadi (skip): %s", e)

    return res


def main_process_tris_pw(page, grouped_tests, *args, **kwargs):
    try:
        try:
            _orig.choose_language(page, "English")
        except Exception as e:
            logger.warning(f"⚠️ English tanlash topilmadi, o'tkazib yuborildi: {e}")

        try:
            sl_code = _orig.extract_sl_code_from_sidebar(page)
        except Exception as e:
            sl_code = None
            logger.warning(f"⚠️ SL code olinmadi (davom etaman): {e}")

        _orig.current_lab = sl_code
        logger.info(f"✅ current_lab auto-set qilindi: {sl_code}")

        _orig.add_test_block_and_fill = add_test_block_and_fill
        _orig.save_all_added_blocks = save_all_added_blocks

    except Exception as e:
        logger.warning(f"⚠️ Pre-step xatolik (davom etaman): {e}")

    return _orig.main_process_tris_pw(page, grouped_tests, *args, **kwargs)


def _v(*args, **kwargs):
    result = _orig._v(*args, **kwargs)
    if result is None or result is False:
        logger.warning("⚠️ _v(): natija topilmadi. 10 sekund manual, keyin davom etadi.")
        try:
            page = None
            for a in args:
                if hasattr(a, "wait_for_timeout"):
                    page = a
                    break
            if page is not None:
                page.wait_for_timeout(10000)
            else:
                time.sleep(10)
        except Exception:
            pass
        return True
    return result