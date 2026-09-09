from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from .geometry import RadialItem, element_polygon
from .model import PatternSettings, Point
from .field_generators import FieldPrimitive, primitive_polygon


def _editable_points(element, steps: int = 28) -> list[tuple[float, float]]:
    """返回旋转椭圆的真实编辑几何；不经 Raster/Generator 重新采样。"""
    angle = math.radians(float(element.rotation)); cosine, sine = math.cos(angle), math.sin(angle)
    return [
        (element.x + element.width / 2 * math.cos(math.tau * index / steps) * cosine - element.height / 2 * math.sin(math.tau * index / steps) * sine,
         element.y + element.width / 2 * math.cos(math.tau * index / steps) * sine + element.height / 2 * math.sin(math.tau * index / steps) * cosine)
        for index in range(steps)
    ]


def _editable_bounds(document) -> tuple[float, float, float, float]:
    items = [item for item in document.elements if item.enabled]
    if not items:
        return (0.0, 0.0, 100.0, 100.0)
    return (
        min(item.x - item.width / 2 for item in items), min(item.y - item.height / 2 for item in items),
        max(item.x + item.width / 2 for item in items), max(item.y + item.height / 2 for item in items),
    )


def write_editable_document_svg(path: str, document) -> None:
    """导出 EditablePatternDocument 当前物化元素，而非参考位图或旧 Generator。"""
    parts = []
    for item in document.elements:
        if not item.enabled or item.opacity <= 0:
            continue
        opacity = max(0.0, min(1.0, float(item.opacity)))
        if item.primitive_type == "line":
            angle = math.radians(item.rotation); dx, dy = math.cos(angle) * item.width / 2, math.sin(angle) * item.width / 2
            parts.append(f'<line id="{item.id}" x1="{item.x-dx:.5f}" y1="{item.y-dy:.5f}" x2="{item.x+dx:.5f}" y2="{item.y+dy:.5f}" stroke="black" stroke-width="{max(.001,item.height):.5f}" stroke-linecap="round" opacity="{opacity:.5f}"/>')
        elif item.primitive_type in ("circle", "dot") and abs(item.width-item.height) < 1e-6:
            parts.append(f'<circle id="{item.id}" cx="{item.x:.5f}" cy="{item.y:.5f}" r="{item.radius:.5f}" fill="black" opacity="{opacity:.5f}"/>')
        else:
            points = " ".join(f"{x:.5f},{y:.5f}" for x, y in _editable_points(item))
            parts.append(f'<polygon id="{item.id}" points="{points}" fill="black" opacity="{opacity:.5f}"/>')
    left, top, right, bottom = _editable_bounds(document); margin = max(1.0, max(right-left, bottom-top) * .04)
    text = f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left-margin:.5f} {top-margin:.5f} {right-left+2*margin:.5f} {bottom-top+2*margin:.5f}" data-source="EditablePatternDocument" data-mode="{document.mode}"><g id="GeometryLayer">{"".join(parts)}</g></svg>\n'
    Path(path).write_text(text, encoding="utf-8")


def write_editable_document_png(path: str, document, size: int = 2000) -> None:
    left, top, right, bottom = _editable_bounds(document); span = max(1.0, right-left, bottom-top); scale, margin = size*.84/span, size*.08
    ox, oy = margin + (size-2*margin-(right-left)*scale)/2-left*scale, margin + (size-2*margin-(bottom-top)*scale)/2-top*scale
    image=Image.new("RGBA",(size,size),"white"); draw=ImageDraw.Draw(image,"RGBA")
    for item in document.elements:
        if not item.enabled or item.opacity<=0: continue
        fill=(0,0,0,round(max(0.0,min(1.0,item.opacity))*255))
        if item.primitive_type=="line":
            angle=math.radians(item.rotation);dx,dy=math.cos(angle)*item.width/2,math.sin(angle)*item.width/2
            draw.line(((item.x-dx)*scale+ox,(item.y-dy)*scale+oy,(item.x+dx)*scale+ox,(item.y+dy)*scale+oy),fill=fill,width=max(1,round(item.height*scale)))
        else:
            draw.polygon([(x*scale+ox,y*scale+oy) for x,y in _editable_points(item)],fill=fill)
    image.convert("RGB").save(path)


