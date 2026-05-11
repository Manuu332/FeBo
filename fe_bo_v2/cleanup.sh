#!/bin/bash

echo "Unifying FeBo's codebase..."

# Define directories (modify paths as needed)
BRAIN_DIR="brain"
CORE_DIR="core"
MEMORY_DIR="memory"

# Ensure required directories exist
mkdir -p "$CORE_DIR" "$MEMORY_DIR"

# 1. Keep only learner.py in brain/, but move it to core/ if needed
if [ -f "$BRAIN_DIR/learner.py" ]; then
    echo "-> Moving learner.py to core/..."
    mv "$BRAIN_DIR/learner.py" "$CORE_DIR/"
fi

# 2. Delete obsolete brain/ handlers
OBSOLETE_FILES=(
    "$BRAIN_DIR/ai.py"
    "$BRAIN_DIR/core.py"
    "$BRAIN_DIR/identity.py"
    "$BRAIN_DIR/emotion.py"   # optional, comment out if you want to keep
    "$BRAIN_DIR/background.py"
    "$BRAIN_DIR/handlers/basic.py"
    "$BRAIN_DIR/handlers/governance.py"
    "$BRAIN_DIR/handlers/knowledge.py"
    "$BRAIN_DIR/handlers/planning.py"
    "$BRAIN_DIR/handlers/reasoning.py"
    "$BRAIN_DIR/handlers/tools.py"
    "$BRAIN_DIR/intents.py"
    "$BRAIN_DIR/rules.py"
)

for file in "${OBSOLETE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "-> Removing obsolete file: $file"
        rm "$file"
    fi
done

# 3. Delete empty directories (if any)
find "$BRAIN_DIR" -type d -empty -delete 2>/dev/null

# 4. Ensure memory/ has correct permissions
chmod -R 755 "$MEMORY_DIR"

echo ""
echo "Done. FeBo's codebase is now unified."
echo "You may need to re-run this script after updating the repository."
