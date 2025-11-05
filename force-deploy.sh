#!/bin/bash
# Force Railway rebuild by updating cache-busting file

echo "BUILD_TIME=$(date +%s)" > .railway-build
echo "BUILD_DATE=$(date)" >> .railway-build
git add .railway-build
git commit -m "Force rebuild - $(date +%Y%m%d-%H%M%S)"
git push origin main
echo "✅ Pushed cache-busting commit to trigger Railway rebuild"
