[app]
title = neon_tagger
package.name = neon_tagger
package.domain = com.sampras0915
source.dir = .
source.include_exts = py,ttf
include_patterns = *.ttf

version = 0.1.0
requirements = python3,kivy,android
orientation = portrait
fullscreen = 0

[buildozer]
env.CFLAGS = -I/data/data/com.termux/files/usr/include
env.LDFLAGS = -L/data/data/com.termux/files/usr/lib
env.PYTHONFORANDROID_NO_DEPS_CHECK = 1
env.P4A_SKIP_DEPS_CHECK = 1
env.P4A_NO_DEPS_CHECK = 1
log_level = 2
warn_on_root = 0

[android]
android.api = 33
android.minapi = 21
