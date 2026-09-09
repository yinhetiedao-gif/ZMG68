"""黑白图片 → 无底板 SVG/STL。

黑色像素是实体，白色像素是孔。模块采用固定像素网格挤出，
便于在没有复杂 CAD 内核的桌面版中稳定生成封闭 STL。
"""
from __future__ import annotations

import json
import math
import struct
from collections import deque
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
import numpy as np


@dataclass
class ConvertResult:
    connected: bool
    components: int
    width_mm: float
    height_mm: float
    triangles: int | None
    output_dir: str
    quality: str = "标准"
    roundness: float = 50.0
    mesh_valid: bool = False


QUALITY_STEP = {"草稿": .55, "标准": .35, "精细": .22, "超精细": .15}


def _load(path: str, width_mm: float, nozzle_mm: float, threshold: int, quality: str, roundness: float) -> tuple[list[bytearray], int, int]:
    image = Image.open(path).convert("L")
    # 质量档控制独立于实时预览的最终网格采样步长，绝不拿预览网格直接导出。
    step = QUALITY_STEP.get(quality, QUALITY_STEP["标准"])
    target_width = min(image.width, max(80, min(700, round(width_mm / max(step, nozzle_mm * .35)))))
    target_height = max(1, round(image.height * target_width / image.width))
    if (target_width, target_height) != image.size:
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    # 先柔化输入场，再取等值线；这不是仅增加三角面，而是在几何生成前连续化轮廓。
    if roundness > 0:
        from PIL import ImageFilter
        image = image.filter(ImageFilter.GaussianBlur(radius=min(2.5, roundness / 55.0)))
    pixels = image.load(); w, h = image.size
    return [bytearray(pixels[x, y] < threshold for x in range(w)) for y in range(h)], w, h


def _components(mask: list[bytearray], w: int, h: int) -> list[int]:
    seen = [bytearray(w) for _ in range(h)]; result = []
    for y in range(h):
        for x in range(w):
            if not mask[y][x] or seen[y][x]: continue
            queue = deque([(x, y)]); seen[y][x] = 1; total = 0
            while queue:
                a, b = queue.popleft(); total += 1
                for c, d in ((a-1,b),(a+1,b),(a,b-1),(a,b+1)):
                    if 0 <= c < w and 0 <= d < h and mask[d][c] and not seen[d][c]: seen[d][c] = 1; queue.append((c,d))
            result.append(total)
    return sorted(result, reverse=True)


def _write_svg(mask: list[bytearray], w: int, h: int, width_mm: float, path: Path) -> None:
    scale = width_mm / w; runs=[]
    for y,row in enumerate(mask):
        x=0
        while x<w:
            if not row[x]: x+=1; continue
            start=x
            while x<w and row[x]: x+=1
            runs.append(f"M{start*scale:.4f} {y*scale:.4f}h{(x-start)*scale:.4f}v{scale:.4f}h-{(x-start)*scale:.4f}Z")
    path.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{h*scale:.4f}mm" viewBox="0 0 {width_mm} {h*scale:.4f}"><path fill="#000" fill-rule="evenodd" d="{" ".join(runs)}"/></svg>\n',encoding="utf-8")


def _triangle_count(mask: list[bytearray], w: int, h: int) -> int:
    amount=0
    for y in range(h):
        for x in range(w):
            if not mask[y][x]: continue
            amount += 4
            if y==0 or not mask[y-1][x]: amount += 2
            if y==h-1 or not mask[y+1][x]: amount += 2
            if x==0 or not mask[y][x-1]: amount += 2
            if x==w-1 or not mask[y][x+1]: amount += 2
    return amount


