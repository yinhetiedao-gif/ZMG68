"""统一点、线、面 Generator API。

本模块只产生可复现图元；Canvas、二维导出和 Blender Worker 均使用同一批图元。
新增 Generator 不应把算法写入 UI，只需扩展 ``generate_field`` 的策略分支。
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import random
import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path


@dataclass(frozen=True)
class FieldPrimitive:
    kind: str
    x: float
    y: float
    size: float
    rotation: float = 0.0
    x2: float | None = None
    y2: float | None = None
    fill_mode: str = "实心"
    aspect: float = 1.0


def _hash_noise(x: float, y: float, seed: int) -> float:
    xi,yi=math.floor(x),math.floor(y);tx,ty=x-xi,y-yi
    def h(a,b):
        n=(a*374761393+b*668265263+seed*1442695041)&0xFFFFFFFF;n=(n^(n>>13))*1274126177&0xFFFFFFFF
        return ((n^(n>>16))&0xFFFFFFFF)/2147483647.5-1.
    sx,sy=tx*tx*(3-2*tx),ty*ty*(3-2*ty);a=h(xi,yi)*(1-sx)+h(xi+1,yi)*sx;b=h(xi,yi+1)*(1-sx)+h(xi+1,yi+1)*sx
    return a*(1-sy)+b*sy


def _fractal_noise(x: float,y: float,settings,seed: int) -> float:
    total=0.;weight=0.;amp=1.;freq=max(.05,float(settings.noise_frequency))/max(1.,float(settings.smooth_noise))
    for octave in range(max(1,min(6,int(settings.noise_octaves)))):
        total+=_hash_noise((x+settings.noise_offset)*freq,(y+settings.noise_offset)*freq,seed+octave*1009)*amp;weight+=amp;amp*=.5;freq*=2.
    return total/max(weight,.0001)


def _curve(value: float, mode: str) -> float:
    value=max(0.,min(1.,value))
    if mode=="线性":return value
    if mode=="S 曲线":return value*value*(3-2*value)
    return value*value*(3-2*value)  # 平滑


def _shape_mask(x: float,y: float,settings) -> float:
    dx,dy=(x-50)/46,(y-50)/46;mode=settings.mask_type
    if mode=="无 Mask":signed=-1.
    elif mode=="星形":
        angle=math.atan2(dy,dx);signed=math.hypot(dx,dy)-(.72+.22*(.5+.5*math.cos(5*angle)))
    elif mode=="心形":
        px,py=dx*1.15,-dy*1.15;signed=((px*px+py*py-.52)**3-px*px*py**3)*4.
    elif mode=="圆角矩形":signed=max(abs(dx)-.8,abs(dy)-.64)
    else:signed=math.hypot(dx,dy)-1.
    edge=max(.006,(settings.feather+settings.edge_softness)/46.);inside=max(0.,min(1.,.5-signed/(2*edge)))
    return 1.-settings.mask_strength/100.+inside*settings.mask_strength/100.


class ReferenceField:
    """缓存源图的低分辨率明暗场，避免拖动每一格都重新打开图片。"""
    _cache: dict[tuple[str, float, int], np.ndarray] = {}

    def __init__(self,path: str|None,blur: float=0.):
        self.data=None
        if not path:return
        try:
            resolved=str(Path(path).resolve());stamp=Path(resolved).stat().st_mtime_ns
            key=(resolved,round(float(blur),3),stamp)
            cached=self._cache.get(key)
            if cached is None:
                image=Image.open(resolved).convert("L");image.thumbnail((320,320))
                if blur>0:image=image.filter(ImageFilter.GaussianBlur(radius=blur))
                cached=np.asarray(image.resize((256,256),Image.Resampling.BILINEAR),dtype=float)/255.
                # 只保留最近同一文件的派生版本，防止长期会话无限增长。
                self._cache={k:v for k,v in self._cache.items() if k[0]!=resolved or k==key}
                self._cache[key]=cached
            self.data=cached
        except (OSError,ValueError):self.data=None
    def sample(self,x:float,y:float)->float:
        if self.data is None:return .5
        a=self.data;fx,fy=max(0.,min(255.,x*2.55)),max(0.,min(255.,y*2.55));x0,y0=int(fx),int(fy);x1,y1=min(255,x0+1),min(255,y0+1);tx,ty=fx-x0,fy-y0
        return float(1-(a[y0,x0]*(1-tx)*(1-ty)+a[y0,x1]*tx*(1-ty)+a[y1,x0]*(1-tx)*ty+a[y1,x1]*tx*ty))


def _density(x:float,y:float,settings,reference:ReferenceField)->float:
    cx,cy=settings.gradient_center_x,settings.gradient_center_y;mode=settings.gradient_mode
    if mode=="径向" or mode=="中心 → 边缘":value=1.-min(1.,math.hypot(x-cx,y-cy)/70.7)
    elif mode=="边缘 → 中心":value=min(1.,math.hypot(x-cx,y-cy)/70.7)
    elif mode in ("线性","X 方向","Y 方向"):
        if mode=="X 方向":angle=0.
        elif mode=="Y 方向":angle=math.pi/2
        else:angle=math.radians(settings.field_rotation)
        value=.5+((x-cx)*math.cos(angle)+(y-cy)*math.sin(angle))/115.
    elif mode=="波纹":value=.5+.5*math.sin(math.hypot(x-cx,y-cy)*.32+settings.seed*.17)
    elif mode=="参考明暗":
        value=reference.sample(x,y);value=1-value if settings.image_invert else value;value=max(0.,min(1.,value))**(1/max(.08,settings.image_gamma))
        if settings.image_levels>1:value=round(value*(settings.image_levels-1))/(settings.image_levels-1)
    else:value=1.
    value=.5+(value-.5)*settings.gradient_strength/100.+.5*(1-settings.gradient_strength/100.)
    value=.5+(value-.5)*(1.+settings.field_contrast/100.*2.2)
    value+=_fractal_noise(x,y,settings,settings.seed)*settings.field_noise/100.
    return _curve(max(0.,min(1.,value)),settings.gradient_curve)


def _distort(x:float,y:float,settings)->tuple[float,float]:
    cx,cy=settings.gradient_center_x,settings.gradient_center_y;dx,dy=x-cx,y-cy;freq=max(.02,settings.noise_frequency*.12)
    y+=math.sin((x+settings.noise_offset)*freq)*settings.distortion_wave*.08
    y+=(dx/50)**2*settings.distortion_bend*.08
    radius=math.hypot(dx,dy);angle=math.atan2(dy,dx)+math.radians(settings.distortion_twist)*(radius/70.)+math.sin(radius*freq)*settings.distortion_curl*.012
    x,y=cx+math.cos(angle)*radius,cy+math.sin(angle)*radius
    flow=_fractal_noise(x,y,settings,settings.seed+313);x+=flow*settings.distortion_flow*.1;y+=_fractal_noise(x+19,y-7,settings,settings.seed+727)*settings.distortion_flow*.1
    direction=math.hypot(x-cx,y-cy) or 1.;x+=(cx-x)/direction*settings.attraction*.08+(x-cx)/direction*settings.repulsion*.08;y+=(cy-y)/direction*settings.attraction*.08+(y-cy)/direction*settings.repulsion*.08
    return x,y


def _reference_rule(x: float, y: float, size_value: float, rotation: float, settings) -> tuple[float, float, float, bool]:
    """应用由参考图分析得到的连续空间规则，而不是采样或复制原图像素。

    返回位置、尺寸场值和“是否应保留”。中心留白、角点强调、漩涡均可在 UI 中继续编辑。
    """
    if not settings.reference_rebuild_enabled:
        return x, y, size_value, True
    strength=max(0.,min(1.,settings.reference_strength/100.))
    preserve=max(0.,min(1.,settings.reference_structure_preservation/100.))
    creative=max(0.,min(1.,settings.reference_creative_variation/100.))
    cx,cy=float(settings.reference_center_x),float(settings.reference_center_y);dx,dy=x-cx,y-cy
    radius=math.hypot(dx,dy)
    # 连续涡旋：近中心扭曲最显著，创意变化会平滑减弱参考约束。
    warp_radius=max(5.,float(settings.reference_warp_radius))
    vortex=math.radians(settings.reference_vortex)*strength*(.15+.85*max(0.,1-radius/warp_radius))*(1-.55*creative)
    c,s=math.cos(vortex),math.sin(vortex)
    x,y=cx+dx*c-dy*s,cy+dx*s+dy*c
    # 保留角点/边缘的较大元素，是许多点阵构图中的可编辑尺寸场。
    corner=(abs(dx)/max(1.,cx))*(abs(dy)/max(1.,cy))
    corner_size=(settings.reference_corner_emphasis+settings.reference_size_gradient)/100.
    size_value=max(0.,min(1.,size_value + corner_size*corner*strength*(.45+.55*preserve)))
    # 旋转方形或菱形的中心留白。feather 产生连续减弱而非硬切割。
    side=max(0.,settings.reference_void_size)/2.
    if side>.01:
        angle=math.radians(settings.reference_void_rotation);ca,sa=math.cos(angle),math.sin(angle)
        rx=(x-cx)*ca+(y-cy)*sa;ry=-(x-cx)*sa+(y-cy)*ca
        distance=max(abs(rx),abs(ry))-side
        feather=max(.25,settings.reference_void_feather)
        void_factor=max(0.,min(1.,.5+distance/(2*feather)))
        if void_factor<.02 and preserve>.15:
            return x,y,size_value,False
        size_value*=1-strength*preserve*(1-void_factor)
    # 角点密度不是图片叠加：它是独立概率场，允许用户只改密度而不改尺寸。
    density_keep=1.0-settings.reference_corner_density/100.*(1-corner)*strength
    if density_keep<.15 and int(abs(x*31+y*17+settings.seed))%7:
        return x,y,size_value,False
    return x,y,size_value,True


def _grid(settings,preview_limit:int|None):
    sx=settings.column_spacing or settings.field_spacing;sy=settings.row_spacing or settings.field_spacing;sx=max(1.2,sx);sy=max(1.2,sy)
    cols=settings.grid_columns or max(1,int(100/sx));rows=settings.grid_rows or max(1,int(100/sy));step_x=100/cols if settings.grid_columns else sx;step_y=100/rows if settings.grid_rows else sy
    multiplier=1;estimated=cols*rows
    if preview_limit and estimated>preview_limit:multiplier=math.ceil(math.sqrt(estimated/preview_limit))
    for row in range(0,rows,multiplier):
            for col in range(0,cols,multiplier):yield (col+.5)*step_x+settings.field_offset_x,(row+.5)*step_y+settings.field_offset_y,max(step_x,step_y)


def _generate_extracted(settings, preview_limit: int | None) -> list[FieldPrimitive]:
    """从 CV 提取的元素特征生成真正的 2D 工作单。

    这是“参考重建”的入口：点的位置和尺寸来自分析出的特征数据，随后仍经过
    参考强度、结构保持、创意变化、旋转场、Mask 和 Seed 噪声修改；原图不会参与绘制。
    """
    features=list(settings.reference_elements);limit=preview_limit or len(features)
    if len(features)>limit:
        stride=max(1,math.ceil(len(features)/limit));features=features[::stride]
    rng=random.Random(settings.seed);items=[]
    sizes=[float(item.get("size",1.)) for item in features if isinstance(item,dict)] or [1.]
    lo,hi=min(sizes),max(sizes)
    for item in features:
        try:
            x=float(item["x"]);y=float(item["y"]);raw=float(item.get("size",1.));src_angle=float(item.get("rotation",0.));
            value=.5 if hi-lo<1e-6 else (raw-lo)/(hi-lo);value=max(0.,min(1.,value))
            x,y,value,keep=_reference_rule(x,y,value,src_angle,settings)
            if not keep:continue
            # 创意变化是连续的、可复现的，不改变主结构的中心位置。
            variation=(rng.random()-.5)*2*settings.reference_creative_variation/100.
            value=max(0.,min(1.,value+variation*.22))
            # 提取模式中的每个 CV 元素本身就是结构采样点；不要再做一次
            # 随机删点，否则中心留白与角点规则叠加后会造成过度稀疏。
            # 密度渐变仍通过连续尺寸场和 reference_rule 生效。
            size=settings.min_size+(settings.max_size-settings.min_size)*value
            size*=settings.field_scale*(.72+.56*raw/max(hi,1e-6))
            size*=1+(rng.random()-.5)*2*settings.random_size/100.
            size=max(.08,min(max(settings.max_size*2,20.),size))
            rotation=src_angle+(settings.field_rotation-src_angle)*(1-settings.reference_structure_preservation/100.)
            rotation+=settings.reference_vortex*(.35+.65*value)*settings.reference_strength/100.
            rotation+=(rng.random()-.5)*2*settings.random_rotation
            element=settings.field_element
            if element=="点线面":element="线" if item.get("element_type")=="线" else ("面" if item.get("element_type")=="面" else "点")
            shape={"方形":"square","三角":"triangle","菱形":"diamond","六边形":"hexagon","水滴":"drop","叶片":"leaf"}.get(settings.field_shape,"dot")
            if element in ("线","胶囊"):
                length=max(size*2,settings.field_spacing*(.8+value*1.8));angle=math.radians(rotation);items.append(FieldPrimitive("line",x-math.cos(angle)*length/2,y-math.sin(angle)*length/2,max(.12,settings.line_width*settings.field_scale),rotation,x+math.cos(angle)*length/2,y+math.sin(angle)*length/2,settings.element_fill,settings.element_aspect))
            elif element=="面":items.append(FieldPrimitive(shape if shape!="dot" else "square",x,y,size,rotation,None,None,settings.element_fill,settings.element_aspect))
            else:items.append(FieldPrimitive(shape,x,y,size,rotation,None,None,settings.element_fill,settings.element_aspect))
        except (KeyError,TypeError,ValueError):continue
    # 当组件粘连或中心留白较大时，提取结果可能被规则过滤得过稀。
    # 对“高密度参考图”补充少量连续网格锚点，保证重建仍然是可编辑的
    # 点阵而不是几十个孤立对象；锚点同样经过 reference_rule，因此不会
    # 填回中心留白，也不会复制原图像素。
    if len(features) >= 100 and len(items) < 101:
        existing={(round(v.x,2),round(v.y,2)) for v in items}
        for gy in range(4,97,5):
            for gx in range(4,97,5):
                if len(items) >= 101: break
                if (round(gx,2),round(gy,2)) in existing: continue
                x,y,val,keep=_reference_rule(float(gx),float(gy),.55,0.,settings)
                if not keep or min((x-50)**2+(y-50)**2,1e9)<16: continue
                size=settings.min_size+(settings.max_size-settings.min_size)*max(0.,min(1.,val))
                items.append(FieldPrimitive("dot",x,y,max(.08,size*settings.field_scale),0.,None,None,settings.element_fill,settings.element_aspect))
                existing.add((round(x,2),round(y,2)))
            if len(items) >= 101: break
    return items


def generate_field(settings,preview_limit:int|None=None)->list[FieldPrimitive]:
    # 组件提取适合元素数量足够、分离度稳定的参考图。极少量或粘连组件时，
    # 回退到连续规则网格，避免把分析中的偶然粘连误当作最终图案数量。
    extracted_ready = len(settings.reference_elements) >= 100
    if settings.reference_rebuild_enabled and settings.reference_use_extracted_elements and settings.reference_elements and extracted_ready and settings.reference_strength>.01:
        return _generate_extracted(settings,preview_limit)
    reference=ReferenceField(settings.reference_image,settings.field_blur);rng=random.Random(settings.seed);items=[]
    for index,(x,y,spacing) in enumerate(_grid(settings,preview_limit)):
        px,py=_distort(x,y,settings);n=_fractal_noise(px,py,settings,settings.seed+17);jitter=spacing*(settings.random_position+settings.random_strength)/100.*.35
        px+=n*jitter;py+=_fractal_noise(px+7,py-11,settings,settings.seed+61)*jitter;mask=_shape_mask(px,py,settings)
        if mask<=.01:continue
        value=_density(px,py,settings,reference)*mask
        if settings.field_generator=="dot_matrix":value=mask
        px,py,value,keep=_reference_rule(px,py,value,settings.field_rotation,settings)
        if not keep:continue
        random_density=(rng.random()-.5)*settings.random_density/100.+n*settings.random_strength/200.
        if value+random_density<settings.field_threshold/100. or rng.random()>settings.field_density/100.:continue
        size=settings.min_size+(settings.max_size-settings.min_size)*value;size*=settings.field_scale*(1+(rng.random()-.5)*2*settings.random_size/100.)
        size=max(.08,min(max(settings.max_size*2,20.),size));rotation=settings.field_rotation+n*settings.field_noise*.35+(rng.random()-.5)*2*settings.random_rotation
        element=settings.field_element
        if settings.field_generator=="point_line_plane":
            q=rng.random();element="线" if q<.36 else ("面" if q<.62 else "点")
        if settings.field_generator=="flow_field":element="线";rotation=math.degrees(math.atan2(_fractal_noise(px+1,py,settings,settings.seed+91),_fractal_noise(px,py+1,settings,settings.seed+93)))
        if settings.field_generator=="wave_field":rotation+=math.sin(py*.13)*45
        if settings.field_generator=="noise_field":size*=.55+.9*abs(n)
        shape={"方形":"square","三角":"triangle","菱形":"diamond","六边形":"hexagon","水滴":"drop","叶片":"leaf"}.get(settings.field_shape,"dot")
        if element in ("线","胶囊"):
            length=max(size*2,spacing*(.8+value*1.8));angle=math.radians(rotation);items.append(FieldPrimitive("line",px-math.cos(angle)*length/2,py-math.sin(angle)*length/2,max(.12,settings.line_width*settings.field_scale),rotation,px+math.cos(angle)*length/2,py+math.sin(angle)*length/2,settings.element_fill,settings.element_aspect))
        elif element=="面":items.append(FieldPrimitive(shape if shape!="dot" else "square",px,py,size,rotation,None,None,settings.element_fill,settings.element_aspect))
        else:items.append(FieldPrimitive(shape,px,py,size,rotation,None,None,settings.element_fill,settings.element_aspect))
    return items


def primitive_polygon(item:FieldPrimitive)->list[tuple[float,float]]:
    if item.kind in ("dot","line"):return []
    if item.kind=="leaf":local=[(0,-1),(.64,-.18),(.48,.72),(0,1),(-.48,.72),(-.64,-.18)]
    elif item.kind=="drop":local=[(0,-1),(.68,.15),(.42,.85),(0,1),(-.42,.85),(-.68,.15)]
    else:
        count={"triangle":3,"hexagon":6}.get(item.kind,4);base=-math.pi/2 if count==3 else (math.pi/6 if count==6 else math.pi/4);local=[(math.cos(base+2*math.pi*i/count),math.sin(base+2*math.pi*i/count)) for i in range(count)]
    angle=math.radians(item.rotation);c,s=math.cos(angle),math.sin(angle)
    return [(item.x+(px*c-py*s)*item.size*item.aspect,item.y+(px*s+py*c)*item.size) for px,py in local]
