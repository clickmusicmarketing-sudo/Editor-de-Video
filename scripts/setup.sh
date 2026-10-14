#!/bin/bash
set -e
sudo apt-get update
sudo apt-get install -y ffmpeg
ffmpeg -version | head -n 1
