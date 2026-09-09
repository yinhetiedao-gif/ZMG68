"""小芒猫：无需网络、可随 DPI 缩放的轻量 Canvas 吉祥物。"""
from __future__ import annotations

import tkinter as tk


def draw_mango_cat(canvas: tk.Canvas, x: float, y: float, scale: float = 1.0, mood: str = "欢迎") -> None:
    """在 Canvas 绘制原创芒果小猫，不覆盖专业操作区域。"""
    s=max(.25,float(scale));c=lambda value:value*s
    canvas.delete("mango_cat")
    # 叶片与芒果身体
    canvas.create_oval(x-c(30),y-c(40),x+c(12),y-c(4),fill="#70A94B",outline="",tags="mango_cat")
    canvas.create_oval(x-c(4),y-c(48),x+c(35),y-c(12),fill="#93BF56",outline="",tags="mango_cat")
    canvas.create_oval(x-c(42),y-c(25),x+c(42),y+c(56),fill="#F5AA27",outline="#E6821C",width=max(1,int(c(2))),tags="mango_cat")
    canvas.create_arc(x-c(31),y-c(18),x+c(35),y+c(47),start=285,extent=110,style="arc",outline="#F8D267",width=max(1,int(c(4))),tags="mango_cat")
    # 猫耳与脸
    canvas.create_polygon(x-c(28),y-c(18),x-c(11),y-c(41),x-c(2),y-c(15),fill="#FFD46B",outline="#D97819",width=max(1,int(c(1))),tags="mango_cat")
    canvas.create_polygon(x+c(5),y-c(15),x+c(18),y-c(41),x+c(31),y-c(18),fill="#FFD46B",outline="#D97819",width=max(1,int(c(1))),tags="mango_cat")
    canvas.create_oval(x-c(30),y-c(23),x+c(31),y+c(30),fill="#FFE188",outline="#D97819",width=max(1,int(c(1))),tags="mango_cat")
    # 眼睛、鼻子、胡须
    for dx in (-11,11):canvas.create_oval(x+c(dx-3),y-c(3),x+c(dx+3),y+c(5),fill="#573A29",outline="",tags="mango_cat")
    canvas.create_polygon(x-c(3),y+c(9),x+c(3),y+c(9),x,y+c(14),fill="#F07C5A",outline="",tags="mango_cat")
    canvas.create_arc(x-c(8),y+c(10),x,y+c(21),start=250,extent=85,style="arc",outline="#6D4430",width=max(1,int(c(1))),tags="mango_cat")
    canvas.create_arc(x,y+c(10),x+c(8),y+c(21),start=205,extent=85,style="arc",outline="#6D4430",width=max(1,int(c(1))),tags="mango_cat")
    for dy in (8,14):
        canvas.create_line(x-c(28),y+c(dy),x-c(43),y+c(dy-3),fill="#6D4430",width=max(1,int(c(1))),tags="mango_cat")
        canvas.create_line(x+c(28),y+c(dy),x+c(43),y+c(dy-3),fill="#6D4430",width=max(1,int(c(1))),tags="mango_cat")
    canvas.create_text(x,y+c(75),text=mood,fill="#8A5E38",font=("Microsoft YaHei UI",max(8,int(c(9)),),"bold"),tags="mango_cat")
