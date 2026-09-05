# Improved MD Colors (Colors match the new color library)
MDCOLOR_VALUES = [x * 255 // 7 for x in range(8)]
# Output: [0x00, 0x24, 0x48, 0x6D, 0x91, 0xB6, 0xDA, 0xFF]

# Standard palette length
PALETTE_LINES = 4
PALLINE_COLORS = 16
PALETTE_MAXCOLORS = PALETTE_LINES * PALLINE_COLORS

""" Palette Editor Length
    Most palettes don't exceed 64 colors (due to the size of CRAM).
    Some cycling palettes and color arrays exceed that length.
    Because of this, Triad allows editing up to 256 colors.
"""
PALEDIT_MAXCOLORS = 256