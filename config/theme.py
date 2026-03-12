"""
Theme Configuration - Tool Manager V14
MINIMAL DESIGN - Grigio + Colori Tenui per Bottoni
"""

# APPEARANCE
APPEARANCE_MODE = "light"
DEFAULT_COLOR_THEME = "blue"

# ============= MINIMAL COLOR PALETTE =============
# GRIGIO per sfondo/struttura + COLORI TENUI per bottoni

# Blu (bottoni normali)
COLOR_PRIMARY = "#2196F3"          # Blu Material (non troppo scuro)
COLOR_PRIMARY_DARK = "#1976D2"     # Blu più scuro per hover

# Verde TENUE (aggiungi)
COLOR_SUCCESS = "#66BB6A"          # Verde tenue (non acceso!)
COLOR_SUCCESS_DARK = "#43A047"     # Verde più scuro per hover

# Rosso TENUE (elimina)
COLOR_ERROR = "#EF5350"            # Rosso tenue/salmone (non acceso!)
COLOR_ERROR_DARK = "#E53935"       # Rosso più scuro per hover

# GRIGIO per struttura
COLOR_BACKGROUND = "#FAFAFA"       # Grigio chiarissimo (sfondo app)
COLOR_SURFACE = "#FFFFFF"          # Bianco (card, contenitori)
COLOR_BORDER = "#E0E0E0"           # Grigio chiaro (bordi)
COLOR_DIVIDER = "#BDBDBD"          # Grigio medio (divisori)

# Testo
COLOR_TEXT_PRIMARY = "#212121"     # Nero quasi puro
COLOR_TEXT_SECONDARY = "#757575"   # Grigio medio
COLOR_TEXT_HINT = "#9E9E9E"        # Grigio chiaro
COLOR_TEXT_ON_PRIMARY = "#FFFFFF"  # Bianco su colore

# Grigio per bottoni secondari
COLOR_NEUTRAL = "#9E9E9E"          # Grigio medio
COLOR_NEUTRAL_DARK = "#757575"     # Grigio più scuro

# Alias per compatibilità
COLOR_ACCENT = COLOR_PRIMARY
COLOR_ACCENT_DARK = COLOR_PRIMARY_DARK
COLOR_SURFACE_VARIANT = "#F5F5F5"
COLOR_PRIMARY_LIGHT = "#E3F2FD"
COLOR_ACCENT_LIGHT = "#E3F2FD"
COLOR_TABLE_HEADER = "#BDBDBD"         # Grigio per header tabelle

# Status colors - TUTTI GRIGI (no colori!)
COLOR_IN_MACCHINA = "#F5F5F5"
COLOR_SCAFFALE = "#F5F5F5"
COLOR_SMONTATO = "#F5F5F5"

# ============= TYPOGRAPHY - DIMENSIONI AUMENTATE =============
FONT_FAMILY = "Segoe UI"
FONT_SIZE_CAPTION = 11
FONT_SIZE_BODY = 13
FONT_SIZE_SUBTITLE = 16      # TAB!
FONT_SIZE_TITLE = 20
FONT_SIZE_HEADLINE = 24

# Alias per retrocompatibilità
FONT_SIZE_SMALL = FONT_SIZE_CAPTION
FONT_SIZE_NORMAL = FONT_SIZE_BODY
FONT_SIZE_MEDIUM = FONT_SIZE_SUBTITLE
FONT_SIZE_LARGE = FONT_SIZE_TITLE
FONT_SIZE_HEADER = FONT_SIZE_HEADLINE

# ============= SPACING =============
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24
SPACING_XL = 32

BORDER_RADIUS = 8
BORDER_RADIUS_SMALL = 4
BORDER_RADIUS_LARGE = 12

PADDING_SMALL = SPACING_SM
PADDING_MEDIUM = SPACING_MD
PADDING_LARGE = SPACING_LG

# ============= DIMENSIONS =============
TREEVIEW_ROW_HEIGHT = 34
TREEVIEW_COL_WIDTH_POS = 80
TREEVIEW_COL_WIDTH_ALIAS = 400
TREEVIEW_COL_WIDTH_STATO = 120
TREEVIEW_COL_WIDTH_QTY = 80

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

