#!/usr/bin/env bash
# exit on error
set -o errexit

storage_dir=/opt/render/project/.render

if [ ! -d "$storage_dir/chrome" ]; then
  echo "...Downloading Chrome"
  mkdir -p "$storage_dir/chrome"
  cd "$storage_dir/chrome"
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  dpkg -x google-chrome-stable_current_amd64.deb .
  rm google-chrome-stable_current_amd64.deb
  cd $HOME/project/src # back to project root
else
  echo "...Chrome is already installed"
fi

pip install -r requirements.txt