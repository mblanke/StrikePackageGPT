#!/usr/bin/env sh
# iSH helper: install deps, run create_and_zip.sh, optionally run upload_repo.py
# Save this as ish_setup_and_run.sh, then:
# chmod +x ish_setup_and_run.sh
# ./ish_setup_and_run.sh

set -e

echo "Updating apk index..."
apk update

echo "Installing packages: python3, py3-pip, zip, unzip, curl, git, bash"
apk add --no-cache python3 py3-pip zip unzip curl git bash

# Ensure pip and requests are available
python3 -m ensurepip || true
pip3 install --no-cache-dir requests

echo "All dependencies installed."

echo
echo "FILES: place create_and_zip.sh and upload_repo.py in the current directory."
echo "Two ways to create files in iSH:"
echo "  1) On iPad: open this chat in Safari side-by-side with iSH, copy the script text, then run:"
echo "       cat > create_and_zip.sh <<'EOF'"
echo "       (paste content)"
echo "       EOF"
echo "     then chmod +x create_and_zip.sh"
echo "  2) Or, use nano/vi if you installed an editor: apk add nano; nano create_and_zip.sh"
echo
echo "If you already have create_and_zip.sh, run:"
echo "  chmod +x create_and_zip.sh"
echo "  ./create_and_zip.sh"
echo
echo "After the zip is created (goose_c2_files.zip), you can either:"
echo " - Upload from iSH to GitHub directly with upload_repo.py (preferred):"
echo "     export GITHUB_TOKEN='<your PAT>'"
echo "     export REPO='owner/repo'      # e.g. mblanke/StrikePackageGPT-Lab"
echo "     export BRANCH='c2-integration'  # optional"
echo "     export ZIP_FILENAME='goose_c2_files.zip'"
echo "     python3 upload_repo.py"
echo
echo " - Or download the zip to your iPad using a simple HTTP server:"
echo "     python3 -m http.server 8000 &"
echo "   Then open Safari and go to http://127.0.0.1:8000 to tap and download goose_c2_files.zip"
echo
echo "Note: iSH storage is in-app. If you want the zip in Files app, use the HTTP server method and save from Safari, or upload to Replit/GitHub directly from iSH."
echo
echo "Done. If you want I can paste create_and_zip.sh and upload_repo.py here for you to paste into iSH."