def write_editable_document_dxf(path: str, document) -> None:
    data=[_pair(0,"SECTION"),_pair(2,"ENTITIES")]
    for item in document.elements:
        if not item.enabled: continue
        if item.primitive_type in ("circle","dot") and abs(item.width-item.height)<1e-6:
            data.extend([_pair(0,"CIRCLE"),_pair(8,"GeometryLayer"),_pair(10,item.x),_pair(20,item.y),_pair(40,item.radius)])
        elif item.primitive_type=="line":
            angle=math.radians(item.rotation);dx,dy=math.cos(angle)*item.width/2,math.sin(angle)*item.width/2
            data.extend([_pair(0,"LINE"),_pair(8,"GeometryLayer"),_pair(10,item.x-dx),_pair(20,item.y-dy),_pair(11,item.x+dx),_pair(21,item.y+dy)])
        else:
            points=_editable_points(item);data.extend([_pair(0,"LWPOLYLINE"),_pair(8,"GeometryLayer"),_pair(90,len(points)),_pair(70,1)])
            for x,y in points:data.extend([_pair(10,x),_pair(20,y)])
    data.extend([_pair(0,"ENDSEC"),_pair(0,"EOF")]);Path(path).write_text("".join(data),encoding="ascii")


def _bounds(contour: list[Point], items: list[RadialItem]) -> tuple[float, float, float, float]:
    all_points = contour + [p for item in items for p in (item.start, item.end)]
    return min(p[0] for p in all_points), min(p[1] for p in all_points), max(p[0] for p in all_points), max(p[1] for p in all_points)


def write_svg(path: str, contour: list[Point], items: list[RadialItem], settings: PatternSettings, custom_element: list[Point] | None = None) -> None:
    min_x, min_y, max_x, max_y = _bounds(contour, items)
    margin = max(max_x-min_x, max_y-min_y)*0.06 + max(settings.dot_radius, settings.width)
    viewbox = f"{min_x-margin:.4f} {min_y-margin:.4f} {max_x-min_x+2*margin:.4f} {max_y-min_y+2*margin:.4f}"
    points = " ".join(f"{x:.4f},{y:.4f}" for x, y in contour)
    lines = []
    for item in items:
        if settings.element_type in ("线条 + 圆点", "直线"):
            lines.append(f'<line x1="{item.start[0]:.4f}" y1="{item.start[1]:.4f}" x2="{item.end[0]:.4f}" y2="{item.end[1]:.4f}" stroke="black" stroke-width="{item.width:.4f}" stroke-linecap="round"/>')
        if settings.element_type in ("线条 + 圆点", "圆点", "珠子"):
            radius = item.radius * (1.3 if settings.element_type == "珠子" else 1.0)
            lines.append(f'<circle cx="{item.end[0]:.4f}" cy="{item.end[1]:.4f}" r="{radius:.4f}" fill="black"/>')
        polygon = element_polygon(item, settings.element_type, custom_element)
        if polygon:
            pts=" ".join(f"{x:.4f},{y:.4f}" for x,y in polygon); lines.append(f'<polygon points="{pts}" fill="black"/>')
    text = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" data-units="{settings.units}">
  <g id="GEN_BaseCurve"><polygon points="{points}" fill="none" stroke="black" stroke-width="{settings.width:.4f}"/></g>
  <g id="GEN_RadialElements">{"".join(lines)}</g>
