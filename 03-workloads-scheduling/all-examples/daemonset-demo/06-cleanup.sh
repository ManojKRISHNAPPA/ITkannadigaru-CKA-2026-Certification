#!/bin/bash
# ============================================================
# Cleanup script — removes the kind cluster created for demo
# Usage: bash 06-cleanup.sh
# ============================================================
echo "Deleting kind cluster cka-demo..."
kind delete cluster --name cka-demo
echo "Done. Cluster deleted."
