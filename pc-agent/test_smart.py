"""Run with:  python -m unittest -v test_smart"""
import unittest

import smart
from matcher import Match
from ocr import Screen, Word


def kinds(p):
    return [type(s).__name__ + ":" + (s.intent if isinstance(s, Match) else getattr(s, "hint", "") or "")
            for s in p.steps]


class PlanTest(unittest.TestCase):
    def test_click_by_name(self):
        for text, names, kind in [
            ("select Gmail", ["gmail"], "left"),
            ("click on Sign in", ["sign in"], "left"),
            ("double click the Recycle Bin", ["recycle bin"], "double"),
            ("right click on Downloads", ["downloads"], "right"),
            ("जीमेल पर क्लिक करो", ["gmail"], "left"),
            ("Gmail ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡು", ["gmail"], "left"),
            ("Gmail పై క్లిక్ చేయి", ["gmail"], "left"),
        ]:
            with self.subTest(text=text):
                p = smart.plan(text)
                self.assertIsNotNone(p)
                step = p.steps[0]
                self.assertIsInstance(step, smart.ClickStep)
                self.assertEqual(step.names[:1], names[:1])
                self.assertEqual(step.kind, kind)

    def test_position_hint(self):
        p = smart.plan("go to top right and select Gmail")
        self.assertEqual(len(p.steps), 1)
        self.assertEqual(p.steps[0].names[0], "gmail")
        self.assertEqual(p.steps[0].hint, "top_right")
        p = smart.plan("click Gmail at the top right")
        self.assertEqual(p.steps[0].hint, "top_right")
        p = smart.plan("ऊपर दाएं जीमेल पर क्लिक करो")
        self.assertEqual(p.steps[0].hint, "top_right")

    def test_chains(self):
        p = smart.plan("open chrome and go to gmail and click compose")
        self.assertEqual(kinds(p), ["Match:open_app", "Match:open_site", "ClickStep:"])
        p = smart.plan("search cats and dogs")           # 'and' inside a search stays one step
        self.assertEqual(kinds(p), ["Match:google_search"])
        self.assertIn("dogs", p.steps[0].arg)
        p = smart.plan("open youtube and search lofi songs")   # search goes to YouTube
        self.assertEqual(kinds(p), ["Match:open_site", "Match:youtube_search"])
        p = smart.plan("क्रोम खोलो और फिर जीमेल पर क्लिक करो")
        self.assertEqual(kinds(p), ["Match:open_app", "ClickStep:"])
        p = smart.plan("volume up then take a screenshot")
        self.assertEqual(kinds(p), ["Match:volume_up", "Match:screenshot"])

    def test_builtins_unchanged(self):
        for text, intent in [("select all", "select_all"), ("click", "click"), ("press enter", "enter"),
                             ("open chrome", "open_app"), ("double click", "double_click")]:
            with self.subTest(text=text):
                p = smart.plan(text)
                self.assertTrue(p.is_single_builtin)
                self.assertEqual(p.steps[0].intent, intent)

    def test_from_real_log(self):
        """Commands that confused BOT before (from bot.log)."""
        cases = [
            ("navigate to restart to update", "ClickStep", "restart to update"),   # NOT restart the PC!
            ("in the chat text box say is it done?", "type_text", "is it done?"),
            ("in the textbox say you didn't", "type_text", "you didn't"),
            ("give a prompt saying is it done", "type_text", "is it done"),
            ("continue the prompt saying now everything is working", "type_text", "now everything is working"),
            ("type here is it done?", "type_text", "is it done?"),
            ("open a new tab in notepad", "new_tab", None),
            ("close one more notepad", "close_app", ""),
            ("close all notepads", "close_app", "all"),
            ("send it", "send_enter", None),
            ("delete it", "delete_key", None),
            ("delete it permanently", "delete_key", "permanent"),
            ("click that", "click", None),
            ("double click here", "double_click", None),
            ("open it", "enter", None),
            ("come down a little", "scroll_down", "little"),
            ("go up a lot", "scroll_up", "lot"),
            ("नीचे जाओ", "scroll_down", None),
            ("select all", "select_all", None),
            ("go to desktop", "show_desktop", None),
            ("डिलीट करो", "delete_key", None),
            ("भेज दो", "send_enter", None),
        ]
        for text, want, detail in cases:
            with self.subTest(text=text):
                p = smart.plan(text)
                self.assertIsNotNone(p)
                step = p.steps[0]
                if want == "ClickStep":
                    self.assertIsInstance(step, smart.ClickStep)
                    self.assertEqual(step.said, detail)
                else:
                    self.assertIsInstance(step, Match)
                    self.assertEqual(step.intent, want)
                    if detail is not None:
                        self.assertEqual(step.arg, detail)

    def test_chain_from_log(self):
        p = smart.plan("come down a little and select open 5.5 model")
        self.assertEqual(kinds(p), ["Match:scroll_down", "ClickStep:"])
        p = smart.plan("type hello and send it")
        self.assertEqual(kinds(p), ["Match:type_text", "Match:send_enter"])
        # "send a mail to rahul" is NOT "press Enter"
        m = smart.plan("send a mail to rahul about tomorrow's meeting")
        self.assertTrue(m is None or not any(isinstance(s, Match) and s.intent == "send_enter" for s in m.steps))

    def test_nonsense(self):
        self.assertIsNone(smart.plan("blah blah"))
        self.assertIsNone(smart.plan("open chrome and blah blah"))


class FindTest(unittest.TestCase):
    def setUp(self):
        W = lambda t, x, y: Word(t, x, y, 10 * len(t), 20)
        self.scr = Screen(lines=[
            [W("Gmail", 1600, 20), W("Images", 1680, 20)],          # top right
            [W("Gmail", 100, 900)],                                  # bottom left
            [W("Sign", 800, 500), W("in", 845, 500)],                # middle
            [W("Recycle", 30, 30), W("Bin", 110, 30)],
        ], left=0, top=0, width=1920, height=1080)

    def test_find(self):
        hits = smart.find_on_screen(self.scr, ["gmail"], "top_right")
        self.assertEqual(len(hits), 1)
        self.assertGreater(hits[0][1], 1500)
        hits = smart.find_on_screen(self.scr, ["gmail"], None)
        self.assertEqual(len(hits), 2)
        self.assertLess(hits[0][2], 100)                            # no hint: top one first
        self.assertEqual(smart.find_on_screen(self.scr, ["sign in"], None)[0][3], "Sign in")
        self.assertEqual(smart.find_on_screen(self.scr, ["recycle bin"], None)[0][3], "Recycle Bin")
        self.assertEqual(smart.find_on_screen(self.scr, ["gmial"], None)[0][3], "Gmail")  # small typo ok
        self.assertEqual(smart.find_on_screen(self.scr, ["youtube"], None), [])

    def test_translit(self):
        self.assertEqual(smart.find_on_screen(self.scr, [smart.translit("साइन इन")], None, exact_known=False)[0][3],
                         "Sign in")


if __name__ == "__main__":
    unittest.main()
