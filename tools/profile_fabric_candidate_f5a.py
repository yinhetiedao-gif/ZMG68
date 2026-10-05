"""Full enabled candidate benchmark; no Boolean, validation or export."""
import json
from time import perf_counter
from xiaomang_pattern_lab.fabric_base import BaseDefinition
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner, RegularPlacement
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate

for count, columns, rows in ((100,10,10),(400,20,20),(1000,20,50),(5000,50,100)):
    started = perf_counter()
    plan = FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition('pyramid',.3,.3,3),
        RegularPlacement(60/columns,60/rows),preview_limit=False)
    plan_ms = (perf_counter()-started)*1000
    candidate = build_fabric_candidate(plan,BaseDefinition('solid',.6,0),(0,0,60,60),
        document_id='f5a-benchmark',document_revision=1)
    print(json.dumps({'count':count,'plan_ms':plan_ms,'timings_ms':candidate.report['timings_ms'],
        'memory_estimate_bytes':candidate.report['memory_estimate_bytes'],
        'attachment_counts':candidate.report['attachment_counts']}))
