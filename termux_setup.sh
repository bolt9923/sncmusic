#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════
#  TuneBot — Termux Setup Script
#  Run: bash termux_setup.sh
# ════════════════════════════════════════════════════════════════

echo "🎵 TuneBot Termux Setup"
echo "══════════════════════"

# Update packages
pkg update -y && pkg upgrade -y

# Install required packages
pkg install -y python python-pip ffmpeg git openssl

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo "📝 Next steps:"
echo "   1. Copy .env.example to .env"
echo "   2. Fill in your credentials"
echo "   3. Run: python3 -m __main__"