BUTTON_HEIGHT_SMALL = 36
BUTTON_HEIGHT_MEDIUM = 44
BUTTON_HEIGHT_LARGE = 52
BUTTON_WIDTH_SMALL = 100
BUTTON_WIDTH_MEDIUM = 140
BUTTON_WIDTH_LARGE = 180

# TAB DIMENSIONI - MOLTO PIÙ GRANDI!
TAB_HEIGHT = 70
TAB_FONT_SIZE = 16

# ============= ELEVATION =============
ELEVATION_LOW = 1
ELEVATION_MEDIUM = 2
ELEVATION_HIGH = 3

# ============= HELPER FUNCTIONS =============

def get_button_style(tipo="primary", size="medium"):
    """
    Stile bottone con COLORI TENUI.
    
    Tipi:
    - success: Verde tenue (aggiungi) #66BB6A
    - primary: Blu (modifica/normale) #2196F3
    - error/danger: Rosso tenue (elimina) #EF5350
    - neutral: Grigio (secondario) #9E9E9E
    """
    colors = {
        "success": (COLOR_SUCCESS, COLOR_SUCCESS_DARK),      # Verde tenue
        "primary": (COLOR_PRIMARY, COLOR_PRIMARY_DARK),      # Blu
        "error": (COLOR_ERROR, COLOR_ERROR_DARK),            # Rosso tenue
        "danger": (COLOR_ERROR, COLOR_ERROR_DARK),           # Alias per error
        "neutral": (COLOR_NEUTRAL, COLOR_NEUTRAL_DARK),      # Grigio
        # Alias compatibilità
        "info": (COLOR_PRIMARY, COLOR_PRIMARY_DARK),
        "warning": (COLOR_PRIMARY, COLOR_PRIMARY_DARK),
        "accent": (COLOR_PRIMARY, COLOR_PRIMARY_DARK)
    }
    
    sizes = {
        "small": (BUTTON_WIDTH_SMALL, BUTTON_HEIGHT_SMALL),
        "medium": (BUTTON_WIDTH_MEDIUM, BUTTON_HEIGHT_MEDIUM),
        "large": (BUTTON_WIDTH_LARGE, BUTTON_HEIGHT_LARGE)
    }
    
    fg_color, hover_color = colors.get(tipo, colors["primary"])
    width, height = sizes.get(size, sizes["medium"])
    
    return {
        "fg_color": fg_color,
        "hover_color": hover_color,
        "text_color": COLOR_TEXT_ON_PRIMARY,
        "width": int(width),
        "height": int(height),
        "font": (FONT_FAMILY, int(FONT_SIZE_BODY), "bold"),
        "corner_radius": int(BORDER_RADIUS)
    }


def get_font(size="body", bold=False):
    """Ritorna font tuple."""
    sizes_map = {
        "caption": FONT_SIZE_CAPTION,
        "body": FONT_SIZE_BODY,
        "subtitle": FONT_SIZE_SUBTITLE,
        "title": FONT_SIZE_TITLE,
        "headline": FONT_SIZE_HEADLINE,
        "small": FONT_SIZE_CAPTION,
        "normal": FONT_SIZE_BODY,
        "medium": FONT_SIZE_SUBTITLE,
        "large": FONT_SIZE_TITLE,
        "header": FONT_SIZE_HEADLINE
    }
    weight = "bold" if bold else "normal"
    return (FONT_FAMILY, sizes_map.get(size, FONT_SIZE_BODY), weight)


def get_card_style():
    """Stile card MINIMAL."""
    return {
        "fg_color": COLOR_SURFACE,
        "corner_radius": int(BORDER_RADIUS),
        "border_width": 1,
        "border_color": COLOR_BORDER
    }


def get_elevation(level="medium"):
    """Border width per elevazione minimal."""
    elevations = {
        "low": ELEVATION_LOW,
        "medium": ELEVATION_MEDIUM,
        "high": ELEVATION_HIGH
    }
    return elevations.get(level, ELEVATION_MEDIUM)
