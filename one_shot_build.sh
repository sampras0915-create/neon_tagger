set -euo pipefail

# ===== Termux 固有の基本パス =====
PREFIX="/data/data/com.termux/files/usr"
export PATH="$PREFIX/bin:$PATH"
export CFLAGS="-I$PREFIX/include"
export CPPFLAGS="$CFLAGS"
export LDFLAGS="-L$PREFIX/lib"

# ===== 1) 必要パッケージ & Python ツール =====
pkg update -y && pkg upgrade -y
pkg install -y python git clang build-essential zlib pkg-config openjdk-17
pip install -U pip wheel setuptools
pip install -U cython virtualenv buildozer

# ===== 2) リポジトリ取得（あれば更新） =====
cd ~
if [ -d neon_tagger ]; then
  cd neon_tagger && git pull --rebase || true
else
  git clone git@github.com:sampras0915-create/neon_tagger.git
  cd neon_tagger
fi

# ===== 3) zlib チェック回避を buildozer.spec に自動追記 =====
#  （既に入っていれば何もしない）
if ! grep -q 'env.PYTHONFORANDROID_NO_DEPS_CHECK' buildozer.spec 2>/dev/null; then
  awk '
  BEGIN{printed=0}
  /^\[buildozer\]/{print;print "env.CFLAGS = -I'"$PREFIX"'/include";print "env.LDFLAGS = -L'"$PREFIX"'/lib";print "env.PYTHONFORANDROID_NO_DEPS_CHECK = 1";print "env.P4A_SKIP_DEPS_CHECK = 1";print "env.P4A_NO_DEPS_CHECK = 1";printed=1;next}
  {print}
  END{
    if(!printed){
      print "\n[buildozer]"
      print "env.CFLAGS = -I'"$PREFIX"'/include"
      print "env.LDFLAGS = -L'"$PREFIX"'/lib"
      print "env.PYTHONFORANDROID_NO_DEPS_CHECK = 1"
      print "env.P4A_SKIP_DEPS_CHECK = 1"
      print "env.P4A_NO_DEPS_CHECK = 1"
    }
  }' buildozer.spec > buildozer.spec.tmp && mv buildozer.spec.tmp buildozer.spec
fi

# シェル環境にも反映（当回のビルドで有効）
export PYTHONFORANDROID_NO_DEPS_CHECK=1
export P4A_SKIP_DEPS_CHECK=1
export P4A_NO_DEPS_CHECK=1

# ===== 4) zlib が見えているか軽く検査（見えていれば OK と表示）=====
pkg-config --exists zlib && echo "zlib: OK" || { echo "zlib が見つかりません"; exit 1; }
ls -l "$PREFIX/include/zlib.h" || true

# ===== 5) APK ビルド =====
buildozer android debug
