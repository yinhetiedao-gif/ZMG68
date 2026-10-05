"""Generate validated test artifacts and timings; never claims physical PASS."""
from datetime import datetime,timezone
from pathlib import Path
from dataclasses import replace
from tempfile import TemporaryDirectory
from time import perf_counter
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_fabric_candidate_f5a import candidate
from test_image_fabric_f4a import image_document,black_circle_bytes
from xiaomang_pattern_lab.fabric_plan import FabricPlanner,RegularPlacement
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_fields import DistanceField

output=Path('work/f5c')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
output.mkdir(parents=True,exist_ok=False)
def run(name,source,started):
    candidate_ms=(perf_counter()-started)*1000
    final=FabricFusionService().build(source)
    payload,report=export_validated_fabric_stl(final)
    filename=output/(name+'.stl');filename.write_bytes(payload)
    print(json.dumps({'case':name,'file':str(filename.resolve()),'count':source.report['enabled_instance_count'],
        'candidate_ms':candidate_ms,'fusion':final.report['timings_ms'],'export':report,
        'total_manufacture_to_stl_ms':(perf_counter()-started)*1000},ensure_ascii=False),flush=True)

for count,columns,rows in ((100,10,10),(400,20,20),(1000,20,50)):
    started=perf_counter()
    plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition('pyramid',.3,.3,3),
        RegularPlacement(60/columns,60/rows),preview_limit=False)
    run('basic-'+str(count),candidate(plan),started)
started=perf_counter()
plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition('fin',2,1,3),RegularPlacement(6,6))
plan=replace(plan,instances=tuple(replace(item,rotation_deg=index%10*9) for index,item in enumerate(plan.instances)))
run('fin-orientation-100',candidate(plan),started)
with TemporaryDirectory() as folder:
    path=Path(folder)/'mask.png';path.write_bytes(black_circle_bytes())
    for mode in ('area_fill','pattern_points'):
        doc=image_document(path,mode,count=100)
        doc.fields=[DistanceField('distance',str(path),sample_bounds=(0,0,100,100)).to_dict()]
        doc.metadata['fabric_config']['field_modifiers']={
            'height':{'enabled':True,'field_id':'distance','min_height_mm':1,'max_height_mm':8},
            'orientation':{'enabled':True,'field_id':'distance','direction_mode':'gradient','alignment':'tangent',
                'angle_offset_deg':12,'min_angle_deg':-45,'max_angle_deg':45}}
        # Representative 60-mm printable test piece, 144 Fin cells. The other
        # unchanged 100-mm fixture provides the required 400-instance gate.
        for size in ([100,60] if mode=='area_fill' else [100]):
            if size==60:
                doc.elements[1].x=59;doc.elements[1].y=59
                doc.fields=[DistanceField('distance',str(path),sample_bounds=(0,0,60,60)).to_dict()]
            dto=PatternDocumentDTO.from_document(doc,'f5c-distance',1,asset_bindings={str(path):'mask'})
            started=perf_counter();design=build_fabric_design(doc,dto,preview_limit=False)
            source=build_fabric_candidate(design.plan,design.config.base,design.design_bounds_mm,
                document_id=dto.document_id,document_revision=1)
            run('distance-'+mode+'-'+str(size)+'mm',source,started)