def _edt_1d(values: np.ndarray) -> np.ndarray:
    """Felzenszwalb 线性时间欧氏距离变换的一维步骤。"""
    n = len(values)
    if not np.isfinite(values).any() or np.min(values) > 1e10:
        return np.full(n, 1e6, dtype=float)
    v = np.zeros(n, dtype=np.int32); z = np.empty(n + 1); d = np.empty(n); k = 0
    z[0], z[1] = -np.inf, np.inf
    for q in range(1, n):
        s = ((values[q] + q*q) - (values[v[k]] + v[k]*v[k])) / (2*q - 2*v[k])
        while s <= z[k]:
            k -= 1
            s = ((values[q] + q*q) - (values[v[k]] + v[k]*v[k])) / (2*q - 2*v[k])
        k += 1; v[k] = q; z[k] = s; z[k+1] = np.inf
    k = 0
    for q in range(n):
        while z[k+1] < q: k += 1
        d[q] = (q-v[k])**2 + values[v[k]]
    return d


def _edt(feature: np.ndarray) -> np.ndarray:
    """到 feature=True 的像素距离。"""
    inf = 1e12; data = np.where(feature, 0.0, inf)
    vertical = np.empty_like(data, dtype=float)
    for x in range(data.shape[1]): vertical[:, x] = _edt_1d(data[:, x])
    result = np.empty_like(data, dtype=float)
    for y in range(data.shape[0]): result[y, :] = _edt_1d(vertical[y, :])
    return np.sqrt(result)


def _signed_distance(mask: list[bytearray]) -> np.ndarray:
    base = np.array(mask, dtype=bool)
    # 加一圈背景，保证贴边图案仍生成封闭外表面。
    base = np.pad(base, 1, constant_values=False)
    return _edt(~base) - _edt(base)


def _unit(vector: tuple[float,float,float]) -> tuple[float,float,float]:
    length = math.sqrt(sum(x*x for x in vector)) or 1.0
    return tuple(x/length for x in vector)


