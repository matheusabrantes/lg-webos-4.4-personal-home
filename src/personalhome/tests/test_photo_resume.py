"""Exercise the actual backdrop timer across short Home visits."""
import os
from pathlib import Path
import sys
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PyQt5.QtCore import QUrl
from PyQt5.QtQuick import QQuickView
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
APP = QGuiApplication.instance() or QGuiApplication([])


class PhotoResume(unittest.TestCase):
    def make_photo(self):
        view = QQuickView()
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.resize(1920, 1080)
        view.setSource(QUrl.fromLocalFile(str(ROOT / 'qml/PhotoBackdrop.qml')))
        self.assertEqual(view.status(), QQuickView.Ready)
        photo = view.rootObject()
        view.show()
        self.addCleanup(view.close)
        deadline = time.monotonic() + 3
        while not photo.property('ready') and time.monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(photo.property('ready'))
        return photo

    def test_expired_photo_changes_on_return_without_loading_while_hidden(self):
        photo = self.make_photo()
        photo.setProperty('interval', 180)
        photo.setProperty('cycling', True)
        QTest.qWait(40)
        photo.setProperty('cycling', False)
        QTest.qWait(200)
        self.assertEqual(photo.property('currentIndex'), 0)
        self.assertFalse(photo.property('loading'))
        photo.setProperty('cycling', True)
        QTest.qWait(90)
        self.assertEqual(photo.property('currentIndex'), 1,
                         'Every short Home visit resets the timer; the photo stays unchanged')
        photo.setProperty('cycling', False)

    def test_every_visit_shows_another_photo_before_interval_expires(self):
        photo = self.make_photo()
        photo.setProperty('interval', 600000)
        photo.setProperty('cycling', True)
        QTest.qWait(30)
        self.assertEqual(photo.property('currentIndex'), 0)
        photo.setProperty('cycling', False)
        QTest.qWait(30)
        photo.setProperty('cycling', True)
        QTest.qWait(120)
        self.assertEqual(photo.property('currentIndex'), 1)
        photo.setProperty('cycling', False)

    def test_elapsed_hidden_intervals_advance_without_background_decoding(self):
        photo = self.make_photo()
        photo.setProperty('interval', 120)
        photo.setProperty('cycling', True)
        QTest.qWait(20)
        photo.setProperty('cycling', False)
        photo.setProperty('nextChangeAt', (time.time() - .25) * 1000)
        QTest.qWait(20)
        self.assertEqual(photo.property('currentIndex'), 0)
        self.assertFalse(photo.property('loading'))
        photo.setProperty('cycling', True)
        QTest.qWait(70)
        self.assertEqual(photo.property('currentIndex'), 3)
        photo.setProperty('cycling', False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
