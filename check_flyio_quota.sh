#!/bin/bash

echo "🔍 Checking Fly.io CPU Usage..."
echo ""

echo "📱 All apps in your account:"
fly apps list
echo ""

echo "🖥️  All machines across all apps:"
fly machine list
echo ""

echo "📊 Status of current survey app:"
fly status --app survey-app-silent-frost-2723 2>&1 || echo "App not fully deployed yet"
echo ""

echo "💡 Next steps:"
echo "   - Look for apps you don't need and destroy them: fly apps destroy <app-name>"
echo "   - Look for stopped machines you can remove"
echo "   - Or try deploying again with the updated fly.toml: fly deploy"
