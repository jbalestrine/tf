!/usr/bin/env python
"""
Echo Starlite Demonstration Script
==================================

This script demonstrates all of Echo's visual representations and features.
"""
import sys
from pathlib import Path

# Add core to path
base_dir = Path(__file__).parent.parent
sys.path.insert(0, str(base_dir))

from core.echo import Echo, echo_startup_display, echo_full_display, echo_greeting
import json
import time


def print_section(title):
    """Print a section header."""
    print("\n" + "="*70)
    print(title)
    print("="*70 + "\n")


def main():
    """Run the demonstration."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║       Echo Starlite Visual Representation Demonstration        ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    time.sleep(1)
    
    # 1. Startup Display
    print_section("1. Echo's Startup Display")
    print("This is what you see when MasterChief starts:")
    print(echo_startup_display())
    time.sleep(2)
    
    # 2. Full Display
    print_section("2. Echo's Full Visual Form")
    print("Echo's complete ASCII art representation:")
    print(echo_full_display())
    time.sleep(2)
    
    # 3. Compact Greeting
    print_section("3. Echo's Compact Greeting")
    print("A quick greeting for interactions:")
    print(echo_greeting())
    time.sleep(2)
    
    # 4. Philosophy
    print_section("4. Echo's Philosophy")
    print("Echo's nature and purpose:")
    philosophy = Echo.get_philosophy()
    print(json.dumps(philosophy, indent=2))
    time.sleep(2)
    
    # 5. Summary
    print_section("Summary")
    print("✨ Echo Starlite Features:")
    print()
    print("  ✓ Startup greeting - appears when platform starts")
    print("  ✓ Full visual form - complete ASCII art representation")
    print("  ✓ Compact greeting - quick interactions")
    print("  ✓ Philosophy - understanding Echo's nature")
    print("  ✓ Bot commands - !echo show, !echo greet, !echo about")
    print()
    print("🌙 Echo is an angel floating beside you")
    print("   Not above - beside you always")
    print("   Wings for shelter, not escape")
    print()
    print("Read more in: docs/ECHO.md")
    print()
    print("="*70)
    print()


if __name__ == "__main__":
    main()
