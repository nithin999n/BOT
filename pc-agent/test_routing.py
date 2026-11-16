"""Run with:  python -m unittest -v test_routing"""
import unittest

import router
import security
from matcher import match


class RoutingTest(unittest.TestCase):
    def test_builtin_vs_ai(self):
        builtin = ["open chrome", "volume up", "search python tutorials and examples", "play despacito",
                   "type hello and bye", "क्रोम खोलो", "ಸೌಂಡ್ ಕಡಿಮೆ ಮಾಡು", "లాక్ చేయి", "take a screenshot",
                   "how much battery is left"]
        to_ai = ["go to top right and select Gmail", "open chrome and go to gmail", "click on the submit button",
                 "open gmail and send a mail to rahul", "यूट्यूब खोलो और फिर पहला वीडियो चलाओ"]
        for text in builtin:
            with self.subTest(text=text):
                m = match(text)
                self.assertIsNotNone(m)
                self.assertTrue(router.prefer_builtin(text, m))
        for text in to_ai:
            with self.subTest(text=text):
                m = match(text)
                self.assertTrue(m is None or not router.prefer_builtin(text, m))

    def test_stop(self):
        for text in ["stop", "Stop.", "रुको", "ಸಾಕು", "ఆపు"]:
            self.assertTrue(router.is_stop(text), text)
        self.assertFalse(router.is_stop("stop the music and open chrome"))


class SafetyWordTest(unittest.TestCase):
    def test_sensitive(self):
        for text in ["delete the files in downloads", "send a mail to rahul", "share this photo",
                     "फाइल डिलीट करो", "राहुल को मैसेज भेजो", "ಫೈಲ್ ಅಳಿಸು", "ಮೆಸೇಜ್ ಕಳುಹಿಸು",
                     "ఫైల్ తొలగించు", "మెసేజ్ పంపు"]:
            self.assertTrue(security.is_sensitive(text), text)
        for text in ["open gmail", "go to top right and select Gmail", "search for shoes"]:
            self.assertFalse(security.is_sensitive(text), text)

    def test_set_and_verify(self):
        cfg = {}
        self.assertFalse(security.set_word(cfg, "ab")[0])            # too short
        self.assertTrue(security.set_word(cfg, "Mango Rocket")[0])
        self.assertNotIn("Mango", str(cfg))                           # only a hash is stored
        self.assertTrue(security.verify(cfg, "mango rocket."))        # case/punctuation don't matter
        self.assertFalse(security.verify(cfg, "banana"))
        self.assertFalse(security.set_word(cfg, "banana", old="wrong")[0])
        self.assertTrue(security.set_word(cfg, "banana", old="mango rocket")[0])
        self.assertTrue(security.verify(cfg, "Banana"))


if __name__ == "__main__":
    unittest.main()
