"""本地、可解释的点线面视觉分析。

分析密度、连通组件、形状紧致度、方向性及规则网格周期，并将结果转成可编辑参数；
不会宣称能复制或完全逆向任何艺术品。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
from collections import deque
import numpy as np
from PIL import Image


@dataclass
class AnalysisResult:
    generator_key: str | None
    confidence: float
    summary: str
    suggestions: dict
    needs_new_generator: bool
    metrics: dict
    details: dict
    def to_dict(self) -> dict: return asdict(self)


def analyze_reference2d(path: str, *, target_width_mm: float | None = None, config=None):
    """Reference → Editable 2D 结构化入口。

    保持 ``analyze_reference`` 的旧 API 不变，供旧项目/插件继续使用；新 UI 入口
    通过 ``ppg.reference2d`` 输出元数据、真实元素、空间场、Generator/Modifier
    和相似度指标。延迟导入是为了避免两层兼容桥在模块加载阶段循环依赖。
    """
    from .reference2d import analyze_reference2d as _analyze_reference2d
    return _analyze_reference2d(path, target_width_mm=target_width_mm, config=config)


def _otsu(a: np.ndarray) -> float:
    hist,_=np.histogram(a,bins=256,range=(0,1));total=a.size;sums=np.cumsum(hist);means=np.cumsum(hist*np.arange(256));whole=means[-1];denom=sums*(total-sums)
    score=np.divide((means*total-whole*sums)**2,denom,out=np.zeros(256,float),where=denom>0)
    return float((np.argmax(score)+.5)/256)


def _components(mask: np.ndarray, limit: int=1000) -> list[tuple[int,int,int,int,int]]:
    """返回 (area,minx,miny,maxx,maxy)，在小代理图上执行。"""
    h,w=mask.shape;seen=np.zeros_like(mask,bool);out=[]
    for y,x in zip(*np.where(mask & ~seen)):
        if seen[y,x]: continue
        q=deque([(int(y),int(x))]);seen[y,x]=True;area=0;minx=maxx=x;miny=maxy=y
        while q:
            yy,xx=q.popleft();area+=1;minx=min(minx,xx);maxx=max(maxx,xx);miny=min(miny,yy);maxy=max(maxy,yy)
            for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:seen[ny,nx]=True;q.append((ny,nx))
        if area>=2:out.append((area,minx,miny,maxx,maxy))
        if len(out)>=limit: break
    return out


def _element_features(mask: np.ndarray, limit: int = 600) -> list[dict]:
    """提取真实元素几何特征，供参数化重建工作单使用。

    每个对象只保存中心、等效半径、长宽比、方向、元素类型和区域；不保存像素块。
    """
    h,w=mask.shape;seen=np.zeros_like(mask,bool);out=[]
    for y,x in zip(*np.where(mask & ~seen)):
        if seen[y,x]:continue
        stack=[(int(y),int(x))];seen[y,x]=True;pixels=[]
        while stack:
            yy,xx=stack.pop();pixels.append((yy,xx))
            for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:seen[ny,nx]=True;stack.append((ny,nx))
        if len(pixels)<5:continue
        ys=np.array([p[0] for p in pixels]);xs=np.array([p[1] for p in pixels]);minx,maxx,miny,maxy=xs.min(),xs.max(),ys.min(),ys.max();bw=maxx-minx+1;bh=maxy-miny+1
        # 二阶矩给出主方向；相近圆形的方向归零。
        xx=xs-xs.mean();yy=ys-ys.mean();cov=np.array([[float(np.mean(xx*xx)),float(np.mean(xx*yy))],[float(np.mean(xx*yy)),float(np.mean(yy*yy))]]);eig=np.linalg.eigh(cov);vector=eig[1][:,1];angle=float(np.degrees(np.arctan2(vector[1],vector[0]))) if abs(eig[0][1]-eig[0][0])>.2 else 0.
        fill=len(pixels)/(bw*bh);kind="圆" if .58<fill<.95 and .65<bw/max(1,bh)<1.55 else ("线" if bw/max(1,bh)>2.4 or bh/max(1,bw)>2.4 else "面")
        out.append({"x":round(float(xs.mean())/max(1,w-1)*100,4),"y":round(float(ys.mean())/max(1,h-1)*100,4),"size":round(float((bw+bh)*.25/max(1,min(w,h))*100),4),"rotation":round(angle,3),"opacity":1.0,"element_type":kind,"region":"角点" if abs(xs.mean()-(w-1)/2)>w*.3 and abs(ys.mean()-(h-1)/2)>h*.3 else "中心/边缘","aspect":round(bw/max(1,bh),4),"area":len(pixels)})
        if len(out)>=limit:break
    return out


def _periodicity(mask: np.ndarray) -> tuple[float,float,float]:
    a=mask.astype(float)-mask.mean()
    def period(v):
        v=v-v.mean();corr=np.correlate(v,v,mode="full")[len(v)-1:]
        if len(corr)<8 or corr[0]<=1e-8:return 0.,0.
        lo,hi=3,min(len(corr)//2,48);i=lo+int(np.argmax(corr[lo:hi]));return float(i),float(corr[i]/corr[0])
    px,sx=period(a.mean(axis=0));py,sy=period(a.mean(axis=1));return px,py,max(sx,sy)


def _central_void_and_rotation(dark: np.ndarray) -> tuple[float, float, float]:
    """在中心区域寻找低密度留白，并比较正方/45°坐标系的留白一致性。

    这不是轮廓追踪；结果只作为“中心留白 Modifier”的初始可编辑参数。
    """
    h,w=dark.shape;cx,cy=(w-1)/2,(h-1)/2
    yy,xx=np.indices(dark.shape);dx,dy=xx-cx,yy-cy
    best=(0.,0.,0.)
    for angle in (0.,45.):
        radians=np.deg2rad(angle);ca,sa=np.cos(radians),np.sin(radians)
        rx=np.abs(dx*ca+dy*sa);ry=np.abs(-dx*sa+dy*ca)
        for half in range(6,min(h,w)//3,3):
            region=(np.maximum(rx,ry)<=half)
            if not np.any(region):continue
            whiteness=1-float(dark[region].mean())
            # 小空洞不应误判；更大、且确实比整体干净的区域才被采用。
            score=whiteness*(half/(min(h,w)*.32))
            if score>best[0]:best=(score,float(half),angle)
    score,signed_half,angle=best
    global_white=1-float(dark.mean())
    if score<.2 or (score/max(.001,global_white))<.7:return 0.,0.,0.
    return round(abs(signed_half)/min(h,w)*100*2,1),angle,round(min(1.,score/max(.001,global_white))*100,1)


def _spatial_rules(dark: np.ndarray) -> dict:
    """将位置、尺寸、密度和扭曲整理为可编辑的高层规则。"""
    h,w=dark.shape;yy,xx=np.indices(dark.shape);cx,cy=(w-1)/2,(h-1)/2
    # 角点相对中心/边缘的黑色覆盖，近似“角落元素更大/更密”的趋势。
    corner=((np.abs(xx-cx)>w*.30)&(np.abs(yy-cy)>h*.30));center=(np.hypot(xx-cx,yy-cy)<min(w,h)*.18)
    corner_density=float(dark[corner].mean()) if np.any(corner) else 0.
    center_density=float(dark[center].mean()) if np.any(center) else 0.
    corner_emphasis=max(0.,min(100.,(corner_density-center_density)*180.))
    # 用局部方向的绕中心相关性作为扭曲/漩涡提示；低置信时保持为 0。
    gy,gx=np.gradient(dark.astype(float));tx=-(yy-cy);ty=(xx-cx);den=np.hypot(gx,gy)*np.hypot(tx,ty)+1e-6
    swirl=float(np.mean(np.abs((gx*tx+gy*ty)/den)[np.hypot(xx-cx,yy-cy)>min(w,h)*.14]))
    vortex=max(0.,min(100.,(swirl-.38)*170.))
    void_size,void_rotation,void_confidence=_central_void_and_rotation(dark)
    return {"position_field":"规则网格", "size_field":"参考明暗 + 角点强调" if corner_emphasis>8 else "参考明暗", "density_field":"中心留白" if void_size>4 else "参考明暗", "rotation_field":"中心涡旋" if vortex>8 else "统一方向", "distortion":"中心旋转 / 涡旋" if vortex>8 else "轻微或无扭曲", "central_void_size":void_size, "central_void_rotation":void_rotation, "central_void_confidence":void_confidence, "corner_emphasis":round(corner_emphasis,1), "vortex":round(vortex,1)}


def analyze_reference(path: str) -> AnalysisResult:
    image=Image.open(path).convert("L");image.thumbnail((256,256));image=image.resize((192,192),Image.Resampling.BILINEAR);a=np.asarray(image,dtype=float)/255.
    contrast=float(a.std());threshold=_otsu(a);dark=a<threshold;coverage=float(dark.mean());comps=_components(dark);meaningful=[c for c in comps if c[0]>=5]
    areas=np.array([c[0] for c in meaningful],float);ratios=np.array([(c[3]-c[1]+1)/max(1,c[4]-c[2]+1) for c in meaningful],float)
    small_ratio=float(np.mean(areas<80)) if len(areas) else 0.;compact_ratio=float(np.mean((ratios>.62)&(ratios<1.6))) if len(ratios) else 0.;line_ratio=float(np.mean((ratios>2.3)|(ratios<.43))) if len(ratios) else 0.
    px,py,period_score=_periodicity(dark);gy,gx=np.gradient(a);mag=np.hypot(gx,gy);orientation=float(abs((gx*gx-gy*gy)[mag>.04].mean())/(mag[mag>.04].mean()+1e-6)) if np.any(mag>.04) else 0.
    yy,xx=np.indices(a.shape);dist=np.hypot(xx-95.5,yy-95.5);ring=np.array([dark[(dist>=i*8)&(dist<(i+1)*8)].mean() for i in range(16)]);radial_score=float(min(1.,ring.std()*4.2))
    metrics={"黑色覆盖率":round(coverage,3),"对比度":round(contrast,3),"阈值":round(threshold,3),"独立组件":len(meaningful),"小组件比例":round(small_ratio,2),"紧致组件比例":round(compact_ratio,2),"线性组件比例":round(line_ratio,2),"网格周期X":round(px,1),"网格周期Y":round(py,1),"网格规则度":round(period_score,2),"方向性":round(orientation,2),"径向变化":round(radial_score,2)}
    if contrast<.045 or coverage<.001:return AnalysisResult(None,.12,"图片对比度过低，未检测到可用于点线面生成的稳定结构。",{},True,metrics,{})
    dot_score=.35*small_ratio+.28*compact_ratio+.27*period_score+.1*(1-min(1,coverage/.65));halftone_score=.38*compact_ratio+.3*(1-min(1,abs(coverage-.32)*2))+.2*period_score+.12*radial_score;plane_score=.45*line_ratio+.25*orientation+.2*(1-small_ratio)+.1*period_score
    if plane_score>max(dot_score,halftone_score) and line_ratio>.2:key,label,element="point_line_plane","点线面构成","点线面"
    elif dot_score>halftone_score and period_score>.18:key,label,element="dot_matrix","规则点阵","点"
    else:key,label,element=("halftone" if radial_score<.45 else "gradient_dots"),"半调 / 渐变点阵","点"
    spacing=max(2.2,min(12.,((px or py or 10)/192)*100*1.15));density="中心到边缘渐变" if radial_score>.18 else ("规则网格" if period_score>.18 else "非规则面状分布")
    suggested_size=round(max(.8,min(5.2,spacing*.58)),2);rules=_spatial_rules(dark);features=_element_features(dark)
    suggestions={"active_generator":"field","field_generator":key,"field_element":"点线面" if element=="点线面" else "点","field_shape":"圆","field_spacing":round(spacing,2),"dot_size":suggested_size,"min_size":round(max(.12,suggested_size*.18),2),"max_size":round(suggested_size*1.45,2),"line_width":round(max(.25,spacing*.14),2),"gradient_mode":"参考明暗","gradient_strength":85,"field_contrast":35,"field_threshold":5,"feather":3,"field_noise":0 if period_score>.2 else 14,"smooth_noise":12,"mask_type":"无 Mask","reference_image":str(Path(path).resolve()),"reference_rebuild_enabled":True,"reference_use_extracted_elements":bool(len(features)>=8),"reference_elements":features,"reference_strength":100,"reference_structure_preservation":85,"reference_creative_variation":0,"reference_void_size":rules["central_void_size"],"reference_void_rotation":rules["central_void_rotation"],"reference_void_feather":max(1.5,spacing*.35),"reference_corner_emphasis":rules["corner_emphasis"],"reference_vortex":rules["vortex"],"reference_center_x":50.0,"reference_center_y":50.0,"reference_warp_radius":48.0,"reference_corner_density":rules["corner_emphasis"],"reference_size_gradient":rules["corner_emphasis"]*.45,"reference_density_gradient":rules["corner_emphasis"]*.35}
    details={"主体轮廓类型":"可编辑密度场（可改为圆形、星形、心形、圆角矩形）","基础元素类型":element,"真实元素数据":f"已提取 {len(features)} 个元素中心/尺寸/方向特征","位置场":rules["position_field"],"排列方式":density,"密度规律":rules["density_field"],"尺寸场":rules["size_field"],"旋转场":rules["rotation_field"],"扭曲规则":rules["distortion"],"中心留白":f"{rules['central_void_size']}% · {rules['central_void_rotation']:.0f}°" if rules["central_void_size"] else "未检测到稳定中心留白","渐变方式":"参考明暗；可切换径向、线性、波纹"}
    confidence=min(.92,.43+max(dot_score,halftone_score,plane_score)*.55);summary=f"检测为「{label}」：{density}，共识别到 {len(meaningful)} 个有效黑色组件。将把明暗、网格与组件形态转为可编辑参数，不复制原始像素。"
    return AnalysisResult(key,confidence,summary,suggestions,False,metrics,details)
