"""Utils package — Utilità riutilizzabili."""

# InputDialog richiede customtkinter (UI desktop) — import opzionale
# In ambiente API/CI questo import viene skippato silenziosamente
try:
    from .dialogs import InputDialog
except ImportError:
    InputDialog = None