</svg>'''
    Path(path).write_text(text, encoding="utf-8")


def write_png(path: str, contour: list[Point], items: list[RadialItem], settings: PatternSettings, size: int = 2000, custom_element: list[Point] | None = None) -> None:
    min_x, min_y, max_x, max_y = _bounds(contour, items)
    span = max(max_x-min_x, max_y-min_y, 1.0)
    scale, margin = (size * .84 / span), size * .08
    ox = margin + (size - 2*margin - (max_x-min_x)*scale)/2 - min_x*scale
    oy = margin + (size - 2*margin - (max_y-min_y)*scale)/2 - min_y*scale
    def tr(p: Point) -> Point: return p[0]*scale+ox, p[1]*scale+oy
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    draw.line([tr(point) for point in contour+[contour[0]]], fill="black", width=max(1, round(settings.width*scale)), joint="curve")
    for item in items:
        if settings.element_type in ("线条 + 圆点", "直线"): draw.line([tr(item.start), tr(item.end)], fill="black", width=max(1, round(item.width*scale)))
        if settings.element_type in ("线条 + 圆点", "圆点", "珠子"):
            x, y = tr(item.end); radius = item.radius*scale*(1.3 if settings.element_type == "珠子" else 1.0); draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill="black")
        polygon=element_polygon(item,settings.element_type,custom_element)
        if polygon: draw.polygon([tr(point) for point in polygon],fill="black")
    image.save(path)


def _pair(code: int, value: str | int | float) -> str: return f"{code}\n{value}\n"


def write_dxf(path: str, contour: list[Point], items: list[RadialItem], settings: PatternSettings, custom_element: list[Point] | None = None) -> None:
    data = [_pair(0,"SECTION"), _pair(2,"ENTITIES"), _pair(0,"LWPOLYLINE"), _pair(8,"GEN_BaseCurve"), _pair(90,len(contour)), _pair(70,1)]
    for x,y in contour: data.extend([_pair(10,x), _pair(20,y)])
    for item in items:
        if settings.element_type in ("线条 + 圆点", "直线"): data.extend([_pair(0,"LINE"),_pair(8,"GEN_RadialLines"),_pair(10,item.start[0]),_pair(20,item.start[1]),_pair(11,item.end[0]),_pair(21,item.end[1])])
        if settings.element_type in ("线条 + 圆点", "圆点", "珠子"): data.extend([_pair(0,"CIRCLE"),_pair(8,"GEN_EndDots"),_pair(10,item.end[0]),_pair(20,item.end[1]),_pair(40,item.radius*(1.3 if settings.element_type=="珠子" else 1.0))])
        polygon=element_polygon(item,settings.element_type,custom_element)
        if polygon:
            data.extend([_pair(0,"LWPOLYLINE"),_pair(8,"GEN_Elements"),_pair(90,len(polygon)),_pair(70,1)])
            for x,y in polygon:data.extend([_pair(10,x),_pair(20,y)])
    data.extend([_pair(0,"ENDSEC"),_pair(0,"EOF")]); Path(path).write_text("".join(data), encoding="ascii")


def write_field_svg(path: str, items: list[FieldPrimitive], settings: PatternSettings) -> None:
    parts=[]
    for item in items:
        fill="black" if item.fill_mode=="实心" else "none";stroke="none" if item.fill_mode=="实心" else "black";stroke_width=max(.12,item.size*.18)
        if item.kind=="dot":parts.append(f'<ellipse cx="{item.x:.4f}" cy="{item.y:.4f}" rx="{item.size*item.aspect:.4f}" ry="{item.size:.4f}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width:.4f}"/>')
        elif item.kind=="line":parts.append(f'<line x1="{item.x:.4f}" y1="{item.y:.4f}" x2="{item.x2:.4f}" y2="{item.y2:.4f}" stroke="black" stroke-width="{item.size:.4f}" stroke-linecap="round"/>')
        else:
            points=" ".join(f"{x:.4f},{y:.4f}" for x,y in primitive_polygon(item));parts.append(f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width:.4f}"/>')
    text=f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" data-units="mm" data-generator="{settings.field_generator}"><g id="GEN_FieldElements">{"".join(parts)}</g></svg>'''
    Path(path).write_text(text,encoding="utf-8")


def write_field_png(path: str, items: list[FieldPrimitive], size: int=2000) -> None:
    image=Image.new("RGB",(size,size),"white");draw=ImageDraw.Draw(image);scale=size/100
    for item in items:
        if item.kind=="dot":
            rx,ry=item.size*item.aspect*scale,item.size*scale;box=(item.x*scale-rx,item.y*scale-ry,item.x*scale+rx,item.y*scale+ry)
            if item.fill_mode=="实心":draw.ellipse(box,fill="black")
            else:draw.ellipse(box,outline="black",width=max(1,round(item.size*scale*.18)))
        elif item.kind=="line":draw.line((item.x*scale,item.y*scale,item.x2*scale,item.y2*scale),fill="black",width=max(1,round(item.size*scale)))
        else:
            points=[(x*scale,y*scale) for x,y in primitive_polygon(item)]
            if item.fill_mode=="实心":draw.polygon(points,fill="black")
            else:draw.line(points+[points[0]],fill="black",width=max(1,round(item.size*scale*.18)),joint="curve")
    image.save(path)


def write_field_dxf(path: str, items: list[FieldPrimitive]) -> None:
    data=[_pair(0,"SECTION"),_pair(2,"ENTITIES")]
    for item in items:
        if item.kind=="dot":data.extend([_pair(0,"CIRCLE"),_pair(8,"GEN_FieldDots"),_pair(10,item.x),_pair(20,item.y),_pair(40,item.size)])
        elif item.kind=="line":data.extend([_pair(0,"LINE"),_pair(8,"GEN_FieldLines"),_pair(10,item.x),_pair(20,item.y),_pair(11,item.x2),_pair(21,item.y2)])
        else:
            poly=primitive_polygon(item);data.extend([_pair(0,"LWPOLYLINE"),_pair(8,"GEN_FieldPlanes"),_pair(90,len(poly)),_pair(70,1)])
            for x,y in poly:data.extend([_pair(10,x),_pair(20,y)])
    data.extend([_pair(0,"ENDSEC"),_pair(0,"EOF")]);Path(path).write_text("".join(data),encoding="ascii")
