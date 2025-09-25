[app]
title = Neon Tagger
package.name = neon_tagger
package.domain = com.sampras0915
source.dir = .
source.include_exts = py,ttf
include_patterns = *.ttf

version = 0.1.0
requirements = python3,kivy==2.3.0,pillow
orientation = portrait
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 0

[android]
android.api = 33
android.minapi = 21
