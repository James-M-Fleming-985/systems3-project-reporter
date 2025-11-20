#!/bin/bash
# Verification script for Report Builder requirements structure

echo "🔍 Verifying Report Builder Requirements Structure"
echo "=================================================="

FEATURE_DIR="/workspaces/control_tower/systems3-project-reporter/FEATURE-WEB-006_PowerPoint_Export"

# Check feature requirements
echo ""
echo "✓ Feature Requirements:"
if [ -f "$FEATURE_DIR/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml" ]; then
    echo "  ✅ FEATURE-WEB-006_PowerPoint_Report_Builder.yaml"
    LINES=$(wc -l < "$FEATURE_DIR/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml")
    echo "     ($LINES lines)"
else
    echo "  ❌ FEATURE-WEB-006_PowerPoint_Report_Builder.yaml MISSING"
    exit 1
fi

# Check layer folders and requirements
echo ""
echo "✓ Layer Structure:"
LAYERS=(
    "LAYER_WEB_006_001_Report_Configuration_Model:REQ-WEB-006-001.yaml"
    "LAYER_WEB_006_002_Report_Template_Repository:REQ-WEB-006-002.yaml"
    "LAYER_WEB_006_003_Screenshot_Capture_Service:REQ-WEB-006-003.yaml"
    "LAYER_WEB_006_004_PowerPoint_Builder_Service:REQ-WEB-006-004.yaml"
    "LAYER_WEB_006_005_Export_Route_Handler:REQ-WEB-006-005.yaml"
)

for layer_info in "${LAYERS[@]}"; do
    IFS=':' read -r layer_name req_file <<< "$layer_info"
    
    if [ -d "$FEATURE_DIR/$layer_name" ]; then
        echo "  ✅ $layer_name/"
        
        # Check subdirectories
        if [ -d "$FEATURE_DIR/$layer_name/src" ]; then
            echo "     ✅ src/"
        else
            echo "     ❌ src/ missing"
        fi
        
        if [ -d "$FEATURE_DIR/$layer_name/tests" ]; then
            echo "     ✅ tests/"
        else
            echo "     ❌ tests/ missing"
        fi
        
        # Check requirements file
        if [ -f "$FEATURE_DIR/$layer_name/$req_file" ]; then
            echo "     ✅ $req_file"
        else
            echo "     ❌ $req_file MISSING"
        fi
    else
        echo "  ❌ $layer_name/ MISSING"
    fi
done

# Check build instructions
echo ""
echo "✓ Documentation:"
if [ -f "$FEATURE_DIR/BUILD_INSTRUCTIONS.md" ]; then
    echo "  ✅ BUILD_INSTRUCTIONS.md"
else
    echo "  ❌ BUILD_INSTRUCTIONS.md MISSING"
fi

# Summary
echo ""
echo "=================================================="
echo "🎯 Structure Verification Complete"
echo ""
echo "📋 Next Steps:"
echo "1. Install dependencies (if needed):"
echo "   pip install playwright pillow"
echo "   playwright install chromium"
echo ""
echo "2. Run the build:"
echo "   cd /workspaces/control_tower"
echo "   python build_feature.py \\"
echo "     --feature-req $FEATURE_DIR/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml \\"
echo "     --project-root /workspaces/control_tower/systems3-project-reporter \\"
echo "     --tests-enabled \\"
echo "     --test-first"
echo ""
echo "⏱️  Estimated build time: 6-8 hours"
echo "=================================================="
