"""小芒造物 1.6 风格：稳定、清晰的浅灰白蓝专业工作台。"""
from __future__ import annotations
from tkinter import ttk

# 吉祥物只用于引导；参数与预览区域保持高对比、低装饰。
COLORS={"space":"#f4f5f7","surface":"#ffffff","surface_2":"#eef1f4","line":"#cbd2da","silver":"#202a35","muted":"#617080","ice":"#356b95","blue":"#356b95","hover":"#e1ebf2","pressed":"#cedce7","canvas":"#fbfcfd","mango":"#f3c35b","orange":"#356b95","leaf":"#6e9b73","success":"#4d8b64","danger":"#c95c46"}

# 集中化 Design Tokens：8px 控件、12px 按钮、16px 卡片、20px 工作区。
TOKENS={"space_1":4,"space_2":8,"space_3":12,"space_4":16,"space_5":24,"space_6":32,"radius_small":8,"radius_input":10,"radius_button":12,"radius_card":16,"radius_workspace":20}

def apply(root) -> None:
    root.configure(bg=COLORS["space"]);style=ttk.Style(root);style.theme_use("clam")
    style.configure(".",background=COLORS["surface"],foreground=COLORS["silver"],font=("Microsoft YaHei UI",9))
    style.configure("TFrame",background=COLORS["surface"]);style.configure("TLabel",background=COLORS["surface"],foreground=COLORS["silver"])
    style.configure("TLabelFrame",background=COLORS["surface"],foreground="#8B591F",bordercolor=COLORS["line"],relief="solid")
    style.configure("TLabelFrame.Label",background=COLORS["surface"],foreground="#A96516",font=("Microsoft YaHei UI",9,"bold"))
    style.configure("TButton",background=COLORS["surface"],foreground=COLORS["silver"],bordercolor=COLORS["line"],padding=(8,5))
    style.map("TButton",background=[("active",COLORS["hover"]),("pressed",COLORS["pressed"]),("disabled","#F6EFE2")],foreground=[("disabled","#A79584")])
    style.configure("Action.TButton",background="#356b95",foreground="white",bordercolor="#2b587b",font=("Microsoft YaHei UI",10,"bold"),padding=(12,8))
    style.map("Action.TButton",background=[("active","#477ea8"),("pressed","#285977")])
    style.configure("ViewActive.TButton",background="#dceaf2",foreground="#234d6a",bordercolor="#356b95",padding=(10,5),font=("Microsoft YaHei UI",9,"bold"))
    style.map("ViewActive.TButton",background=[("active","#c9dfea"),("pressed","#b8d2e0")])
    style.configure("Toolbar.TButton",background=COLORS["surface"],bordercolor=COLORS["line"],padding=(8,5))
    style.map("Toolbar.TButton",background=[("active",COLORS["hover"]),("pressed",COLORS["pressed"]),("disabled","#F6EFE2")])
    style.configure("Icon.TButton",background=COLORS["surface"],foreground=COLORS["blue"],bordercolor=COLORS["line"],padding=(4,3))
    style.configure("IconActive.TButton",background=COLORS["hover"],foreground=COLORS["blue"],bordercolor=COLORS["ice"],padding=(4,3))
    style.configure("Nav.TButton",background=COLORS["surface"],foreground=COLORS["silver"],anchor="w",padding=(12,9))
    style.map("Nav.TButton",background=[("active",COLORS["hover"])])
    style.configure("NavActive.TButton",background="#dceaf2",foreground="#234d6a",anchor="w",bordercolor=COLORS["ice"],padding=(12,9),font=("Microsoft YaHei UI",9,"bold"))
    style.configure("Generator.TButton",background="#f6f8fa",foreground=COLORS["silver"],bordercolor=COLORS["line"],padding=(6,8))
    style.map("Generator.TButton",background=[("active",COLORS["hover"])])
    style.configure("GeneratorActive.TButton",background="#e1ebf2",foreground="#234d6a",bordercolor=COLORS["ice"],padding=(6,8),font=("Microsoft YaHei UI",9,"bold"))
    style.configure("TCombobox",fieldbackground="#FFFDF8",background=COLORS["surface_2"],foreground=COLORS["silver"],arrowcolor="#B86E17",bordercolor=COLORS["line"])
    style.map("TCombobox",fieldbackground=[("readonly","#FFFDF8")],foreground=[("readonly",COLORS["silver"])])
    style.configure("TEntry",fieldbackground="#FFFDF8",foreground=COLORS["silver"],bordercolor=COLORS["line"])
    style.configure("TNotebook",background=COLORS["space"],bordercolor=COLORS["line"]);style.configure("TNotebook.Tab",background="#FCEBC6",foreground="#7B5A3D",padding=(12,7))
    style.map("TNotebook.Tab",background=[("selected","#FFFDF8"),("active",COLORS["hover"])],foreground=[("selected","#A96516")]);style.configure("TPanedwindow",background=COLORS["space"]);style.configure("TSeparator",background=COLORS["line"])
