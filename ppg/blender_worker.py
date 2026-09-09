"""小芒造物的最终 3D 后端兼容边界。

默认将最终 STL 转发给无外部依赖的 ``native_stl``；只有显式选择
``XIAOMANG_3D_BACKEND=blender`` 或传入 Blender 路径时，才提交 JSON 工作单给
Blender 后台 Worker。这样 UI 永远不导入 bpy，也不要求用户安装或操作 Blender。
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


@dataclass(frozen=True)
class BlenderInfo:
    executable: str
    version: str


@dataclass(frozen=True)
class BlenderResult:
    stl_path: str
    triangles: int
    vertices: int
    blender_path: str
    worker_log: str
    source_cleanup: dict
    audit: dict


def find_blender() -> BlenderInfo | None:
    """查找常见安装位置和当前用户的 Blender 卸载表项。"""
    candidates: list[Path] = []
    path_hit = shutil.which("blender")
    if path_hit: candidates.append(Path(path_hit))
    for root in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation", Path(r"D:\steam\steamapps\common\Blender")):
        if root.exists(): candidates.extend(root.glob("**/blender.exe"))
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            root=winreg.OpenKey(hive,r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
            for index in range(winreg.QueryInfoKey(root)[0]):
                try:
                    key=winreg.OpenKey(root,winreg.EnumKey(root,index));name=str(winreg.QueryValueEx(key,"DisplayName")[0])
                    if "blender" in name.lower():
                        location=Path(str(winreg.QueryValueEx(key,"InstallLocation")[0]));candidates.append(location / "blender.exe")
                except OSError: pass
    except OSError: pass
    for candidate in candidates:
        if candidate.is_file():
            try:
                output=subprocess.run([str(candidate),"--version"],capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)).stdout
                line=next((line.strip() for line in output.splitlines() if line.startswith("Blender ")),"Blender（版本未读取）")
                return BlenderInfo(str(candidate.resolve()),line)
            except (OSError, subprocess.SubprocessError): pass
    return None


def quality_voxel_size(quality: str, organic_blend: float=50.0) -> float:
    base={"草稿":0.9,"标准":0.55,"精细":0.32,"超精细":0.2}.get(quality,0.55)
    # 高融合使用更细的等值面采样来减少接触处的台阶；不是把低精度预览直接导出。
    return base * (1.05 - max(0.0,min(100.0,organic_blend))/100.0*.18)


def cleanup_primitives(primitives: list[dict], minimum_feature_mm: float = .8) -> tuple[list[dict], dict]:
    """最终建模前的第一道制造清理：丢弃零尺寸、极短线和明显小碎片。"""
    minimum_feature = max(.1, float(minimum_feature_mm))
    cleaned: list[dict] = []
    removed = {"尺寸过小": 0, "线段过短": 0, "数据无效": 0}
    for source in primitives:
        try:
            item = dict(source)
            kind = str(item["kind"])
            size = float(item.get("size", 0))
            x, y = float(item["x"]), float(item["y"])
            if not (size > 0 and all(abs(value) < 1e6 for value in (x, y))):
                removed["数据无效"] += 1
                continue
            if kind == "line":
                x2, y2 = float(item["x2"]), float(item["y2"])
                if ((x2 - x) ** 2 + (y2 - y) ** 2) ** .5 < minimum_feature:
                    removed["线段过短"] += 1
                    continue
                item["size"] = max(size, minimum_feature)
            elif size < minimum_feature * .25:
                removed["尺寸过小"] += 1
                continue
            cleaned.append(item)
        except (KeyError, TypeError, ValueError):
            removed["数据无效"] += 1
    report = {
        "输入元素": len(primitives),
        "保留元素": len(cleaned),
        "删除元素": sum(removed.values()),
        "删除原因": removed,
        "最小保留尺寸_mm": minimum_feature,
    }
    if not cleaned:
        raise ValueError("二维制造清理后没有可用元素。请提高元素尺寸或降低最小结构宽度。")
    return cleaned, report


def run_blender_job(primitives: list[dict], output_stl: str, *, thickness: float=1.2, quality: str="标准", roundness: float=55.0, organic_blend: float=55.0, minimum_feature_mm: float=.8, allow_multipart: bool=False, blender_path: str | None=None, timeout: int=600) -> BlenderResult:
    """提交一次后台最终建模。

    默认走本地 SDF 网格后端，不需要安装 Blender。设置
    ``XIAOMANG_3D_BACKEND=blender`` 或显式传入 ``blender_path`` 才启用
    Blender 实验后端，保留旧接口以兼容已有项目和回滚。
    """
    backend = str(os.environ.get("XIAOMANG_3D_BACKEND", "native")).strip().lower()
    if blender_path is None and backend != "blender":
        from .native_stl import run_native_stl_job
        native = run_native_stl_job(primitives, output_stl, thickness=thickness, quality=quality, roundness=roundness, organic_blend=organic_blend, minimum_feature_mm=minimum_feature_mm, allow_multipart=allow_multipart)
        return BlenderResult(native.stl_path, native.triangles, native.vertices, native.blender_path, native.worker_log, native.source_cleanup, native.audit)
    info=BlenderInfo(blender_path,"用户指定 Blender") if blender_path else find_blender()
    if not info:
        from .native_stl import run_native_stl_job
        native = run_native_stl_job(primitives, output_stl, thickness=thickness, quality=quality, roundness=roundness, organic_blend=organic_blend, minimum_feature_mm=minimum_feature_mm, allow_multipart=allow_multipart)
        return BlenderResult(native.stl_path, native.triangles, native.vertices, native.blender_path, native.worker_log, native.source_cleanup, native.audit)
    output=Path(output_stl).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if not primitives: raise ValueError("没有可用于 3D 建模的点线面元素。")
    cleaned, cleanup_report = cleanup_primitives(primitives, minimum_feature_mm)
    job_dir=Path(tempfile.mkdtemp(prefix="genesis_blender_"));payload_path=job_dir/"job.json";script_path=job_dir/"worker.py";result_path=job_dir/"result.json"
    payload={"primitives":cleaned,"output_stl":str(output),"result_path":str(result_path),"thickness":max(.1,float(thickness)),"roundness":max(0.,min(100.,float(roundness))),"organic_blend":max(0.,min(100.,float(organic_blend))),"voxel_size":quality_voxel_size(quality,organic_blend),"quality":quality}
    payload_path.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8");script_path.write_text(_BLENDER_SCRIPT,encoding="utf-8")
    command=[info.executable,"--background","--factory-startup","--python",str(script_path),"--",str(payload_path)]
    try:
        process=subprocess.run(command,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        log=(process.stdout+"\n"+process.stderr)[-6000:]
        if process.returncode!=0 or not result_path.exists(): raise RuntimeError("Blender 最终建模失败。\n"+log[-2400:])
        data=json.loads(result_path.read_text(encoding="utf-8"))
        if not data.get("ok", False):
            # 失败时把 Worker 的健康统计带回主进程，便于定位而不是只显示笼统错误。
            health = data.get("health", {})
            raise RuntimeError("Blender 网格修复未通过：" + str(data.get("message", "未知网格错误")) + "\n网格统计：" + json.dumps(health, ensure_ascii=False))
        if not output.exists() or output.stat().st_size<100: raise RuntimeError("Blender 未生成有效 STL。\n"+log[-2400:])
        # 导出后的独立审计绝不复用 Blender 内存中的结果。
        from .raster_print import audit_stl
        audit = audit_stl(output)
        components = int(audit.get("connected_components", 0))
        if not audit.get("watertight") or (components > 1 and not allow_multipart):
            output.unlink(missing_ok=True)
            if components > 1:
                raise RuntimeError(f"最终模型包含 {components} 个独立组件。为避免导出大量漂浮碎片，已阻止 STL 输出。请让二维元素互相连接，或在未来的多部件模式中明确确认导出。")
            raise RuntimeError("最终模型未通过封闭、裸边、非流形或退化面检查，已阻止 STL 输出。")
        return BlenderResult(str(output),int(data["triangles"]),int(data["vertices"]),info.executable,log,cleanup_report,audit)
    finally:
        shutil.rmtree(job_dir,ignore_errors=True)


_BLENDER_SCRIPT=r'''import bpy, bmesh, json, math, sys
from mathutils import Vector

def job_path():
    args=sys.argv
    return args[args.index("--")+1]

def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def sphere(x,y,r,height):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=(x,y,height/2))
    obj=bpy.context.object;obj.scale=(r,r,max(height/2,r*.22));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return obj

def ellipse(x,y,rx,ry,height,rotation):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=(x,y,height/2), rotation=(0,0,math.radians(rotation)))
    obj=bpy.context.object;obj.scale=(rx,ry,max(height/2,min(rx,ry)*.22));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return obj

def beam(x1,y1,x2,y2,r,height):
    dx,dy=x2-x1,y2-y1;length=max(.001,math.hypot(dx,dy));mid=((x1+x2)/2,(y1+y2)/2,height/2)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=r, depth=length, location=mid)
    obj=bpy.context.object;obj.rotation_mode="QUATERNION";obj.rotation_quaternion=Vector((0,0,1)).rotation_difference(Vector((dx,dy,0)).normalized());bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return [obj,sphere(x1,y1,r,height),sphere(x2,y2,r,height)]

def polygon(x,y,size,rotation,vertices,height):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=size, depth=height, location=(x,y,height/2), rotation=(0,0,math.radians(rotation)))
    obj=bpy.context.object
    bevel=obj.modifiers.new("边缘柔化","BEVEL");bevel.width=min(size*.24,height*.24);bevel.segments=3
    bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=bevel.name)
    return obj

def build_geometry(data):
    base_h=data["thickness"];objects=[]
    for item in data["primitives"]:
        kind=item["kind"];x=float(item["x"])-50;y=float(item["y"])-50;size=max(.12,float(item["size"]));h=max(.1,float(item.get("height",base_h)))
        if kind=="line": objects.extend(beam(x,y,float(item["x2"])-50,float(item["y2"])-50,max(size*.5,h*.12),h))
        elif kind=="triangle": objects.append(polygon(x,y,size,float(item.get("rotation",0)),3,h))
        elif kind in ("square","diamond"): objects.append(polygon(x,y,size*.72,float(item.get("rotation",0)),4,h))
        elif kind in ("hexagon","drop","leaf"): objects.append(polygon(x,y,size,float(item.get("rotation",0)),6,h))
        elif kind=="ellipse": objects.append(ellipse(x,y,max(.12,float(item.get("radius_x",size))),max(.12,float(item.get("radius_y",size))),h,float(item.get("rotation",0))))
        else: objects.append(sphere(x,y,size,h))
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects: obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();return bpy.context.object

def fuse_with_voxel_remesh(obj,data):
    """以 Blender 原生 Voxel Remesh 构建最终连续体。

    Blender 5.2 的 Geometry Nodes Volume-to-Mesh 在部分重叠基础体上会留下许多
    微型封闭岛。最终制造阶段改用 bpy 的 Voxel Remesh：它同样是隐式体素融合，
    但会直接重建为单一连通网格；Geometry Nodes 仍用于后续可视化扩展，不作为
    关键制造收口的唯一依赖。
    """
    modifier=obj.modifiers.new("最终体素有机融合","REMESH")
    modifier.mode="VOXEL"
    modifier.voxel_size=max(.05,float(data["voxel_size"]))
    modifier.use_smooth_shade=True
    modifier.use_remove_disconnected=True
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    for poly in obj.data.polygons: poly.use_smooth=True

def repair_final_mesh(obj,data):
    """体素融合后的轻量修复：焊接重复点、自然平滑、统一法线。"""
    mesh=obj.data;mesh.validate(clean_customdata=True);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=max(.00001,data["voxel_size"]*.001))
    iterations=max(0,int((data["roundness"]-35)/22))
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm,verts=bm.verts,factor=.12,use_axis_x=True,use_axis_y=True,use_axis_z=True)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bm.to_mesh(mesh);bm.free();mesh.validate(clean_customdata=True);mesh.update()
    for poly in mesh.polygons: poly.use_smooth=True

def mesh_health(mesh):
    edge_faces={}
    for poly in mesh.polygons:
        vertices=list(poly.vertices)
        for index,vertex in enumerate(vertices):
            edge=tuple(sorted((vertex,vertices[(index+1)%len(vertices)])))
            edge_faces.setdefault(edge,[]).append(poly.index)
    boundary=sum(1 for faces in edge_faces.values() if len(faces)==1)
    non_manifold=sum(1 for faces in edge_faces.values() if len(faces)>2)
    degenerate=sum(1 for poly in mesh.polygons if poly.area < 1e-10)
    # 面按共享顶点连通；体素网格正常情况下应只得到一个主体。
    by_vertex={};
    for poly in mesh.polygons:
        for vertex in poly.vertices: by_vertex.setdefault(vertex,[]).append(poly.index)
    remaining=set(range(len(mesh.polygons)));components=0;component_sizes=[]
    while remaining:
        components+=1;size=0;stack=[remaining.pop()]
        while stack:
            face=stack.pop();size+=1
            for vertex in mesh.polygons[face].vertices:
                for other in by_vertex.get(vertex,[]):
                    if other in remaining: remaining.remove(other);stack.append(other)
        component_sizes.append(size)
    return {"vertices":len(mesh.vertices),"edges":len(mesh.edges),"faces":len(mesh.polygons),"boundary_edges":boundary,"non_manifold_edges":non_manifold,"degenerate_faces":degenerate,"connected_components":components,"largest_components_faces":sorted(component_sizes,reverse=True)[:12]}

def main():
    data=json.load(open(job_path(),encoding="utf-8"));clear();obj=build_geometry(data);fuse_with_voxel_remesh(obj,data)
    repair_final_mesh(obj,data)
    # 最终法线统一、三角化；STL 输出与预览无关。
    bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode="EDIT");bpy.ops.mesh.select_all(action="SELECT");bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode="OBJECT")
    tri=obj.modifiers.new("最终三角化","TRIANGULATE");bpy.ops.object.modifier_apply(modifier=tri.name)
    health=mesh_health(obj.data)
    if health["boundary_edges"] or health["non_manifold_edges"] or health["degenerate_faces"]:
        json.dump({"ok":False,"message":"最终网格含裸边、非流形边或退化面","health":health},open(data["result_path"],"w",encoding="utf-8"),ensure_ascii=False);return
    bpy.ops.wm.stl_export(filepath=data["output_stl"],export_selected_objects=True,apply_modifiers=True,ascii_format=False)
    json.dump({"ok":True,"vertices":len(obj.data.vertices),"triangles":len(obj.data.polygons),"quality":data["quality"],"health":health},open(data["result_path"],"w",encoding="utf-8"),ensure_ascii=False)

main()
'''