def _write_smooth_stl(mask: list[bytearray], w: int, h: int, width_mm: float, thickness_mm: float, roundness: float, organic_blend: float, quality: str, path: Path) -> int:
    """SDF + Marching Tetrahedra 最终建模。

    2D 欧氏距离场产生连续轮廓，Z 向采用圆角厚度场。每个最终质量档都重新采样并
    提取等值面，因此 STL 与 Canvas 预览完全独立。
    """
    step = width_mm / w; sdf = _signed_distance(mask) * step
    bevel = min(thickness_mm*.45, max(step*.75, thickness_mm*(roundness/100.0)*.42))
    blend = max(0.0, min(100.0, organic_blend)) / 100.0
    bevel *= .75 + .5 * blend
    z_step = min(step, max(.10, thickness_mm / (5 + int(roundness/20))))
    z_low, z_high = -bevel, thickness_mm + bevel
    nz = max(6, int(math.ceil((z_high-z_low) / z_step)))
    zs = [z_low + (z_high-z_low) * z / nz for z in range(nz+1)]
    half = thickness_mm*.5
    layers=[]
    for z in zs:
        q=max(0.0,abs(z-half)-(half-bevel)); inset=bevel-math.sqrt(max(0.0,bevel*bevel-q*q)) if q>0 else 0.0
        # 与顶部/底部的有符号距离共同构成封闭体；inset 使横截面在边缘连续收缩。
        layers.append(np.minimum(sdf-inset, min(z, thickness_mm-z)))
    tetrahedra=((0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6))
    offsets=((0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1))
    edges=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
    def emit(file, points, desired):
        if len(points)<3:return 0
        center=tuple(sum(point[i] for point in points)/len(points) for i in range(3)); normal=_unit(desired)
        ref=(0.,0.,1.) if abs(normal[2])<.9 else (1.,0.,0.); u=_unit((normal[1]*ref[2]-normal[2]*ref[1],normal[2]*ref[0]-normal[0]*ref[2],normal[0]*ref[1]-normal[1]*ref[0]));v=(normal[1]*u[2]-normal[2]*u[1],normal[2]*u[0]-normal[0]*u[2],normal[0]*u[1]-normal[1]*u[0])
        points=sorted(points,key=lambda p:math.atan2((p[0]-center[0])*v[0]+(p[1]-center[1])*v[1]+(p[2]-center[2])*v[2],(p[0]-center[0])*u[0]+(p[1]-center[1])*u[1]+(p[2]-center[2])*u[2]))
        count=0
        for i in range(1,len(points)-1):
            a,b,c=points[0],points[i],points[i+1];cross=((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),(b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
            if sum(cross[j]*desired[j] for j in range(3))<0:b,c=c,b;cross=tuple(-x for x in cross)
            length=math.sqrt(sum(x*x for x in cross))
            if length>1e-10:file.write(struct.pack("<12fH",*(x/length for x in cross),*a,*b,*c,0));count+=1
        return count
    triangle_count=0
    with path.open("wb+") as file:
        file.write(b"Xiaomang Studio smooth SDF no-base STL".ljust(80,b"\0"));file.write(struct.pack("<I",0))
        for z in range(nz):
            for y in range(h+1):
                for x in range(w+1):
                    values=[float(layers[z+oz][y+oy,x+ox]) for ox,oy,oz in offsets]
                    if min(values)>0 or max(values)<=0:continue
                    positions=[((x+ox-1)*step,(h-y-oy+1)*step,zs[z+oz]) for ox,oy,oz in offsets]
                    for tet in tetrahedra:
                        ins=[index for index in tet if values[index]>0];outs=[index for index in tet if values[index]<=0]
                        if not ins or not outs:continue
                        points=[]
                        for a,b in edges:
                            ia,ib=tet[a],tet[b];fa,fb=values[ia],values[ib]
                            if (fa>0)!=(fb>0):
                                t=fa/(fa-fb);pa,pb=positions[ia],positions[ib];points.append(tuple(pa[k]+(pb[k]-pa[k])*t for k in range(3)))
                        inside=tuple(sum(positions[i][k] for i in ins)/len(ins) for k in range(3));outside=tuple(sum(positions[i][k] for i in outs)/len(outs) for k in range(3));triangle_count+=emit(file,points,tuple(outside[k]-inside[k] for k in range(3)))
        file.seek(80);file.write(struct.pack("<I",triangle_count))
    return triangle_count


def audit_stl(path: Path, max_triangles: int = 1_200_000) -> dict:
    """从已落盘的二进制 STL 独立检查封闭性、退化面和独立组件。

    这是最终制造闸门，不能相信 Blender 或预览阶段的内存状态。自交和最小壁厚需要
    更重的几何内核，当前明确标为未覆盖，不能伪报“全部通过”。
    """
    with path.open("rb") as file:
        header = file.read(80)
        count_bytes = file.read(4)
        if len(count_bytes) != 4:
            raise ValueError("STL 文件头不完整。")
        count = struct.unpack("<I", count_bytes)[0]
        if count > max_triangles:
            return {"triangles": count, "audit": "partial", "watertight": None,
                    "message": "网格超过完整审计上限；为避免把未经检查的模型交给切片软件，未判定为可打印。"}
        edge_faces: dict[tuple[tuple[float, float, float], tuple[float, float, float]], list[int]] = {}
        parent = list(range(count))
        degenerate = 0
        min_edge = float("inf")

        def root(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def join(first: int, second: int) -> None:
            first, second = root(first), root(second)
            if first != second:
                parent[second] = first

        for face_index in range(count):
            data = file.read(50)
            if len(data) != 50:
                raise ValueError("STL 三角面数据不完整。")
            values = struct.unpack("<12fH", data)
            vertices = [tuple(round(value, 6) for value in values[3 + i * 3:6 + i * 3]) for i in range(3)]
            normal_length = math.sqrt(sum(value * value for value in values[:3]))
            if normal_length < 1e-8 or len(set(vertices)) < 3:
                degenerate += 1
            for first, second in ((vertices[0], vertices[1]), (vertices[1], vertices[2]), (vertices[2], vertices[0])):
                min_edge = min(min_edge, math.dist(first, second))
                edge = tuple(sorted((first, second)))
                linked = edge_faces.setdefault(edge, [])
                for other in linked:
                    join(face_index, other)
                linked.append(face_index)
    naked = sum(1 for linked in edge_faces.values() if len(linked) == 1)
    non_manifold = sum(1 for linked in edge_faces.values() if len(linked) > 2)
    components = len({root(index) for index in range(count)}) if count else 0
    watertight = bool(count) and naked == 0 and non_manifold == 0 and degenerate == 0
    return {
        "triangles": count,
        "audit": "full",
        "watertight": watertight,
        "naked_edges": naked,
        "non_manifold_edges": non_manifold,
        "degenerate_faces": degenerate,
        "connected_components": components,
        "floating_components": max(0, components - 1),
        "minimum_edge_mm": 0.0 if min_edge == float("inf") else round(min_edge, 6),
        "self_intersection": "未覆盖（需要专用几何内核）",
        "message": "网格通过封闭性与组件审计" if watertight and components == 1 else "网格审计发现裸边、非流形边、退化面或多个独立组件。",
    }


def convert_image(path: str, output_dir: str, width_mm: float=100.0, thickness_mm: float=.8, nozzle_mm: float=.4, threshold: int=200, allow_multipart: bool=False, quality: str="标准", roundness: float=55.0, organic_blend: float=55.0) -> ConvertResult:
    if width_mm <= 0 or thickness_mm <= 0 or nozzle_mm <= 0: raise ValueError("宽度、厚度和喷嘴直径必须大于 0。")
    mask,w,h=_load(path,width_mm,nozzle_mm,threshold,quality,roundness);sizes=_components(mask,w,h)
    if not sizes: raise ValueError("图片中没有检测到黑色实体。请使用黑色图案、白色背景的图片。")
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True);height_mm=h*width_mm/w;connected=len(sizes)==1
    preview=Image.new("1",(w,h),1);pixels=preview.load()
    for y in range(h):
        for x in range(w): pixels[x,y]=0 if mask[y][x] else 1
    preview.save(out/"黑白预览.png");_write_svg(mask,w,h,width_mm,out/"图案.svg")
    report={"connected":connected,"component_count":len(sizes),"largest_components_px":sizes[:20],"message":"单一连通网络" if connected else "存在多个断开区域：默认不输出 STL。可在软件提示中确认多部件导出。","width_mm":width_mm,"height_mm":height_mm,"thickness_mm":thickness_mm,"nozzle_mm":nozzle_mm,"recommended_min_feature_mm":max(.8,nozzle_mm*2)}
    triangles=_write_smooth_stl(mask,w,h,width_mm,thickness_mm,roundness,organic_blend,quality,out/"图案.stl") if connected or allow_multipart else None
    audit=audit_stl(out/"图案.stl") if triangles else {"watertight":False,"message":"未生成 STL。"}
    report.update({"stl_triangles":triangles,"quality":quality,"roundness":roundness,"organic_blend":organic_blend,"pipeline":"SDF continuous contour + rounded thickness field + marching tetrahedra final mesh","mesh_checks":{**audit,"disconnected_components":len(sizes),"self_intersection":"not yet generalized", "minimum_wall_thickness_mm":"requires material-aware 3D analysis"}});(out/"连通性检测.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    scale=width_mm/w;(out/"参数公式说明.md").write_text(f"# 图片转 SVG / STL 参数公式\n\n```text\nS = {width_mm} / {w} = {scale:.6f} mm/px\nx_mm = x_px × S\ny_mm = y_px × S\nV = {{(x,y,z) | black(x,y)=1 and 0≤z≤{thickness_mm}}}\n```\n\n黑色为实体，白色为孔洞；模型无底板。\n",encoding="utf-8")
    return ConvertResult(connected,len(sizes),width_mm,height_mm,triangles,str(out),quality,roundness,bool(audit.get("watertight")))
